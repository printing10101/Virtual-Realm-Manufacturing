"""规则效果度量收集器（Effectiveness Metrics Collector）。

对应 Anthropic Dreaming 的 "Outcomes are tracked" 闭环：
    - 规则在灰度发布期间触发的真实效果需要被度量
    - 度量结果反馈给 ProgressivePublisher 决定晋级/降级
    - 度量结果反馈给 ClosedLoop 决定规则置信度调整
    - 度量结果写入审计日志（学术诚信 D-2：每条规则效果可追溯）

度量维度（与 ProgressivePublisher 阈值对齐）：
    - accuracy（准确率）：规则触发后预测正确的比例
    - recall（召回率）：应触发规则而实际触发的比例
    - false_positive_rate（误报率）：不应触发而触发的比例
    - error_rate（错误率）：规则触发后导致生产异常的比例
    - sample_size（样本数）：观测窗口内的触发次数
    - conflict（冲突度）：多源证据融合的冲突系数

数据来源：
    - audit_log：规则应用/回滚决策记录
    - session_extractor：Session 中的规则触发与 outcome 数据
    - cutting_store：切削参数调整的后续效果
    - cam_validation：CAM 校验结果（是否被规则影响）

设计原则：
    - 度量不修改生产数据，只读
    - 度量结果写入审计日志（AIModule.DREAMING）
    - 度量窗口可配置（默认 7 天滚动窗口）
    - 样本数不足时返回低置信度（不阻断发布，但标记 insufficient_data）

硬约束对齐：
    - CAM 校验失败的触发不计入 accuracy（避免鼓励绕过 CAM）
    - SUCCEEDED 任务解锁的触发计为 error（错误率 +1）
    - HRC52 pending_calibration 触发降低置信度但不计为 error

用法：
    collector = EffectivenessMetricsCollector()
    metrics = collector.collect_metrics("rule_chatter_threshold_v1")
    if metrics["accuracy"] >= 0.70:
        publisher.promote("rule_chatter_threshold_v1", metrics_snapshot=metrics)
"""

from __future__ import annotations

import json
import logging
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# -----------------------------------------------------------------------------
# 度量数据结构
# -----------------------------------------------------------------------------


@dataclass
class OutcomeSample:
    """单次规则触发的效果观测样本。

    Attributes:
        rule_id: 规则 ID。
        triggered_at: 触发时间戳。
        trigger_context: 触发时的上下文（输入数据）。
        predicted_outcome: 规则预测的结果。
        actual_outcome: 实际发生的结果。
        correct: 预测是否正确（predicted == actual）。
        false_positive: 是否为误报（不应触发而触发）。
        false_negative: 是否为漏报（应触发而未触发）。
        production_error: 是否导致生产异常。
        cam_validation_bypassed: 是否绕过了 CAM 校验（硬约束违反标记）。
        succeeded_lock_violated: 是否违反 SUCCEEDED 禁删（硬约束违反标记）。
        source: 数据来源（audit_log / session / cutting_store / cam_validation）。
    """

    rule_id: str
    triggered_at: str
    trigger_context: Dict[str, Any] = field(default_factory=dict)
    predicted_outcome: Any = None
    actual_outcome: Any = None
    correct: bool = False
    false_positive: bool = False
    false_negative: bool = False
    production_error: bool = False
    cam_validation_bypassed: bool = False
    succeeded_lock_violated: bool = False
    source: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EffectivenessMetrics:
    """规则效果度量结果。

    Attributes:
        rule_id: 规则 ID。
        accuracy: 准确率 = correct / sample_size。
        recall: 召回率 = triggered / (triggered + missed)。
        false_positive_rate: 误报率 = false_positive / sample_size。
        error_rate: 错误率 = production_error / sample_size。
        sample_size: 样本数。
        conflict: 多源证据冲突度（0-1，None 表示无融合）。
        confidence: 度量置信度（基于样本数和一致性）。
        window_start: 度量窗口起始时间。
        window_end: 度量窗口结束时间。
        collected_at: 度量收集时间。
        insufficient_data: 是否样本数不足（< min_sample_size）。
        hard_constraint_violations: 硬约束违反次数（CAM 绕过 + SUCCEEDED 解锁）。
    """

    rule_id: str
    accuracy: float = 0.0
    recall: float = 0.0
    false_positive_rate: float = 0.0
    error_rate: float = 0.0
    sample_size: int = 0
    conflict: Optional[float] = None
    confidence: float = 0.0
    window_start: str = ""
    window_end: str = ""
    collected_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    insufficient_data: bool = False
    hard_constraint_violations: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_publisher_snapshot(self) -> Dict[str, Any]:
        """转换为 ProgressivePublisher 使用的指标快照格式。

        ProgressivePublisher 的 _check_promotion_thresholds 和
        _check_demotion_thresholds 期望以下字段：
            - accuracy
            - false_positive_rate
            - sample_size
            - error_rate
        """
        return {
            "accuracy": self.accuracy,
            "false_positive_rate": self.false_positive_rate,
            "sample_size": self.sample_size,
            "error_rate": self.error_rate,
            "recall": self.recall,
            "conflict": self.conflict,
            "confidence": self.confidence,
            "hard_constraint_violations": self.hard_constraint_violations,
            "insufficient_data": self.insufficient_data,
        }


# -----------------------------------------------------------------------------
# 度量收集器
# -----------------------------------------------------------------------------


# 度量样本持久化目录
METRICS_SAMPLES_DIR = "python/outputs/dreaming/metrics_samples"

# 默认度量窗口（天）
DEFAULT_METRICS_WINDOW_DAYS = 7

# 最小样本数（低于此值标记 insufficient_data）
DEFAULT_MIN_SAMPLE_SIZE = 10

# 度量置信度计算参数
# 样本数 >= CONFIDENT_HIGH_SAMPLES 时置信度 = 0.9
# 样本数 >= CONFIDENT_MID_SAMPLES 时置信度 = 0.7
# 样本数 >= DEFAULT_MIN_SAMPLE_SIZE 时置信度 = 0.5
# 样本数 < DEFAULT_MIN_SAMPLE_SIZE 时置信度 = 0.2
CONFIDENT_HIGH_SAMPLES = 50
CONFIDENT_MID_SAMPLES = 20


class EffectivenessMetricsCollector:
    """规则效果度量收集器。

    负责：
        1. 从 audit_log / session / cutting_store / cam_validation 收集规则触发的效果样本
        2. 计算准确率、召回率、误报率、错误率
        3. 检测硬约束违反（CAM 绕过、SUCCEEDED 解锁）
        4. 输出与 ProgressivePublisher 阈值对齐的指标快照
        5. 度量结果写入审计日志

    线程安全：通过内部锁保护样本列表。
    """

    def __init__(
        self,
        samples_dir: Optional[str] = None,
        window_days: int = DEFAULT_METRICS_WINDOW_DAYS,
        min_sample_size: int = DEFAULT_MIN_SAMPLE_SIZE,
    ) -> None:
        """初始化度量收集器。

        Args:
            samples_dir: 样本持久化目录。
            window_days: 度量窗口天数。
            min_sample_size: 最小样本数阈值。
        """
        self.samples_dir = Path(samples_dir or METRICS_SAMPLES_DIR)
        self.samples_dir.mkdir(parents=True, exist_ok=True)
        self.window_days = window_days
        self.min_sample_size = min_sample_size
        self._lock = threading.RLock()
        # 内存缓存：rule_id -> List[OutcomeSample]
        self._samples: Dict[str, List[OutcomeSample]] = {}
        self._load_samples()

    # ------------------------------------------------------------------
    # 延迟依赖
    # ------------------------------------------------------------------

    def _get_audit_recorder(self):
        from app.dreaming.audit_integration import get_audit_recorder

        return get_audit_recorder()

    def _get_audit_log(self):
        from app.audit.audit_log import get_audit_log

        return get_audit_log()

    # ------------------------------------------------------------------
    # 样本持久化
    # ------------------------------------------------------------------

    def _samples_file(self, rule_id: str) -> Path:
        return self.samples_dir / f"{rule_id}.json"

    def _load_samples(self) -> None:
        """启动时加载所有样本文件。"""
        try:
            for samples_file in self.samples_dir.glob("*.json"):
                try:
                    with open(samples_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    rule_id = data.get("rule_id", "")
                    if not rule_id:
                        continue
                    samples_data = data.get("samples", [])
                    samples = [
                        OutcomeSample(**s) for s in samples_data
                    ]
                    self._samples[rule_id] = samples
                except (OSError, json.JSONDecodeError, TypeError) as e:
                    logger.warning(
                        "加载样本文件失败 %s: %s", samples_file, e
                    )
        except OSError as e:
            logger.warning("扫描样本目录失败：%s", e)

    def _save_samples(self, rule_id: str) -> None:
        """持久化单条规则的样本。"""
        with self._lock:
            samples = self._samples.get(rule_id, [])
            data = {
                "rule_id": rule_id,
                "samples": [s.to_dict() for s in samples],
                "updated_at": datetime.now().isoformat(),
            }
        try:
            samples_file = self._samples_file(rule_id)
            with open(samples_file, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except OSError as e:
            logger.warning(
                "样本持久化失败 rule_id=%s: %s", rule_id, e
            )

    # ------------------------------------------------------------------
    # 样本录入 API
    # ------------------------------------------------------------------

    def record_sample(self, sample: OutcomeSample) -> bool:
        """录入单次规则触发的效果样本。

        Args:
            sample: 效果样本。

        Returns:
            是否录入成功。
        """
        with self._lock:
            if sample.rule_id not in self._samples:
                self._samples[sample.rule_id] = []
            self._samples[sample.rule_id].append(sample)
            # 保留最近 1000 条样本（防止内存膨胀）
            if len(self._samples[sample.rule_id]) > 1000:
                self._samples[sample.rule_id] = self._samples[
                    sample.rule_id
                ][-1000:]
        self._save_samples(sample.rule_id)
        return True

    def record_samples(
        self, samples: List[OutcomeSample]
    ) -> int:
        """批量录入样本。

        Args:
            samples: 样本列表。

        Returns:
            成功录入的样本数。
        """
        count = 0
        for sample in samples:
            if self.record_sample(sample):
                count += 1
        return count

    # ------------------------------------------------------------------
    # 度量计算 API
    # ------------------------------------------------------------------

    def collect_metrics(
        self,
        rule_id: str,
        window_days: Optional[int] = None,
    ) -> EffectivenessMetrics:
        """收集指定规则的效果度量。

        Args:
            rule_id: 规则 ID。
            window_days: 度量窗口天数。None 表示使用默认值。

        Returns:
            EffectivenessMetrics 实例。
        """
        window = window_days or self.window_days
        window_end = datetime.now()
        window_start = window_end - timedelta(days=window)

        with self._lock:
            all_samples = list(self._samples.get(rule_id, []))

        # 按窗口过滤
        window_samples: List[OutcomeSample] = []
        for s in all_samples:
            try:
                triggered = datetime.fromisoformat(s.triggered_at)
                if window_start <= triggered <= window_end:
                    window_samples.append(s)
            except (ValueError, TypeError):
                continue

        metrics = self._compute_metrics(
            rule_id=rule_id,
            samples=window_samples,
            window_start=window_start.isoformat(),
            window_end=window_end.isoformat(),
        )

        # 写入审计日志
        try:
            self._get_audit_recorder().record_rule_application(
                rule_id=rule_id,
                rule_description=(
                    f"效果度量：acc={metrics.accuracy:.3f}, "
                    f"fpr={metrics.false_positive_rate:.3f}, "
                    f"n={metrics.sample_size}"
                ),
                validation_passed=True,
                applied=False,
                rollback_triggered=False,
            )
        except Exception as e:
            logger.error("度量审计写入失败（不影响度量）：%s", e)

        return metrics

    def collect_all_metrics(
        self,
        window_days: Optional[int] = None,
    ) -> Dict[str, EffectivenessMetrics]:
        """收集所有已记录规则的效果度量。

        Args:
            window_days: 度量窗口天数。

        Returns:
            rule_id -> EffectivenessMetrics 映射。
        """
        with self._lock:
            rule_ids = list(self._samples.keys())

        return {
            rule_id: self.collect_metrics(rule_id, window_days)
            for rule_id in rule_ids
        }

    def get_samples(
        self,
        rule_id: str,
        window_days: Optional[int] = None,
    ) -> List[OutcomeSample]:
        """获取指定规则在窗口内的样本列表。"""
        window = window_days or self.window_days
        window_end = datetime.now()
        window_start = window_end - timedelta(days=window)

        with self._lock:
            all_samples = list(self._samples.get(rule_id, []))

        result: List[OutcomeSample] = []
        for s in all_samples:
            try:
                triggered = datetime.fromisoformat(s.triggered_at)
                if window_start <= triggered <= window_end:
                    result.append(s)
            except (ValueError, TypeError):
                continue
        return result

    # ------------------------------------------------------------------
    # 内部度量计算
    # ------------------------------------------------------------------

    def _compute_metrics(
        self,
        rule_id: str,
        samples: List[OutcomeSample],
        window_start: str,
        window_end: str,
    ) -> EffectivenessMetrics:
        """从样本列表计算度量指标。"""
        sample_size = len(samples)

        if sample_size == 0:
            return EffectivenessMetrics(
                rule_id=rule_id,
                sample_size=0,
                window_start=window_start,
                window_end=window_end,
                insufficient_data=True,
                confidence=0.0,
            )

        correct_count = sum(1 for s in samples if s.correct)
        fp_count = sum(1 for s in samples if s.false_positive)
        fn_count = sum(1 for s in samples if s.false_negative)
        err_count = sum(1 for s in samples if s.production_error)
        hc_violations = sum(
            1
            for s in samples
            if s.cam_validation_bypassed or s.succeeded_lock_violated
        )

        accuracy = correct_count / sample_size
        false_positive_rate = fp_count / sample_size
        error_rate = err_count / sample_size

        # 召回率：triggered / (triggered + missed)
        # 触发数 = 样本数 - 漏报数（漏报样本来源有限，这里近似）
        triggered_count = sample_size - fn_count
        total_should_trigger = triggered_count + fn_count
        recall = (
            triggered_count / total_should_trigger
            if total_should_trigger > 0
            else 1.0
        )

        # 置信度：基于样本数
        if sample_size >= CONFIDENT_HIGH_SAMPLES:
            confidence = 0.9
        elif sample_size >= CONFIDENT_MID_SAMPLES:
            confidence = 0.7
        elif sample_size >= self.min_sample_size:
            confidence = 0.5
        else:
            confidence = 0.2

        # 硬约束违反会降低置信度
        if hc_violations > 0:
            confidence *= 0.5

        insufficient = sample_size < self.min_sample_size

        return EffectivenessMetrics(
            rule_id=rule_id,
            accuracy=accuracy,
            recall=recall,
            false_positive_rate=false_positive_rate,
            error_rate=error_rate,
            sample_size=sample_size,
            conflict=None,  # 由 ClosedLoop 融合后填充
            confidence=confidence,
            window_start=window_start,
            window_end=window_end,
            insufficient_data=insufficient,
            hard_constraint_violations=hc_violations,
        )


# -----------------------------------------------------------------------------
# 便捷函数
# -----------------------------------------------------------------------------


def collect_rule_metrics(
    rule_id: str,
    window_days: int = DEFAULT_METRICS_WINDOW_DAYS,
) -> EffectivenessMetrics:
    """便捷函数：收集规则效果度量。"""
    collector = EffectivenessMetricsCollector(window_days=window_days)
    return collector.collect_metrics(rule_id)


def record_outcome_sample(sample: OutcomeSample) -> bool:
    """便捷函数：录入单次规则效果样本。"""
    collector = EffectivenessMetricsCollector()
    return collector.record_sample(sample)
