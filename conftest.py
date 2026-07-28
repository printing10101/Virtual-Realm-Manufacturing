"""项目根 conftest.py（阶段2 解耦改造新增）.

职责：
    在 pytest 启动阶段（早于任何 test module collect）将 ``engineering/python/``
    加入 sys.path，确保 ``from plugins.data_flywheel.xxx import ...`` 等绝对
    导入在 collect 阶段可用。

背景：
    - ``engineering/python/conftest.py`` 和 ``engineering/python/tests/conftest.py``
      都有 sys.path 注入，但它们的加载时机可能晚于部分 test module 的 collect。
    - 特别是 ``--collect-only`` 场景下，pytest 可能在 conftest.py 完全加载之前
      就开始 import test module，导致 ModuleNotFoundError。
    - 项目根 conftest.py 是 pytest 启动时最先加载的 conftest，确保 sys.path
      在最早时机被正确设置。

防复发机制：
    - 本文件与 ``engineering/python/conftest.py`` 的 sys.path 注入形成双重防护。
    - 如果未来 pytest 版本改变 conftest 加载顺序，项目根 conftest 仍然最先加载。
"""

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent
_ENGINEERING_PYTHON = _ROOT / "engineering" / "python"
if _ENGINEERING_PYTHON.exists() and str(_ENGINEERING_PYTHON) not in sys.path:
    sys.path.insert(0, str(_ENGINEERING_PYTHON))
