"""Heidenhain TNC640 hooks — 对话式编程（CYCL DEF / TOOL CALL）。

Heidenhain TNC640 与 Fanuc/Siemens 的差异：
1. 编程风格是对话式：CYCL DEF 200 DRILLING / CYCL DEF 240 TAPPING；
2. 换刀用 TOOL CALL（刀具名 + Z/S 主轴参数），而非 T 指令；
3. 程序头用 BEGIN PGM ... MM 结尾用 END PGM ...；
4. 深孔钻用 CYCL DEF 200（DRILLING）与 241（DRILLING DEEP）；
5. 坐标用绝对/增量混合，半径用 R 而非 I/J/K。

hooks 方法以方言实例为 self，可访问 _fmt / get_spindle_rpm /
get_feed_rate / get_cycle_config / rapid_feed / safe_z_height。
"""

from __future__ import annotations


class HeidenhainTNC640Hooks:
    """Heidenhain TNC640 对话式循环 hooks。"""

    def format_cycle_drill(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        dwell: float = 0.0,
        pecking: bool = True,
    ) -> str:
        """钻孔：CYCL DEF 200 DRILLING（普通）/ 241 DEEP HOLE（啄钻）。"""
        cfg = self.get_cycle_config("drilling", "200")
        feed = self._fmt(self.get_feed_rate(self.rapid_feed * 0.3))
        z_end = self._fmt(-abs(depth))
        if pecking:
            peck_depth = cfg.get("peck_depth", 5.0)
            return (
                f"CYCL DEF 241 DRILLING DEEP\n"
                f"Q200=2.0 ;SET-UP CLEARANCE\n"
                f"Q201={z_end} ;DEPTH\n"
                f"Q206={feed} ;FEED RATE\n"
                f"Q202={self._fmt(peck_depth)} ;PLNGNG DEPTH"
            )
        return (
            f"CYCL DEF 200 DRILLING\n"
            f"Q200=2.0 ;SET-UP CLEARANCE\n"
            f"Q201={z_end} ;DEPTH\n"
            f"Q206={feed} ;FEED RATE"
        )

    def format_cycle_tapping(
        self,
        x: float,
        y: float,
        z: float,
        depth: float,
        dwell: float = 0.0,
    ) -> str:
        """刚性攻丝：CYCL DEF 240 TAPPING（带 Q239 螺距）。"""
        cfg = self.get_cycle_config("tapping", "240")
        rpm = self.get_spindle_rpm()
        feed = self._fmt(self.get_feed_rate(rpm))
        z_end = self._fmt(-abs(depth))
        return (
            f"CYCL DEF 240 TAPPING\n"
            f"Q200=2.0 ;SET-UP CLEARANCE\n"
            f"Q201={z_end} ;DEPTH\n"
            f"Q206={feed} ;FEED RATE\n"
            f"Q239=1.5 ;PITCH"
        )

    def format_tool_change(
        self,
        tool_number: int,
        length_comp: float = 0.0,
        safe_z: float = 0.0,
    ) -> str:
        """Heidenhain 换刀：TOOL CALL（刀具号 + Z 安全高度 + 主轴转速）。"""
        rpm = int(self.get_spindle_rpm())
        return f"TOOL CALL {int(tool_number):02d} Z S{rpm}"

    def format_probe(self, probe_number: int = 1, x_pos: float = 0.0) -> str:
        """测头循环：TCH PROBE（Heidenhain 特色）。"""
        return f"TCH PROBE {probe_number} X{self._fmt(x_pos)}"


class HeidenhainHeaderHooks:
    """Heidenhain TNC640 程序头/尾 hooks。"""

    def format_header(self) -> str:
        """程序头：BEGIN PGM ... MM。"""
        num = self._program_number_safe()
        return f"BEGIN PGM {num} MM"

    def format_footer(self) -> str:
        """程序尾：END PGM ... MM。"""
        num = self._program_number_safe()
        return f"END PGM {num} MM"

    def _program_number_safe(self) -> str:
        """程序号安全格式化。"""
        num = int(getattr(self, "program_number", 1000))
        return f"{num:04d}"


__all__ = ["HeidenhainTNC640Hooks", "HeidenhainHeaderHooks"]
