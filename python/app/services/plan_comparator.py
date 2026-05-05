"""
方案对比分析器模块
实现多方案指标的标准化评分和对比分析
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class PlanScore:
    """方案评分数据"""
    plan_id: str
    strategy_id: str
    strategy_name: str
    raw_metrics: dict[str, float]
    normalized_scores: dict[str, float]
    weighted_score: float
    advantage_analysis: str
    recommendation: str


class PlanComparator:
    """方案对比分析器"""

    def __init__(self, default_weights: dict[str, float] | None = None):
        self.default_weights = default_weights or {
            "quality": 0.25,
            "cost": 0.25,
            "efficiency": 0.25,
            "tool_life": 0.25
        }

    def normalize_and_compare(
        self,
        plans: list[dict[str, Any]],
        weights: dict[str, float] | None = None
    ) -> list[PlanScore]:
        """
        对多个方案进行标准化评分和对比
        """
        if not plans:
            return []

        effective_weights = weights or self.default_weights

        all_metrics = self._collect_all_metrics(plans)

        normalized_plans = []
        for plan in plans:
            normalized_scores = self._min_max_normalize(plan, all_metrics)

            weighted_score = self._calculate_weighted_score(normalized_scores, effective_weights)

            advantage = self._generate_advantage_analysis(plan, normalized_scores)
            recommendation = self._generate_recommendation(plan, normalized_scores, weighted_score)

            normalized_plans.append(PlanScore(
                plan_id=plan["plan_id"],
                strategy_id=plan["strategy_id"],
                strategy_name=plan["strategy_name"],
                raw_metrics={
                    "surface_roughness": plan["surface_roughness"],
                    "cost": plan["cost"],
                    "processing_time": plan["processing_time"],
                    "tool_life": plan["tool_life"],
                    "cutting_speed": plan["cutting_speed"],
                    "feed_rate": plan["feed_rate"],
                    "depth_of_cut": plan["depth_of_cut"]
                },
                normalized_scores=normalized_scores,
                weighted_score=weighted_score,
                advantage_analysis=advantage,
                recommendation=recommendation
            ))

        return normalized_plans

    def get_trade_off_analysis(self, plan_a: PlanScore, plan_b: PlanScore) -> dict[str, str]:
        """生成两个方案之间的关键指标取舍说明"""
        trade_offs = {}

        if plan_a.normalized_scores["quality"] > plan_b.normalized_scores["quality"]:
            quality_diff = plan_a.normalized_scores["quality"] - plan_b.normalized_scores["quality"]
            trade_offs["quality"] = f"{plan_a.strategy_name}质量优于{plan_b.strategy_name}{quality_diff:.1f}分"
        else:
            quality_diff = plan_b.normalized_scores["quality"] - plan_a.normalized_scores["quality"]
            trade_offs["quality"] = f"{plan_b.strategy_name}质量优于{plan_a.strategy_name}{quality_diff:.1f}分"

        if plan_a.normalized_scores["cost"] > plan_b.normalized_scores["cost"]:
            cost_diff = plan_a.normalized_scores["cost"] - plan_b.normalized_scores["cost"]
            trade_offs["cost"] = f"{plan_a.strategy_name}成本优于{plan_b.strategy_name}{cost_diff:.1f}分"
        else:
            cost_diff = plan_b.normalized_scores["cost"] - plan_a.normalized_scores["cost"]
            trade_offs["cost"] = f"{plan_b.strategy_name}成本优于{plan_a.strategy_name}{cost_diff:.1f}分"

        if plan_a.normalized_scores["efficiency"] > plan_b.normalized_scores["efficiency"]:
            time_diff = plan_a.normalized_scores["efficiency"] - plan_b.normalized_scores["efficiency"]
            trade_offs["efficiency"] = f"{plan_a.strategy_name}效率优于{plan_b.strategy_name}{time_diff:.1f}分"
        else:
            time_diff = plan_b.normalized_scores["efficiency"] - plan_a.normalized_scores["efficiency"]
            trade_offs["efficiency"] = f"{plan_b.strategy_name}效率优于{plan_a.strategy_name}{time_diff:.1f}分"

        if plan_a.normalized_scores["tool_life"] > plan_b.normalized_scores["tool_life"]:
            life_diff = plan_a.normalized_scores["tool_life"] - plan_b.normalized_scores["tool_life"]
            trade_offs["tool_life"] = f"{plan_a.strategy_name}刀具寿命优于{plan_b.strategy_name}{life_diff:.1f}分"
        else:
            life_diff = plan_b.normalized_scores["tool_life"] - plan_a.normalized_scores["tool_life"]
            trade_offs["tool_life"] = f"{plan_b.strategy_name}刀具寿命优于{plan_a.strategy_name}{life_diff:.1f}分"

        return trade_offs

    def _collect_all_metrics(self, plans: list[dict[str, Any]]) -> dict[str, dict[str, float]]:
        """收集所有方案的关键指标用于归一化"""
        metrics_ranges = {
            "surface_roughness": {"min": float("inf"), "max": float("-inf")},
            "cost": {"min": float("inf"), "max": float("-inf")},
            "processing_time": {"min": float("inf"), "max": float("-inf")},
            "tool_life": {"min": float("inf"), "max": float("-inf")}
        }

        for plan in plans:
            for metric in metrics_ranges:
                value = plan.get(metric, 0)
                metrics_ranges[metric]["min"] = min(metrics_ranges[metric]["min"], value)
                metrics_ranges[metric]["max"] = max(metrics_ranges[metric]["max"], value)

        return metrics_ranges

    def _min_max_normalize(
        self,
        plan: dict[str, Any],
        metrics_ranges: dict[str, dict[str, float]]
    ) -> dict[str, float]:
        """
        Min-Max标准化,将指标转换为0-100分
        越低越好的指标(粗糙度、成本、时间): 分数 = (max - value) / (max - min) * 100
        越高越好的指标(刀具寿命): 分数 = (value - min) / (max - min) * 100
        """
        normalized = {}

        roughness_range = metrics_ranges["surface_roughness"]
        roughness_span = roughness_range["max"] - roughness_range["min"]
        if roughness_span > 0:
            normalized["quality"] = (roughness_range["max"] - plan["surface_roughness"]) / roughness_span * 100
        else:
            normalized["quality"] = 50.0

        cost_range = metrics_ranges["cost"]
        cost_span = cost_range["max"] - cost_range["min"]
        if cost_span > 0:
            normalized["cost"] = (cost_range["max"] - plan["cost"]) / cost_span * 100
        else:
            normalized["cost"] = 50.0

        time_range = metrics_ranges["processing_time"]
        time_span = time_range["max"] - time_range["min"]
        if time_span > 0:
            normalized["efficiency"] = (time_range["max"] - plan["processing_time"]) / time_span * 100
        else:
            normalized["efficiency"] = 50.0

        life_range = metrics_ranges["tool_life"]
        life_span = life_range["max"] - life_range["min"]
        if life_span > 0:
            normalized["tool_life"] = (plan["tool_life"] - life_range["min"]) / life_span * 100
        else:
            normalized["tool_life"] = 50.0

        normalized["quality"] = max(0, min(100, normalized["quality"]))
        normalized["cost"] = max(0, min(100, normalized["cost"]))
        normalized["efficiency"] = max(0, min(100, normalized["efficiency"]))
        normalized["tool_life"] = max(0, min(100, normalized["tool_life"]))

        return normalized

    def _calculate_weighted_score(
        self,
        normalized_scores: dict[str, float],
        weights: dict[str, float]
    ) -> float:
        """计算加权综合得分"""
        total_weight = sum(weights.values())
        if total_weight == 0:
            return 0.0

        weighted_sum = 0.0
        for dimension, weight in weights.items():
            weighted_sum += normalized_scores.get(dimension, 0) * weight

        return round(weighted_sum / total_weight, 2)

    def _generate_advantage_analysis(
        self,
        plan: dict[str, Any],
        normalized_scores: dict[str, float]
    ) -> str:
        """生成方案的优势分析"""
        scores_sorted = sorted(normalized_scores.items(), key=lambda x: x[1], reverse=True)

        best_dimension = scores_sorted[0][0]
        best_score = scores_sorted[0][1]

        dimension_names = {
            "quality": "加工质量",
            "cost": "成本控制",
            "efficiency": "加工效率",
            "tool_life": "刀具寿命"
        }

        advantages = []
        for dim, score in scores_sorted:
            if score >= 70:
                advantages.append(f"{dimension_names.get(dim, dim)}({score:.1f}分)")

        if advantages:
            advantage_text = f"该方案在{ '、'.join(advantages[:2]) }方面表现突出"
        else:
            advantage_text = f"该方案在{dimension_names.get(best_dimension, best_dimension)}方面相对较好({best_score:.1f}分)"

        return advantage_text

    def _generate_recommendation(
        self,
        plan: dict[str, Any],
        normalized_scores: dict[str, float],
        weighted_score: float
    ) -> str:
        """生成推荐理由"""
        strategy_name = plan["strategy_name"]

        if weighted_score >= 80:
            return f"强烈推荐{strategy_name}方案,综合评分{weighted_score:.1f}分,各项指标均衡优秀"
        elif weighted_score >= 60:
            return f"推荐{strategy_name}方案,综合评分{weighted_score:.1f}分,适合大多数生产场景"
        elif weighted_score >= 40:
            return f"{strategy_name}方案综合评分{weighted_score:.1f}分,在特定场景下具有一定优势"
        else:
            return f"{strategy_name}方案综合评分{weighted_score:.1f}分,建议结合具体需求评估"
