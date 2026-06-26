"""影子模式运行器：在产品中跑研究模块但不影响用户体验。

工作流程：
1. 产品调用 baseline 算法（用户看到的是 baseline 的结果）
2. 同时后台跑 research 算法（用户看不到）
3. 把两者的结果对比记录到 data/bridge/usage_logs/shadow_diff.jsonl
4. 不向用户暴露 research 失败的情况
5. 累积 N 条 diff 后，研究模块可以分析自己错在哪
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any, Callable, Optional

from .data_collector import UsageDataCollector
from .feature_flags import ResearchFeature, is_shadow_mode

logger = logging.getLogger(__name__)


@dataclass
class ShadowResult:
    """影子模式结果（不返回给用户，只用于研究分析）。"""

    feature: str
    baseline_output: Any
    research_output: Optional[Any]
    match: Optional[bool]
    baseline_latency_ms: int
    research_latency_ms: int
    research_failed: bool


class ShadowRunner:
    """影子模式运行器（单例）。"""

    _instance: Optional["ShadowRunner"] = None

    def __init__(self):
        self._collector = UsageDataCollector.get_instance()

    @classmethod
    def get_instance(cls) -> "ShadowRunner":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def run(
        self,
        feature: ResearchFeature,
        baseline_fn: Callable[[], Any],
        research_fn: Callable[[], Any],
        dxf_path: str = "",
        user_id: Optional[str] = None,
    ) -> Any:
        """运行影子模式：返回 baseline 结果，但同时后台跑 research 并记录 diff。

        即便研究模块对该用户禁用（DISABLED），只要 is_shadow_mode 开启，
        也会跑 research 用于研究分析。

        返回值：baseline 的结果（用户感知不到 research）
        """
        # 跑 baseline
        t0 = time.perf_counter()
        baseline_output = baseline_fn()
        baseline_latency = int((time.perf_counter() - t0) * 1000)

        # 判断是否需要跑 research
        should_shadow = is_shadow_mode(feature) or _master_shadow_enabled()

        research_output: Optional[Any] = None
        research_latency = 0
        research_failed = False
        match: Optional[bool] = None

        if should_shadow:
            t1 = time.perf_counter()
            try:
                research_output = research_fn()
                match = baseline_output == research_output
            except (ValueError, TypeError, KeyError, RuntimeError, OSError) as e:
                research_failed = True
                logger.warning(
                    "shadow_research_failed feature=%s err=%s", feature.value, e
                )
            research_latency = int((time.perf_counter() - t1) * 1000)

            # 记录
            self._collector.record_shadow_diff(
                feature=feature.value,
                baseline_result=baseline_output,
                research_result=research_output,
                dxf_path=dxf_path,
                user_id=user_id,
            )

        return baseline_output

    def should_shadow(self, feature: ResearchFeature) -> bool:
        """判断某功能是否在跑影子模式。"""
        return is_shadow_mode(feature) or _master_shadow_enabled()


def _master_shadow_enabled() -> bool:
    """全局影子开关（研究阶段强制开启）。"""
    from .feature_flags import SHADOW_MODE_MASTER

    return SHADOW_MODE_MASTER


__all__ = ["ShadowRunner", "ShadowResult"]
