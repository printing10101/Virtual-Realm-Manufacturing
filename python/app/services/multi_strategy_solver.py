"""
多策略工艺方案求解器模块
实现四种预设策略的工艺方案优化计算
"""

import time
import uuid
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class StrategyId(StrEnum):
    QUALITY_FIRST = "quality_first"
    COST_FIRST = "cost_first"
    EFFICIENCY_FIRST = "efficiency_first"
    BALANCED = "balanced"


@dataclass
class StrategyProfile:
    """策略配置数据类"""
    strategy_id: str
    name: str
    objective_weights: dict[str, float]
    constraint_relaxation: dict[str, float] = field(default_factory=dict)


DEFAULT_STRATEGIES: dict[str, StrategyProfile] = {
    StrategyId.QUALITY_FIRST: StrategyProfile(
        strategy_id=StrategyId.QUALITY_FIRST,
        name="质量优先",
        objective_weights={
            "surface_roughness": 0.5,
            "cost": 0.1,
            "time": 0.2,
            "tool_life": 0.2
        },
        constraint_relaxation={
            "roughness_tolerance": 0.8
        }
    ),
    StrategyId.COST_FIRST: StrategyProfile(
        strategy_id=StrategyId.COST_FIRST,
        name="成本优先",
        objective_weights={
            "cost": 0.5,
            "surface_roughness": 0.1,
            "time": 0.2,
            "tool_life": 0.2
        },
        constraint_relaxation={
            "cost_budget": 1.2
        }
    ),
    StrategyId.EFFICIENCY_FIRST: StrategyProfile(
        strategy_id=StrategyId.EFFICIENCY_FIRST,
        name="效率优先",
        objective_weights={
            "time": 0.5,
            "surface_roughness": 0.15,
            "cost": 0.15,
            "tool_life": 0.2
        },
        constraint_relaxation={
            "time_limit": 1.3
        }
    ),
    StrategyId.BALANCED: StrategyProfile(
        strategy_id=StrategyId.BALANCED,
        name="均衡模式",
        objective_weights={
            "surface_roughness": 0.25,
            "cost": 0.25,
            "time": 0.25,
            "tool_life": 0.25
        },
        constraint_relaxation={}
    )
}


@dataclass
class ProcessPlanResult:
    """工艺方案计算结果"""
    plan_id: str
    strategy_id: str
    strategy_name: str
    cutting_speed: float
    feed_rate: float
    depth_of_cut: float
    surface_roughness: float
    cost: float
    processing_time: float
    tool_life: float
    objective_weights: dict[str, float]
    computation_time_ms: float
    status: str = "optimal"


class MultiStrategySolver:
    """多策略求解器核心类"""

    def __init__(self):
        self.strategies = DEFAULT_STRATEGIES.copy()

    def get_available_strategies(self) -> list[dict[str, Any]]:
        """获取所有可用策略列表"""
        return [
            {
                "strategy_id": s.strategy_id,
                "name": s.name,
                "objective_weights": s.objective_weights
            }
            for s in self.strategies.values()
        ]

    def solve_all_strategies(self, part_info: dict[str, Any]) -> dict[str, ProcessPlanResult]:
        """针对同一零件生成所有预设策略的工艺方案"""
        results = {}

        for strategy_id, _profile in self.strategies.items():
            result = self._solve_single_strategy(strategy_id, part_info)
            results[strategy_id] = result

        return results

    def solve_with_custom_weights(
        self,
        part_info: dict[str, Any],
        custom_weights: dict[str, float]
    ) -> ProcessPlanResult:
        """使用自定义权重生成单组定制化工艺方案"""
        total = sum(custom_weights.values())
        if abs(total - 1.0) > 0.01:
            custom_weights = {k: v / total for k, v in custom_weights.items()}

        plan_id = f"custom_{uuid.uuid4().hex[:8]}"
        start_time = time.time()

        params = self._optimize_parameters(part_info, custom_weights)

        computation_time = (time.time() - start_time) * 1000

        return ProcessPlanResult(
            plan_id=plan_id,
            strategy_id="custom",
            strategy_name="自定义方案",
            cutting_speed=params["cutting_speed"],
            feed_rate=params["feed_rate"],
            depth_of_cut=params["depth_of_cut"],
            surface_roughness=params["surface_roughness"],
            cost=params["cost"],
            processing_time=params["processing_time"],
            tool_life=params["tool_life"],
            objective_weights=custom_weights,
            computation_time_ms=round(computation_time, 2)
        )

    def _solve_single_strategy(
        self,
        strategy_id: str,
        part_info: dict[str, Any]
    ) -> ProcessPlanResult:
        """求解单个策略的工艺方案"""
        profile = self.strategies[strategy_id]
        start_time = time.time()

        params = self._optimize_parameters(part_info, profile.objective_weights)

        computation_time = (time.time() - start_time) * 1000

        return ProcessPlanResult(
            plan_id=f"{strategy_id}_{uuid.uuid4().hex[:8]}",
            strategy_id=strategy_id,
            strategy_name=profile.name,
            cutting_speed=params["cutting_speed"],
            feed_rate=params["feed_rate"],
            depth_of_cut=params["depth_of_cut"],
            surface_roughness=params["surface_roughness"],
            cost=params["cost"],
            processing_time=params["processing_time"],
            tool_life=params["tool_life"],
            objective_weights=profile.objective_weights,
            computation_time_ms=round(computation_time, 2)
        )

    def _optimize_parameters(
        self,
        part_info: dict[str, Any],
        weights: dict[str, float]
    ) -> dict[str, float]:
        """基于权重优化工艺参数"""
        material = part_info.get("material", "steel_45")
        part_type = part_info.get("part_type", "shaft")
        part_info.get("constraints", {})

        material_factors = self._get_material_factors(material)
        part_factors = self._get_part_type_factors(part_type)

        roughness_weight = weights.get("surface_roughness", 0.25)
        cost_weight = weights.get("cost", 0.25)
        time_weight = weights.get("time", 0.25)
        tool_life_weight = weights.get("tool_life", 0.25)

        base_cutting_speed = 120.0 * material_factors["speed"] * part_factors["speed"]
        base_feed_rate = 0.15 * material_factors["feed"] * part_factors["feed"]
        base_depth = 2.0 * material_factors["depth"] * part_factors["depth"]

        speed_factor = 1.0 + (time_weight - 0.25) * 0.4 - (roughness_weight - 0.25) * 0.2
        feed_factor = 1.0 + (cost_weight - 0.25) * 0.3 - (roughness_weight - 0.25) * 0.15
        depth_factor = 1.0 + (time_weight - 0.25) * 0.2 - (tool_life_weight - 0.25) * 0.1

        cutting_speed = base_cutting_speed * speed_factor
        feed_rate = base_feed_rate * feed_factor
        depth_of_cut = base_depth * depth_factor

        cutting_speed = max(50.0, min(300.0, cutting_speed))
        feed_rate = max(0.05, min(0.5, feed_rate))
        depth_of_cut = max(0.5, min(5.0, depth_of_cut))

        surface_roughness = self._calculate_roughness(cutting_speed, feed_rate, roughness_weight)
        cost = self._calculate_cost(cutting_speed, feed_rate, depth_of_cut, cost_weight)
        processing_time = self._calculate_time(cutting_speed, feed_rate, depth_of_cut, time_weight)
        tool_life = self._calculate_tool_life(cutting_speed, feed_rate, tool_life_weight)

        return {
            "cutting_speed": round(cutting_speed, 2),
            "feed_rate": round(feed_rate, 4),
            "depth_of_cut": round(depth_of_cut, 2),
            "surface_roughness": round(surface_roughness, 3),
            "cost": round(cost, 2),
            "processing_time": round(processing_time, 2),
            "tool_life": round(tool_life, 2)
        }

    def _get_material_factors(self, material: str) -> dict[str, float]:
        """获取材料系数"""
        factors = {
            "steel_45": {"speed": 1.0, "feed": 1.0, "depth": 1.0},
            "aluminum_6061": {"speed": 1.5, "feed": 1.3, "depth": 1.2},
            "stainless_304": {"speed": 0.7, "feed": 0.8, "depth": 0.8},
            "titanium_tc4": {"speed": 0.5, "feed": 0.6, "depth": 0.6},
            "copper": {"speed": 1.4, "feed": 1.2, "depth": 1.1}
        }
        return factors.get(material.lower(), factors["steel_45"])

    def _get_part_type_factors(self, part_type: str) -> dict[str, float]:
        """获取零件类型系数"""
        factors = {
            "shaft": {"speed": 1.0, "feed": 1.0, "depth": 1.0},
            "gear": {"speed": 0.9, "feed": 0.9, "depth": 0.8},
            "housing": {"speed": 1.1, "feed": 1.1, "depth": 1.2},
            "plate": {"speed": 1.2, "feed": 1.2, "depth": 1.3},
            "flange": {"speed": 1.0, "feed": 1.0, "depth": 1.1}
        }
        return factors.get(part_type.lower(), factors["shaft"])

    def _calculate_roughness(
        self,
        cutting_speed: float,
        feed_rate: float,
        weight: float
    ) -> float:
        """计算表面粗糙度"""
        base_roughness = 3.2
        speed_factor = 1.0 - (cutting_speed - 120.0) / 300.0 * 0.3
        feed_factor = (feed_rate / 0.15) ** 0.5
        roughness = base_roughness * speed_factor * feed_factor

        if weight > 0.3:
            roughness *= 0.85

        return max(0.4, min(12.8, roughness))

    def _calculate_cost(
        self,
        cutting_speed: float,
        feed_rate: float,
        depth_of_cut: float,
        weight: float
    ) -> float:
        """计算制造成本"""
        base_cost = 150.0
        tool_cost = 50.0 * (cutting_speed / 120.0) ** 1.5
        machine_cost = 80.0 * (feed_rate / 0.15) ** 0.5
        material_cost = 30.0 * (depth_of_cut / 2.0) ** 0.3

        cost = base_cost + tool_cost + machine_cost + material_cost

        if weight > 0.3:
            cost *= 0.9

        return max(80.0, min(350.0, cost))

    def _calculate_time(
        self,
        cutting_speed: float,
        feed_rate: float,
        depth_of_cut: float,
        weight: float
    ) -> float:
        """计算加工时间"""
        base_time = 25.0
        speed_factor = 120.0 / max(cutting_speed, 50.0)
        feed_factor = 0.15 / max(feed_rate, 0.05)
        depth_factor = 2.0 / max(depth_of_cut, 0.5)

        processing_time = base_time * (speed_factor * 0.4 + feed_factor * 0.4 + depth_factor * 0.2)

        if weight > 0.3:
            processing_time *= 0.85

        return max(8.0, min(60.0, processing_time))

    def _calculate_tool_life(
        self,
        cutting_speed: float,
        feed_rate: float,
        weight: float
    ) -> float:
        """计算刀具寿命"""
        base_life = 180.0
        speed_factor = (120.0 / max(cutting_speed, 50.0)) ** 2.0
        feed_factor = (0.15 / max(feed_rate, 0.05)) ** 0.8

        tool_life = base_life * speed_factor * feed_factor

        if weight > 0.3:
            tool_life *= 1.15

        return max(30.0, min(400.0, tool_life))
