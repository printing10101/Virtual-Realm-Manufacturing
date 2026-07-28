"""Outcomes 反馈闭环：将规则真实效果反馈到置信度与灰度阶段。

对应 Anthropic Dreaming 的 "Outcomes" 机制：
    - 工作中规则触发后产生 Outcome 样本（成功/失败/异常）
    - 闭环收集多源证据，通过 Dempster-Shafer 融合得到聚合置信度
    - 基于 FusionResult 的 confidence + conflict + ds_mass 决策晋级/降级
    - TaskRouter 接收反馈更新 EngineType.RULE 的在线成功率
    - 异常时联动 RollbackManager 自动回滚

本地化实现策略（与 HybridInferenceEngine 解耦）：
    - 自行实例化 DempsterShaferFusion 与 TaskRouter，不复用
      HybridInferenceEngine 内部实例，避免参数耦合
    - 自持 ``Dict[rule_id, Deque[float]]`` 滚动窗口按 rule_id 分别
      追踪效果，因 TaskRouter.update_outcome 的 engine 参数限定为
      EngineType 枚举，无法按 rule_id 细粒度追踪
    - 将规则效果证据包装为 InferenceResult 列表（成功/失败两类），
      调用 DempsterShaferFusion.fuse() 得到 FusionResult
    - 通过 EffectivenessMetricsCollector 获取度量
    - 通过 ProgressivePublisher 执行升级/降级
    - 通过 RollbackManager 处理硬约束违反
    - 所有决策写入审计日志（AIModule.DREAMING）

硬约束对齐：
    - cam_validation_required 始终 True
    - SUCCEEDED 任务禁删
    - HRC52 pending_calibration 强制降低置信度
    - K_s → cutting_force_coeff 直接传递
    - 单轮审核状态机不破坏
"""

from __future__ import annotations

import json
import logging
import threading
from collections import deque
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Deque, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 默认参数（12-Factor App：环境变量可覆盖，代码提供合理默认值）
# ---------------------------------------------------------------------------

DEFAULT_ROUTER_CONFIDENCE_THRESHOLD = 0.7
DEFAULT_FUSION_MIN_CONFIDENCE = 0.3
DEFAULT_FUSION_CONFLICT_THRESHOLD = 0.8
DEFAULT_RULE_WINDOW_SIZE = 64  # 每条规则维护的滚动样本窗口
DEFAULT_PROMOTE_CONFIDENCE = 0.75  # 融合置信度 ≥ 该值 → 建议晋级
DEFAULT_DEMOTE_CONFIDENCE = 0.45  # 融合置信度 ≤ 该值 → 建议降级
DEFAULT_MAX_CONFLICT_FOR_PROMOTE = 0.25  # 冲突高于此值不晋级
DEFAULT_MIN_SAMPLES_FOR_DECISION = 5  # 样本数不足则 keep，避免噪声决策
DEFAULT_HRC52_CONFIDENCE_PENALTY = 0.5  # HRC52 pending_calibration 乘子

# 闭环决策持久化目录
CLOSED_LOOP_STATE_DIR = "python/outputs/dreaming/closed_loop"


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------


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
    evaluated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
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
    recorded_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# ClosedLoop
# ---------------------------------------------------------------------------


class ClosedLoop:
    """Outcomes 反馈闭环核心。

    用法：
        loop = ClosedLoop()
        # 1. 记录规则触发结果
        loop.record_outcome("rule_xxx", success=True, confidence=0.8)
        # 2. 评估单条规则
        decision = loop.evaluate_rule("rule_xxx")
        # 3. 应用决策（晋级/降级/保持）
        loop.apply_decision(decision)
        # 4. 批量迭代
        results = loop.run_closed_loop_iteration()
    """

    def __init__(
        self,
        window_size: int = DEFAULT_RULE_WINDOW_SIZE,
        promote_confidence: float = DEFAULT_PROMOTE_CONFIDENCE,
        demote_confidence: float = DEFAULT_DEMOTE_CONFIDENCE,
        max_conflict_for_promote: float = DEFAULT_MAX_CONFLICT_FOR_PROMOTE,
        min_samples_for_decision: int = DEFAULT_MIN_SAMPLES_FOR_DECISION,
        hrc52_confidence_penalty: float = DEFAULT_HRC52_CONFIDENCE_PENALTY,
        fusion_conflict_threshold: float = DEFAULT_FUSION_CONFLICT_THRESHOLD,
        fusion_min_confidence: float = DEFAULT_FUSION_MIN_CONFIDENCE,
        router_confidence_threshold: float = DEFAULT_ROUTER_CONFIDENCE_THRESHOLD,
        progressive_publisher: Optional[Any] = None,
        metrics_collector: Optional[Any] = None,
        rollback_manager: Optional[Any] = None,
        state_dir: Optional[str] = None,
    ) -> None:
        """初始化闭环。

        Args:
            window_size: 每条规则的滚动样本窗口大小。
            promote_confidence: 晋级置信度阈值。
            demote_confidence: 降级置信度阈值。
            max_conflict_for_promote: 晋级允许的最大冲突系数。
            min_samples_for_decision: 决策所需的最小样本数。
            hrc52_confidence_penalty: HRC52 pending_calibration 置信度乘子。
            fusion_conflict_threshold: DempsterShaferFusion 冲突阈值。
            fusion_min_confidence: DempsterShaferFusion 最小置信度。
            router_confidence_threshold: TaskRouter 置信度阈值。
            progressive_publisher: ProgressivePublisher 实例。None 表示延迟初始化。
            metrics_collector: EffectivenessMetricsCollector 实例。None 表示延迟初始化。
            rollback_manager: RollbackManager 实例。None 表示延迟初始化。
            state_dir: 决策状态持久化目录。
        """
        self._lock = threading.RLock()
        self._window_size = max(1, int(window_size))
        self._promote_confidence = float(promote_confidence)
        self._demote_confidence = float(demote_confidence)
        self._max_conflict_for_promote = float(max_conflict_for_promote)
        self._min_samples_for_decision = max(1, int(min_samples_for_decision))
        self._hrc52_confidence_penalty = float(hrc52_confidence_penalty)

        # 自持滚动窗口：Dict[rule_id, Deque[RuleOutcomeRecord]]
        self._windows: Dict[str, Deque[RuleOutcomeRecord]] = {}

        # 延迟初始化的依赖
        self._publisher = progressive_publisher
        self._collector = metrics_collector
        self._rollback_mgr = rollback_manager

        # 自行实例化 DempsterShaferFusion 与 TaskRouter（不复用 HybridInferenceEngine 实例）
        self._fusion: Optional[Any] = None
        self._router: Optional[Any] = None
        self._fusion_params = {
            "conflict_threshold": fusion_conflict_threshold,
            "min_confidence": fusion_min_confidence,
            "enable_conflict_resolution": True,
        }
        self._router_params = {
            "rule_weight": 0.4,
            "ml_weight": 0.6,
            "confidence_threshold": router_confidence_threshold,
            "enable_fallback": True,
            "history_size": 256,
        }

        # 持久化目录
        self._state_dir = Path(state_dir or CLOSED_LOOP_STATE_DIR)
        self._state_dir.mkdir(parents=True, exist_ok=True)

        # 决策历史（内存）
        self._decision_history: Dict[str, List[ClosedLoopDecision]] = {}

    # ------------------------------------------------------------------
    # 延迟初始化依赖
    # ------------------------------------------------------------------

    def _get_fusion(self):
        """延迟获取 DempsterShaferFusion 实例。"""
        if self._fusion is None:
            try:
                from app.ai.lnn.fusion import DempsterShaferFusion

                self._fusion = DempsterShaferFusion(**self._fusion_params)
                logger.debug(
                    "ClosedLoop: DempsterShaferFusion 已实例化 params=%s",
                    self._fusion_params,
                )
            except Exception as e:
                logger.warning(
                    "ClosedLoop: DempsterShaferFusion 初始化失败，"
                    "将退化为加权平均：%s",
                    e,
                )
                self._fusion = None
        return self._fusion

    def _get_router(self):
        """延迟获取 TaskRouter 实例。"""
        if self._router is None:
            try:
                from app.ai.lnn.router.task_router import TaskRouter

                self._router = TaskRouter(**self._router_params)
                logger.debug(
                    "ClosedLoop: TaskRouter 已实例化 params=%s",
                    self._router_params,
                )
            except Exception as e:
                logger.warning(
                    "ClosedLoop: TaskRouter 初始化失败，"
                    "router 反馈将跳过：%s",
                    e,
                )
                self._router = None
        return self._router

    def _get_publisher(self):
        """延迟获取 ProgressivePublisher 实例。"""
        if self._publisher is None:
            try:
                from app.dreaming.progressive_publisher import (
                    ProgressivePublisher,
                )

                self._publisher = ProgressivePublisher()
            except Exception as e:
                logger.warning(
                    "ClosedLoop: ProgressivePublisher 初始化失败：%s", e
                )
                self._publisher = None
        return self._publisher

    def _get_collector(self):
        """延迟获取 EffectivenessMetricsCollector 实例。"""
        if self._collector is None:
            try:
                from app.dreaming.effectiveness_metrics import (
                    EffectivenessMetricsCollector,
                )

                self._collector = EffectivenessMetricsCollector()
            except Exception as e:
                logger.warning(
                    "ClosedLoop: EffectivenessMetricsCollector 初始化失败：%s",
                    e,
                )
                self._collector = None
        return self._collector

    def _get_rollback_manager(self):
        """延迟获取 RollbackManager 实例。"""
        if self._rollback_mgr is None:
            try:
                from app.dreaming.rollback_manager import RollbackManager

                self._rollback_mgr = RollbackManager(
                    publisher=self._get_publisher(),
                )
            except Exception as e:
                logger.warning(
                    "ClosedLoop: RollbackManager 初始化失败：%s", e
                )
                self._rollback_mgr = None
        return self._rollback_mgr

    def _get_audit_recorder(self):
        """延迟获取审计记录器。"""
        try:
            from app.dreaming.audit_integration import get_audit_recorder

            return get_audit_recorder()
        except Exception as e:
            logger.warning("ClosedLoop: 审计记录器获取失败：%s", e)
            return None

    # ------------------------------------------------------------------
    # 1. 记录规则触发结果
    # ------------------------------------------------------------------

    def record_outcome(
        self,
        rule_id: str,
        success: bool,
        confidence: float,
        source: str = "manual",
    ) -> None:
        """记录一次规则触发的结果。

        Args:
            rule_id: 规则 ID。
            success: 是否成功。
            confidence: 触发时的置信度（0.0-1.0）。
            source: 来源标签。
        """
        if not rule_id:
            return
        confidence = max(0.0, min(1.0, float(confidence)))

        with self._lock:
            if rule_id not in self._windows:
                self._windows[rule_id] = deque(
                    maxlen=self._window_size
                )
            record = RuleOutcomeRecord(
                rule_id=rule_id,
                success=success,
                confidence=confidence,
                source=source,
            )
            self._windows[rule_id].append(record)

        # 同步反馈到 TaskRouter（EngineType.RULE 的全局在线成功率）
        router = self._get_router()
        if router is not None:
            try:
                from app.ai.lnn.core import EngineType

                router.update_outcome(
                    engine=EngineType.RULE,
                    success=success,
                    confidence=confidence,
                )
            except Exception as e:
                logger.debug(
                    "ClosedLoop: TaskRouter.update_outcome 失败（忽略）：%s",
                    e,
                )

        # 同步录入 EffectivenessMetricsCollector（便于统一度量）
        collector = self._get_collector()
        if collector is not None:
            try:
                from app.dreaming.effectiveness_metrics import (
                    OutcomeSample,
                )

                sample = OutcomeSample(
                    rule_id=rule_id,
                    triggered_at=datetime.now(timezone.utc).isoformat(),
                    correct=success,
                    false_positive=(not success),
                    false_negative=False,
                    production_error=False,
                    cam_validation_bypassed=False,
                    succeeded_lock_violated=False,
                    source=source,
                )
                collector.record_sample(sample)
            except Exception as e:
                logger.debug(
                    "ClosedLoop: EffectivenessMetricsCollector 录入失败（忽略）：%s",
                    e,
                )

    # ------------------------------------------------------------------
    # 2. 评估规则
    # ------------------------------------------------------------------

    def evaluate_rule(self, rule_id: str) -> ClosedLoopDecision:
        """评估指定规则，返回决策建议。

        决策逻辑：
            1. 从滚动窗口取出最近样本
            2. 将成功/失败样本包装为 InferenceResult 列表
            3. 调用 DempsterShaferFusion.fuse() 得到 FusionResult
            4. 基于 confidence + conflict + ds_mass 决策：
                - 硬约束违反 → rollback
                - 样本不足 → keep
                - confidence ≥ promote_confidence 且 conflict ≤ max → promote
                - confidence ≤ demote_confidence 或 conflict > fusion_threshold → demote
                - 否则 → keep

        Args:
            rule_id: 规则 ID。

        Returns:
            ClosedLoopDecision 实例。
        """
        evaluated_at = datetime.now(timezone.utc).isoformat()

        with self._lock:
            window = self._windows.get(rule_id, deque(maxlen=self._window_size))
            samples = list(window)

        sample_count = len(samples)
        decision = ClosedLoopDecision(
            rule_id=rule_id,
            action="keep",
            reason="",
            sample_count=sample_count,
            evaluated_at=evaluated_at,
        )

        # 阶段 1：检查硬约束违反（通过 EffectivenessMetricsCollector）
        collector = self._get_collector()
        if collector is not None:
            try:
                metrics = collector.collect_metrics(rule_id)
                if metrics and metrics.hard_constraint_violations > 0:
                    decision.action = "rollback"
                    decision.reason = (
                        f"硬约束违反 {metrics.hard_constraint_violations} 次，"
                        f"触发自动回滚"
                    )
                    decision.fused_confidence = metrics.confidence
                    decision.conflict = 0.0
                    decision.ds_mass = 0.0
                    return decision
            except Exception as e:
                logger.debug(
                    "ClosedLoop: collect_metrics 失败（继续评估）：%s", e
                )

        # 阶段 2：样本不足直接 keep
        if sample_count < self._min_samples_for_decision:
            decision.action = "keep"
            decision.reason = (
                f"样本数不足（{sample_count}/"
                f"{self._min_samples_for_decision}），暂不决策"
            )
            return decision

        # 阶段 3：Dempster-Shafer 融合
        fused_confidence, conflict, ds_mass = self._fuse_rule_evidence(
            samples
        )
        decision.fused_confidence = fused_confidence
        decision.conflict = conflict
        decision.ds_mass = ds_mass

        # 阶段 4：HRC52 pending_calibration 惩罚（强制降低置信度）
        fused_confidence = self._apply_hrc52_penalty(rule_id, fused_confidence)
        decision.fused_confidence = fused_confidence

        # 阶段 5：决策
        if fused_confidence >= self._promote_confidence and conflict <= self._max_conflict_for_promote:
            decision.action = "promote"
            decision.target_stage = self._get_next_stage(rule_id)
            decision.reason = (
                f"融合置信度 {fused_confidence:.3f} ≥ "
                f"{self._promote_confidence} 且冲突 {conflict:.3f} ≤ "
                f"{self._max_conflict_for_promote}，建议晋级"
            )
        elif fused_confidence <= self._demote_confidence or conflict > self._fusion_params["conflict_threshold"]:
            decision.action = "demote"
            decision.target_stage = self._get_previous_stage(rule_id)
            decision.reason = (
                f"融合置信度 {fused_confidence:.3f} ≤ "
                f"{self._demote_confidence} 或冲突 {conflict:.3f} 过高，"
                f"建议降级"
            )
        else:
            decision.action = "keep"
            decision.reason = (
                f"融合置信度 {fused_confidence:.3f} 与冲突 {conflict:.3f} "
                f"均在容忍区间，保持现状"
            )

        return decision

    def _fuse_rule_evidence(
        self, samples: List[RuleOutcomeRecord]
    ) -> tuple:
        """将规则样本融合为单一置信度。

        将成功样本与失败样本分别包装为 InferenceResult：
            - 成功样本：prediction=1.0, confidence=record.confidence
            - 失败样本：prediction=0.0, confidence=1-record.confidence

        调用 DempsterShaferFusion.fuse() 得到 FusionResult，
        返回 (fused_confidence, conflict, ds_mass)。

        若 DempsterShaferFusion 不可用，退化为加权平均。

        Args:
            samples: 滚动窗口内的样本列表。

        Returns:
            (fused_confidence, conflict, ds_mass) 三元组。
        """
        fusion = self._get_fusion()

        if fusion is None or not samples:
            # 退化为加权平均
            total_weight = 0.0
            weighted_sum = 0.0
            for s in samples:
                w = max(0.1, min(1.0, s.confidence))
                weighted_sum += (1.0 if s.success else 0.0) * w
                total_weight += w
            fused = weighted_sum / total_weight if total_weight > 0 else 0.0
            return (fused, 0.0, fused)

        try:
            from app.ai.lnn.core import EngineType, InferenceResult

            results: List[InferenceResult] = []
            for s in samples:
                if s.success:
                    results.append(
                        InferenceResult(
                            prediction=1.0,
                            confidence=max(0.3, s.confidence),
                            engine_used=EngineType.RULE,
                            model_used=s.rule_id,
                            processing_time_ms=0.0,
                            metadata={"source": s.source, "outcome": "success"},
                        )
                    )
                else:
                    results.append(
                        InferenceResult(
                            prediction=0.0,
                            confidence=max(0.3, 1.0 - s.confidence),
                            engine_used=EngineType.RULE,
                            model_used=s.rule_id,
                            processing_time_ms=0.0,
                            metadata={"source": s.source, "outcome": "failure"},
                        )
                    )

            fusion_result = fusion.fuse(results)
            qm = fusion_result.quality_metrics or {}
            return (
                float(fusion_result.confidence),
                float(qm.get("conflict", 0.0)),
                float(qm.get("ds_mass", fusion_result.confidence)),
            )
        except Exception as e:
            logger.warning(
                "ClosedLoop: DempsterShaferFusion.fuse 失败，退化为加权平均：%s",
                e,
            )
            total_weight = 0.0
            weighted_sum = 0.0
            for s in samples:
                w = max(0.1, min(1.0, s.confidence))
                weighted_sum += (1.0 if s.success else 0.0) * w
                total_weight += w
            fused = weighted_sum / total_weight if total_weight > 0 else 0.0
            return (fused, 0.0, fused)

    def _apply_hrc52_penalty(
        self, rule_id: str, confidence: float
    ) -> float:
        """对 HRC52 pending_calibration 规则强制降低置信度。

        硬约束：HRC52 pending_calibration 强制降低置信度，
        避免未校准数据流入高阶段灰度。

        Args:
            rule_id: 规则 ID。
            confidence: 原始融合置信度。

        Returns:
            惩罚后的置信度。
        """
        if "HRC52" in rule_id or "hrc52" in rule_id.lower():
            penalized = confidence * self._hrc52_confidence_penalty
            logger.debug(
                "ClosedLoop: HRC52 pending_calibration 惩罚 %s %.3f → %.3f",
                rule_id,
                confidence,
                penalized,
            )
            return penalized
        return confidence

    def _get_next_stage(self, rule_id: str) -> Optional[str]:
        """获取规则的下一晋级阶段。"""
        publisher = self._get_publisher()
        if publisher is None:
            return None
        try:
            record = publisher.get_record(rule_id)
            if record is None:
                # 规则尚未发布，下一阶段为 shadow
                return "shadow"
            # record.current_stage 已是 PublicationStage 枚举
            current_stage = record.current_stage
            nxt = current_stage.next_stage
            return nxt.value if nxt else None
        except Exception as e:
            logger.debug("ClosedLoop: get_next_stage 失败：%s", e)
            return None

    def _get_previous_stage(self, rule_id: str) -> Optional[str]:
        """获取规则的降级目标阶段。"""
        publisher = self._get_publisher()
        if publisher is None:
            return None
        try:
            record = publisher.get_record(rule_id)
            if record is None:
                return None
            current_stage = record.current_stage
            prev = current_stage.previous_stage
            return prev.value if prev else None
        except Exception as e:
            logger.debug("ClosedLoop: get_previous_stage 失败：%s", e)
            return None

    # ------------------------------------------------------------------
    # 3. 应用决策
    # ------------------------------------------------------------------

    def apply_decision(self, decision: ClosedLoopDecision) -> bool:
        """应用闭环决策。

        Args:
            decision: 决策结果。

        Returns:
            是否应用成功。
        """
        if decision.action == "keep":
            decision.applied = True
            return True

        if decision.action == "rollback":
            return self._apply_rollback(decision)

        if decision.action == "promote":
            return self._apply_promote(decision)

        if decision.action == "demote":
            return self._apply_demote(decision)

        logger.warning("ClosedLoop: 未知 action=%s", decision.action)
        return False

    def _apply_promote(self, decision: ClosedLoopDecision) -> bool:
        """执行晋级决策。"""
        publisher = self._get_publisher()
        if publisher is None:
            decision.apply_error = "ProgressivePublisher 不可用"
            return False
        try:
            from app.dreaming.progressive_publisher import PublicationStage

            target_stage = None
            if decision.target_stage:
                try:
                    target_stage = PublicationStage(decision.target_stage)
                except ValueError:
                    logger.warning(
                        "ClosedLoop: 未知 target_stage=%s，使用默认晋级",
                        decision.target_stage,
                    )
            result = publisher.promote(
                rule_id=decision.rule_id,
                target_stage=target_stage,
                metrics_snapshot={
                    "fused_confidence": decision.fused_confidence,
                    "conflict": decision.conflict,
                    "ds_mass": decision.ds_mass,
                    "sample_count": decision.sample_count,
                    "source": "closed_loop",
                },
            )
            decision.applied = bool(result.success)
            if not result.success:
                decision.apply_error = result.error
            self._record_decision_to_audit(decision)
            return decision.applied
        except Exception as e:
            decision.apply_error = f"{type(e).__name__}: {e}"
            logger.error(
                "ClosedLoop: 晋级失败 rule=%s：%s",
                decision.rule_id,
                e,
                exc_info=True,
            )
            return False

    def _apply_demote(self, decision: ClosedLoopDecision) -> bool:
        """执行降级决策。"""
        publisher = self._get_publisher()
        if publisher is None:
            decision.apply_error = "ProgressivePublisher 不可用"
            return False
        try:
            from app.dreaming.progressive_publisher import PublicationStage

            target_stage = None
            if decision.target_stage:
                try:
                    target_stage = PublicationStage(decision.target_stage)
                except ValueError:
                    logger.warning(
                        "ClosedLoop: 未知 target_stage=%s，使用默认降级",
                        decision.target_stage,
                    )
            result = publisher.demote(
                rule_id=decision.rule_id,
                reason=decision.reason,
                target_stage=target_stage,
                auto=False,
            )
            decision.applied = bool(result.success)
            if not result.success:
                decision.apply_error = result.error
            self._record_decision_to_audit(decision)
            return decision.applied
        except Exception as e:
            decision.apply_error = f"{type(e).__name__}: {e}"
            logger.error(
                "ClosedLoop: 降级失败 rule=%s：%s",
                decision.rule_id,
                e,
                exc_info=True,
            )
            return False

    def _apply_rollback(self, decision: ClosedLoopDecision) -> bool:
        """执行回滚决策（硬约束违反）。"""
        rollback_mgr = self._get_rollback_manager()
        if rollback_mgr is None:
            decision.apply_error = "RollbackManager 不可用"
            return False
        try:
            result = rollback_mgr.rollback_rule(
                rule_id=decision.rule_id,
                reason=decision.reason,
                severity="hard_constraint",
                fully_deprecate=True,
            )
            decision.applied = bool(result.success)
            if not result.success:
                decision.apply_error = result.error
            self._record_decision_to_audit(decision)
            return decision.applied
        except Exception as e:
            decision.apply_error = f"{type(e).__name__}: {e}"
            logger.error(
                "ClosedLoop: 回滚失败 rule=%s：%s",
                decision.rule_id,
                e,
                exc_info=True,
            )
            return False

    def _record_decision_to_audit(
        self, decision: ClosedLoopDecision
    ) -> None:
        """将闭环决策写入审计日志。"""
        recorder = self._get_audit_recorder()
        if recorder is None:
            return
        try:
            # DreamingAuditRecorder 提供 record_rule_application 方法
            recorder.record_rule_application(
                rule_id=decision.rule_id,
                rule_description=(
                    f"闭环决策 action={decision.action} "
                    f"reason={decision.reason}"
                ),
                validation_passed=True,
                applied=decision.applied,
                rollback_triggered=(decision.action == "rollback"),
            )
        except Exception as e:
            logger.debug(
                "ClosedLoop: 审计记录失败（忽略）：%s", e
            )

    # ------------------------------------------------------------------
    # 4. 批量迭代
    # ------------------------------------------------------------------

    def run_closed_loop_iteration(
        self,
        rule_ids: Optional[List[str]] = None,
        apply: bool = True,
    ) -> List[ClosedLoopDecision]:
        """执行一次闭环迭代。

        Args:
            rule_ids: 指定评估的规则 ID 列表。None 表示评估所有有样本的规则。
            apply: 是否自动应用决策。False 表示仅评估不应用。

        Returns:
            决策结果列表。
        """
        if rule_ids is None:
            with self._lock:
                rule_ids = list(self._windows.keys())

        if not rule_ids:
            logger.info("ClosedLoop: 无可评估规则，迭代结束")
            return []

        decisions: List[ClosedLoopDecision] = []
        for rule_id in rule_ids:
            try:
                decision = self.evaluate_rule(rule_id)
                if apply:
                    self.apply_decision(decision)
                decisions.append(decision)

                # 记录到历史
                with self._lock:
                    if rule_id not in self._decision_history:
                        self._decision_history[rule_id] = []
                    self._decision_history[rule_id].append(decision)
            except Exception as e:
                logger.error(
                    "ClosedLoop: 评估 rule=%s 失败：%s",
                    rule_id,
                    e,
                    exc_info=True,
                )

        # 持久化本次迭代结果
        self._persist_iteration(decisions)

        logger.info(
            "ClosedLoop: 迭代完成，共 %d 条决策（promote=%d, demote=%d, "
            "keep=%d, rollback=%d）",
            len(decisions),
            sum(1 for d in decisions if d.action == "promote"),
            sum(1 for d in decisions if d.action == "demote"),
            sum(1 for d in decisions if d.action == "keep"),
            sum(1 for d in decisions if d.action == "rollback"),
        )
        return decisions

    def _persist_iteration(
        self, decisions: List[ClosedLoopDecision]
    ) -> None:
        """持久化单次迭代结果到 JSON 文件。"""
        if not decisions:
            return
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self._state_dir / f"iteration_{timestamp}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "iteration_at": datetime.now(timezone.utc).isoformat(),
                        "decision_count": len(decisions),
                        "decisions": [d.to_dict() for d in decisions],
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            logger.debug(
                "ClosedLoop: 迭代结果已持久化 %s", output_file
            )
        except OSError as e:
            logger.warning(
                "ClosedLoop: 迭代结果持久化失败（不影响决策）：%s", e
            )

    # ------------------------------------------------------------------
    # 5. 查询接口
    # ------------------------------------------------------------------

    def get_decision_history(
        self, rule_id: str, limit: int = 10
    ) -> List[ClosedLoopDecision]:
        """获取指定规则的决策历史。"""
        with self._lock:
            history = self._decision_history.get(rule_id, [])
            return list(history[-limit:])

    def get_window_samples(
        self, rule_id: str
    ) -> List[RuleOutcomeRecord]:
        """获取指定规则的当前窗口样本。"""
        with self._lock:
            window = self._windows.get(rule_id, deque(maxlen=self._window_size))
            return list(window)

    def get_stats(self) -> Dict[str, Any]:
        """获取闭环整体统计信息。"""
        with self._lock:
            total_samples = sum(len(w) for w in self._windows.values())
            rule_count = len(self._windows)
            total_decisions = sum(
                len(h) for h in self._decision_history.values()
            )
        return {
            "tracked_rule_count": rule_count,
            "total_samples": total_samples,
            "total_decisions": total_decisions,
            "window_size": self._window_size,
            "promote_confidence": self._promote_confidence,
            "demote_confidence": self._demote_confidence,
            "max_conflict_for_promote": self._max_conflict_for_promote,
            "min_samples_for_decision": self._min_samples_for_decision,
            "fusion_available": self._fusion is not None,
            "router_available": self._router is not None,
        }

    # ------------------------------------------------------------------
    # 6. 持久化与恢复
    # ------------------------------------------------------------------

    def save_state(self) -> None:
        """将当前窗口与决策历史持久化到磁盘。"""
        state = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "windows": {},
            "decision_history": {},
        }
        with self._lock:
            for rule_id, window in self._windows.items():
                state["windows"][rule_id] = [
                    {
                        "rule_id": r.rule_id,
                        "success": r.success,
                        "confidence": r.confidence,
                        "source": r.source,
                        "recorded_at": r.recorded_at,
                    }
                    for r in window
                ]
            for rule_id, history in self._decision_history.items():
                state["decision_history"][rule_id] = [
                    d.to_dict() for d in history
                ]

        try:
            state_file = self._state_dir / "closed_loop_state.json"
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(
                "ClosedLoop: 状态已保存到 %s", state_file
            )
        except OSError as e:
            logger.warning("ClosedLoop: 状态保存失败：%s", e)

    def load_state(self) -> None:
        """从磁盘恢复窗口与决策历史。"""
        state_file = self._state_dir / "closed_loop_state.json"
        if not state_file.exists():
            return
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            with self._lock:
                self._windows.clear()
                for rule_id, samples in state.get("windows", {}).items():
                    window: Deque[RuleOutcomeRecord] = deque(
                        maxlen=self._window_size
                    )
                    for s in samples:
                        window.append(
                            RuleOutcomeRecord(
                                rule_id=s["rule_id"],
                                success=s["success"],
                                confidence=s["confidence"],
                                source=s.get("source", "restored"),
                                recorded_at=s.get(
                                    "recorded_at",
                                    datetime.now(timezone.utc).isoformat(),
                                ),
                            )
                        )
                    self._windows[rule_id] = window

                self._decision_history.clear()
                for rule_id, history in state.get(
                    "decision_history", {}
                ).items():
                    self._decision_history[rule_id] = [
                        ClosedLoopDecision(
                            rule_id=d["rule_id"],
                            action=d["action"],
                            target_stage=d.get("target_stage"),
                            reason=d.get("reason", ""),
                            fused_confidence=d.get(
                                "fused_confidence", 0.0
                            ),
                            conflict=d.get("conflict", 0.0),
                            ds_mass=d.get("ds_mass", 0.0),
                            sample_count=d.get("sample_count", 0),
                            evaluated_at=d.get(
                                "evaluated_at",
                                datetime.now(timezone.utc).isoformat(),
                            ),
                            applied=d.get("applied", False),
                            apply_error=d.get("apply_error"),
                        )
                        for d in history
                    ]
            logger.info(
                "ClosedLoop: 状态已恢复（%d 条规则，%d 个样本）",
                len(self._windows),
                sum(len(w) for w in self._windows.values()),
            )
        except (OSError, json.JSONDecodeError, KeyError) as e:
            logger.warning("ClosedLoop: 状态恢复失败：%s", e)


# ---------------------------------------------------------------------------
# 便捷函数
# ---------------------------------------------------------------------------


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
    loop = ClosedLoop()
    loop.record_outcome(
        rule_id=rule_id,
        success=success,
        confidence=confidence,
        source=source,
    )
