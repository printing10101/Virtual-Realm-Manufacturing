"""产品轨 import 守卫：禁止 python/app/** 直接 import research/**。

设计目的：
- 保持产品轨与研究轨的隔离
- 研究模块改算法时不能破坏产品代码
- 任何想从产品轨调研究模块的需求，必须走 research_bridge

使用方法：
- 在 python/app/ai/__init__.py 顶部 import 此模块
- 它会在模块加载时检查 sys.modules，如发现违规立即报错
"""
from __future__ import annotations

import logging
import sys

logger = logging.getLogger(__name__)

# 允许的产品轨模块前缀
_ALLOWED_PRODUCT_PREFIXES = (
    "python.app.",
    "app.",
    "research_bridge.",
    "mcp_server.",
)

# 禁止产品轨直接 import 的研究模块前缀
_FORBIDDEN_RESEARCH_PREFIXES = (
    "research.",
    "research_bridge_violation.",  # 用于测试
)


def check_imports() -> None:
    """检查已加载的模块中是否有违规 import。

    如果发现产品轨代码 import 了 research/，抛出 RuntimeError。
    """
    violations = []
    for module_name in list(sys.modules.keys()):
        # 跳过自身
        if module_name == __name__:
            continue
        if not any(module_name.startswith(p) for p in _FORBIDDEN_RESEARCH_PREFIXES):
            continue
        # 找到这个 research 模块的来源
        mod = sys.modules[module_name]
        # 检查是否被产品轨模块 import
        violations.append((module_name, getattr(mod, "__file__", None)))

    if violations:
        msg = (
            "检测到产品轨代码 import 了 research/ 模块，违反双轨隔离：\n"
            + "\n".join(f"  - {n} ({f})" for n, f in violations)
            + "\n请通过 python/app/research_bridge/ 与研究模块通信。"
        )
        raise RuntimeError(msg)


def install() -> None:
    """在产品轨 __init__.py 中调用，安装 import 守卫。"""
    # 1. 先把 research 路径从 sys.path 里移除（防止被自动 import）
    # 2. 安装 import hook
    import builtins

    _real_import = builtins.__import__

    def _guarded_import(name, *args, **kwargs):
        result = _real_import(name, *args, **kwargs)
        # 如果产品轨代码尝试 import research/，报错
        if any(name.startswith(p) for p in _FORBIDDEN_RESEARCH_PREFIXES):
            # 但是允许 research_bridge 自己 import
            if "research_bridge" not in name:
                # 检查调用栈
                import traceback

                stack = traceback.extract_stack()
                for frame in stack[-5:-1]:
                    if any(
                        frame.filename.replace("\\", "/").startswith(p.replace(".", "/"))
                        for p in _ALLOWED_PRODUCT_PREFIXES
                    ):
                        raise RuntimeError(
                            f"产品轨禁止 import 研究模块: {name}\n"
                            f"调用方: {frame.filename}:{frame.lineno}\n"
                            f"请通过 python/app/research_bridge/ 通信。"
                        )
        return result

    builtins.__import__ = _guarded_import
    logger.info("research_bridge.install_import_guard: OK")


# 不在 import 时立即报错，避免破坏现有代码
# 安装调用方：python/app/ai/__init__.py 顶部（仅当 RESEARCH_BRIDGE_STRICT=1 时）
