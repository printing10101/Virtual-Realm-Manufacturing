"""
灵境制造 - 性能监控装饰器
提供关键操作计时、内存监控和API调用统计
"""
from __future__ import annotations

import asyncio
import functools
import logging
import time
import tracemalloc
from collections import defaultdict
from collections.abc import Callable
from typing import Any, TypeVar

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class PerformanceMetrics:
    """性能指标收集器"""

    def __init__(self) -> None:
        self._timings: dict[str, list[float]] = defaultdict(list)
        self._calls: dict[str, int] = defaultdict(int)
        self._errors: dict[str, int] = defaultdict(int)
        self._memory_snapshots: dict[str, float] = {}

    def record_timing(self, name: str, duration: float) -> None:
        """记录执行时间"""
        self._timings[name].append(duration)
        self._calls[name] += 1

    def record_error(self, name: str) -> None:
        """记录错误"""
        self._errors[name] += 1

    def record_memory(self, name: str) -> None:
        """记录内存使用"""
        current, _peak = tracemalloc.get_traced_memory()
        self._memory_snapshots[name] = current / (1024 * 1024)  # MB

    def get_stats(self) -> dict[str, Any]:
        """获取所有统计信息"""
        stats: dict[str, Any] = {}
        for name, timings in self._timings.items():
            stats[name] = {
                "count": len(timings),
                "total": sum(timings),
                "avg": sum(timings) / len(timings),
                "min": min(timings),
                "max": max(timings),
                "calls": self._calls[name],
                "errors": self._errors[name]
            }
        stats["memory"] = self._memory_snapshots
        return stats


# 全局性能指标收集器
metrics = PerformanceMetrics()


def timing(name: str) -> Callable[[F], F]:
    """性能计时装饰器"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = await func(*args, **kwargs)
                return result
            except Exception:
                metrics.record_error(name)
                raise
            finally:
                duration = time.perf_counter() - start
                metrics.record_timing(name, duration)
                if duration > 1.0:
                    logger.warning(f"[PERF] {name} took {duration:.3f}s")

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            start = time.perf_counter()
            try:
                result = func(*args, **kwargs)
                return result
            except Exception:
                metrics.record_error(name)
                raise
            finally:
                duration = time.perf_counter() - start
                metrics.record_timing(name, duration)
                if duration > 1.0:
                    logger.warning(f"[PERF] {name} took {duration:.3f}s")

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    return decorator


def memory_monitor(name: str) -> Callable[[F], F]:
    """内存监控装饰器"""
    def decorator(func: F) -> F:
        @functools.wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracemalloc.start()
            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                metrics.record_memory(name)
                tracemalloc.stop()

        @functools.wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            tracemalloc.start()
            try:
                result = func(*args, **kwargs)
                return result
            finally:
                metrics.record_memory(name)
                tracemalloc.stop()

        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        return sync_wrapper  # type: ignore
    return decorator
