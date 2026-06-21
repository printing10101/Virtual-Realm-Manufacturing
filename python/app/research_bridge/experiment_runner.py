"""A/B 测试运行器：在产品中同时跑 baseline 和 research 算法，对比结果。

工作流程：
1. 灰度打开某研究模块后，调用方走 experiment_runner 而不是直接调算法
2. experiment_runner 同时跑 baseline 和 research
3. 把两次结果都记录到 data/bridge/usage_logs/ab_test.jsonl
4. 返回 baseline 的结果（确保用户体验不变）
5. 后台分析脚本可读取 ab_test.jsonl 评估 research 是否更好
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Optional

from .data_anonymizer import DataAnonymizer
from .feature_flags import ResearchFeature, is_feature_enabled

logger = logging.getLogger(__name__)


@dataclass
class ABTestResult:
    """一次 A/B 测试结果。"""

    feature: str
    baseline_output: Any
    research_output: Any
    match: bool
    baseline_latency_ms: int
    research_latency_ms: int
    user_id: str


class ExperimentRunner:
    """A/B 测试运行器。"""

    def __init__(self, log_path: Optional[str] = None):
        self._anonymizer = DataAnonymizer()
        self._log_path = Path(log_path or "data/bridge/usage_logs/ab_test.jsonl")
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def run_with_baseline(
        self,
        feature: ResearchFeature,
        baseline_fn: Callable[[], Any],
        research_fn: Callable[[], Any],
        user_id: str = "anonymous",
        context: Optional[dict] = None,
    ) -> Any:
        """同时跑 baseline 和 research（如果研究模块对该用户启用），返回 baseline 结果。"""
        # 1. 跑 baseline（一定执行）
        t0 = time.perf_counter()
        try:
            baseline_output = baseline_fn()
            baseline_ok = True
            baseline_err = None
        except Exception as e:  # noqa: BLE001
            baseline_output = None
            baseline_ok = False
            baseline_err = repr(e)
        baseline_latency = int((time.perf_counter() - t0) * 1000)

        # 2. 判断 research 是否对该用户启用
        research_output: Any = None
        research_latency = 0
        match: Optional[bool] = None
        research_enabled = is_feature_enabled(feature, user_id)

        if research_enabled and baseline_ok:
            t1 = time.perf_counter()
            try:
                research_output = research_fn()
                match = baseline_output == research_output
            except Exception as e:  # noqa: BLE001
                research_output = None
                match = None
                logger.warning(
                    "research_module_failed feature=%s err=%s", feature.value, e
                )
            research_latency = int((time.perf_counter() - t1) * 1000)

        # 3. 记录
        result = ABTestResult(
            feature=feature.value,
            baseline_output=baseline_output,
            research_output=research_output,
            match=match if match is not None else False,
            baseline_latency_ms=baseline_latency,
            research_latency_ms=research_latency,
            user_id=self._anonymizer.anonymize_user_id(user_id),
        )
        self._append(result, context)

        # 4. 返回 baseline（用户体验不变）
        if not baseline_ok:
            raise RuntimeError(
                f"baseline_failed feature={feature.value} err={baseline_err}"
            )
        return baseline_output

    def _append(self, result: ABTestResult, context: Optional[dict]) -> None:
        """追加一条记录到 ab_test.jsonl。"""
        record = {
            "feature": result.feature,
            "baseline_output": _safe_serialize(result.baseline_output),
            "research_output": _safe_serialize(result.research_output),
            "match": result.match,
            "baseline_latency_ms": result.baseline_latency_ms,
            "research_latency_ms": result.research_latency_ms,
            "user_id": result.user_id,
            "context": context or {},
        }
        try:
            with open(self._log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False, default=str))
                f.write("\n")
        except Exception as e:  # noqa: BLE001
            logger.warning("ab_test_log_failed err=%s", e)


def _safe_serialize(obj: Any) -> Any:
    """尽量把对象转成可序列化的形式。"""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _safe_serialize(v) for k, v in obj.items()}
    if hasattr(obj, "__dict__"):
        return {k: _safe_serialize(v) for k, v in obj.__dict__.items()}
    return repr(obj)


__all__ = ["ExperimentRunner", "ABTestResult"]
