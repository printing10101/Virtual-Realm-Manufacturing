"""Siemens 840D CNC控制器后处理器。

实现Siemens 840D控制器特有的G代码方言，包括：
- $TC_DP6刀具表数据调用
- G41/G42配合DISC偏置
- G02/G03 CR=圆心半径模式
- CYCLE81/CYCLE83钻孔循环
- CYCLE84攻丝循环
- CYCLE86/CYCLE89镗孔循环
- CYCLE76螺纹加工循环
- CYCLE_CALL子程序调用和M17返回
- 符合Siemens程序段号及参数表示方式
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional, Tuple

from app.postprocessor.base import BasePostProcessor

logger = logging.getLogger(__name__)


class SiemensPostProcessor(BasePostProcessor):
    """Siemens 840D CNC控制器后处理器。

    生成符合Siemens 840D语法规范的G代码。
    支持Siemens特殊循环CYCLE8x格式及宏程序。
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

    def _next_block(self) -> int:
        self._block_counter += 10
        return self._block_counter

    def format_header(self, program_number: int = 1) -> str:
        self._block_counter = 0
        default_rpm = int(self.get_spindle_rpm())

        lines = [
            f"N{self._next_block():05d} ; PROGRAM {program_number} - {self._date_string()}",
            f"N{self._next_block():05d} ; POST: Siemens 840D",
            f"N{self._next_block():05d} G17 G40 G90 G94",
            f"N{self._next_block():05d} G00 Z{self._fmt(self.safe_z_height)}",
            f"N{self._next_block():05d} G00 X0. Y0.",
            f"N{self._next_block():05d} M03 S{default_rpm}",
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
        radius = self._calc_arc_radius(end, center)
        feed = self._fmt(self.get_feed_rate(self.rapid_feed))
        return (
            f"N{self._next_block():05d} {g_code} "
            f"X{self._fmt(end[0])} Y{self._fmt(end[1])} "
            f"CR={self._fmt(radius)} F{feed}"
        )

    def format_coolant(self, state: str) -> str:
        n = self._next_block()
        code = self._format_coolant(state) or "M09"
        return f"N{n:05d} {code}"

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
        # On Siemens 840D, CYCLE81 is the simple drilling cycle that
        # is normally paired with a dwell at the bottom of the hole.
        # CYCLE83 is the deep-hole peck-drilling cycle used when no
        # dwell is requested.
        cycle_code = "CYCLE81" if dwell > 0 else "CYCLE83"
        cfg = self.get_cycle_config("drilling", cycle_code)
        r_plane = self.safe_z_height
        peck_depth = cfg.get("peck_depth", 5.0)
        retract_dist = cfg.get("retract_distance", 1.0)
        drill_feed = self._fmt(self.get_feed_rate(self.rapid_feed * 0.3))

        if dwell > 0:
            lines = [
                f"N{self._next_block():05d} CYCLE81("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(retract_dist)}, {self._fmt(-abs(depth))}, "
                f"{drill_feed}, {self._fmt(dwell)})",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE81",
            ]
        else:
            lines = [
                f"N{self._next_block():05d} CYCLE83("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(retract_dist)}, {self._fmt(-abs(depth))}, "
                f"{self._fmt(-abs(depth))}, ,{self._fmt(peck_depth)}, "
                f", ,{self._fmt(0.0)}, ,1, ,1,1)",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE83",
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
        spindle_dir = 3 if cfg.get("spindle_direction", "M03") == "M03" else 4
        dwell = cfg.get("dwell_time", 0.0)

        lines = [
            f"N{self._next_block():05d} CYCLE84("
            f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
            f"{self._fmt(1.0)}, {self._fmt(-abs(depth))}, , "
            f"{spindle_dir}, , , "
            f"{self._fmt(pitch)}, , "
            f"{self._fmt(dwell)}, {int(rpm)}, {int(rpm)})",
            f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
            f"N{self._next_block():05d} CYCLE84",
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
        _retract_mode = cfg.get("retract_mode", "G98")  # noqa: F841  # noqa: F841
        orient_spindle = 1 if cfg.get("orient_spindle", False) else 0
        shift_axis = cfg.get("shift_axis")
        shift_dist = cfg.get("shift_distance", 0.0)
        bore_feed = self._fmt(self.get_feed_rate(self.rapid_feed * 0.15))

        if cycle_type == "G86":
            dx = self._fmt(shift_dist) if shift_axis == "X" else self._fmt(0.0)
            dy = self._fmt(shift_dist) if shift_axis == "Y" else self._fmt(0.0)
            lines = [
                f"N{self._next_block():05d} CYCLE86("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(1.0)}, {self._fmt(-abs(depth))}, , "
                f"{orient_spindle}, {dx}, {dy}, "
                f"{self._fmt(dwell)}, , , "
                f"{bore_feed})",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE86",
            ]
        elif cycle_type == "G89":
            lines = [
                f"N{self._next_block():05d} CYCLE89("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(1.0)}, {self._fmt(-abs(depth))}, "
                f"{self._fmt(dwell)}, {bore_feed})",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE89",
            ]
        else:
            lines = [
                f"N{self._next_block():05d} CYCLE86("
                f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
                f"{self._fmt(1.0)}, {self._fmt(-abs(depth))}, , "
                f"0, 0, 0, 0, , , "
                f"{bore_feed})",
                f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
                f"N{self._next_block():05d} CYCLE86",
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
        taper_val = taper if taper is not None else cfg.get("taper", 0.0)
        shift_axis = cfg.get("shift_axis", "X")
        shift_dist = cfg.get("shift_distance", 0.1)

        r_plane = self.safe_z_height
        _retract_mode = cfg.get("retract_mode", "G99")  # noqa: F841
        infeed = cfg.get("infeed_method", "radial")
        infeed_map = {"compound": 1, "radial": 2, "flank": 3}
        _infeed_code = infeed_map.get(infeed, 2)  # noqa: F841

        dx = self._fmt(shift_dist) if shift_axis == "X" else self._fmt(0.0)
        dy = self._fmt(shift_dist) if shift_axis == "Y" else self._fmt(0.0)

        lines = [
            f"N{self._next_block():05d} CYCLE76("
            f"{self._fmt(r_plane)}, {self._fmt(0.0)}, "
            f"{self._fmt(1.0)}, {self._fmt(-abs(depth))}, , "
            f"1, {dx}, {dy}, "
            f"1, {self._fmt(lead)}, "
            f"{-int(angle)}, {self._fmt(taper_val)}, "
            f"{p}, {self._fmt(d_first)}, "
            f"{self._fmt(d_last)}, {finish})",
            f"N{self._next_block():05d} G00 X{self._fmt(x)} Y{self._fmt(y)}",
            f"N{self._next_block():05d} CYCLE76",
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
        rep_max = repeat_cfg.get("maximum", 9999)

        program_number = max(prog_min, min(prog_max, program_number))
        repeat = max(rep_min, min(rep_max, repeat))

        return f"N{self._next_block():05d} L{program_number:04d} P{repeat}"

    def format_subprogram_end(
        self,
        return_value: Optional[str] = None,
    ) -> str:
        sub_cfg = self.get_subprogram_config()
        end_code = sub_cfg.get("end_code", "M17")
        return f"N{self._next_block():05d} {end_code}"

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
