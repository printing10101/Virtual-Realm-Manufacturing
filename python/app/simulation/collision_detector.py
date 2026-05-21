"""Basic collision detection engine for CNC toolpath validation.

Uses AABB (Axis-Aligned Bounding Box) for efficient collision detection,
covering tool-stock collision, overcut boundary detection, and tool-change
point safety checks.

Example:
    >>> stock = StockModel(length=200, width=150, height=50)
    >>> detector = CollisionDetector(stock, safe_z_height=10.0)
    >>> report = detector.check_segments(parsed_segments)
    >>> print(f"Safe: {report.safe}, Collisions: {report.collision_count}")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.simulation.stock_model import StockBoundingBox, StockModel
from app.simulation.toolpath_parser import ToolpathSegment


@dataclass
class CollisionEvent:
    """Represents a single collision event detected during toolpath validation.

    Attributes:
        collision_type: Type of collision (e.g., "rapid_into_stock", "overcut_z").
        severity: Severity level ("high", "medium", "low").
        block_number: NC block number where the collision occurred.
        position: (x, y, z) coordinates of the collision point.
        message: Human-readable description of the collision.
        suggestion: Suggested corrective action.
    """

    collision_type: str
    severity: str
    block_number: int
    position: tuple[float, float, float]
    message: str
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert the collision event to a dictionary.

        Returns:
            Dictionary with all collision event fields.
        """
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
    """Aggregated report from a full toolpath collision check.

    Attributes:
        total_segments: Total number of toolpath segments in the input.
        segments_checked: Number of segments actually checked.
        collisions: List of detected collision events.
        warnings: List of boundary warning messages.
        safe: Whether the toolpath is collision-free.
    """

    total_segments: int
    segments_checked: int
    collisions: list[CollisionEvent] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    safe: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert the collision report to a dictionary.

        Returns:
            Dictionary with all collision report fields and collision count.
        """
        return {
            "total_segments": self.total_segments,
            "segments_checked": self.segments_checked,
            "collisions": [c.to_dict() for c in self.collisions],
            "warnings": self.warnings,
            "safe": self.safe,
            "collision_count": len(self.collisions),
        }


class CollisionDetector:
    """AABB-based collision detector for CNC toolpaths.

    Checks toolpath segments against the stock bounding box for:
    - Rapid move (G00) collision with stock material
    - Z-axis safety during rapid moves
    - Overcut beyond stock boundaries

    Attributes:
        stock: The stock model to check against.
        safe_z_height: Minimum safe clearance above stock (mm).
        spindle_clearance: Spindle clearance margin (mm).

    Example:
        >>> detector = CollisionDetector(stock_model, safe_z_height=10.0)
        >>> report = detector.check_segments(segments)
        >>> if not report.safe:
        ...     for c in report.collisions:
        ...         print(c.message)
    """

    def __init__(
        self,
        stock: StockModel | None = None,
        safe_z_height: float = 10.0,
        spindle_clearance: float = 5.0,
    ) -> None:
        """Initialize the collision detector.

        Args:
            stock: Stock model defining the workpiece boundaries.
            safe_z_height: Safe Z clearance above the stock in mm.
            spindle_clearance: Spindle clearance margin in mm.
        """
        self.stock = stock
        self.safe_z_height = safe_z_height
        self.spindle_clearance = spindle_clearance

    def check_segments(
        self,
        segments: list[ToolpathSegment],
    ) -> CollisionReport:
        """Check all toolpath segments for collisions.

        Iterates through each segment and performs type-specific checks:
        rapid moves are checked for stock collision and Z safety, while
        cutting moves (linear/arc) are checked for overcut.

        Args:
            segments: List of toolpath segments to validate.

        Returns:
            CollisionReport summarizing all detected collisions and warnings.
        """
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
        """Check if a rapid move intersects the stock bounding box.

        Constructs an AABB for the rapid move line segment and checks
        intersection with the stock. If intersecting, samples points
        along the path to detect actual stock penetration.

        Args:
            seg: The rapid move toolpath segment.
            bbox: Stock bounding box (None skips the check).
            collisions: List to append detected collision events to.
        """
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
                            message=f"G00 rapid move cuts into stock at N{seg.block_number}",
                            suggestion=(
                                f"Increase safe Z height to >= {safe_plane}mm, "
                                "or retract to safe plane before positioning"
                            ),
                        )
                    )
                    break

    def _check_z_safety(
        self,
        seg: ToolpathSegment,
        stock_z_top: float,
        collisions: list[CollisionEvent],
    ) -> None:
        """Check Z-axis safety for rapid moves.

        Verifies that the rapid move starts above the safe Z plane
        (stock top + safe_z_height).

        Args:
            seg: The rapid move toolpath segment.
            stock_z_top: Z coordinate of the stock top surface.
            collisions: List to append detected collision events to.
        """
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
                    message=f"G00 start Z={sz:.1f} is below safe height {safe_z:.1f}",
                    suggestion=f"Retract to G00 Z{safe_z} before rapid movement",
                )
            )

    def _check_overcut(
        self,
        seg: ToolpathSegment,
        bbox: StockBoundingBox | None,
        collisions: list[CollisionEvent],
        warnings: list[str],
    ) -> None:
        """Check for overcut beyond stock boundaries.

        Detects when the toolpath endpoint extends beyond the stock
        bounding box with a 0.5mm tolerance margin.

        Args:
            seg: The cutting toolpath segment (linear or arc).
            bbox: Stock bounding box (None skips the check).
            collisions: List to append detected collision events to.
            warnings: List to append boundary warning messages to.
        """
        if bbox is None:
            return

        ex, ey, ez = seg.end_point
        margin = 0.5

        if ex < bbox.x_min - margin or ex > bbox.x_max + margin:
            warnings.append(
                f"N{seg.block_number}: Tool path X={ex:.2f} exceeds stock boundary "
                f"[{bbox.x_min:.2f}, {bbox.x_max:.2f}]"
            )
        if ey < bbox.y_min - margin or ey > bbox.y_max + margin:
            warnings.append(
                f"N{seg.block_number}: Tool path Y={ey:.2f} exceeds stock boundary "
                f"[{bbox.y_min:.2f}, {bbox.y_max:.2f}]"
            )
        if ez < bbox.z_min - margin:
            collisions.append(
                CollisionEvent(
                    collision_type="overcut_z",
                    severity="high",
                    block_number=seg.block_number,
                    position=seg.end_point,
                    message=f"Tool path Z={ez:.3f} is below stock bottom Z={bbox.z_min}, risk of overcut",
                    suggestion=f"Check Z-axis cutting depth; stock bottom is at Z={bbox.z_min}",
                )
            )

    def check_single_rapid(
        self,
        seg: ToolpathSegment,
    ) -> list[CollisionEvent]:
        """Check a single rapid move segment for collisions.

        Convenience method for checking one rapid segment at a time.

        Args:
            seg: A rapid move toolpath segment.

        Returns:
            List of collision events (empty if safe or segment is not rapid).
        """
        if seg.type != "rapid":
            return []
        bbox = self.stock.get_bbox() if self.stock else None
        collisions: list[CollisionEvent] = []
        self._check_rapid_collision(seg, bbox, collisions)
        return collisions
