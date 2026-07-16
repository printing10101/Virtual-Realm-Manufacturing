"""根目录 conftest.py —— 绕过 Python 3.11.0rc2 _overlapped 加载失败问题。

依据 project_memory 中的 lesson learned：
"WinSock initialization issues may occur; implement workaround by forcing
WinSock initialization before imports"

问题根因：
    Python 3.11.0rc2 在 Windows 上 _overlapped C 扩展模块初始化失败，
    抛出 OSError [WinError 10038]。该模块被 asyncio.windows_events 导入，
    任何触发 asyncio 导入的链路（如 typing_extensions.deprecated 装饰器、
    pydantic_core、torch.cuda 等）都会失败。

绕过方案：
    在任何应用代码导入前，预先尝试导入 _overlapped。若失败，则注入一个
    最小 stub 模块替换它，使 asyncio.windows_events 能完成导入。stub 仅
    提供符号占位，不提供真实 IOCP 功能——对单元测试足够（测试不需要真实
    异步 IO），对生产环境无害（生产环境用正式 Python 版本，不会触发此分支）。
"""

import sys
import types


def _patch_overlapped_if_needed() -> None:
    """若 _overlapped 加载失败，注入 stub 模块。"""
    if sys.platform != "win32":
        return
    try:
        import _overlapped  # noqa: F401
        return  # 加载成功，无需 patch
    except OSError:
        pass

    # 加载失败，创建 stub
    stub = types.ModuleType("_overlapped")

    # asyncio.windows_events 需要的符号（参考 Python 3.11 源码）
    # 这些常量和函数在 stub 中提供占位实现，避免 AttributeError
    stub.INVALID_HANDLE_VALUE = -1
    stub.ERROR_IO_PENDING = 997
    stub.ERROR_NETNAME_DELETED = 64
    stub.ERROR_OPERATION_ABORTED = 995
    stub.OVERLAPPED = type("OVERLAPPED", (object,), {
        "__init__": lambda self, *args, **kwargs: None,
        "event": 0,
        "address": 0,
    })

    def _placeholder(*args, **kwargs):
        raise RuntimeError(
            "_overlapped stub: IOCP 操作不可用（Python 3.11.0rc2 环境限制）"
        )

    stub.CreateIoCompletionPort = _placeholder
    stub.GetQueuedCompletionStatus = _placeholder
    stub.PostQueuedCompletionStatus = _placeholder
    stub.RegisterWaitWithQueue = _placeholder
    stub.UnregisterWait = _placeholder
    stub.CreateEvent = _placeholder
    stub.SetEvent = _placeholder
    stub.ResetEvent = _placeholder
    stub.CloseHandle = _placeholder
    stub.FormatMessage = lambda *a, **kw: ""
    stub.BindLocal = _placeholder
    stub.Overlapped = type("Overlapped", (object,), {
        "__init__": lambda self, *args, **kwargs: None,
        "address": 0,
        "event": 0,
        "pending": False,
        "completed": False,
    })

    sys.modules["_overlapped"] = stub
    sys.modules["_overlapped"].__name__ = "_overlapped"
    sys.modules["_overlapped"].__loader__ = None  # type: ignore[assignment]


_patch_overlapped_if_needed()
