"""闭环决策数据模型与顶层入口（从 closed_loop 拆分，D5）。

数据类 + 独立入口函数；ClosedLoop 实现见 closed_loop.ClosedLoop。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ClosedLoopDecision:
    """闭环决策结果。

    Attributes:
        rule_id: 规则 ID。
        action: 决策动作（promote / demote / keep / rollback）。
        target_stage: 目标阶段（仅 promote/demote 有效）。
        reason: 决策原因（人类可读）。
        fused_confidence: Dempster-Shafer 融合后的置信度。
        conflict: 融合冲突系数（越高越不可信）。
        ds_mass: Dempster-Shafer 聚合质量。
        sample_count: 决策依据的样本数。
        evaluated_at: 决策时间戳。
        applied: 是否已应用（通过 ProgressivePublisher）。
        apply_error: 应用失败时的错误信息。
    """

    rule_id: str
    action: str  # promote | demote | keep | rollback
    target_stage: Optional[str] = None
    reason: str = ""
    fused_confidence: float = 0.0
    conflict: float = 0.0
    ds_mass: float = 0.0
    sample_count: int = 0
    evaluated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    applied: bool = False
    apply_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RuleOutcomeRecord:
    """单次规则触发的结果记录（用于滚动窗口）。

    Attributes:
        rule_id: 规则 ID。
        success: 是否成功。
        confidence: 触发时的置信度（0.0-1.0）。
        source: 来源（如 "mlflow_run" / "cam_validation" / "audit_log"）。
        recorded_at: 记录时间戳。
    """

    rule_id: str
    success: bool
    confidence: float
    source: str = "manual"
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


def run_closed_loop(
    rule_ids: Optional[List[str]] = None,
    apply: bool = True,
) -> List[ClosedLoopDecision]:
    """便捷函数：执行一次闭环迭代。

    Args:
        rule_ids: 指定评估的规则 ID 列表。None 表示评估所有。
        apply: 是否自动应用决策。

    Returns:
        决策结果列表。
    """
    from app.dreaming.closed_loop import ClosedLoop  # 延迟导入避免循环

    loop = ClosedLoop()
    return loop.run_closed_loop_iteration(rule_ids=rule_ids, apply=apply)


def record_rule_outcome(
    rule_id: str,
    success: bool,
    confidence: float,
    source: str = "manual",
) -> None:
    """便捷函数：记录规则触发结果。

    Args:
        rule_id: 规则 ID。
        success: 是否成功。
        confidence: 触发时的置信度。
        source: 来源标签。
    """
    from app.dreaming.closed_loop import ClosedLoop  # 延迟导入避免循环

    loop = ClosedLoop()
    loop.record_outcome(
        rule_id=rule_id,
        success=success,
        confidence=confidence,
        source=source,
    )
