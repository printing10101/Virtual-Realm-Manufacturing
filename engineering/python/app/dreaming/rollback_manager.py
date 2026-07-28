"""规则回滚管理器（Rollback Manager）。

对应 Anthropic Dreaming 的 "Auto-rollback on anomaly" 机制：
    - 灰度发布中的规则触发异常指标时，自动回滚
    - 异常检测：连续 N 次效果指标低于阈值、硬约束违反、生产异常率超限
    - 回滚动作：降级灰度阶段 → 标记 DEPRECATED → 知识图谱回滚
    - 所有回滚决策写入审计日志

设计原则：
    - 回滚不删除审计记录，仅标记规则状态为 deprecated
    - 回滚优先级：硬约束违反 > 生产异常 > 指标恶化
    - 硬约束违反立即回滚，不等指标窗口
    - 回滚后规则进入冷却期（默认 24h），期间不可重新发布
    - 回滚幂等：已 deprecated 的规则再次回滚返回成功

硬约束对齐：
    - CAM 校验绕过 → 立即回滚
    - SUCCEEDED 任务解锁 → 立即回滚
    - HRC52 pending_calibration 阈值降低 → 立即回滚
    - 这些回滚不通过 ProgressivePublisher.demote，直接调用 RuleApplicator.rollback

用法：
    manager = RollbackManager()
    # 自动检测异常并回滚
    rolled_back = manager.monitor_and_rollback()
    # 显式回滚
    result = manager.rollback_rule("rule_chatter_v1", "硬约束违反")
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.dreaming.apply_rules import RollbackResult, RuleApplicator
from app.dreaming.effectiveness_metrics import (
    EffectivenessMetrics,
    EffectivenessMetricsCollector,
    OutcomeSample,
)
from app.dreaming.progressive_publisher import (
    PublicationRecord,
    PublicationStage,
    ProgressivePublisher,
)

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 回滚数据结构
# -----------------------------------------------------------------------------


@dataclass
class RollbackDecision:
    """回滚决策。

    Attributes:
        rule_id: 规则 ID。
        should_rollback: 是否应该回滚。
        reason: 回滚原因（若 should_rollback=True）。
        severity: 严重级别（hard_constraint / production_error / metrics_degradation）。
        detected_at: 检测时间戳。
        metrics_snapshot: 触发回滚的指标快照。
    """

    rule_id: str
    should_rollback: bool
    reason: str = ""
    severity: str = "none"  # hard_constraint | production_error | metrics_degradation | none
    detected_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    metrics_snapshot: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class RollbackExecutionResult:
    """回滚执行结果。

    Attributes:
        success: 回滚是否成功。
        rule_id: 规则 ID。
        previous_stage: 回滚前的灰度阶段。
        current_stage: 回滚后的灰度阶段。
        fully_deprecated: 是否完全废弃（DEPRECATED 状态）。
        rollback_result: RuleApplicator.rollback 的返回值（若调用了）。
        operated_at: 操作时间戳。
        reason: 回滚原因。
        error: 失败时的错误信息。
    """

    success: bool
    rule_id: str
    previous_stage: str = ""
    current_stage: str = ""
    fully_deprecated: bool = False
    rollback_result: Optional[RollbackResult] = None
    operated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    reason: str = ""
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.rollback_result is not None:
            d["rollback_result"] = self.rollback_result.to_dict()
        return d


# -----------------------------------------------------------------------------
# 回滚管理器
# -----------------------------------------------------------------------------


# 回滚历史持久化目录
ROLLBACK_HISTORY_DIR = "python/outputs/dreaming/rollback_history"

# 默认冷却期（小时）：回滚后规则进入冷却，期间不可重新发布
DEFAULT_COOLDOWN_HOURS = 24

# 连续异常次数阈值：连续 N 次指标低于阈值触发回滚
DEFAULT_CONSECUTIVE_ANOMALY_THRESHOLD = 3

# 生产异常率阈值：超过此值立即回滚
DEFAULT_PRODUCTION_ERROR_RATE_THRESHOLD = 0.25

# 硬约束违反次数阈值：任意一次即触发回滚
DEFAULT_HARD_CONSTRAINT_VIOLATION_THRESHOLD = 1


class RollbackManager:
    """规则回滚管理器。

    负责：
        1. 定期检查所有灰度发布中规则的效果指标
        2. 检测异常：硬约束违反、生产异常、指标连续恶化
        3. 触发自动回滚（通过 ProgressivePublisher.demote 或 RuleApplicator.rollback）
        4. 管理回滚冷却期
        5. 所有回滚决策写入审计日志

    回滚优先级：
        1. 硬约束违反（立即回滚到 DEPRECATED）
        2. 生产异常率超限（立即降级，连续触发则回滚）
        3. 指标连续恶化（连续 N 次低于阈值则回滚）

    线程安全：通过内部锁保护冷却期字典和回滚历史。
    """

    def __init__(
        self,
        history_dir: Optional[str] = None,
        publisher: Optional[ProgressivePublisher] = None,
        applicator: Optional[RuleApplicator] = None,
        metrics_collector: Optional[EffectivenessMetricsCollector] = None,
        cooldown_hours: int = DEFAULT_COOLDOWN_HOURS,
        consecutive_anomaly_threshold: int = DEFAULT_CONSECUTIVE_ANOMALY_THRESHOLD,
        production_error_rate_threshold: float = DEFAULT_PRODUCTION_ERROR_RATE_THRESHOLD,
    ) -> None:
        """初始化回滚管理器。

        Args:
            history_dir: 回滚历史持久化目录。
            publisher: ProgressivePublisher 实例。
            applicator: RuleApplicator 实例。
            metrics_collector: 效果度量收集器实例。
            cooldown_hours: 冷却期小时数。
            consecutive_anomaly_threshold: 连续异常次数阈值。
            production_error_rate_threshold: 生产异常率阈值。
        """
        self.history_dir = Path(history_dir or ROLLBACK_HISTORY_DIR)
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self._publisher = publisher
        self._applicator = applicator
        self._metrics_collector = metrics_collector
        self.cooldown_hours = cooldown_hours
        self.consecutive_anomaly_threshold = consecutive_anomaly_threshold
        self.production_error_rate_threshold = (
            production_error_rate_threshold
        )
        self._lock = threading.RLock()
        # rule_id -> 冷却到期时间戳
        self._cooldowns: Dict[str, str] = {}
        # rule_id -> 连续异常计数
        self._consecutive_anomalies: Dict[str, int] = {}
        # 回滚历史
        self._rollback_history: List[Dict[str, Any]] = []
        self._load_history()

    # ------------------------------------------------------------------
    # 延迟依赖
    # ------------------------------------------------------------------

    def _get_publisher(self) -> ProgressivePublisher:
        if self._publisher is None:
            self._publisher = ProgressivePublisher()
        return self._publisher

    def _get_applicator(self) -> RuleApplicator:
        if self._applicator is None:
            self._applicator = RuleApplicator()
        return self._applicator

    def _get_metrics_collector(self) -> EffectivenessMetricsCollector:
        if self._metrics_collector is None:
            self._metrics_collector = EffectivenessMetricsCollector()
        return self._metrics_collector

    def _get_audit_recorder(self):
        from app.dreaming.audit_integration import get_audit_recorder

        return get_audit_recorder()

    # ------------------------------------------------------------------
    # 历史持久化
    # ------------------------------------------------------------------

    def _history_file(self) -> Path:
        return self.history_dir / "rollback_history.json"

    def _cooldown_file(self) -> Path:
        return self.history_dir / "cooldowns.json"

    def _load_history(self) -> None:
        """加载回滚历史和冷却期。"""
        # 加载回滚历史
        try:
            hist_file = self._history_file()
            if hist_file.exists():
                with open(hist_file, "r", encoding="utf-8") as f:
                    self._rollback_history = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("加载回滚历史失败：%s", e)

        # 加载冷却期
        try:
            cd_file = self._cooldown_file()
            if cd_file.exists():
                with open(cd_file, "r", encoding="utf-8") as f:
                    self._cooldowns = json.load(f)
        except (OSError, json.JSONDecodeError) as e:
            logger.warning("加载冷却期失败：%s", e)

    def _save_history(self) -> None:
        """持久化回滚历史。"""
        try:
            with open(self._history_file(), "w", encoding="utf-8") as f:
                json.dump(
                    self._rollback_history[-200:],
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
        except OSError as e:
            logger.warning("回滚历史持久化失败：%s", e)

    def _save_cooldowns(self) -> None:
        """持久化冷却期。"""
        try:
            with open(self._cooldown_file(), "w", encoding="utf-8") as f:
                json.dump(self._cooldowns, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning("冷却期持久化失败：%s", e)

    # ------------------------------------------------------------------
    # 异常检测
    # ------------------------------------------------------------------

    def detect_anomaly(
        self,
        rule_id: str,
        metrics: EffectivenessMetrics,
        samples: Optional[List[OutcomeSample]] = None,
    ) -> RollbackDecision:
        """检测规则是否存在异常需要回滚。

        检测顺序（优先级从高到低）：
            1. 硬约束违反（立即回滚）
            2. 生产异常率超限（立即降级）
            3. 指标连续恶化（累计计数，达阈值回滚）

        Args:
            rule_id: 规则 ID。
            metrics: 当前效果度量。
            samples: 触发样本列表（用于检测硬约束违反）。

        Returns:
            RollbackDecision 实例。
        """
        detected_at = datetime.now(timezone.utc).isoformat()
        metrics_snapshot = metrics.to_publisher_snapshot()

        # 优先级 1：硬约束违反
        if metrics.hard_constraint_violations > 0:
            reason = (
                f"硬约束违反 {metrics.hard_constraint_violations} 次"
                f"（CAM 绕过 / SUCCEEDED 解锁）"
            )
            logger.warning(
                "规则 %s 触发硬约束违反回滚：%s",
                rule_id,
                reason,
            )
            return RollbackDecision(
                rule_id=rule_id,
                should_rollback=True,
                reason=reason,
                severity="hard_constraint",
                detected_at=detected_at,
                metrics_snapshot=metrics_snapshot,
            )

        # 优先级 2：生产异常率超限
        if (
            metrics.error_rate > self.production_error_rate_threshold
            and metrics.sample_size > 0
        ):
            reason = (
                f"生产异常率 {metrics.error_rate:.3f} 超过阈值 "
                f"{self.production_error_rate_threshold}"
            )
            logger.warning(
                "规则 %s 触发生产异常回滚：%s", rule_id, reason
            )
            return RollbackDecision(
                rule_id=rule_id,
                should_rollback=True,
                reason=reason,
                severity="production_error",
                detected_at=detected_at,
                metrics_snapshot=metrics_snapshot,
            )

        # 优先级 3：指标连续恶化
        with self._lock:
            anomaly_count = self._consecutive_anomalies.get(rule_id, 0)
            # 指标恶化判定：准确率低于 0.5 或误报率高于 0.4
            if (
                metrics.sample_size > 0
                and metrics.accuracy < 0.5
            ) or (
                metrics.sample_size > 0
                and metrics.false_positive_rate > 0.4
            ):
                anomaly_count += 1
                self._consecutive_anomalies[rule_id] = anomaly_count
            else:
                # 指标恢复，重置计数
                if anomaly_count > 0:
                    self._consecutive_anomalies[rule_id] = 0
                    anomaly_count = 0

            if anomaly_count >= self.consecutive_anomaly_threshold:
                reason = (
                    f"连续 {anomaly_count} 次指标低于阈值"
                    f"（accuracy={metrics.accuracy:.3f}, "
                    f"fpr={metrics.false_positive_rate:.3f}）"
                )
                logger.warning(
                    "规则 %s 触发指标恶化回滚：%s", rule_id, reason
                )
                return RollbackDecision(
                    rule_id=rule_id,
                    should_rollback=True,
                    reason=reason,
                    severity="metrics_degradation",
                    detected_at=detected_at,
                    metrics_snapshot=metrics_snapshot,
                )

        # 样本不足时标记但不回滚
        if metrics.insufficient_data:
            logger.info(
                "规则 %s 样本不足（n=%d），暂不判定回滚",
                rule_id,
                metrics.sample_size,
            )

        return RollbackDecision(
            rule_id=rule_id,
            should_rollback=False,
            severity="none",
            detected_at=detected_at,
            metrics_snapshot=metrics_snapshot,
        )

    # ------------------------------------------------------------------
    # 回滚执行
    # ------------------------------------------------------------------

    def rollback_rule(
        self,
        rule_id: str,
        reason: str,
        severity: str = "manual",
        fully_deprecate: bool = False,
    ) -> RollbackExecutionResult:
        """执行规则回滚。

        回滚策略：
            - severity=hard_constraint 或 fully_deprecate=True：
              直接调用 RuleApplicator.rollback 并标记 DEPRECATED
            - 其他 severity：通过 ProgressivePublisher.demote 降级
              若已在 SHADOW 阶段，则触发 DEPRECATED

        Args:
            rule_id: 规则 ID。
            reason: 回滚原因。
            severity: 严重级别。
            fully_deprecate: 是否强制完全废弃。

        Returns:
            RollbackExecutionResult 实例。
        """
        operated_at = datetime.now(timezone.utc).isoformat()
        publisher = self._get_publisher()
        applicator = self._get_applicator()

        # 获取当前灰度阶段
        record = publisher.get_record(rule_id)
        previous_stage = (
            record.current_stage.value if record else "unknown"
        )

        rollback_result: Optional[RollbackResult] = None
        current_stage = previous_stage
        fully_deprecated = False

        # 硬约束违反或强制废弃：直接 RuleApplicator.rollback
        if severity == "hard_constraint" or fully_deprecate:
            rollback_result = applicator.rollback(rule_id)
            current_stage = PublicationStage.DEPRECATED.value
            fully_deprecated = True
            if not rollback_result.success:
                logger.error(
                    "规则 %s 硬约束回滚失败：%s",
                    rule_id,
                    rollback_result.error,
                )
        else:
            # 其他 severity：通过 ProgressivePublisher.demote 降级
            demote_result = publisher.demote(
                rule_id=rule_id,
                reason=reason,
                auto=True,
            )
            if demote_result.success:
                current_stage = demote_result.stage.value
                fully_deprecated = (
                    demote_result.stage == PublicationStage.DEPRECATED
                )
            else:
                # demote 失败：尝试直接 rollback
                logger.warning(
                    "规则 %s demote 失败，尝试直接 rollback：%s",
                    rule_id,
                    demote_result.error,
                )
                rollback_result = applicator.rollback(rule_id)
                current_stage = PublicationStage.DEPRECATED.value
                fully_deprecated = True

        # 设置冷却期
        cooldown_until = (
            datetime.now(timezone.utc) + timedelta(hours=self.cooldown_hours)
        ).isoformat()
        with self._lock:
            self._cooldowns[rule_id] = cooldown_until
            # 重置连续异常计数
            self._consecutive_anomalies[rule_id] = 0
            # 记录历史
            self._rollback_history.append({
                "rule_id": rule_id,
                "reason": reason,
                "severity": severity,
                "previous_stage": previous_stage,
                "current_stage": current_stage,
                "fully_deprecated": fully_deprecated,
                "operated_at": operated_at,
                "cooldown_until": cooldown_until,
            })
            self._save_history()
            self._save_cooldowns()

        # 写入审计日志
        try:
            self._get_audit_recorder().record_rule_application(
                rule_id=rule_id,
                rule_description=(
                    f"规则回滚：{reason}（severity={severity}）"
                ),
                validation_passed=True,
                applied=False,
                rollback_triggered=True,
            )
        except Exception as e:
            logger.error("回滚审计写入失败（不影响回滚）：%s", e)

        logger.info(
            "规则 %s 回滚完成：%s → %s（reason=%s）",
            rule_id,
            previous_stage,
            current_stage,
            reason,
        )

        return RollbackExecutionResult(
            success=True,
            rule_id=rule_id,
            previous_stage=previous_stage,
            current_stage=current_stage,
            fully_deprecated=fully_deprecated,
            rollback_result=rollback_result,
            operated_at=operated_at,
            reason=reason,
        )

    # ------------------------------------------------------------------
    # 批量监控
    # ------------------------------------------------------------------

    def monitor_and_rollback(self) -> List[RollbackExecutionResult]:
        """扫描所有灰度发布中的规则，检测异常并自动回滚。

        Returns:
            触发回滚的规则列表。
        """
        publisher = self._get_publisher()
        collector = self._get_metrics_collector()

        # 获取所有灰度发布中的规则
        publications = publisher.list_publications()
        results: List[RollbackExecutionResult] = []

        for record in publications:
            rule_id = record.rule_id

            # 跳过已废弃的规则
            if record.current_stage == PublicationStage.DEPRECATED:
                continue

            # 跳过 SHADOW 阶段（无流量，不收集指标）
            if record.current_stage == PublicationStage.SHADOW:
                continue

            # 跳过冷却期内的规则
            if self._is_in_cooldown(rule_id):
                logger.debug(
                    "规则 %s 在冷却期内，跳过检测", rule_id
                )
                continue

            # 收集指标
            try:
                metrics = collector.collect_metrics(rule_id)
            except Exception as e:
                logger.error(
                    "规则 %s 指标收集失败：%s", rule_id, e
                )
                continue

            # 检测异常
            decision = self.detect_anomaly(rule_id, metrics)
            if not decision.should_rollback:
                continue

            # 执行回滚
            result = self.rollback_rule(
                rule_id=rule_id,
                reason=decision.reason,
                severity=decision.severity,
                fully_deprecate=(decision.severity == "hard_constraint"),
            )
            results.append(result)

        if results:
            logger.info(
                "本轮监控触发了 %d 条规则回滚", len(results)
            )
        return results

    # ------------------------------------------------------------------
    # 冷却期管理
    # ------------------------------------------------------------------

    def _is_in_cooldown(self, rule_id: str) -> bool:
        """检查规则是否在冷却期内。"""
        with self._lock:
            cooldown_str = self._cooldowns.get(rule_id)
            if cooldown_str is None:
                return False
            try:
                cooldown_until = datetime.fromisoformat(cooldown_str)
                return datetime.now(timezone.utc) < cooldown_until
            except (ValueError, TypeError):
                # TypeError：旧 naive datetime 与 aware 比较时触发，
                # 视为冷却失效（兼容旧数据）
                return False

    def get_cooldown_remaining(self, rule_id: str) -> Optional[timedelta]:
        """获取规则剩余冷却时间。

        Args:
            rule_id: 规则 ID。

        Returns:
            剩余冷却时间；None 表示不在冷却期。
        """
        with self._lock:
            cooldown_str = self._cooldowns.get(rule_id)
            if cooldown_str is None:
                return None
            try:
                cooldown_until = datetime.fromisoformat(cooldown_str)
                remaining = cooldown_until - datetime.now(timezone.utc)
                return remaining if remaining.total_seconds() > 0 else None
            except (ValueError, TypeError):
                # TypeError：旧 naive datetime 与 aware 比较时触发
                return None

    def clear_cooldown(self, rule_id: str) -> bool:
        """手动清除规则冷却期（用于人工干预后重新发布）。

        Args:
            rule_id: 规则 ID。

        Returns:
            是否清除成功。
        """
        with self._lock:
            if rule_id in self._cooldowns:
                del self._cooldowns[rule_id]
                self._save_cooldowns()
                logger.info("规则 %s 冷却期已手动清除", rule_id)
                return True
            return False

    # ------------------------------------------------------------------
    # 历史查询
    # ------------------------------------------------------------------

    def get_rollback_history(
        self,
        rule_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """查询回滚历史。

        Args:
            rule_id: 过滤指定规则。None 表示全部。
            limit: 返回条数上限。

        Returns:
            回滚历史列表（按时间倒序）。
        """
        with self._lock:
            history = list(self._rollback_history)
        if rule_id is not None:
            history = [h for h in history if h.get("rule_id") == rule_id]
        history.sort(key=lambda h: h.get("operated_at", ""), reverse=True)
        return history[:limit]

    def get_consecutive_anomaly_count(self, rule_id: str) -> int:
        """获取规则当前连续异常计数。"""
        with self._lock:
            return self._consecutive_anomalies.get(rule_id, 0)

    def reset_anomaly_count(self, rule_id: str) -> None:
        """重置规则连续异常计数（用于人工确认指标恢复后）。"""
        with self._lock:
            self._consecutive_anomalies[rule_id] = 0


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------


def rollback_rule(rule_id: str, reason: str) -> RollbackExecutionResult:
    """便捷函数：执行规则回滚。"""
    manager = RollbackManager()
    return manager.rollback_rule(rule_id, reason=reason)


def monitor_and_rollback() -> List[RollbackExecutionResult]:
    """便捷函数：扫描并回滚异常规则。"""
    manager = RollbackManager()
    return manager.monitor_and_rollback()
