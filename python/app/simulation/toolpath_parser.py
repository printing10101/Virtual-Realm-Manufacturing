"""NC代码解析器。

解析Fanuc/Siemens/Heidenhain格式的G代码，
提取刀具路径点序列，维护模态指令状态。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolpathSegment:
    type: str
    start_point: tuple[float, float, float]
    end_point: tuple[float, float, float]
    feed_rate: float | None = None
    spindle_speed: int | None = None
    tool_id: int | None = None
    block_number: int = 0
    g_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "start_point": list(self.start_point),
            "end_point": list(self.end_point),
            "feed_rate": self.feed_rate,
            "spindle_speed": self.spindle_speed,
            "tool_id": self.tool_id,
            "block_number": self.block_number,
            "g_code": self.g_code,
        }

    @property
    def start(self) -> tuple[float, float, float]:
        return self.start_point

    @property
    def end(self) -> tuple[float, float, float]:
        return self.end_point


class ToolpathParser:
    _RE_WORD = re.compile(r"([A-Z])\s*([\-+]?\d+\.?\d*)")

    def __init__(self, controller_type: str = "fanuc") -> None:
        self.controller_type = controller_type
        self._reset_state()

    def _reset_state(self) -> None:
        self._x = 0.0
        self._y = 0.0
        self._z = 100.0
        self._i = 0.0
        self._j = 0.0
        self._k = 0.0
        self._r = 0.0
        self._feed = 500.0
        self._spindle = 0
        self._tool = 1
        self._motion = "G00"
        self._plane = "G17"
        self._units = "G21"
        self._absolute = True
        self._line_num = 0
        self._arc_center: tuple[float, float, float] = (0.0, 0.0, 0.0)

    def parse_gcode(
        self,
        gcode_text: str,
    ) -> list[ToolpathSegment]:
        self._reset_state()
        segments: list[ToolpathSegment] = []
        prev_point = (self._x, self._y, self._z)
        segment_start = prev_point

        for line in gcode_text.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("(") or stripped.startswith(";"):
                continue
            if stripped.startswith("%") or stripped.startswith("O"):
                continue

            self._line_num += 1
            words = self._parse_words(stripped)
            if not words:
                continue

            move_type = self._process_words(words, prev_point)
            new_point = (self._x, self._y, self._z)

            if move_type and (new_point != prev_point or move_type == "dwell"):
                seg = ToolpathSegment(
                    type=move_type,
                    start_point=segment_start,
                    end_point=new_point,
                    feed_rate=self._feed if move_type in ("linear", "arc") else None,
                    spindle_speed=self._spindle if self._spindle > 0 else None,
                    tool_id=self._tool,
                    block_number=self._line_num,
                    g_code=move_type.upper(),
                )
                segments.append(seg)
                segment_start = new_point
                prev_point = new_point

        return segments

    def _parse_words(self, line: str) -> dict[str, float]:
        words: dict[str, float] = {}
        for m in self._RE_WORD.finditer(line.upper()):
            key = m.group(1)
            try:
                val = float(m.group(2))
            except ValueError:
                continue
            words[key] = val
        return words

    def _process_words(
        self,
        words: dict[str, float],
        prev_point: tuple[float, float, float],
    ) -> str | None:
        move_type = None

        if "G" in words:
            g = int(words["G"])
            if g in (0,):
                move_type = "rapid"
                self._motion = "G00"
            elif g in (1,):
                move_type = "linear"
                self._motion = "G01"
            elif g in (2, 3):
                move_type = "arc"
                self._motion = f"G0{g}"
            elif g == 4:
                move_type = "dwell"
                self._motion = "G04"
            elif g == 80:
                self._motion = "G00"
            elif g in (17, 18, 19):
                self._plane = f"G{g}"
            elif g == 90:
                self._absolute = True
            elif g == 91:
                self._absolute = False

        if not move_type and self._motion in ("G00",):
            if any(k in words for k in ("X", "Y", "Z")):
                move_type = "rapid"
        elif not move_type and self._motion == "G01":
            if any(k in words for k in ("X", "Y", "Z")):
                move_type = "linear"

        if "X" in words:
            if self._absolute:
                self._x = words["X"]
            else:
                self._x += words["X"]
        if "Y" in words:
            if self._absolute:
                self._y = words["Y"]
            else:
                self._y += words["Y"]
        if "Z" in words:
            if self._absolute:
                self._z = words["Z"]
            else:
                self._z += words["Z"]

        if "I" in words:
            self._i = words["I"]
        if "J" in words:
            self._j = words["J"]
        if "K" in words:
            self._k = words["K"]
        if "R" in words:
            self._r = words["R"]

        if move_type == "arc":
            if "R" in words and "I" not in words and "J" not in words:
                r_val = self._r
                px, py = prev_point[0], prev_point[1]
                dx = self._x - px
                dy = self._y - py
                chord_sq = dx * dx + dy * dy
                if chord_sq > 4 * r_val * r_val:
                    r_val = max(abs(r_val), (chord_sq**0.5) / 2 + 0.001)
                h = max((r_val * r_val - chord_sq / 4) ** 0.5, 0)
                mx = (px + self._x) / 2
                my = (py + self._y) / 2
                if self._motion == "G02":
                    self._arc_center = (
                        mx - dy * h / (chord_sq**0.5) if chord_sq > 0 else mx,
                        my + dx * h / (chord_sq**0.5) if chord_sq > 0 else my,
                        prev_point[2],
                    )
                else:
                    self._arc_center = (
                        mx + dy * h / (chord_sq**0.5) if chord_sq > 0 else mx,
                        my - dx * h / (chord_sq**0.5) if chord_sq > 0 else my,
                        prev_point[2],
                    )
            else:
                self._arc_center = (
                    prev_point[0] + self._i,
                    prev_point[1] + self._j,
                    prev_point[2] + self._k,
                )

        if "F" in words:
            self._feed = words["F"]
        if "S" in words:
            self._spindle = int(words["S"])
        if "T" in words:
            self._tool = int(words["T"])

        return move_type
