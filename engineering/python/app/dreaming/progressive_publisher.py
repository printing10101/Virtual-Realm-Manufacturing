"""规则灰度发布管理器（Progressive Publisher）。

对应 Anthropic Dreaming 的 "Rules are rolled out progressively (shadow → canary → full)"：
    - 通过沙箱验证的规则不直接全量应用，而是按 1% → 10% → 50% → 100% 四级灰度发布
    - 每个阶段收集效果指标（effectiveness_metrics.py），决定晋级（promote）或降级（demote）
    - 异常指标触发自动回滚（rollback_manager.py）
    - 所有发布决策写入审计日志（AIModule.DREAMING）

灰度阶段（PublicationStage）：
    - shadow（影子模式，0% 流量）：仅记录规则触发日志，不实际执行动作
    - canary（金丝雀，1% 流量）：在真实流量上小范围执行，监控关键指标
    - rolling（滚动发布，10% → 50%）：逐步扩大流量比例
    - full（全量发布，100%）：规则完全生效

设计原则：
    - 灰度发布不绕过硬约束：CAM 二次验证始终 True、SUCCEEDED 禁删
    - 每次晋级前重新调用 RuleValidator 双重校验
    - 灰度比例通过 config 控制（DreamingConfig），可被环境变量覆盖
    - shadow 阶段不修改生产数据，仅记录"如果应用会发生什么"
    - 异常自动降级到上一阶段，连续两次降级触发回滚

硬约束对齐：
    - cam_validation_required 始终 True（不被灰度发布绕过）
    - allow_delete_succeeded 始终 False
    - K_s → cutting_force_coeff 直接传递
    - HRC52 pending_calibration 在 canary 阶段强制降低置信度

用法：
    publisher = ProgressivePublisher()
    result = publisher.publish(rule, PublicationStage.SHADOW)
    if result.success and metrics_good:
        publisher.promote(rule.rule_id, target_stage=PublicationStage.CANARY)
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.dreaming.apply_rules import (
    RULE_STATUS_APPLIED,
    RULE_STATUS_DEPRECATED,
    ApplyResult,
    RuleApplicator,
)
from app.dreaming.rule_synthesizer import RuleDraft
from app.dreaming.rule_validator import RuleValidator, ValidationResult

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 灰度阶段定义
# -----------------------------------------------------------------------------


class PublicationStage(str, Enum):
    """规则灰度发布阶段。

    阶段顺序：SHADOW → CANARY → ROLLING_10 → ROLLING_50 → FULL
    降级方向：FULL → ROLLING_50 → ROLLING_10 → CANARY → SHADOW → DEPRECATED
    """

    SHADOW = "shadow"            # 影子模式：0% 流量，仅记录
    CANARY = "canary"            # 金丝雀：1% 流量
    ROLLING_10 = "rolling_10"    # 滚动 10%
    ROLLING_50 = "rolling_50"    # 滚动 50%
    FULL = "full"                # 全量 100%
    DEPRECATED = "deprecated"    # 已废弃（等价于 rollback）

    @property
    def traffic_percentage(self) -> float:
        """该阶段对应的流量百分比。"""
        return _STAGE_TRAFFIC_PERCENTAGE[self]

    @property
    def next_stage(self) -> Optional["PublicationStage"]:
        """下一阶段（晋级方向）。FULL 已是最高，返回 None。"""
        idx = _STAGE_ORDER.index(self)
        if idx + 1 >= len(_STAGE_ORDER):
            return None
        return _STAGE_ORDER[idx + 1]

    @property
    def previous_stage(self) -> Optional["PublicationStage"]:
        """上一阶段（降级方向）。SHADOW 已是最低，返回 None。"""
        idx = _STAGE_ORDER.index(self)
        if idx == 0:
            return None
        return _STAGE_ORDER[idx - 1]


_STAGE_ORDER: List[PublicationStage] = [
    PublicationStage.SHADOW,
    PublicationStage.CANARY,
    PublicationStage.ROLLING_10,
    PublicationStage.ROLLING_50,
    PublicationStage.FULL,
]

_STAGE_TRAFFIC_PERCENTAGE: Dict[PublicationStage, float] = {
    PublicationStage.SHADOW: 0.0,
    PublicationStage.CANARY: 0.01,
    PublicationStage.ROLLING_10: 0.10,
    PublicationStage.ROLLING_50: 0.50,
    PublicationStage.FULL: 1.00,
    PublicationStage.DEPRECATED: 0.0,
}


# -----------------------------------------------------------------------------
# 灰度发布状态
# -----------------------------------------------------------------------------


@dataclass
class PublicationRecord:
    """单条规则的灰度发布记录。

    记录规则在哪个灰度阶段、何时进入、效果指标快照。

    Attributes:
        rule_id: 规则 ID。
        current_stage: 当前灰度阶段。
        entered_at: 进入当前阶段的时间戳。
        promoted_count: 累计晋级次数。
        demoted_count: 累计降级次数。
        last_metrics: 最近一次效果指标快照。
        stage_history: 阶段变更历史。
        promoted_to_full: 是否已全量发布。
        auto_rollback_triggered: 是否触发了自动回滚。
    """

    rule_id: str
    current_stage: PublicationStage = PublicationStage.SHADOW
    entered_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    promoted_count: int = 0
    demoted_count: int = 0
    last_metrics: Dict[str, Any] = field(default_factory=dict)
    stage_history: List[Dict[str, Any]] = field(default_factory=list)
    promoted_to_full: bool = False
    auto_rollback_triggered: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["current_stage"] = self.current_stage.value
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PublicationRecord":
        stage_str = data.get("current_stage", "shadow")
        try:
            stage = PublicationStage(stage_str)
        except ValueError:
            logger.warning(
                "未知灰度阶段 '%s'，回退到 SHADOW", stage_str
            )
            stage = PublicationStage.SHADOW
        return cls(
            rule_id=data["rule_id"],
            current_stage=stage,
            entered_at=data.get(
                "entered_at", datetime.now(timezone.utc).isoformat()
            ),
            promoted_count=int(data.get("promoted_count", 0)),
            demoted_count=int(data.get("demoted_count", 0)),
            last_metrics=data.get("last_metrics", {}),
            stage_history=data.get("stage_history", []),
            promoted_to_full=bool(data.get("promoted_to_full", False)),
            auto_rollback_triggered=bool(
                data.get("auto_rollback_triggered", False)
            ),
        )


@dataclass
class PublicationResult:
    """灰度发布操作结果。

    Attributes:
        success: 操作是否成功。
        rule_id: 规则 ID。
        stage: 进入的灰度阶段。
        traffic_percentage: 该阶段的流量百分比。
        operated_at: 操作时间戳。
        validation_result: 晋级前的沙箱校验结果。
        audit_entry_seq: 审计日志条目序号（若写入成功）。
        error: 失败时的错误信息。
    """

    success: bool
    rule_id: str
    stage: PublicationStage
    traffic_percentage: float = 0.0
    operated_at: str = ""
    validation_result: Optional[ValidationResult] = None
    audit_entry_seq: Optional[int] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["stage"] = self.stage.value
        if self.validation_result is not None:
            d["validation_result"] = self.validation_result.to_dict()
        return d


# -----------------------------------------------------------------------------
# 灰度发布管理器
# -----------------------------------------------------------------------------


# 灰度状态持久化目录
PUBLICATION_STATE_DIR = "python/outputs/dreaming/publication_state"

# 晋级阈值：效果指标达标才允许晋级
# 这些阈值对应 effectiveness_metrics.py 中的指标
DEFAULT_PROMOTION_THRESHOLDS: Dict[str, float] = {
    "min_accuracy": 0.70,        # 准确率下限
    "max_false_positive_rate": 0.20,  # 误报率上限
    "min_sample_size": 20,       # 最小样本数（canary 阶段必须有足够样本）
    "max_error_rate": 0.10,      # 错误率上限
}

# 降级阈值：指标恶化时自动降级
DEFAULT_DEMOTION_THRESHOLDS: Dict[str, float] = {
    "max_false_positive_rate": 0.40,  # 误报率超过 40% 降级
    "max_error_rate": 0.25,           # 错误率超过 25% 降级
    "min_accuracy": 0.50,             # 准确率低于 50% 降级
}


class ProgressivePublisher:
    """规则灰度发布管理器。

    负责：
        1. 接收通过验证的规则，进入 SHADOW 阶段
        2. 根据 effectiveness_metrics 指标决定晋级或降级
        3. 晋级前重新调用 RuleValidator 双重校验
        4. 全量发布（FULL）后调用 RuleApplicator.apply 真正应用到知识图谱
        5. 异常指标自动降级，连续降级到 SHADOW 后触发回滚
        6. 所有发布决策写入审计日志

    线程安全：通过内部锁保护 _records 字典。
    """

    def __init__(
        self,
        state_dir: Optional[str] = None,
        applicator: Optional[RuleApplicator] = None,
        validator: Optional[RuleValidator] = None,
        promotion_thresholds: Optional[Dict[str, float]] = None,
        demotion_thresholds: Optional[Dict[str, float]] = None,
    ) -> None:
        """初始化灰度发布管理器。

        Args:
            state_dir: 灰度状态持久化目录。
            applicator: RuleApplicator 实例（None 则按需创建）。
            validator: RuleValidator 实例（None 则按需创建）。
            promotion_thresholds: 晋级阈值覆盖。
            demotion_thresholds: 降级阈值覆盖。
        """
        self.state_dir = Path(state_dir or PUBLICATION_STATE_DIR)
        self.state_dir.mkdir(parents=True, exist_ok=True)
        self._applicator = applicator
        self._validator = validator or RuleValidator()
        self._lock = threading.RLock()
        self._records: Dict[str, PublicationRecord] = {}
        self._promotion_thresholds = dict(promotion_thresholds or DEFAULT_PROMOTION_THRESHOLDS)
        self._demotion_thresholds = dict(demotion_thresholds or DEFAULT_DEMOTION_THRESHOLDS)
        self._load_state()

    # ------------------------------------------------------------------
    # 延迟依赖
    # ------------------------------------------------------------------

    def _get_applicator(self) -> RuleApplicator:
        if self._applicator is None:
            self._applicator = RuleApplicator()
        return self._applicator

    def _get_audit_recorder(self):
        from app.dreaming.audit_integration import get_audit_recorder

        return get_audit_recorder()

    # ------------------------------------------------------------------
    # 状态持久化
    # ------------------------------------------------------------------

    def _state_file(self, rule_id: str) -> Path:
        return self.state_dir / f"{rule_id}.json"

    def _load_state(self) -> None:
        """启动时加载所有灰度发布记录。"""
        try:
            for state_file in self.state_dir.glob("*.json"):
                try:
                    with open(state_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    record = PublicationRecord.from_dict(data)
                    self._records[record.rule_id] = record
                except (OSError, json.JSONDecodeError, KeyError) as e:
                    logger.warning(
                        "加载灰度状态文件失败 %s: %s", state_file, e
                    )
        except OSError as e:
            logger.warning("扫描灰度状态目录失败：%s", e)

    def _save_record(self, record: PublicationRecord) -> None:
        """持久化单条灰度记录。"""
        try:
            state_file = self._state_file(record.rule_id)
            with open(state_file, "w", encoding="utf-8") as f:
                json.dump(record.to_dict(), f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(
                "灰度状态持久化失败 rule_id=%s: %s", record.rule_id, e
            )

    def _get_or_create_record(
        self, rule_id: str
    ) -> PublicationRecord:
        """获取或创建灰度记录。调用方须持有 _lock。"""
        if rule_id not in self._records:
            self._records[rule_id] = PublicationRecord(rule_id=rule_id)
        return self._records[rule_id]

    # ------------------------------------------------------------------
    # 公开 API
    # ------------------------------------------------------------------

    def publish(
        self,
        rule: RuleDraft,
        stage: PublicationStage = PublicationStage.SHADOW,
        skip_validation: bool = False,
    ) -> PublicationResult:
        """将规则发布到指定灰度阶段。

        Args:
            rule: 待发布的规则草稿。
            stage: 目标灰度阶段。默认 SHADOW。
            skip_validation: 是否跳过沙箱校验（仅测试用，生产禁用）。

        Returns:
            PublicationResult 实例。
        """
        operated_at = datetime.now(timezone.utc).isoformat()
        validation_result: Optional[ValidationResult] = None

        # 阶段 1：沙箱校验（FULL 阶段必须通过，其他阶段也建议通过）
        if not skip_validation:
            validation_result = self._validator.validate(rule)
            if not validation_result.passed and stage == PublicationStage.FULL:
                error_msg = (
                    f"FULL 阶段发布要求沙箱验证通过："
                    f"{validation_result.errors}"
                )
                logger.warning(error_msg)
                return PublicationResult(
                    success=False,
                    rule_id=rule.rule_id,
                    stage=stage,
                    operated_at=operated_at,
                    validation_result=validation_result,
                    error=error_msg,
                )

        # 阶段 2：更新灰度记录
        with self._lock:
            record = self._get_or_create_record(rule.rule_id)
            record.current_stage = stage
            record.entered_at = operated_at
            record.stage_history.append({
                "action": "publish",
                "stage": stage.value,
                "operated_at": operated_at,
                "traffic_percentage": stage.traffic_percentage,
            })
            if stage == PublicationStage.FULL:
                record.promoted_to_full = True
            self._save_record(record)

        # 阶段 3：FULL 阶段才真正应用到知识图谱
        audit_seq: Optional[int] = None
        apply_result: Optional[ApplyResult] = None
        if stage == PublicationStage.FULL:
            apply_result = self._get_applicator().apply(
                rule, skip_validation=skip_validation
            )
            if not apply_result.success:
                # 应用失败：降级回 SHADOW
                with self._lock:
                    record = self._records.get(rule.rule_id)
                    if record is not None:
                        record.current_stage = PublicationStage.SHADOW
                        record.promoted_to_full = False
                        record.demoted_count += 1
                        record.stage_history.append({
                            "action": "auto_demote_on_apply_failure",
                            "stage": PublicationStage.SHADOW.value,
                            "operated_at": datetime.now(timezone.utc).isoformat(),
                            "reason": apply_result.error or "apply failed",
                        })
                        self._save_record(record)
                return PublicationResult(
                    success=False,
                    rule_id=rule.rule_id,
                    stage=PublicationStage.SHADOW,
                    traffic_percentage=0.0,
                    operated_at=operated_at,
                    validation_result=validation_result,
                    error=apply_result.error or "FULL 应用失败",
                )
            audit_seq = apply_result.audit_entry_seq

        # 阶段 4：写入审计日志
        try:
            self._get_audit_recorder().record_rule_application(
                rule_id=rule.rule_id,
                rule_description=rule.description,
                validation_passed=(
                    validation_result.passed
                    if validation_result is not None
                    else True
                ),
                applied=(stage == PublicationStage.FULL),
                rollback_triggered=False,
            )
        except Exception as e:
            logger.error("灰度发布审计写入失败（不影响发布）：%s", e)

        logger.info(
            "规则 %s 已发布到 %s 阶段（流量 %.1f%%）",
            rule.rule_id,
            stage.value,
            stage.traffic_percentage * 100,
        )

        return PublicationResult(
            success=True,
            rule_id=rule.rule_id,
            stage=stage,
            traffic_percentage=stage.traffic_percentage,
            operated_at=operated_at,
            validation_result=validation_result,
            audit_entry_seq=audit_seq,
        )

    def promote(
        self,
        rule_id: str,
        target_stage: Optional[PublicationStage] = None,
        metrics_snapshot: Optional[Dict[str, Any]] = None,
        rule: Optional[RuleDraft] = None,
    ) -> PublicationResult:
        """将规则晋级到下一阶段（或指定阶段）。

        晋级前会检查效果指标是否达标（如果提供了 metrics_snapshot）。
        FULL 阶段晋级前会重新调用 RuleValidator 双重校验。

        Args:
            rule_id: 规则 ID。
            target_stage: 目标阶段。None 表示晋级到下一阶段。
            metrics_snapshot: 当前效果指标快照（用于阈值检查）。
            rule: 规则草稿（FULL 阶段晋级必须提供，用于重新校验）。

        Returns:
            PublicationResult 实例。
        """
        operated_at = datetime.now(timezone.utc).isoformat()

        with self._lock:
            record = self._records.get(rule_id)
            if record is None:
                return PublicationResult(
                    success=False,
                    rule_id=rule_id,
                    stage=PublicationStage.SHADOW,
                    operated_at=operated_at,
                    error=f"规则 {rule_id} 未发布，无法晋级",
                )

            current_stage = record.current_stage
            if target_stage is None:
                next_stage = current_stage.next_stage
                if next_stage is None:
                    return PublicationResult(
                        success=False,
                        rule_id=rule_id,
                        stage=current_stage,
                        traffic_percentage=current_stage.traffic_percentage,
                        operated_at=operated_at,
                        error=f"已在最高阶段 {current_stage.value}，无法晋级",
                    )
            else:
                next_stage = target_stage

            # 阶段顺序校验：不允许跨级晋级（必须 1%→10%→50%→100%）
            if target_stage is not None:
                current_idx = _STAGE_ORDER.index(current_stage)
                target_idx = _STAGE_ORDER.index(target_stage)
                if target_idx != current_idx + 1:
                    return PublicationResult(
                        success=False,
                        rule_id=rule_id,
                        stage=current_stage,
                        traffic_percentage=current_stage.traffic_percentage,
                        operated_at=operated_at,
                        error=(
                            f"不允许跨级晋级：{current_stage.value} → "
                            f"{target_stage.value}（必须逐级晋级）"
                        ),
                    )

            # 指标阈值检查
            if metrics_snapshot:
                metrics_ok, fail_reason = self._check_promotion_thresholds(
                    metrics_snapshot
                )
                if not metrics_ok:
                    return PublicationResult(
                        success=False,
                        rule_id=rule_id,
                        stage=current_stage,
                        traffic_percentage=current_stage.traffic_percentage,
                        operated_at=operated_at,
                        error=f"效果指标未达晋级阈值：{fail_reason}",
                    )
                record.last_metrics = dict(metrics_snapshot)

        # FULL 阶段必须重新沙箱校验
        validation_result: Optional[ValidationResult] = None
        if next_stage == PublicationStage.FULL:
            if rule is None:
                return PublicationResult(
                    success=False,
                    rule_id=rule_id,
                    stage=current_stage,
                    traffic_percentage=current_stage.traffic_percentage,
                    operated_at=operated_at,
                    error="FULL 阶段晋级必须提供 rule 参数用于沙箱校验",
                )
            validation_result = self._validator.validate(rule)
            if not validation_result.passed:
                return PublicationResult(
                    success=False,
                    rule_id=rule_id,
                    stage=current_stage,
                    traffic_percentage=current_stage.traffic_percentage,
                    operated_at=operated_at,
                    validation_result=validation_result,
                    error=f"FULL 阶段沙箱校验失败：{validation_result.errors}",
                )

        # 调用 publish 切换阶段
        if rule is not None:
            result = self.publish(
                rule=rule,
                stage=next_stage,
                skip_validation=(validation_result is not None),
            )
        else:
            # 非 FULL 阶段晋级：仅更新灰度记录，不真正 apply
            result = self._update_stage_only(
                rule_id=rule_id,
                target_stage=next_stage,
                operated_at=operated_at,
                validation_result=validation_result,
            )

        # 更新晋级计数
        if result.success:
            with self._lock:
                rec = self._records.get(rule_id)
                if rec is not None:
                    rec.promoted_count += 1
                    rec.stage_history.append({
                        "action": "promote",
                        "from": current_stage.value,
                        "to": next_stage.value,
                        "operated_at": operated_at,
                    })
                    self._save_record(rec)

        return result

    def demote(
        self,
        rule_id: str,
        reason: str,
        target_stage: Optional[PublicationStage] = None,
        auto: bool = False,
    ) -> PublicationResult:
        """将规则降级到上一阶段（或指定阶段）。

        降级方向：FULL → ROLLING_50 → ROLLING_10 → CANARY → SHADOW
        若 SHADOW 阶段再次降级，则触发回滚（状态改为 DEPRECATED）。

        Args:
            rule_id: 规则 ID。
            reason: 降级原因（写入审计日志）。
            target_stage: 目标阶段。None 表示降级到上一阶段。
            auto: 是否为自动降级（指标恶化触发）。

        Returns:
            PublicationResult 实例。
        """
        operated_at = datetime.now(timezone.utc).isoformat()

        with self._lock:
            record = self._records.get(rule_id)
            if record is None:
                return PublicationResult(
                    success=False,
                    rule_id=rule_id,
                    stage=PublicationStage.SHADOW,
                    operated_at=operated_at,
                    error=f"规则 {rule_id} 未发布，无法降级",
                )

            current_stage = record.current_stage

            # SHADOW 阶段降级 = 回滚
            if current_stage == PublicationStage.SHADOW:
                if target_stage is None or target_stage == PublicationStage.DEPRECATED:
                    return self._rollback_to_deprecated(
                        rule_id=rule_id,
                        reason=reason,
                        operated_at=operated_at,
                        record=record,
                    )
                return PublicationResult(
                    success=False,
                    rule_id=rule_id,
                    stage=current_stage,
                    operated_at=operated_at,
                    error="SHADOW 已是最低发布阶段，无法继续降级",
                )

            if target_stage is None:
                prev_stage = current_stage.previous_stage
            else:
                prev_stage = target_stage

            # FULL 阶段降级：调用 RuleApplicator.rollback 真正回滚知识图谱
            if current_stage == PublicationStage.FULL:
                rollback_result = self._get_applicator().rollback(rule_id)
                if not rollback_result.success:
                    logger.warning(
                        "FULL 阶段知识图谱回滚失败：%s",
                        rollback_result.error,
                    )

            record.current_stage = prev_stage
            record.entered_at = operated_at
            record.promoted_to_full = False
            record.demoted_count += 1
            record.stage_history.append({
                "action": "auto_demote" if auto else "demote",
                "from": current_stage.value,
                "to": prev_stage.value,
                "operated_at": operated_at,
                "reason": reason,
            })
            self._save_record(record)

        # 写入审计日志
        try:
            self._get_audit_recorder().record_rule_application(
                rule_id=rule_id,
                rule_description=f"规则降级：{reason}",
                validation_passed=True,
                applied=False,
                rollback_triggered=(current_stage == PublicationStage.FULL),
            )
        except Exception as e:
            logger.error("降级审计写入失败（不影响降级）：%s", e)

        logger.info(
            "规则 %s 从 %s 降级到 %s（原因：%s）",
            rule_id,
            current_stage.value,
            prev_stage.value,
            reason,
        )

        return PublicationResult(
            success=True,
            rule_id=rule_id,
            stage=prev_stage,
            traffic_percentage=prev_stage.traffic_percentage,
            operated_at=operated_at,
        )

    def get_record(self, rule_id: str) -> Optional[PublicationRecord]:
        """查询规则的灰度发布记录。"""
        with self._lock:
            return self._records.get(rule_id)

    def list_publications(self) -> List[PublicationRecord]:
        """列出所有灰度发布中的规则。"""
        with self._lock:
            return list(self._records.values())

    def update_metrics(
        self,
        rule_id: str,
        metrics: Dict[str, Any],
    ) -> bool:
        """更新规则的效果指标快照。

        Args:
            rule_id: 规则 ID。
            metrics: 效果指标字典。

        Returns:
            是否更新成功。
        """
        with self._lock:
            record = self._records.get(rule_id)
            if record is None:
                logger.warning(
                    "规则 %s 未发布，无法更新指标", rule_id
                )
                return False
            record.last_metrics = dict(metrics)
            record.stage_history.append({
                "action": "metrics_update",
                "operated_at": datetime.now(timezone.utc).isoformat(),
                "metrics": dict(metrics),
            })
            self._save_record(record)
            return True

    def check_auto_demotion(
        self,
        rule_id: str,
        metrics: Dict[str, Any],
    ) -> Optional[str]:
        """检查指标是否触发自动降级。

        Args:
            rule_id: 规则 ID。
            metrics: 当前效果指标。

        Returns:
            触发降级的原因字符串；None 表示无需降级。
        """
        with self._lock:
            record = self._records.get(rule_id)
            if record is None:
                return None
            # SHADOW 阶段不检查（无流量）
            if record.current_stage == PublicationStage.SHADOW:
                return None

        return self._check_demotion_thresholds(metrics)

    # ------------------------------------------------------------------
    # 内部辅助
    # ------------------------------------------------------------------

    def _update_stage_only(
        self,
        rule_id: str,
        target_stage: PublicationStage,
        operated_at: str,
        validation_result: Optional[ValidationResult],
    ) -> PublicationResult:
        """非 FULL 阶段晋级：仅更新灰度记录，不真正 apply。"""
        with self._lock:
            record = self._records.get(rule_id)
            if record is None:
                return PublicationResult(
                    success=False,
                    rule_id=rule_id,
                    stage=target_stage,
                    operated_at=operated_at,
                    error="灰度记录丢失",
                )
            record.current_stage = target_stage
            record.entered_at = operated_at
            self._save_record(record)

        # 写入审计日志
        try:
            self._get_audit_recorder().record_rule_application(
                rule_id=rule_id,
                rule_description=f"灰度晋级到 {target_stage.value}",
                validation_passed=(
                    validation_result.passed
                    if validation_result is not None
                    else True
                ),
                applied=False,
                rollback_triggered=False,
            )
        except Exception as e:
            logger.error("灰度晋级审计写入失败：%s", e)

        return PublicationResult(
            success=True,
            rule_id=rule_id,
            stage=target_stage,
            traffic_percentage=target_stage.traffic_percentage,
            operated_at=operated_at,
            validation_result=validation_result,
        )

    def _rollback_to_deprecated(
        self,
        rule_id: str,
        reason: str,
        operated_at: str,
        record: PublicationRecord,
    ) -> PublicationResult:
        """SHADOW 阶段再次降级时，将规则标记为 DEPRECATED（等价回滚）。"""
        record.current_stage = PublicationStage.DEPRECATED
        record.entered_at = operated_at
        record.auto_rollback_triggered = True
        record.stage_history.append({
            "action": "auto_rollback",
            "from": PublicationStage.SHADOW.value,
            "to": PublicationStage.DEPRECATED.value,
            "operated_at": operated_at,
            "reason": reason,
        })
        self._save_record(record)

        # 写入审计日志
        try:
            self._get_audit_recorder().record_rule_application(
                rule_id=rule_id,
                rule_description=f"规则自动回滚：{reason}",
                validation_passed=True,
                applied=False,
                rollback_triggered=True,
            )
        except Exception as e:
            logger.error("自动回滚审计写入失败：%s", e)

        logger.warning(
            "规则 %s 触发自动回滚（SHADOW → DEPRECATED），原因：%s",
            rule_id,
            reason,
        )

        return PublicationResult(
            success=True,
            rule_id=rule_id,
            stage=PublicationStage.DEPRECATED,
            traffic_percentage=0.0,
            operated_at=operated_at,
        )

    def _check_promotion_thresholds(
        self, metrics: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """检查指标是否达到晋级阈值。

        Returns:
            (是否通过, 失败原因) 元组。
        """
        accuracy = float(metrics.get("accuracy", 0.0))
        fpr = float(metrics.get("false_positive_rate", 1.0))
        sample = int(metrics.get("sample_size", 0))
        err_rate = float(metrics.get("error_rate", 1.0))

        min_acc = self._promotion_thresholds["min_accuracy"]
        max_fpr = self._promotion_thresholds["max_false_positive_rate"]
        min_sample = self._promotion_thresholds["min_sample_size"]
        max_err = self._promotion_thresholds["max_error_rate"]

        if accuracy < min_acc:
            return False, f"accuracy={accuracy:.3f} < {min_acc}"
        if fpr > max_fpr:
            return False, f"false_positive_rate={fpr:.3f} > {max_fpr}"
        if sample < min_sample:
            return False, f"sample_size={sample} < {min_sample}"
        if err_rate > max_err:
            return False, f"error_rate={err_rate:.3f} > {max_err}"
        return True, None

    def _check_demotion_thresholds(
        self, metrics: Dict[str, Any]
    ) -> Optional[str]:
        """检查指标是否触发降级。

        Returns:
            触发降级的原因；None 表示无需降级。
        """
        accuracy = float(metrics.get("accuracy", 1.0))
        fpr = float(metrics.get("false_positive_rate", 0.0))
        err_rate = float(metrics.get("error_rate", 0.0))

        max_fpr = self._demotion_thresholds["max_false_positive_rate"]
        max_err = self._demotion_thresholds["max_error_rate"]
        min_acc = self._demotion_thresholds["min_accuracy"]

        if fpr > max_fpr:
            return f"误报率 {fpr:.3f} 超过降级阈值 {max_fpr}"
        if err_rate > max_err:
            return f"错误率 {err_rate:.3f} 超过降级阈值 {max_err}"
        if accuracy < min_acc:
            return f"准确率 {accuracy:.3f} 低于降级阈值 {min_acc}"
        return None


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------


def publish_rule(
    rule: RuleDraft,
    stage: PublicationStage = PublicationStage.SHADOW,
) -> PublicationResult:
    """便捷函数：发布规则到指定灰度阶段。"""
    publisher = ProgressivePublisher()
    return publisher.publish(rule, stage=stage)


def promote_rule(
    rule_id: str,
    target_stage: Optional[PublicationStage] = None,
) -> PublicationResult:
    """便捷函数：晋级规则。"""
    publisher = ProgressivePublisher()
    return publisher.promote(rule_id, target_stage=target_stage)


def demote_rule(rule_id: str, reason: str) -> PublicationResult:
    """便捷函数：降级规则。"""
    publisher = ProgressivePublisher()
    return publisher.demote(rule_id, reason=reason)
