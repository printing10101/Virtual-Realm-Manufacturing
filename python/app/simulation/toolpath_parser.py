"""NC code parser for G-code toolpath extraction.

Parses Fanuc, Siemens, and Heidenhain format G-code, extracting toolpath
point sequences while maintaining modal command state. Supports G00/G01/G02/G03
motion commands, coordinate systems (G90/G91), and tool/feed/spindle parameters.

Supported G-codes:
    - G00: Rapid positioning
    - G01: Linear interpolation
    - G02: Clockwise circular interpolation
    - G03: Counterclockwise circular interpolation
    - G04: Dwell
    - G17/G18/G19: Plane selection (XY/XZ/YZ)
    - G21: Metric units
    - G90/G91: Absolute/incremental positioning

Example:
    >>> parser = ToolpathParser(controller_type="fanuc")
    >>> segments = parser.parse_gcode("N1 G00 X0 Y0 Z5\\nN2 G01 X10 Y0 Z-2 F500")
    >>> for seg in segments:
    ...     print(f"{seg.type}: {seg.start_point} -> {seg.end_point}")
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class ToolpathSegment:
    """A single segment of a CNC toolpath.

    Represents one motion command from the parsed G-code, including start
    and end positions and associated machining parameters.

    Attributes:
        type: Motion type - "rapid", "linear", "arc", or "dwell".
        start_point: (x, y, z) start coordinates in mm.
        end_point: (x, y, z) end coordinates in mm.
        feed_rate: Feed rate in mm/min (None for rapid moves).
        spindle_speed: Spindle speed in RPM (None if not specified).
        tool_id: Tool number (None if not specified).
        block_number: NC block/line number.
        g_code: Original G-code string (e.g., "G01").
    """

    type: str
    start_point: tuple[float, float, float]
    end_point: tuple[float, float, float]
    feed_rate: float | None = None
    spindle_speed: int | None = None
    tool_id: int | None = None
    block_number: int = 0
    g_code: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert the segment to a dictionary.

        Returns:
            Dictionary with all segment fields.
        """
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
        """Alias for start_point.

        Returns:
            Start coordinates (x, y, z).
        """
        return self.start_point

    @property
    def end(self) -> tuple[float, float, float]:
        """Alias for end_point.

        Returns:
            End coordinates (x, y, z).
        """
        return self.end_point


class ToolpathParser:
    """G-code parser that extracts toolpath segments from NC programs.

    Maintains modal state (current position, feed rate, spindle speed,
    motion mode, coordinate system) across lines. Supports Fanuc, Siemens,
    and Heidenhain controller formats.

    Attributes:
        controller_type: Controller dialect ("fanuc", "siemens", "heidenhain").

    Example:
        >>> parser = ToolpathParser(controller_type="fanuc")
        >>> gcode = "N1 G00 X0 Y0 Z5\\nN2 G01 X50 Y0 Z-2 F1000"
        >>> segments = parser.parse_gcode(gcode)
        >>> print(f"Parsed {len(segments)} segments")
    """

    _RE_WORD = re.compile(r"([A-Z])\s*([\-+]?\d+\.?\d*)")

    def __init__(self, controller_type: str = "fanuc") -> None:
        """Initialize the parser with a controller dialect.

        Args:
            controller_type: Controller type ("fanuc", "siemens", "heidenhain").
        """
        self.controller_type = controller_type
        self._reset_state()

    def _reset_state(self) -> None:
        """Reset all modal state variables to their default values."""
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
        """Parse G-code text into a list of toolpath segments.

        Processes the input line by line, skipping comments (lines starting
        with ';' or '(') and program header lines ('%' or 'O'). Maintains
        modal state throughout the parsing process.

        Args:
            gcode_text: The complete G-code program as a string.

        Returns:
            List of ToolpathSegment objects representing the toolpath.
        """
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
        """Extract G-code words (letter+number pairs) from a line.

        Args:
            line: A single G-code line (comments already stripped).

        Returns:
            Dictionary mapping word letters to their numeric values.
        """
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
        """Process parsed G-code words, updating modal state.

        Handles G-codes (motion, plane, positioning mode), axis coordinates
        (X, Y, Z), arc center parameters (I, J, K, R), and machining
        parameters (F, S, T).

        Args:
            words: Dictionary of parsed G-code words.
            prev_point: Previous tool position (x, y, z).

        Returns:
            The detected motion type ("rapid", "linear", "arc", "dwell")
            or None if no motion occurred on this line.
        """
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
