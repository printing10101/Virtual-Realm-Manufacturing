"""基础碰撞检测引擎。

采用AABB（轴对齐包围盒）进行高效碰撞检测，
覆盖刀具-毛坯碰撞、过切边界检测、换刀点安全检查。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.simulation.stock_model import StockBoundingBox, StockModel
from app.simulation.toolpath_parser import ToolpathSegment


@dataclass
class CollisionEvent:
    collision_type: str
    severity: str
    block_number: int
    position: tuple[float, float, float]
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "collision_type": self.collision_type,
            "severity": self.severity,
            "block_number": self.block_number,
            "position": list(self.position),
            "message": self.message,
            "suggestion": self.suggestion,
        }


@dataclass
class CollisionReport:
    total_segments: int
    segments_checked: int
    collisions: list[CollisionEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_segments": self.total_segments,
            "segments_checked": self.segments_checked,
            "collisions": [c.to_dict() for c in self.collisions],
            "warnings": self.warnings,
            "safe": self.safe,
            "collision_count": len(self.collisions),
        }


class CollisionDetector:
    def __init__(
        self,
        stock: StockModel | None = None,
        safe_z_height: float = 10.0,
        spindle_clearance: float = 5.0,
    ) -> None:
        self.stock = stock
        self.safe_z_height = safe_z_height
        self.spindle_clearance = spindle_clearance

    def check_segments(
        self,
        segments: list[ToolpathSegment],
    ) -> CollisionReport:
        bbox = self.stock.get_bbox() if self.stock else None
        stock_z_top = bbox.z_max if bbox else 100.0

        collisions: list[CollisionEvent] = []
        warnings: list[str] = []

        for seg in segments:
            if seg.type == "rapid":
                self._check_rapid_collision(seg, bbox, collisions)
                self._check_z_safety(seg, stock_z_top, collisions)
            elif seg.type in ("linear", "arc"):
                self._check_overcut(seg, bbox, collisions, warnings)

        safe = len(collisions) == 0
        return CollisionReport(
            total_segments=len(segments),
            segments_checked=len(segments),
            collisions=collisions,
            warnings=warnings,
            safe=safe,
        )

    def _check_rapid_collision(
        self,
        seg: ToolpathSegment,
        bbox: StockBoundingBox | None,
        collisions: list[CollisionEvent],
    ) -> None:
        if bbox is None:
            return

        sx, sy, sz = seg.start_point
        ex, ey, ez = seg.end_point

        line_bbox = StockBoundingBox(
            x_min=min(sx, ex),
            x_max=max(sx, ex),
            y_min=min(sy, ey),
            y_max=max(sy, ey),
            z_min=min(sz, ez),
            z_max=max(sz, ez),
        )

        if not bbox.intersects_bbox(line_bbox):
            return

        safe_plane = bbox.z_max + self.safe_z_height
        if sz < safe_plane or ez < safe_plane:
            steps = max(
                int(((ex - sx) ** 2 + (ey - sy) ** 2 + (ez - sz) ** 2) ** 0.5 / 2), 5
            )
            for i in range(steps + 1):
                t = i / steps
                px = sx + (ex - sx) * t
                py = sy + (ey - sy) * t
                pz = sz + (ez - sz) * t
                if bbox.contains_point(px, py, pz):
                    collisions.append(
                        CollisionEvent(
                            collision_type="rapid_into_stock",
                            severity="high",
                            block_number=seg.block_number,
                            position=(round(px, 3), round(py, 3), round(pz, 3)),
                            message=f"G00快速移动在N{seg.block_number}处切入毛坯",
                            suggestion=f"增加安全Z高度至≥{safe_plane}mm，或先抬刀至安全平面再定位",
                        )
                    )
                    break

    def _check_z_safety(
        self,
        seg: ToolpathSegment,
        stock_z_top: float,
        collisions: list[CollisionEvent],
    ) -> None:
        if seg.type != "rapid":
            return

        _, _, sz = seg.start_point
        _, _, ez = seg.end_point
        safe_z = stock_z_top + self.safe_z_height

        if sz < safe_z:
            collisions.append(
                CollisionEvent(
                    collision_type="rapid_z_low",
                    severity="medium",
                    block_number=seg.block_number,
                    position=seg.start_point,
                    message=f"G00起点Z={sz:.1f}低于安全高度{safe_z:.1f}",
                    suggestion=f"在快速移动前先抬刀至G00 Z{safe_z}",
                )
            )

    def _check_overcut(
        self,
        seg: ToolpathSegment,
        bbox: StockBoundingBox | None,
        collisions: list[CollisionEvent],
        warnings: list[str],
    ) -> None:
        if bbox is None:
            return

        ex, ey, ez = seg.end_point
        margin = 0.5

        if ex < bbox.x_min - margin or ex > bbox.x_max + margin:
            warnings.append(
                f"N{seg.block_number}: 刀具路径X={ex:.2f}超出毛坯边界"
                f"[{bbox.x_min:.2f}, {bbox.x_max:.2f}]"
            )
        if ey < bbox.y_min - margin or ey > bbox.y_max + margin:
            warnings.append(
                f"N{seg.block_number}: 刀具路径Y={ey:.2f}超出毛坯边界"
                f"[{bbox.y_min:.2f}, {bbox.y_max:.2f}]"
            )
        if ez < bbox.z_min - margin:
            collisions.append(
                CollisionEvent(
                    collision_type="overcut_z",
                    severity="high",
                    block_number=seg.block_number,
                    position=seg.end_point,
                    message=f"刀具路径Z={ez:.3f}低于毛坯底面Z={bbox.z_min}，存在过切风险",
                    suggestion=f"检查Z轴切深，毛坯底面为Z={bbox.z_min}",
                )
            )

    def check_single_rapid(
        self,
        seg: ToolpathSegment,
    ) -> list[CollisionEvent]:
        if seg.type != "rapid":
            return []
        bbox = self.stock.get_bbox() if self.stock else None
        collisions: list[CollisionEvent] = []
        self._check_rapid_collision(seg, bbox, collisions)
        return collisions
