"""仿真结果报告生成器。

汇总碰撞检测结果和可视化输出，生成结构化的仿真报告。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.simulation.collision_detector import CollisionReport
from app.simulation.toolpath_parser import ToolpathSegment


@dataclass
class SimulationReport:
    timestamp: str
    total_segments: int
    rapid_segments: int
    linear_segments: int
    arc_segments: int
    dwell_segments: int
    collision_report: CollisionReport
    visualization_path: str = ""
    duration_seconds: float = 0.0
    part_name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_segments": self.total_segments,
            "rapid_segments": self.rapid_segments,
            "linear_segments": self.linear_segments,
            "arc_segments": self.arc_segments,
            "dwell_segments": self.dwell_segments,
            "collision_report": self.collision_report.to_dict(),
            "visualization_path": self.visualization_path,
            "duration_seconds": round(self.duration_seconds, 3),
            "part_name": self.part_name,
            "status": "PASS" if self.collision_report.safe else "FAIL",
        }

    def save_json(self, output_path: str) -> str:
        out = Path(output_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        with open(out, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
        return str(out)

    @classmethod
    def from_validation(
        cls,
        segments: list[ToolpathSegment],
        collision_report: CollisionReport,
        visualization_path: str = "",
        duration_seconds: float = 0.0,
        part_name: str = "",
    ) -> SimulationReport:
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            total_segments=len(segments),
            rapid_segments=sum(1 for s in segments if s.type == "rapid"),
            linear_segments=sum(1 for s in segments if s.type == "linear"),
            arc_segments=sum(1 for s in segments if s.type == "arc"),
            dwell_segments=sum(1 for s in segments if s.type == "dwell"),
            collision_report=collision_report,
            visualization_path=visualization_path,
            duration_seconds=duration_seconds,
            part_name=part_name,
        )


def generate_summary_text(report: SimulationReport) -> str:
    cr = report.collision_report
    status = "✓ 安全" if cr.safe else "✗ 检测到碰撞"
    lines = [
        "=" * 60,
        f"  NC刀具路径仿真报告 - {report.part_name or '未命名'}",
        "=" * 60,
        f"  生成时间: {report.timestamp}",
        f"  仿真耗时: {report.duration_seconds:.2f}s",
        "",
        "  运动段统计:",
        f"    总计: {report.total_segments}",
        f"    G00快速: {report.rapid_segments}",
        f"    G01直线: {report.linear_segments}",
        f"    G02/G03圆弧: {report.arc_segments}",
        f"    G04暂停: {report.dwell_segments}",
        "",
        f"  安全状态: {status}",
        f"  碰撞事件: {len(cr.collisions)}",
    ]

    for c in cr.collisions:
        lines.append(
            f"    [{c.severity.upper()}] N{c.block_number} "
            f"{c.collision_type}: {c.message}"
        )

    if cr.warnings:
        lines.append("")
        lines.append("  边界警告:")
        for w in cr.warnings:
            lines.append(f"    - {w}")

    return "\n".join(lines)
