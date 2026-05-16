"""Siemens 840D CNC控制器后处理器。

实现Siemens 840D控制器特有的G代码方言，包括：
- $TC_DP6刀具表数据调用
- G41/G42配合DISC偏置
- G02/G03 CR=圆心半径模式
- CYCLE81/CYCLE83钻孔循环
- 符合Siemens程序段号及参数表示方式
"""

from __future__ import annotations

from typing import Tuple

from app.postprocessor.base import BasePostProcessor


class SiemensPostProcessor(BasePostProcessor):
    """Siemens 840D CNC控制器后处理器。

    生成符合Siemens 840D语法规范的G代码。
    """

    def __init__(
        self,
        decimal_places: int = 3,
        safe_z_height: float = 50.0,
        rapid_feed: float = 10000,
    ) -> None:
        super().__init__(decimal_places, safe_z_height, rapid_feed)
        self._block_counter = 0

    def _next_block(self) -> int:
        self._block_counter += 10
        return self._block_counter

    def format_header(self, program_number: int = 1) -> str:
        self._block_counter = 0
        n = self._next_block()
        lines = [
            f"N{n:05d} ; PROGRAM {program_number} - {self._date_string()}",
            f"N{n:05d} ; POST: Siemens 840D",
            f"N{self._next_block():05d} G17 G40 G90 G94",
            f"N{self._next_block():05d} G00 Z{self._fmt(self.safe_z_height)}",
            f"N{self._next_block():05d} G00 X0. Y0.",
            f"N{self._next_block():05d} M03 S8000",
            f"N{self._next_block():05d} M08",
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
            f"N{self._next_block():05d} G00 Z{self._fmt(self.safe_z_height)}",
            f'N{self._next_block():05d} T="TOOL{tool_id:02d}"',
            f"N{self._next_block():05d} M06",
            f"N{self._next_block():05d} D1",
            f"N{self._next_block():05d} G00 X0. Y0.",
            f"N{self._next_block():05d} Z{self._fmt(self.safe_z_height)}",
        ]
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
            f"N{self._next_block():05d} {g_code} "
            f"X{self._fmt(end[0])} Y{self._fmt(end[1])} "
            f"CR={self._fmt(radius)} F{self._fmt(self.rapid_feed)}"
        )

    def format_coolant(self, state: str) -> str:
        n = self._next_block()
        if state.lower() == "on":
            return f"N{n:05d} M08"
        if state.lower() == "off":
            return f"N{n:05d} M09"
        return f"N{n:05d} M09"

    def format_tool_compensation(
        self,
        length_offset: int = 0,
        radius_offset: int = 0,
    ) -> str:
        lines = []
        if length_offset > 0:
            lines.append(
                f"N{self._next_block():05d} $TC_DP6[{length_offset},1]={self._fmt(0.0)}"
            )
        if radius_offset > 0:
            lines.append(f"N{self._next_block():05d} G41 DISC{radius_offset}")
        if not lines:
            lines.append(f"N{self._next_block():05d} G40")
        return "\n".join(lines)

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
                f"N{self._next_block():05d} CYCLE81("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(abs(retract))}, {self._fmt(depth)}, "
                f"{self._fmt(dwell)})",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE81",
            ]
        else:
            lines = [
                f"N{self._next_block():05d} CYCLE83("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(abs(retract))}, {self._fmt(depth)}, "
                f", ,{self._fmt(1.0)}, ,1, ,1,1)",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE83",
            ]
        return "\n".join(lines)

    def format_footer(self) -> str:
        lines = [
            "",
            f"N{self._next_block():05d} M09",
            f"N{self._next_block():05d} M05",
            f"N{self._next_block():05d} G00 Z{self._fmt(self.safe_z_height)}",
            f"N{self._next_block():05d} G00 X0. Y0.",
            f"N{self._next_block():05d} M30",
        ]
        return "\n".join(lines)
