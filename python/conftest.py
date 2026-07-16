"""项目根 conftest.py（python/ 目录）。

职责：
1. 将 ``python/`` 加入 sys.path，使 ``from app.xxx import yyy`` 绝对导入可用。
2. 显式忽略 ``app/`` 目录的收集，防止 pytest 9.x 跨目录调用时 testpaths
   解析不一致导致递归扫描 ``app/**/tests/`` 内嵌测试。

防复发机制 [E-P0-3]：
    ``app/ai/lnn/tests/test_gpu_training.py`` 顶层导入 torch → pandas →
    pyarrow.compute，在 pytest 字节码改写上下文中触发 STATUS_HEAP_CORRUPTION
    (0xC0000374)。本文件与 ``pytest.ini`` 的 ``norecursedirs = app`` 形成双重
    防护，确保默认收集只扫描 ``python/tests`` 集中测试目录。

如需运行模块自测，显式指定路径：
    pytest python/app/ai/lnn/tests/ --no-cov -p no:cacheprovider
"""

import sys
import types
from pathlib import Path

# === WinSock 损坏绕过补丁 ===
# 本机 _overlapped 模块因系统级 WinSock 损坏无法导入（WinError 10038），
# 导致 anyio → asyncio.windows_events → _overlapped 导入链失败，
# 进而使 pytest 启动阶段（load_setuptools_entrypoints）崩溃。
# 此处注入一个空实现的 _overlapped 模块以绕过导入阶段失败。
# 测试用例中需要真实异步 IO 的场景应使用 asyncio.SelectorEventLoop，
# 或在 fixture 内显式 patch asyncio.ProactorEventLoop。
# 根因修复：以管理员身份运行 `netsh winsock reset` 并重启系统。
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 模块加载失败，已注入空实现绕过 WinSock 损坏。")

# 将 python/ 目录加入 sys.path（与 python/tests/conftest.py 保持一致）
_PYTHON_ROOT = Path(__file__).parent.resolve()
if str(_PYTHON_ROOT) not in sys.path:
    sys.path.insert(0, str(_PYTHON_ROOT))

# 显式忽略 app/ 目录的测试收集（双重防护：与 pytest.ini norecursedirs 配合）
collect_ignore = ["app"]
