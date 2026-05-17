"""Heidenhain TNC CNC控制器后处理器。

实现Heidenhain TNC控制器特有的代码方言，包括：
- TOOL CALL刀具调用语法
- L（顺时针）/ CC（逆时针）圆弧插补
- CYCLE DEF钻孔循环定义
- 符合Heidenhain独特的程序结构和指令格式
"""

from __future__ import annotations

from typing import Tuple

from app.postprocessor.base import BasePostProcessor


class HeidenhainPostProcessor(BasePostProcessor):
    """Heidenhain TNC CNC控制器后处理器。

    生成符合Heidenhain TNC语法规范的程序代码。
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
        self._block_counter += 1
        return self._block_counter

    def format_header(self, program_number: int = 1) -> str:
        self._block_counter = 0
        lines = [
            f"0  BEGIN PGM {program_number:04d} MM",
            "1  BLK FORM 0.1 Z X+0 Y+0 Z-50",
            "2  BLK FORM 0.2 X+100 Y+100 Z+0",
            f"3  ; PROGRAM {program_number} - {self._date_string()}",
            "4  ; POST: Heidenhain TNC",
            "5  TOOL CALL 1 Z S8000",
            f"6  L  Z+{self._fmt(self.safe_z_height)} R0 FMAX",
            "7  L  X+0 Y+0 R0 FMAX",
            "8  M08",
            "",
        ]
        return "\n".join(lines)

    def format_tool_change(
        self,
        tool_id: int,
        length_comp: float = 0.0,
        radius_comp: float = 0.0,
    ) -> str:
        n = self._next_block()
        lines = [
            f"{n}  TOOL CALL {tool_id} Z S8000",
            f"{self._next_block()}  L  Z+{self._fmt(self.safe_z_height)} R0 FMAX",
            f"{self._next_block()}  L  X+0 Y+0 R0 FMAX",
        ]
        return "\n".join(lines)

    def format_arc(
        self,
        start: Tuple[float, float, float],
        end: Tuple[float, float, float],
        center: Tuple[float, float, float],
        clockwise: bool = True,
    ) -> str:
        if clockwise:
            return (
                f"{self._next_block()}  L  X+{self._fmt(end[0])} "
                f"Y+{self._fmt(end[1])} F{self._fmt(self.rapid_feed)}"
            )

        n = self._next_block()
        lines = [
            f"{n}  CC  X+{self._fmt(center[0])} Y+{self._fmt(center[1])}",
            f"{self._next_block()}  C  X+{self._fmt(end[0])} "
            f"Y+{self._fmt(end[1])} F{self._fmt(self.rapid_feed)}",
        ]
        return "\n".join(lines)

    def format_coolant(self, state: str) -> str:
        return self._format_coolant(state) or "M09"

    def format_tool_compensation(
        self,
        length_offset: int = 0,
        radius_offset: int = 0,
    ) -> str:
        if length_offset > 0 or radius_offset > 0:
            parts = ["TOOL CALL 1 Z"]
            if radius_offset > 0:
                parts.append(f"DR+{radius_offset}")
            return " ".join(parts)
        return "TOOL CALL 0 Z"

    def format_cycle_drill(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        dwell: float = 0.0,
    ) -> str:
        r_plane = self.safe_z_height

        if dwell > 0:
            lines = [
                f"{self._next_block()}  CYCL DEF 200 DRILLING",
                f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
                f"{self._next_block()}     Q201={self._fmt(depth)}  ;DEPTH",
                f"{self._next_block()}     Q206={self._fmt(self.rapid_feed * 0.3)}  ;FEED RATE",
                f"{self._next_block()}     Q202={self._fmt(depth * 0.3)}  ;PLUNGING DEPTH",
                f"{self._next_block()}     Q210={self._fmt(dwell)}  ;DWELL TIME AT TOP",
                f"{self._next_block()}     Q211={self._fmt(dwell)}  ;DWELL TIME AT DEPTH",
                f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
                f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
                f"{self._next_block()}  CYCL CALL",
            ]
        else:
            lines = [
                f"{self._next_block()}  CYCL DEF 203 UNIVERSAL DRILLING",
                f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
                f"{self._next_block()}     Q201={self._fmt(depth)}  ;DEPTH",
                f"{self._next_block()}     Q206={self._fmt(self.rapid_feed * 0.3)}  ;FEED RATE",
                f"{self._next_block()}     Q202={self._fmt(depth * 0.3)}  ;PLUNGING DEPTH",
                f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
                f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
                f"{self._next_block()}  CYCL CALL",
            ]
        return "\n".join(lines)

    def format_footer(self) -> str:
        lines = [
            "",
            f"{self._next_block()}  M09",
            f"{self._next_block()}  M05",
            f"{self._next_block()}  L  Z+{self._fmt(self.safe_z_height)} R0 FMAX",
            f"{self._next_block()}  L  X+0 Y+0 R0 FMAX",
            f"{self._next_block()}  M30",
            f"{self._next_block()}  END PGM {0:04d} MM",
        ]
        return "\n".join(lines)
