"""Python 启动时自动导入的 sitecustomize 模块（项目根级）.

职责：
    在 Python 解释器启动阶段（早于所有第三方模块导入）注入 _overlapped
    空实现补丁，绕过本机 WinSock 损坏导致的 ``import _overlapped`` 失败。

背景：
    - 本机 _overlapped C 扩展因系统级 WinSock 损坏无法导入
      （OSError: [WinError 10038]）。
    - pytest 在启动阶段通过 setuptools entrypoints 加载 pytest_asyncio 插件，
      该插件 ``import asyncio`` → ``asyncio.windows_events`` → ``_overlapped``
      导入链失败，导致 pytest 在解析配置之前就崩溃。
    - ``engineering/python/conftest.py`` 中已有同样的补丁，但 conftest.py 加载
      时机晚于 pytest 插件加载，无法保护插件导入阶段。
    - sitecustomize.py 是 Python 启动时自动导入的模块（在 site 模块中），
      早于所有第三方模块，是注入此补丁的正确时机。
    - 当从项目根目录运行 ``python -m pytest`` 时，cwd（项目根）在 sys.path 上，
      本文件会被自动导入。

根因修复：
    以管理员身份运行 ``netsh winsock reset`` 并重启系统。修复后
    ``import _overlapped`` 会成功，本文件不会做任何事（try 块通过即返回）。

防复发机制：
    - 本文件仅在 ``import _overlapped`` 失败时注入空实现，不影响正常环境。
    - WinSock 修复后可安全删除本文件，或保留作为兜底防护。
    - ``engineering/python/conftest.py`` 中保留同样的补丁作为双重防护。
"""

import sys
import types

try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
