"""自动化性能基准测试与回归检测框架。

提供LNN推理、NC代码生成、三视图解析等关键流程的性能基准。
"""

from __future__ import annotations

from app.benchmarks.performance.run_perf_benchmark import (
    PerformanceBenchmarkRunner,
    RegressionEntry,
    RegressionReport,
    check_regression,
)
from app.benchmarks.performance.thresholds import (
    PERFORMANCE_THRESHOLDS,
    REGRESSION_THRESHOLDS,
    check_violations,
    is_within_threshold,
)

__all__ = [
    "PERFORMANCE_THRESHOLDS",
    "REGRESSION_THRESHOLDS",
    "check_violations",
    "is_within_threshold",
    "check_regression",
    "PerformanceBenchmarkRunner",
    "RegressionEntry",
    "RegressionReport",
]
