"""进给速率优化器。

根据切削条件动态优化进给速率。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CuttingConditions:
    """切削条件参数。"""

    material: str
    tool_diameter: float
    tool_material: str
    depth_of_cut: float
    width_of_cut: float
    spindle_speed: float
    feed_rate: float

    @property
    def surface_speed(self) -> float:
        """计算切削速度 (m/min)。"""
        import math
        return (math.pi * self.tool_diameter * self.spindle_speed) / 1000.0

    @property
    def feed_per_tooth(self) -> float:
        """计算每齿进给量 (mm/tooth)。"""
        # Assume 2 flutes as default
        flute_count = 2
        return self.feed_rate / (self.spindle_speed * flute_count)


class FeedRateOptimizer:
    """进给速率优化器。"""

    def __init__(self) -> None:
        """初始化优化器。"""
        self._material_database: dict[str, dict[str, Any]] = {}
        self._load_default_database()

    def _load_default_database(self) -> None:
        """加载默认材料切削参数数据库。"""
        # 加载完整的材料切削参数数据库
        # 当前使用简化的内置数据库，后续可从外部配置文件或数据库加载
        self._material_database = {
            "aluminum": {
                "surface_speed_range": (150, 600),  # m/min
                "feed_per_tooth_range": (0.05, 0.3),  # mm/tooth
            },
            "steel": {
                "surface_speed_range": (30, 150),
                "feed_per_tooth_range": (0.05, 0.2),
            },
            "stainless": {
                "surface_speed_range": (20, 80),
                "feed_per_tooth_range": (0.03, 0.15),
            },
            "titanium": {
                "surface_speed_range": (15, 60),
                "feed_per_tooth_range": (0.02, 0.1),
            },
        }

    def optimize_feed_rate(
        self,
        conditions: CuttingConditions,
        optimization_goal: str = "efficiency",
    ) -> float:
        """优化进给速率。

        Args:
            conditions: 切削条件
            optimization_goal: 优化目标 ("efficiency", "tool_life", "surface_finish")

        Returns:
            优化后的进给速率 (mm/min)
        """
        material_data = self._material_database.get(
            conditions.material.lower(),
            {"surface_speed_range": (50, 200), "feed_per_tooth_range": (0.05, 0.2)},
        )

        # 优化算法（待实现）
        # - 考虑材料属性
        # - 考虑刀具磨损
        # - 考虑机床功率限制
        # - 考虑表面质量要求
        # 当前使用推荐范围的中间值作为简单优化

        # Simple optimization: use middle of recommended range
        recommended_feed = (
            material_data["feed_per_tooth_range"][0]
            + material_data["feed_per_tooth_range"][1]
        ) / 2.0

        # Assume 2 flutes
        flute_count = 2
        optimized_feed = (
            recommended_feed * conditions.spindle_speed * flute_count
        )

        logger.debug(
            "Feed rate optimized: %.1f -> %.1f mm/min",
            conditions.feed_rate,
            optimized_feed,
        )

        return optimized_feed

    def validate_conditions(self, conditions: CuttingConditions) -> tuple[bool, list[str]]:
        """验证切削条件是否在推荐范围内。

        Args:
            conditions: 切削条件

        Returns:
            (是否有效, 警告信息列表)
        """
        warnings: list[str] = []

        material_data = self._material_database.get(conditions.material.lower())
        if material_data is None:
            warnings.append(f"Material '{conditions.material}' not in database")
            return True, warnings

        surface_speed = conditions.surface_speed
        speed_range = material_data["surface_speed_range"]
        if surface_speed < speed_range[0] or surface_speed > speed_range[1]:
            warnings.append(
                f"Surface speed {surface_speed:.1f} m/min outside recommended range "
                f"{speed_range[0]}-{speed_range[1]} m/min"
            )

        feed_per_tooth = conditions.feed_per_tooth
        feed_range = material_data["feed_per_tooth_range"]
        if feed_per_tooth < feed_range[0] or feed_per_tooth > feed_range[1]:
            warnings.append(
                f"Feed per tooth {feed_per_tooth:.3f} mm/tooth outside recommended range "
                f"{feed_range[0]}-{feed_range[1]} mm/tooth"
            )

        return len(warnings) == 0, warnings
