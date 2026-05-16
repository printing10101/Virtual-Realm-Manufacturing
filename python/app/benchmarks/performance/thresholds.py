"""系统性能阈值定义与管理。

定义各关键业务流程的性能基准线和回归检测标准。
"""

from __future__ import annotations

PERFORMANCE_THRESHOLDS: dict[str, dict[str, float]] = {
    "lnn_inference_ms": {
        "p50": 50,
        "p95": 200,
        "p99": 500,
    },
    "nc_generation_total_s": {
        "max": 30,
    },
    "drawing_parse_s": {
        "max": 10,
    },
    "model_load_s": {
        "max": 5,
    },
    "toolpath_gen_s": {
        "max": 15,
    },
    "post_processor_s": {
        "max": 5,
    },
    "batch_10_inference_ms": {
        "max": 200,
    },
    "batch_50_inference_ms": {
        "max": 800,
    },
    "batch_100_inference_ms": {
        "max": 1500,
    },
}

REGRESSION_THRESHOLDS: dict[str, float] = {
    "warning_pct": 20.0,
    "critical_pct": 50.0,
}

BOTTLENECK_THRESHOLD_PCT: float = 30.0


def get_threshold(metric: str) -> dict[str, float] | None:
    return PERFORMANCE_THRESHOLDS.get(metric)


def is_within_threshold(metric: str, value: float) -> bool:
    t = PERFORMANCE_THRESHOLDS.get(metric)
    if t is None:
        return True
    if "max" in t:
        return value <= t["max"]
    for key, limit in t.items():
        if value > limit:
            return False
    return True


def check_violations(results: dict[str, float]) -> list[dict[str, str]]:
    violations: list[dict[str, str]] = []
    for metric, value in results.items():
        t = PERFORMANCE_THRESHOLDS.get(metric)
        if t is None:
            continue
        if "max" in t and value > t["max"]:
            violations.append(
                {
                    "metric": metric,
                    "value": str(value),
                    "threshold": str(t["max"]),
                    "status": "VIOLATED",
                    "message": f"{metric}={value} 超过阈值 {t['max']}",
                }
            )
        for key, limit in t.items():
            if key == "max":
                continue
            if value > limit:
                violations.append(
                    {
                        "metric": f"{metric}.{key}",
                        "value": str(value),
                        "threshold": str(limit),
                        "status": "VIOLATED",
                        "message": f"{metric}.{key}={value} 超过阈值 {limit}",
                    }
                )
    return violations
