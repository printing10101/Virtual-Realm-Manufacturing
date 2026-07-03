"""飞轮指标计算与报告生成模块。

实现飞轮核心指标的计算：
- 加工记录数：系统处理的数据记录总量
- 模型质量：模型预测准确率
- 用户采纳率：用户接受模型建议的比例
- 不确定性均值：模型预测不确定性的平均值
- 回灌延迟：数据从产生到反馈回系统的时间
"""

from __future__ import annotations

import datetime
import json
import logging
import threading
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class FlywheelMetrics:
    """飞轮指标数据类。"""
    data_volume: int  # 加工记录数
    model_quality: float  # 模型质量(%)
    adoption_rate: float  # 用户采纳率(%)
    uncertainty_mean: float  # 不确定性均值(0-1)
    feedback_delay: float  # 回灌延迟(分钟)
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()

    def to_dict(self) -> dict[str, Any]:
        """转换为字典格式。"""
        return asdict(self)


class FlywheelMetricsCollector:
    """飞轮指标采集器。"""

    def __init__(self, data_source: Any = None):
        """初始化采集器。

        Args:
            data_source: 数据源（数据库连接、API客户端等）
        """
        self.data_source = data_source
        self._cache: dict[str, FlywheelMetrics] = {}

    def collect_current_metrics(self) -> FlywheelMetrics:
        """采集当前飞轮指标。"""
        # 这里应该从实际数据源采集数据
        # 由于这是演示实现，我们返回模拟数据
        metrics = FlywheelMetrics(
            data_volume=self._get_data_volume(),
            model_quality=self._get_model_quality(),
            adoption_rate=self._get_adoption_rate(),
            uncertainty_mean=self._get_uncertainty_mean(),
            feedback_delay=self._get_feedback_delay(),
        )

        # 缓存当前指标
        self._cache[metrics.timestamp] = metrics
        return metrics

    def _get_data_volume(self) -> int:
        """获取加工记录数。"""
        # 实际实现应该查询数据库
        # 例如：SELECT COUNT(*) FROM machining_records
        return 1250

    def _get_model_quality(self) -> float:
        """获取模型质量（准确率%）。"""
        # 实际实现应该计算模型预测准确率
        # 例如：正确预测数 / 总预测数 * 100
        return 87.5

    def _get_adoption_rate(self) -> float:
        """获取用户采纳率(%)。"""
        # 实际实现应该统计用户接受模型建议的比例
        # 例如：采纳建议次数 / 总建议次数 * 100
        return 72.3

    def _get_uncertainty_mean(self) -> float:
        """获取不确定性均值(0-1)。"""
        # 实际实现应该计算模型预测不确定性的平均值
        # 例如：AVG(uncertainty_score) FROM predictions
        return 0.23

    def _get_feedback_delay(self) -> float:
        """获取回灌延迟(分钟)。"""
        # 实际实现应该计算数据从产生到反馈回系统的平均时间
        # 例如：AVG(feedback_time - data_time) FROM feedback_loop
        return 45.2

    def get_historical_metrics(self, days: int = 7) -> list[FlywheelMetrics]:
        """获取历史指标数据。

        Args:
            days: 查询天数范围

        Returns:
            历史指标列表
        """
        # 实际实现应该从数据库或时序数据库查询历史数据
        # 这里返回模拟数据
        historical = []
        now = datetime.datetime.now(datetime.timezone.utc)

        for i in range(days):
            timestamp = (now - datetime.timedelta(days=i)).isoformat()
            metrics = FlywheelMetrics(
                data_volume=1250 - i * 10,
                model_quality=87.5 - i * 0.2,
                adoption_rate=72.3 - i * 0.5,
                uncertainty_mean=0.23 + i * 0.01,
                feedback_delay=45.2 + i * 2,
                timestamp=timestamp,
            )
            historical.append(metrics)

        return historical

    def generate_weekly_report(self) -> dict[str, Any]:
        """生成每周飞轮报告。

        Returns:
            包含周度数据和趋势分析的字典
        """
        current = self.collect_current_metrics()
        historical = self.get_historical_metrics(days=7)

        # 计算趋势
        trends = self._calculate_trends(historical)

        report = {
            "report_type": "weekly",
            "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "period": {
                "start": historical[-1].timestamp if historical else current.timestamp,
                "end": current.timestamp,
            },
            "current_metrics": current.to_dict(),
            "historical_metrics": [m.to_dict() for m in historical],
            "trends": trends,
            "summary": self._generate_summary(current, trends),
        }

        return report

    def _calculate_trends(self, historical: list[FlywheelMetrics]) -> dict[str, Any]:
        """计算指标趋势。"""
        if len(historical) < 2:
            return {}

        latest = historical[0]
        oldest = historical[-1]

        return {
            "data_volume": {
                "current": latest.data_volume,
                "change": latest.data_volume - oldest.data_volume,
                "change_percent": ((latest.data_volume - oldest.data_volume) / oldest.data_volume * 100)
                if oldest.data_volume > 0 else 0,
            },
            "model_quality": {
                "current": latest.model_quality,
                "change": round(latest.model_quality - oldest.model_quality, 2),
                "change_percent": round(
                    (latest.model_quality - oldest.model_quality) / oldest.model_quality * 100, 2
                ) if oldest.model_quality > 0 else 0,
            },
            "adoption_rate": {
                "current": latest.adoption_rate,
                "change": round(latest.adoption_rate - oldest.adoption_rate, 2),
                "change_percent": round(
                    (latest.adoption_rate - oldest.adoption_rate) / oldest.adoption_rate * 100, 2
                ) if oldest.adoption_rate > 0 else 0,
            },
            "uncertainty_mean": {
                "current": latest.uncertainty_mean,
                "change": round(latest.uncertainty_mean - oldest.uncertainty_mean, 3),
                "trend": "improving" if latest.uncertainty_mean < oldest.uncertainty_mean else "degrading",
            },
            "feedback_delay": {
                "current": latest.feedback_delay,
                "change": round(latest.feedback_delay - oldest.feedback_delay, 2),
                "trend": "improving" if latest.feedback_delay < oldest.feedback_delay else "degrading",
            },
        }

    def _generate_summary(
        self, current: FlywheelMetrics, trends: dict[str, Any]
    ) -> dict[str, Any]:
        """生成报告摘要。"""
        # 评估整体健康状态
        health_score = self._calculate_health_score(current, trends)

        return {
            "health_score": round(health_score, 1),
            "health_status": self._get_health_status(health_score),
            "highlights": self._generate_highlights(current, trends),
            "recommendations": self._generate_recommendations(current, trends),
        }

    def _calculate_health_score(
        self, current: FlywheelMetrics, trends: dict[str, Any]
    ) -> float:
        """计算飞轮健康分数(0-100)。"""
        score = 0.0

        # 模型质量权重 30%
        score += min(current.model_quality, 100) * 0.3

        # 用户采纳率权重 25%
        score += min(current.adoption_rate, 100) * 0.25

        # 不确定性权重 20% (越低越好)
        uncertainty_score = (1 - current.uncertainty_mean) * 100
        score += uncertainty_score * 0.2

        # 回灌延迟权重 15% (越低越好)
        delay_score = max(0, 100 - current.feedback_delay)
        score += delay_score * 0.15

        # 数据量权重 10%
        volume_score = min(current.data_volume / 100, 100)
        score += volume_score * 0.1

        return score

    def _get_health_status(self, score: float) -> str:
        """根据分数返回健康状态。"""
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "fair"
        else:
            return "poor"

    def _generate_highlights(
        self, current: FlywheelMetrics, trends: dict[str, Any]
    ) -> list[str]:
        """生成亮点摘要。"""
        highlights = []

        if current.model_quality >= 85:
            highlights.append(f"模型质量优秀，达到 {current.model_quality:.1f}%")

        if current.adoption_rate >= 70:
            highlights.append(f"用户采纳率良好，达到 {current.adoption_rate:.1f}%")

        if trends.get("model_quality", {}).get("change", 0) > 0:
            highlights.append("模型质量呈上升趋势")

        if trends.get("adoption_rate", {}).get("change", 0) > 0:
            highlights.append("用户采纳率持续提升")

        return highlights

    def _generate_recommendations(
        self, current: FlywheelMetrics, trends: dict[str, Any]
    ) -> list[str]:
        """生成改进建议。"""
        recommendations = []

        if current.model_quality < 80:
            recommendations.append("建议优化模型训练流程，提升预测准确率")

        if current.adoption_rate < 60:
            recommendations.append("建议改进模型建议的可解释性，提升用户采纳率")

        if current.uncertainty_mean > 0.3:
            recommendations.append("模型不确定性较高，建议增加训练数据或优化模型结构")

        if current.feedback_delay > 60:
            recommendations.append("回灌延迟较长，建议优化数据处理流程")

        if not recommendations:
            recommendations.append("飞轮运转良好，继续保持当前策略")

        return recommendations


def save_report_to_file(report: dict[str, Any], output_dir: str | Path) -> Path:
    """将报告保存到文件。

    Args:
        report: 报告数据
        output_dir: 输出目录

    Returns:
        报告文件路径
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"flywheel_report_{timestamp}.json"
    filepath = output_dir / filename

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info(f"Report saved to: {filepath}")
    return filepath


# 全局采集器实例
_collector: FlywheelMetricsCollector | None = None
_collector_lock = threading.Lock()


def get_flywheel_collector() -> FlywheelMetricsCollector:
    """获取全局飞轮指标采集器实例。"""
    global _collector
    if _collector is None:
        with _collector_lock:
            if _collector is None:
                _collector = FlywheelMetricsCollector()
    return _collector


if __name__ == "__main__":
    # 命令行接口：生成周报
    import argparse

    parser = argparse.ArgumentParser(description="飞轮指标报告生成器")
    parser.add_argument(
        "--report",
        choices=["weekly"],
        default="weekly",
        help="报告类型",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="reports",
        help="报告输出目录",
    )

    args = parser.parse_args()

    collector = get_flywheel_collector()

    if args.report == "weekly":
        report = collector.generate_weekly_report()
        filepath = save_report_to_file(report, args.output_dir)
        logger.info(f"Weekly report generated: {filepath}")
