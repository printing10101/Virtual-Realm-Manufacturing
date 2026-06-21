"""G 代码（NC 文件）反向解析器：把 G 代码文本转为结构化刀路几何。

**用途**：
    - G 代码可视化（前端展示刀路）
    - G 代码审计（检查碰撞、超程、不合理参数）
    - G 代码转 DXF（CAM 反向工程）
    - 教学：解释 G 代码到底在做什么

**支持语法**：
    - **运动指令**：
        - ``G00`` 快速定位
        - ``G01`` 直线进给
        - ``G02`` 顺时针圆弧
        - ``G03`` 逆时针圆弧
        - ``G02.1/G03.1`` 渐开线（部分支持）
    - **坐标系 / 模式**：
        - ``G17/G18/G19`` 平面选择
        - ``G20/G21`` 英制/公制
        - ``G90/G91`` 绝对/增量
        - ``G54-G59`` 工件坐标系
    - **刀具 & 主轴**：
        - ``Txx M06`` 换刀
        - ``M03 Sxxxx`` 主轴正转 + 转速
        - ``M04`` 主轴反转
        - ``M05`` 主轴停
    - **辅助**：
        - ``M08/M09`` 冷却液开/关
        - ``Fxxxx`` 进给率
        - ``;`` 注释（单行）

**不完整支持**：
    - 固定循环（G73/G81-G89）— 仅记录不展开
    - 子程序（M98）— 仅记录不展开
    - 高级模式（G41/G42 半径补偿）— 仅记录
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# 词法：每个 G/M/T/S/F 字 + 后面的数字（无空格也识别）
_TOKEN_RE = re.compile(
    r"\s*(?P<word>[A-Z])(?P<number>-?\d+\.?\d*)",
    re.IGNORECASE,
)

# 括号注释：删除所有非嵌套的 (...) 块（G 代码标准不支持嵌套注释）
_PAREN_COMMENT_RE = re.compile(r"\([^()]*\)")


@dataclass
class ModalState:
    """当前模态状态：运动模式、坐标系、主轴、进给。"""

    motion_mode: str = "G00"          # 当前运动模式
    plane: str = "G17"                # 当前平面
    absolute: bool = True             # G90/G91
    units_metric: bool = True         # G21/G20
    coord_system: str = "G54"         # G54-G59
    coord_x: float = 0.0              # 工件坐标系偏移
    coord_y: float = 0.0
    coord_z: float = 0.0
    spindle_rpm: float = 0.0
    spindle_cw: bool = False
    feed_rate: float = 0.0
    coolant_on: bool = False
    current_tool: int = 0
    tool_length_offset: float = 0.0   # H 寄存器
    # 半径补偿
    cutter_compensation: Optional[str] = None  # "G41" / "G42" / None


@dataclass
class Segment:
    """一条刀路段。"""

    seq: int
    motion: str                       # G00/G01/G02/G03
    target: Tuple[float, float, float]
    feed: float
    # 仅圆弧：
    center: Optional[Tuple[float, float, float]] = None
    radius: Optional[float] = None
    clockwise: Optional[bool] = None
    # 元数据
    raw_line: str = ""
    tool: int = 0
    spindle_rpm: float = 0.0
    coolant_on: bool = False
    note: str = ""


@dataclass
class ParseResult:
    """G 代码反向解析结果。"""

    source: str = ""
    lines_total: int = 0
    lines_parsed: int = 0
    lines_skipped: int = 0
    modal_history: List[ModalState] = field(default_factory=list)
    segments: List[Segment] = field(default_factory=list)
    tool_changes: List[Tuple[int, int]] = field(
        default_factory=list
    )  # (line_no, tool_id)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    bounding_box: dict[str, float] = field(
        default_factory=dict
    )  # min_x/min_y/min_z/max_x/max_y/max_z

    def to_dict(self) -> dict:
        return {
            "source": self.source,
            "lines_total": self.lines_total,
            "lines_parsed": self.lines_parsed,
            "lines_skipped": self.lines_skipped,
            "segments_count": len(self.segments),
            "tool_changes_count": len(self.tool_changes),
            "tool_changes": self.tool_changes,
            "bounding_box": self.bounding_box,
            "warnings": self.warnings,
            "errors": self.errors,
        }


# ===========================================================================
# 词法 / 解析
# ===========================================================================


def _strip_comment(line: str) -> str:
    """去掉行末注释（';' 起和 '(' ')' 块）。

    G 代码注释格式：``(comment)``，不嵌套，但一行可能包含多个独立块，
    例如 ``G01 X1 (rough) Y2 (finish)``。之前实现用 ``split("(", 1)[0]``
    会把第一个 ``(`` 之后的所有内容（含后续运动参数）全部丢弃。
    """
    # 块注释 (...)：用正则删除所有非嵌套的 (...) 块
    line = _PAREN_COMMENT_RE.sub("", line)
    # 行注释 ;
    if ";" in line:
        line = line.split(";", 1)[0]
    return line.strip()


def _tokenize(line: str) -> List[Tuple[str, float]]:
    """把一行 G 代码拆成 [(字, 数值), ...] 列表。"""
    return [
        (m.group("word").upper(), float(m.group("number")))
        for m in _TOKEN_RE.finditer(line)
    ]


def _resolve_center(
    start: Tuple[float, float],
    target: Tuple[float, float],
    plane: str,
    cw: bool,
    i: Optional[float],
    j: Optional[float],
    r: Optional[float],
) -> Tuple[float, float]:
    """从 I/J/K 或 R 计算圆弧中心。

    Args:
        start: 弧起点（仅 XY 分量，调用方负责按平面选取）。
        target: 弧终点（仅 XY 分量，调用方负责按平面选取）。
        plane: 当前平面模态 ``G17`` / ``G18`` / ``G19``。
            - G17 (XY): I=X 偏移, J=Y 偏移
            - G18 (ZX): I=Z 偏移, K=X 偏移（调用方应传 (z, x) 分量）
            - G19 (YZ): J=Y 偏移, K=Z 偏移（调用方应传 (y, z) 分量）
            当前实现仅完整支持 G17；G18/G19 由调用方负责分量重排后
            仍以双分量传入，本函数按二维平面几何计算。
        cw: 顺时针为 True。
        i, j: 起点到圆心的增量坐标（按平面解释）。
        r: 圆弧半径（带符号：负值取劣弧）。

    Returns:
        圆心坐标（与输入分量顺序一致）。
    """
    if i is not None and j is not None:
        # I/J 模式：圆心 = 起点 + (I, J)
        return (start[0] + i, start[1] + j)
    if i is not None and j is None and plane != "G17":
        # G18/G19 平面：可能只提供 I/K 或 J/K 中的一个组合
        # 调用方应将另一分量作为 j 传入（已重排）
        return (start[0] + i, start[1])
    if j is not None and i is None and plane != "G17":
        return (start[0], start[1] + j)
    if r is not None:
        # R 模式：两解中按方向选一个
        import math
        dx = target[0] - start[0]
        dy = target[1] - start[1]
        d = math.hypot(dx, dy)
        if d == 0 or abs(r) * 2 < d - 1e-9:
            raise ValueError(
                f"invalid arc: chord={d:.4f}, R={r:.4f} (R 必须 >= chord/2)"
            )
        # 圆心到弦中点
        mx = (start[0] + target[0]) / 2
        my = (start[1] + target[1]) / 2
        # 弦垂线方向（垂直于 dx,dy）
        nx = -dy / d
        ny = dx / d
        h = math.sqrt(r * r - (d / 2) ** 2)
        # CW: 中心在弦左侧
        if cw:
            h = -h
        return (mx + nx * h, my + ny * h)
    raise ValueError("arc missing both I/J and R")


# ===========================================================================
# 公共 API
# ===========================================================================


def parse_gcode(
    text: str, source: str = "<inline>"
) -> ParseResult:
    """解析 G 代码文本。

    Args:
        text: G 代码文本（每行一条指令）
        source: 来源标签（仅用于显示）

    Returns:
        ParseResult（含 segments / tool_changes / warnings / errors）
    """
    result = ParseResult(source=source)
    modal = ModalState()
    modal_history: List[ModalState] = []
    seq = 0
    cur_pos: Tuple[float, float, float] = (0.0, 0.0, 0.0)
    min_x = min_y = min_z = float("inf")
    max_x = max_y = max_z = float("-inf")
    last_line_no = 0

    lines = text.splitlines()
    result.lines_total = len(lines)
    for line_no, raw in enumerate(lines, start=1):
        last_line_no = line_no
        line = _strip_comment(raw)
        if not line:
            continue
        try:
            words = _tokenize(line)
        except Exception as e:  # noqa: BLE001
            result.errors.append(f"line {line_no}: tokenize error: {e}")
            result.lines_skipped += 1
            continue
        if not words:
            continue

        # 提取参数
        x: Optional[float] = None
        y: Optional[float] = None
        z: Optional[float] = None
        i: Optional[float] = None
        j: Optional[float] = None
        k: Optional[float] = None
        r: Optional[float] = None
        for letter, val in words:
            uletter = letter
            if uletter == "X":
                x = val
            elif uletter == "Y":
                y = val
            elif uletter == "Z":
                z = val
            elif uletter == "I":
                i = val
            elif uletter == "J":
                j = val
            elif uletter == "K":
                k = val
            elif uletter == "R":
                r = val
            elif uletter == "F":
                modal.feed_rate = val
            elif uletter == "S":
                modal.spindle_rpm = val
            elif uletter == "T":
                modal.current_tool = int(val)
            elif uletter == "H":
                modal.tool_length_offset = val
            elif uletter == "G":
                # 保留小数以支持 G02.1 / G03.1 等子代码
                gcode_int = int(val)
                gcode_frac = round((val - gcode_int) * 10)
                if gcode_int in (0, 1, 2, 3):
                    if gcode_frac > 0:
                        modal.motion_mode = f"G{gcode_int:02d}.{gcode_frac}"
                    else:
                        modal.motion_mode = f"G0{gcode_int}"
                elif gcode_int in (17, 18, 19):
                    modal.plane = f"G{gcode_int:02d}"
                elif gcode_int == 20:
                    modal.units_metric = False
                elif gcode_int == 21:
                    modal.units_metric = True
                elif gcode_int == 90:
                    modal.absolute = True
                elif gcode_int == 91:
                    modal.absolute = False
                elif 54 <= gcode_int <= 59:
                    modal.coord_system = f"G{gcode_int}"
                elif gcode_int in (41, 42):
                    modal.cutter_compensation = f"G{gcode_int}"
                elif gcode_int in (40, 49):
                    modal.cutter_compensation = None
            elif uletter == "M":
                mcode = int(val)
                if mcode == 0 or mcode == 1:
                    pass
                elif mcode == 2 or mcode == 30:
                    pass  # 程序结束
                elif mcode == 3:
                    modal.spindle_cw = True
                elif mcode == 4:
                    modal.spindle_cw = False
                elif mcode == 5:
                    modal.spindle_cw = False
                    modal.spindle_rpm = 0.0
                elif mcode == 6:
                    result.tool_changes.append(
                        (line_no, modal.current_tool)
                    )
                elif mcode == 8:
                    modal.coolant_on = True
                elif mcode == 9:
                    modal.coolant_on = False

        # 计算目标位置
        try:
            new_pos: Tuple[float, float, float] = (
                cur_pos[0]
                + (x if x is not None and not modal.absolute else 0.0),
                cur_pos[1]
                + (y if y is not None and not modal.absolute else 0.0),
                cur_pos[2]
                + (z if z is not None and not modal.absolute else 0.0),
            )
            if x is not None and modal.absolute:
                new_pos = (x, new_pos[1], new_pos[2])
            if y is not None and modal.absolute:
                new_pos = (new_pos[0], y, new_pos[2])
            if z is not None and modal.absolute:
                new_pos = (new_pos[0], new_pos[1], z)
        except Exception as e:  # noqa: BLE001
            result.errors.append(
                f"line {line_no}: position calc error: {e}"
            )
            result.lines_skipped += 1
            continue

        # 只在有运动指令时记录 segment
        motion = modal.motion_mode
        if motion in ("G00", "G01"):
            # 仅当有 X/Y/Z 变化时记录
            if x is not None or y is not None or z is not None:
                seq += 1
                seg = Segment(
                    seq=seq,
                    motion=motion,
                    target=new_pos,
                    feed=(
                        modal.feed_rate
                        if motion == "G01"
                        else 0.0
                    ),
                    raw_line=raw,
                    tool=modal.current_tool,
                    spindle_rpm=modal.spindle_rpm,
                    coolant_on=modal.coolant_on,
                )
                result.segments.append(seg)
        elif motion in ("G02", "G03"):
            cw = motion == "G02"
            try:
                cx, cy = _resolve_center(
                    cur_pos[:2],
                    new_pos[:2],
                    modal.plane,
                    cw,
                    i,
                    j,
                    r,
                )
                import math
                radius = math.hypot(
                    cur_pos[0] - cx, cur_pos[1] - cy
                )
            except Exception as e:  # noqa: BLE001
                result.errors.append(
                    f"line {line_no}: arc center error: {e}"
                )
                result.lines_skipped += 1
                continue
            seq += 1
            seg = Segment(
                seq=seq,
                motion=motion,
                target=new_pos,
                center=(cx, cy, cur_pos[2]),
                radius=radius,
                clockwise=cw,
                feed=modal.feed_rate,
                raw_line=raw,
                tool=modal.current_tool,
                spindle_rpm=modal.spindle_rpm,
                coolant_on=modal.coolant_on,
            )
            result.segments.append(seg)
        elif motion in ("G02.1", "G03.1"):
            result.warnings.append(
                f"line {line_no}: 渐开线 G02.1/G03.1 未完整支持"
            )
        else:
            # 其他 G 码：仅记录模态，不产生段
            pass

        # 推进 cur_pos
        if (
            x is not None or y is not None or z is not None
        ):
            cur_pos = new_pos
            min_x = min(min_x, cur_pos[0])
            max_x = max(max_x, cur_pos[0])
            min_y = min(min_y, cur_pos[1])
            max_y = max(max_y, cur_pos[1])
            min_z = min(min_z, cur_pos[2])
            max_z = max(max_z, cur_pos[2])

        # 模态快照（每隔一段存一次）
        if len(modal_history) < 200:
            modal_history.append(_copy_modal(modal))
        result.lines_parsed += 1

    if min_x == float("inf"):
        min_x = min_y = min_z = 0.0
        max_x = max_y = max_z = 0.0
    result.bounding_box = {
        "min_x": min_x,
        "min_y": min_y,
        "min_z": min_z,
        "max_x": max_x,
        "max_y": max_y,
        "max_z": max_z,
        "width": max_x - min_x,
        "height": max_y - min_y,
        "depth": max_z - min_z,
    }
    result.modal_history = modal_history
    return result


def _copy_modal(m: ModalState) -> ModalState:
    return ModalState(
        motion_mode=m.motion_mode,
        plane=m.plane,
        absolute=m.absolute,
        units_metric=m.units_metric,
        coord_system=m.coord_system,
        coord_x=m.coord_x,
        coord_y=m.coord_y,
        coord_z=m.coord_z,
        spindle_rpm=m.spindle_rpm,
        spindle_cw=m.spindle_cw,
        feed_rate=m.feed_rate,
        coolant_on=m.coolant_on,
        current_tool=m.current_tool,
        tool_length_offset=m.tool_length_offset,
        cutter_compensation=m.cutter_compensation,
    )


# ===========================================================================
# 工具函数
# ===========================================================================


def to_dxf_like_segments(
    segments: List[Segment],
) -> List[dict]:
    """把段序列转成"DXF-like" 的几何段（给前端 2D 展示用）。

    每段返回：
        {"motion": "G00|G01|G02|G03", "from": [x, y], "to": [x, y],
         "center": [cx, cy]?, "radius": r?, "cw": bool?, "tool": int}
    """
    out: List[dict] = []
    cur: Tuple[float, float] = (0.0, 0.0)
    for s in segments:
        item: dict = {
            "motion": s.motion,
            "from": [cur[0], cur[1]],
            "to": [s.target[0], s.target[1]],
            "tool": s.tool,
        }
        if s.center is not None:
            item["center"] = [s.center[0], s.center[1]]
        if s.radius is not None:
            item["radius"] = s.radius
        if s.clockwise is not None:
            item["cw"] = s.clockwise
        out.append(item)
        cur = (s.target[0], s.target[1])
    return out


__all__ = [
    "ModalState",
    "Segment",
    "ParseResult",
    "parse_gcode",
    "to_dxf_like_segments",
]
