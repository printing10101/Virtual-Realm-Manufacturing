"""Heidenhain TNC CNC控制器后处理器。

实现Heidenhain TNC控制器特有的代码方言，包括：
- TOOL CALL刀具调用语法
- L（顺时针）/ CC（逆时针）圆弧插补
- CYCL DEF 200/203钻孔循环定义
- CYCL DEF 206攻丝循环
- CYCL DEF 202/209镗孔循环
- CYCL DEF 264螺纹加工循环
- LBL CALL/LBL 0标签子程序支持
- 符合Heidenhain独特的程序结构和指令格式
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.postprocessor.base import BasePostProcessor

logger = logging.getLogger(__name__)


class HeidenhainPostProcessor(BasePostProcessor):
    """Heidenhain TNC CNC控制器后处理器。

    生成符合Heidenhain TNC语法规范的程序代码。
    适配Heidenhain专用固定循环定义及子程序LBL CALL格式。
    """

    def __init__(
        self,
        decimal_places: int = 3,
        safe_z_height: float = 50.0,
        rapid_feed: float = 10000,
        config: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(decimal_places, safe_z_height, rapid_feed, config)
        self._block_counter = 0
        self._last_program_number = 1  # 与 format_header 默认值一致

    def _next_block(self) -> int:
        self._block_counter += 1
        return self._block_counter

    def format_header(self, program_number: int = 1) -> str:
        self._block_counter = 0
        self._last_program_number = program_number  # 记录供 format_footer 使用
        default_rpm = int(self.get_spindle_rpm())

        lines = [
            f"0  BEGIN PGM {program_number:04d} MM",
            "1  BLK FORM 0.1 Z X+0 Y+0 Z-50",
            "2  BLK FORM 0.2 X+100 Y+100 Z+0",
            f"3  ; PROGRAM {program_number} - {self._date_string()}",
            "4  ; POST: Heidenhain TNC",
            f"5  TOOL CALL 1 Z S{default_rpm}",
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
        default_rpm = int(self.get_spindle_rpm())

        n = self._next_block()
        lines = [
            f"{n}  TOOL CALL {tool_id} Z S{default_rpm}",
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
        cfg = self.get_cycle_config("drilling", "G83" if dwell > 0 else "G81")
        r_plane = self.safe_z_height
        peck_depth = cfg.get("peck_depth", 5.0)
        drill_feed = self._fmt(self.get_feed_rate(self.rapid_feed * 0.3))

        if dwell > 0:
            lines = [
                f"{self._next_block()}  CYCL DEF 200 DRILLING",
                f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
                f"{self._next_block()}     Q201={self._fmt(-abs(depth))}  ;DEPTH",
                f"{self._next_block()}     Q206={drill_feed}  ;FEED RATE",
                f"{self._next_block()}     Q202={self._fmt(peck_depth)}  ;PLUNGING DEPTH",
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
                f"{self._next_block()}     Q201={self._fmt(-abs(depth))}  ;DEPTH",
                f"{self._next_block()}     Q206={drill_feed}  ;FEED RATE",
                f"{self._next_block()}     Q202={self._fmt(peck_depth)}  ;PLUNGING DEPTH",
                f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
                f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
                f"{self._next_block()}  CYCL CALL",
            ]
        return "\n".join(lines)

    def format_cycle_tapping(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        pitch: float = 1.0,
        spindle_rpm: Optional[float] = None,
    ) -> str:
        cfg = self.get_cycle_config("tapping", "G84")
        rpm = self.get_spindle_rpm(spindle_rpm)
        r_plane = self.safe_z_height
        dwell = cfg.get("dwell_time", 0.0)

        lines = [
            f"{self._next_block()}  CYCL DEF 206 TAPPING NEW",
            f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
            f"{self._next_block()}     Q201={self._fmt(-abs(depth))}  ;DEPTH",
            f"{self._next_block()}     Q206={self._fmt(self.get_feed_rate(self.rapid_feed * 0.2))}  ;FEED RATE",
            f"{self._next_block()}     Q202={self._fmt(pitch)}  ;PITCH",
            f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
            f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
            f"{self._next_block()}     Q211={self._fmt(dwell)}  ;DWELL TIME AT DEPTH",
            f"{self._next_block()}     Q220={int(rpm)}  ;SPINDLE SPEED",
            f"{self._next_block()}  CYCL CALL",
        ]
        return "\n".join(lines)

    def format_cycle_boring(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        cycle_type: str = "G86",
        dwell: float = 0.5,
    ) -> str:
        cfg = self.get_cycle_config("boring", cycle_type)
        r_plane = self.safe_z_height
        orient = 1 if cfg.get("orient_spindle", False) else 0
        _shift_dist = cfg.get("shift_distance", 0.0)  # noqa: F841
        bore_feed = self._fmt(self.get_feed_rate(self.rapid_feed * 0.15))

        if cycle_type == "G86":
            lines = [
                f"{self._next_block()}  CYCL DEF 202 BORING",
                f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
                f"{self._next_block()}     Q201={self._fmt(-abs(depth))}  ;DEPTH",
                f"{self._next_block()}     Q206={bore_feed}  ;FEED RATE",
                f"{self._next_block()}     Q202={self._fmt(2.0)}  ;PLUNGING DEPTH",
                f"{self._next_block()}     Q210={self._fmt(0.0)}  ;DWELL TIME AT TOP",
                f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
                f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
                f"{self._next_block()}     Q211={self._fmt(dwell)}  ;DWELL TIME AT DEPTH",
                f"{self._next_block()}     Q214={orient}  ;SPINDLE ORIENTATION",
                f"{self._next_block()}  CYCL CALL",
            ]
        elif cycle_type == "G89":
            lines = [
                f"{self._next_block()}  CYCL DEF 209 BORING SPINDLE ORIENTED",
                f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
                f"{self._next_block()}     Q201={self._fmt(-abs(depth))}  ;DEPTH",
                f"{self._next_block()}     Q206={bore_feed}  ;FEED RATE",
                f"{self._next_block()}     Q202={self._fmt(2.0)}  ;PLUNGING DEPTH",
                f"{self._next_block()}     Q210={self._fmt(0.0)}  ;DWELL TIME AT TOP",
                f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
                f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
                f"{self._next_block()}     Q211={self._fmt(dwell)}  ;DWELL TIME AT DEPTH",
                f"{self._next_block()}     Q214={orient}  ;SPINDLE ORIENTATION",
                f"{self._next_block()}  CYCL CALL",
            ]
        else:
            lines = [
                f"{self._next_block()}  CYCL DEF 202 BORING",
                f"{self._next_block()}     Q200={self._fmt(r_plane)}",
                f"{self._next_block()}     Q201={self._fmt(-abs(depth))}",
                f"{self._next_block()}     Q206={bore_feed}",
                f"{self._next_block()}     Q202={self._fmt(2.0)}",
                f"{self._next_block()}     Q210={self._fmt(0.0)}",
                f"{self._next_block()}     Q203={self._fmt(0.0)}",
                f"{self._next_block()}     Q204={self._fmt(r_plane)}",
                f"{self._next_block()}     Q211={self._fmt(dwell)}",
                f"{self._next_block()}  CYCL CALL",
            ]

        return "\n".join(lines)

    def format_cycle_threading(
        self,
        x: float,
        y: float,
        depth: float,
        lead: float = 1.0,
        passes: Optional[int] = None,
        depth_cut_first: Optional[float] = None,
        depth_cut_last: Optional[float] = None,
        finishing_passes: Optional[int] = None,
        tool_angle: Optional[float] = None,
        taper: Optional[float] = None,
    ) -> str:
        cfg = self.get_cycle_config("threading", "G76")

        p = passes if passes is not None else cfg.get("passes", 5)
        d_first = depth_cut_first if depth_cut_first is not None else cfg.get("depth_cut_first", 0.2)
        d_last = depth_cut_last if depth_cut_last is not None else cfg.get("depth_cut_last", 0.05)
        finish = finishing_passes if finishing_passes is not None else cfg.get("finishing_passes", 2)
        angle = tool_angle if tool_angle is not None else cfg.get("tool_angle", 60.0)
        _taper_val = taper if taper is not None else cfg.get("taper", 0.0)  # noqa: F841
        _shift_axis = cfg.get("shift_axis")  # noqa: F841
        _shift_dist = cfg.get("shift_distance", 0.0)  # noqa: F841

        r_plane = self.safe_z_height
        _retract_type = cfg.get("retract_type", "feed")  # noqa: F841
        infeed = cfg.get("infeed_method", "radial")
        infeed_map = {"compound": 0, "radial": 1, "flank": 2}
        infeed_code = infeed_map.get(infeed, 1)

        lines = [
            f"{self._next_block()}  CYCL DEF 264 THREAD DRILLING/MILLING",
            f"{self._next_block()}     Q200={self._fmt(r_plane)}  ;SET-UP CLEARANCE",
            f"{self._next_block()}     Q201={self._fmt(-abs(depth))}  ;DEPTH OF THREAD",
            f"{self._next_block()}     Q206={self._fmt(self.get_feed_rate(self.rapid_feed * 0.05))}  ;FEED RATE",
            f"{self._next_block()}     Q202={self._fmt(lead)}  ;PITCH",
            f"{self._next_block()}     Q203={self._fmt(0.0)}  ;SURFACE COORDINATE",
            f"{self._next_block()}     Q204={self._fmt(r_plane)}  ;2ND SET-UP CLEARANCE",
            f"{self._next_block()}     Q211={self._fmt(0.0)}  ;DWELL TIME AT DEPTH",
            f"{self._next_block()}     Q239={self._fmt(d_first)}  ;FIRST PASS DEPTH",
            f"{self._next_block()}     Q240={self._fmt(d_last)}  ;LAST PASS DEPTH",
            f"{self._next_block()}     Q241={infeed_code}  ;INFEED METHOD",
            f"{self._next_block()}     Q242={p}  ;NUMBER OF PASSES",
            f"{self._next_block()}     Q243={finish}  ;FINISHING PASSES",
            f"{self._next_block()}     Q244={self._fmt(angle)}  ;TOOL ANGLE",
            f"{self._next_block()}  CYCL CALL",
        ]
        return "\n".join(lines)

    def format_subprogram_call(
        self,
        program_number: int,
        repeat: int = 1,
    ) -> str:
        sub_cfg = self.get_subprogram_config()
        prog_cfg = sub_cfg.get("program_number", {})
        repeat_cfg = sub_cfg.get("repeat", {})

        prog_min = prog_cfg.get("minimum", 1)
        prog_max = prog_cfg.get("maximum", 9999)
        rep_min = repeat_cfg.get("minimum", 1)
        rep_max = repeat_cfg.get("maximum", 999)

        program_number = max(prog_min, min(prog_max, program_number))
        repeat = max(rep_min, min(rep_max, repeat))

        call_fmt = sub_cfg.get("call_format", "LBL CALL {program_num:04d} REP{repeat}")
        try:
            formatted = call_fmt.format(program_num=program_number, repeat=repeat)
        except KeyError:
            formatted = f"LBL CALL {program_number:04d}"
            if repeat > 1:
                formatted += f" REP{repeat}"

        return f"{self._next_block()}  {formatted}"

    def format_subprogram_end(
        self,
        return_value: Optional[str] = None,
    ) -> str:
        sub_cfg = self.get_subprogram_config()
        end_code = sub_cfg.get("end_code", "LBL 0")
        return f"{self._next_block()}  {end_code}"

    def format_footer(self) -> str:
        lines = [
            "",
            f"{self._next_block()}  M09",
            f"{self._next_block()}  M05",
            f"{self._next_block()}  L  Z+{self._fmt(self.safe_z_height)} R0 FMAX",
            f"{self._next_block()}  L  X+0 Y+0 R0 FMAX",
            f"{self._next_block()}  M30",
            f"{self._next_block()}  END PGM {self._last_program_number:04d} MM",
        ]
        return "\n".join(lines)
