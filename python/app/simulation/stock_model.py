"""毛坯模型管理模块。

支持矩形毛坯和圆柱毛坯两种基础类型，
提供包围盒查询和坐标系转换接口。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class StockBoundingBox:
    x_min: float
    x_max: float
    y_min: float
    y_max: float
    z_min: float
    z_max: float

    def contains_point(self, x: float, y: float, z: float) -> bool:
        return (
            self.x_min <= x <= self.x_max
            and self.y_min <= y <= self.y_max
            and self.z_min <= z <= self.z_max
        )

    def intersects_bbox(self, other: StockBoundingBox) -> bool:
        return not (
            other.x_max < self.x_min
            or other.x_min > self.x_max
            or other.y_max < self.y_min
            or other.y_min > self.y_max
            or other.z_max < self.z_min
            or other.z_min > self.z_max
        )

    def volume(self) -> float:
        return (
            (self.x_max - self.x_min)
            * (self.y_max - self.y_min)
            * (self.z_max - self.z_min)
        )

    def center(self) -> tuple[float, float, float]:
        return (
            (self.x_min + self.x_max) / 2,
            (self.y_min + self.y_max) / 2,
            (self.z_min + self.z_max) / 2,
        )

    def to_dict(self) -> dict[str, float]:
        return {
            "x_min": self.x_min,
            "x_max": self.x_max,
            "y_min": self.y_min,
            "y_max": self.y_max,
            "z_min": self.z_min,
            "z_max": self.z_max,
        }


class StockModel:
    """矩形毛坯模型。

    定义长方体毛坯的几何尺寸和包围盒。
    坐标系约定：X/Y为水平面，Z为垂直轴（向上为正）。
    毛坯底面置于Z=0平面。
    """

    def __init__(
        self,
        length: float = 200,
        width: float = 150,
        height: float = 50,
    ) -> None:
        self.length = length
        self.width = width
        self.height = height
        self.origin_x = 0.0
        self.origin_y = 0.0

    def set_dimensions(
        self,
        length: float,
        width: float,
        height: float,
    ) -> None:
        self.length = length
        self.width = width
        self.height = height

    def get_bbox(self) -> StockBoundingBox:
        hl = self.length / 2
        hw = self.width / 2
        return StockBoundingBox(
            x_min=self.origin_x - hl,
            x_max=self.origin_x + hl,
            y_min=self.origin_y - hw,
            y_max=self.origin_y + hw,
            z_min=0.0,
            z_max=self.height,
        )

    def contains_point(self, x: float, y: float, z: float) -> bool:
        return self.get_bbox().contains_point(x, y, z)

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "rectangular",
            "length": self.length,
            "width": self.width,
            "height": self.height,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "bbox": self.get_bbox().to_dict(),
        }


class CylindricalStock(StockModel):
    """圆柱毛坯模型。

    定义圆柱形毛坯的几何尺寸和包围盒。
    轴线沿Z轴方向。
    """

    def __init__(
        self,
        diameter: float = 100,
        height: float = 200,
    ) -> None:
        self.diameter = diameter
        super().__init__(length=diameter, width=diameter, height=height)

    def set_dimensions(
        self,
        diameter: float,
        height: float,
    ) -> None:
        self.diameter = diameter
        self.length = diameter
        self.width = diameter
        self.height = height

    def get_bbox(self) -> StockBoundingBox:
        r = self.diameter / 2
        return StockBoundingBox(
            x_min=self.origin_x - r,
            x_max=self.origin_x + r,
            y_min=self.origin_y - r,
            y_max=self.origin_y + r,
            z_min=0.0,
            z_max=self.height,
        )

    def contains_point(self, x: float, y: float, z: float) -> bool:
        r = self.diameter / 2
        dx = x - self.origin_x
        dy = y - self.origin_y
        if dx * dx + dy * dy > r * r + 0.001:
            return False
        return 0.0 <= z <= self.height + 0.001

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": "cylindrical",
            "diameter": self.diameter,
            "height": self.height,
            "origin_x": self.origin_x,
            "origin_y": self.origin_y,
            "bbox": self.get_bbox().to_dict(),
        }
