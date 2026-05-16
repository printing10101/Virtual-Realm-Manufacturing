"""Fanuc 0i系列CNC控制器后处理器。

实现Fanuc 0i系列控制器特有的G代码方言，包括：
- G43/G44刀具长度补偿
- G41/G42刀具半径补偿
- G02/G03圆弧插补（R半径模式）
- G73高速深孔啄钻 / G83深孔啄钻循环
- M03/M04/M05主轴控制
- M08/M09冷却液控制
"""

from __future__ import annotations

from typing import Tuple

from app.postprocessor.base import BasePostProcessor


class FanucPostProcessor(BasePostProcessor):
    """Fanuc 0i系列CNC控制器后处理器。

    生成符合Fanuc 0i语法规范的G代码。
    """

    def format_header(self, program_number: int = 1) -> str:
        lines = [
            "%",
            f"O{program_number:04d} (PROGRAM {program_number} - {self._date_string()})",
            "(POST: Fanuc 0i-MF)",
            "G21 G17 G40 G49 G80 G90 G94",
            "G00 G91 G28 Z0.",
            "G00 G91 G28 X0. Y0.",
            "G00 G90 G54 X0. Y0.",
            f"G00 G43 Z{self._fmt(self.safe_z_height)} H00",
            "M03 S8000",
            "M08",
            "",
        ]
        return "\n".join(lines)

    def format_tool_change(
        self,
        tool_id: int,
        length_comp: float = 0.0,
        radius_comp: float = 0.0,
    ) -> str:
        lines = [
            "G00 G91 G28 Z0.",
            "G00 G91 G28 X0. Y0.",
            f"T{tool_id:02d} M06",
            "G00 G90 G54 X0. Y0.",
            f"G43 Z{self._fmt(self.safe_z_height)} H{tool_id:02d}",
            f"G01 Z{self._fmt(length_comp)} F{self._fmt(self.rapid_feed)}",
        ]
        if radius_comp != 0.0:
            lines.append("M03 S8000")
        return "\n".join(lines)

    def format_arc(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        center: Tuple[float, float, float],
        clockwise: bool = True,
    ) -> str:
        g_code = "G02" if clockwise else "G03"
        radius = ((end[0] - center[0]) ** 2 + (end[1] - center[1]) ** 2) ** 0.5
        return (
            f"{g_code} X{self._fmt(end[0])} Y{self._fmt(end[1])} "
            f"R{self._fmt(radius)} F{self._fmt(self.rapid_feed)}"
        )

    def format_coolant(self, state: str) -> str:
        if state.lower() == "on":
            return "M08"
        if state.lower() == "off":
            return "M09"
        return "M09"

    def format_tool_compensation(
        self,
        length_offset: int = 0,
        radius_offset: int = 0,
    ) -> str:
        lines = []
        if length_offset > 0:
            lines.append(f"G43 H{length_offset:02d}")
        if radius_offset > 0:
            lines.append(f"G41 D{radius_offset:02d}")
        return "\n".join(lines) if lines else "G49 G40"

    def format_cycle_drill(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        dwell: float = 0.0,
    ) -> str:
        r_plane = self.safe_z_height
        retract = depth - 1.0 if depth > 1.0 else 0.0

        if dwell > 0:
            lines = [
                f"G98 G73 X{self._fmt(x)} Y{self._fmt(y)} "
                f"Z{self._fmt(depth)} R{self._fmt(r_plane)} "
                f"Q{self._fmt(abs(retract))} P{int(dwell * 1000)} "
                f"F{self._fmt(self.rapid_feed * 0.3)}",
                "G80",
            ]
        else:
            lines = [
                f"G98 G83 X{self._fmt(x)} Y{self._fmt(y)} "
                f"Z{self._fmt(depth)} R{self._fmt(r_plane)} "
                f"Q{self._fmt(abs(retract))} "
                f"F{self._fmt(self.rapid_feed * 0.3)}",
                "G80",
            ]
        return "\n".join(lines)

    def format_footer(self) -> str:
        lines = [
            "",
            "M09",
            "M05",
            "G00 G91 G28 Z0.",
            "G00 G91 G28 X0. Y0.",
            "G90",
            "M30",
            "%",
        ]
        return "\n".join(lines)
