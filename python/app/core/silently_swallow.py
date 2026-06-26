"""统一的「静默吞咽异常」工具。

.. deprecated:: 1.0.0
    此工具已弃用，请改用显式的异常处理和日志记录。
    新代码应该使用 try-except 块并记录适当的日志级别。

用于以下场景：
- 第三方库/可选依赖缺失时不希望影响主流程
- 副作用失败（如写入文件、关闭资源）但不影响主返回值
- 已知可忽略的「最佳努力」操作

设计原则：
- 必须显式声明 reason，强制在代码审查时暴露意图
- 默认记录到 debug 级别日志，reason 会被包含
- 仍可选择把异常向上抛（fallback=return_default）
- 集中暴露统一接口，避免散落的 ``except Exception: pass``
"""

from __future__ import annotations

import functools
import logging
import warnings
from typing import Any, Callable, ParamSpec, TypeVar

logger = logging.getLogger(__name__)

P = ParamSpec("P")
R = TypeVar("R")


def silently_swallow(
    *exceptions: type[BaseException],
    reason: str,
    default: Any = None,
    log_level: int = logging.DEBUG,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """装饰器：在指定异常上静默吞咽，但强制要求声明 ``reason``。

    .. deprecated:: 1.0.0
        此装饰器已弃用。请使用显式的异常处理和日志记录。

    Args:
        *exceptions: 要捕获的异常类型；为空表示捕获 ``Exception``。
        reason: 必须提供的「为何可以忽略」说明，会写入日志。
        default: 异常发生时函数的返回值。
        log_level: 日志级别，默认 DEBUG；可设为 WARNING 让 review 更醒目。

    用法::

        @silently_swallow(OSError, reason="审计日志写失败不影响主流程")
        def _safe_write(...): ...

        @silently_swallow(reason="可选功能缺失", default=False)
        def has_feature_x() -> bool: ...
    """
    warnings.warn(
        "silently_swallow 装饰器已弃用，请使用显式的异常处理和日志记录",
        DeprecationWarning,
        stacklevel=2,
    )
    if not reason or not reason.strip():
        raise ValueError("silently_swallow 必须提供非空 reason 字段")
    catch = exceptions or (Exception,)

    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        qualname = f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            try:
                return func(*args, **kwargs)
            except catch as exc:
                logger.log(
                    log_level,
                    "silently_swallow at %s | reason=%s | exc=%s: %s",
                    qualname,
                    reason,
                    type(exc).__name__,
                    exc,
                )
                return default  # type: ignore[return-value]

        return wrapper

    return decorator
