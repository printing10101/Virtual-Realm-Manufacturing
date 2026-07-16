"""pytest 启动器：在 pytest 加载插件之前注入 WinSock 损坏绕过补丁.

背景：
    本机 _overlapped 模块因系统级 WinSock 损坏无法导入（WinError 10038），
    导致 anyio → asyncio.windows_events → _overlapped 导入链失败。
    而 ``python -m pytest`` 启动时会通过 ``load_setuptools_entrypoints("pytest11")``
    加载 anyio 插件，此阶段早于 ``conftest.py`` 的加载，
    因此 conftest.py 中的 patch 来不及生效。

用法：
    python run_pytest.py [pytest 参数...]

    例：
        python run_pytest.py tests/integration/test_workflow_dag.py -m integration -v

根因修复：
    以管理员身份运行 ``netsh winsock reset`` 并重启系统后，
    本启动器的 patch 会被 ``try: import _overlapped`` 短路，不再生效。
"""
from __future__ import annotations

# === WinSock 损坏绕过补丁（必须在 import asyncio 之前执行）===
# 原因：asyncio/__init__.py 顶层 `from .windows_events import *`，
# 而 windows_events.py 顶层 `import _overlapped`。
# 若 _overlapped 因系统级 WinSock 损坏（WinError 10038）无法导入，
# 则 `import asyncio` 本身就会失败。因此 stub 注入必须先于 asyncio 导入。
import sys
import types

try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print(
        "[run_pytest] _overlapped 模块加载失败，"
        "已注入空实现绕过 WinSock 损坏。",
        file=sys.stderr,
    )

# _asyncio 兜底（asyncio.events 顶层会 from ._asyncio import ...）
try:
    import _asyncio  # noqa: F401  pylint: disable=unused-import
except OSError:
    _asyncio_patch = types.ModuleType("_asyncio")
    sys.modules["_asyncio"] = _asyncio_patch

# 现在 asyncio 可以安全导入
import asyncio  # noqa: E402
import os  # noqa: E402
import socket as _socket_module  # noqa: E402

# === 强制使用 SelectorEventLoop ===
# ProactorEventLoop 依赖 _overlapped.Overlapped 真实实现（IOCP），
# 而我们的空实现 patch 不支持。SelectorEventLoop 基于 select()，
# 不依赖 _overlapped，适用于 WinSock 损坏环境下的 asyncio 测试。
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# === socket.socketpair mock（WinSock 损坏环境下必需）===
# SelectorEventLoop._make_self_pipe() 调用 socket.socketpair() 创建自管道，
# 但 WinSock 目录损坏会导致 socket() 调用失败（WinError 10038）。
# self-pipe 是单向通信（_csock.send → _ssock.recv），用 os.pipe() 完全可替代。
# 此 patch 仅在真实 socketpair 失败时启用，不影响正常环境。
class _PipeSocket:
    """用 os.pipe() 模拟 socketpair 的一端.

    asyncio BaseSelectorEventLoop 对 self-pipe 的使用：
        - _ssock: fileno() + recv(1)  （读端，注册到 selector）
        - _csock: fileno() + send(b'\\0')  （写端）
    setblocking/close 调用均被 mock 为 no-op 或 os.close。
    """

    def __init__(self, fd: int, *, is_reader: bool) -> None:
        self._fd = fd
        self._is_reader = is_reader
        self._closed = False

    def fileno(self) -> int:
        return self._fd

    def setblocking(self, flag: bool) -> None:  # noqa: ARG002
        # os.pipe() 的 fd 是阻塞的；asyncio 在 SelectorEventLoop 中
        # 通过 selector 的 select() 调度，不依赖非阻塞模式。
        pass

    def recv(self, bufsize: int) -> bytes:
        if self._closed:
            raise OSError("socket closed")
        return os.read(self._fd, bufsize)

    def send(self, data: bytes) -> int:
        if self._closed:
            raise OSError("socket closed")
        return os.write(self._fd, data)

    def close(self) -> None:
        if not self._closed:
            try:
                os.close(self._fd)
            except OSError:
                pass
            self._closed = True


def _mock_socketpair(*args, **kwargs):  # noqa: ARG001
    """用 os.pipe() 替代 socket.socketpair()，返回 (_PipeSocket, _PipeSocket)."""
    r_fd, w_fd = os.pipe()
    # _ssock=读端, _csock=写端，与 asyncio._make_self_pipe 的解包顺序一致
    return _PipeSocket(r_fd, is_reader=True), _PipeSocket(w_fd, is_reader=False)


# 探测真实 socketpair 是否可用；不可用则注入 mock
_winsock_broken = False
try:
    _probe_s, _probe_c = _socket_module.socketpair()
    _probe_s.close()
    _probe_c.close()
except OSError as _probe_err:
    _winsock_broken = True
    _socket_module.socketpair = _mock_socketpair  # type: ignore[attr-defined]
    print(
        "[run_pytest] socket.socketpair() 探测失败 "
        f"({_probe_err!s})，已注入 os.pipe() 替代实现。",
        file=sys.stderr,
    )


def _main() -> int:
    """启动 pytest，返回退出码."""
    from pytest import console_main

    return console_main()


if __name__ == "__main__":
    # 透传命令行参数给 pytest（去掉 argv[0] = run_pytest.py）
    raise SystemExit(_main())
