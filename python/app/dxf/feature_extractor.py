"""加工特征提取模块。

基于DXF解析结果中的几何实体和尺寸标注，识别加工特征。
实现孔特征和平面特征的自动提取算法。

特征识别策略：
1. 孔特征：关联圆实体与尺寸标注 → 提取直径 → 推断深度
2. 平面特征：检测矩形轮廓 → 提取长宽尺寸

输出与process_planning模块的MachiningFeature格式完全兼容。
"""

from __future__ import annotations

import logging
import math
import re
from dataclasses import dataclass, field
from typing import Any

from app.dxf.dxf_parser import (
    DxfParseResult,
    DxfDimension,
    DxfLine,
)
from app.dxf.exceptions import DxfFeatureError

logger = logging.getLogger(__name__)

PROXIMITY_THRESHOLD = 15.0
RECTANGLE_ANGLE_TOLERANCE = 2.0
RECTANGLE_LENGTH_TOLERANCE = 5.0


@dataclass
class HoleFeatureInfo:
    """孔特征信息。

    Attributes:
        hole_id: 孔标识符
        center_x: 圆心X坐标
        center_y: 圆心Y坐标
        diameter: 孔径(直径，mm)
        depth: 孔深(mm)，通孔为0
        depth_inferred: 深度是否由推断得出
        tolerance_grade: 公差等级
        hole_type: 孔类型 (through_hole/blind_hole/counterbore/center_hole)
        surface: 所在加工面
        layer: 原始图层
        associated_dim_handle: 关联尺寸标注句柄
        dimension_text: 尺寸标注文本
    """
    hole_id: str
    center_x: float
    center_y: float
    diameter: float
    depth: float = 0.0
    depth_inferred: bool = True
    tolerance_grade: str = "IT8"
    hole_type: str = "through_hole"
    surface: str = "A"
    layer: str = "0"
    associated_dim_handle: str = ""
    dimension_text: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "hole_id": self.hole_id,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "diameter": self.diameter,
            "depth": self.depth,
            "depth_inferred": self.depth_inferred,
            "tolerance_grade": self.tolerance_grade,
            "hole_type": self.hole_type,
            "surface": self.surface,
            "layer": self.layer,
            "dimension_text": self.dimension_text,
        }


@dataclass
class PlaneFeatureInfo:
    """平面特征信息（矩形轮廓）。

    Attributes:
        plane_id: 平面标识符
        center_x: 中心X坐标
        center_y: 中心Y坐标
        length: 长度(X方向)
        width: 宽度(Y方向)
        surface: 所在加工面
        layer: 原始图层
    """
    plane_id: str
    center_x: float
    center_y: float
    length: float
    width: float
    surface: str = "A"
    layer: str = "0"

    def to_dict(self) -> dict[str, Any]:
        return {
            "plane_id": self.plane_id,
            "center_x": self.center_x,
            "center_y": self.center_y,
            "length": self.length,
            "width": self.width,
            "surface": self.surface,
            "layer": self.layer,
        }


@dataclass
class FeatureExtractionResult:
    """特征提取结果。

    Attributes:
        holes: 孔特征列表
        planes: 平面特征列表
        overall_length: 零件总长(X方向)
        overall_width: 零件总宽(Y方向)
        overall_height: 推断的零件高度(Z方向)
        height_inferred: 高度是否由推断得出
        warnings: 提取过程中的警告
        errors: 提取过程中的错误
    """
    holes: list[HoleFeatureInfo] = field(default_factory=list)
    planes: list[PlaneFeatureInfo] = field(default_factory=list)
    overall_length: float = 0.0
    overall_width: float = 0.0
    overall_height: float = 10.0
    height_inferred: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0

    @property
    def hole_count(self) -> int:
        return len(self.holes)

    @property
    def plane_count(self) -> int:
        return len(self.planes)

    def to_dict(self) -> dict[str, Any]:
        return {
            "hole_count": self.hole_count,
            "plane_count": self.plane_count,
            "overall_length": self.overall_length,
            "overall_width": self.overall_width,
            "overall_height": self.overall_height,
            "height_inferred": self.height_inferred,
            "holes": [h.to_dict() for h in self.holes],
            "planes": [p.to_dict() for p in self.planes],
            "warnings": self.warnings,
            "errors": self.errors,
        }


class FeatureExtractor:
    """加工特征提取器。

    基于DXF解析结果，通过规则匹配算法识别：
    1. 孔特征——关联圆与尺寸标注
    2. 平面特征——检测矩形轮廓

    使用方式:
        extractor = FeatureExtractor()
        features = extractor.extract(parse_result)
        for hole in features.holes:
            print(f"孔: {hole.hole_id}, 直径={hole.diameter}mm")
    """

    DEFAULT_DEPTH_RATIO = 3.0
    MIN_DEPTH = 5.0
    MAX_DEPTH = 200.0
    DEFAULT_PLATE_THICKNESS = 10.0

    def __init__(self) -> None:
        logger.info("FeatureExtractor初始化完成")

    def extract(self, parse_result: DxfParseResult) -> FeatureExtractionResult:
        """从DXF解析结果中提取加工特征。

        Args:
            parse_result: DxfParser的解析结果

        Returns:
            FeatureExtractionResult: 包含孔和平面特征列表

        Raises:
            DxfFeatureError: 输入数据无效
        """
        if parse_result is None:
            raise DxfFeatureError("DXF解析结果为空，无法提取特征。"
                                  "请先调用DxfParser.parse()获取解析结果。")

        result = FeatureExtractionResult()

        if parse_result.total_entities == 0:
            result.errors.append("DXF文件中无几何实体，无法提取加工特征")
            return result

        try:
            self._extract_overall_dimensions(parse_result, result)
            self._extract_plane_features(parse_result, result)
            self._extract_hole_features(parse_result, result)
        except Exception as e:
            # 兜底捕获：特征提取涉及几何运算/属性访问，异常类型多源
            # (AttributeError/ValueError/TypeError/cadquery 异常等)
            # 任何阶段失败都通过 errors 字段暴露给上层，特征提取整体标记为失败
            result.errors.append(f"特征提取过程中发生异常: {e}")
            logger.error("特征提取异常: %s", e, exc_info=True)

        if not result.holes and not result.planes:
            result.warnings.append(
                "未识别到任何孔特征或平面特征。可能原因："
                "1) DXF中无可识别的圆或矩形轮廓；"
                "2) 几何实体过于分散或尺寸标注缺失"
            )

        logger.info(
            "特征提取完成: 孔=%d, 平面=%d, 外形=%.1fx%.1fx%.1f",
            result.hole_count,
            result.plane_count,
            result.overall_length,
            result.overall_width,
            result.overall_height,
        )
        return result

    def _extract_overall_dimensions(
        self,
        parse_result: DxfParseResult,
        result: FeatureExtractionResult,
    ) -> None:
        """从图形范围推断零件整体尺寸。

        优先从尺寸标注中提取，标注缺失时使用几何边界。
        """
        extents = parse_result.extents
        result.overall_length = extents.get("width", 100.0)
        result.overall_width = extents.get("height", 80.0)

        dim_texts = [d.text for d in parse_result.dimensions if d.text]
        numbers = []
        for text in dim_texts:
            found = re.findall(r'[\d.]+', text)
            numbers.extend(float(n) for n in found)

        if numbers and len(numbers) >= 2:
            sorted_nums = sorted(numbers, reverse=True)
            max_dim = sorted_nums[0]
            second_dim = sorted_nums[1] if len(sorted_nums) > 1 else max_dim * 0.6
            if max_dim > result.overall_length * 0.8:
                result.overall_length = max_dim
            if second_dim > result.overall_width * 0.8:
                result.overall_width = second_dim

        result.overall_height = self.DEFAULT_PLATE_THICKNESS
        result.height_inferred = True

        for dim in parse_result.dimensions:
            if dim.dim_type in ("LINEAR_ROTATED", "ALIGNED"):
                if "厚" in dim.text or "深" in dim.text or "H" in dim.text.upper():
                    try:
                        nums = re.findall(r'[\d.]+', dim.text)
                        if nums:
                            result.overall_height = float(nums[0])
                            result.height_inferred = False
                            break
                    except (ValueError, IndexError) as parse_err:
                        # 解析厚/深尺寸文本失败时，保留默认值并继续
                        logger.debug(
                            "Failed to parse height dimension text %r: %s",
                            dim.text,
                            parse_err,
                            exc_info=True,
                        )

        if result.overall_length < 1.0 or result.overall_width < 1.0:
            result.warnings.append(
                f"推断的零件尺寸异常(长={result.overall_length:.1f}mm, "
                f"宽={result.overall_width:.1f}mm)，请检查DXF文件内容"
            )

    def _extract_hole_features(
        self,
        parse_result: DxfParseResult,
        result: FeatureExtractionResult,
    ) -> None:
        """识别孔特征：将圆关联到尺寸标注并提取参数。"""
        if not parse_result.circles:
            return

        dim_map = self._build_dimension_proximity_map(parse_result)
        hole_index = 0

        for circle in parse_result.circles:
            hole_index += 1
            hole_id = f"HOLE_{hole_index:03d}"

            diameter = circle.radius * 2.0
            depth = self.DEFAULT_DEPTH_RATIO * diameter
            depth = max(self.MIN_DEPTH, min(depth, self.MAX_DEPTH))
            tolerance_grade = "IT8"
            hole_type = "through_hole" if depth >= result.overall_height * 0.9 else "blind_hole"
            dim_text = ""
            dim_handle = ""
            depth_inferred = True

            matched_dim = dim_map.get(circle.handle)
            if matched_dim:
                dim_handle = matched_dim.handle
                dim_text = matched_dim.text

                if matched_dim.dim_type == "DIAMETER":
                    if matched_dim.measurement > 0:
                        diameter = matched_dim.measurement
                elif matched_dim.measurement > 0:
                    if abs(matched_dim.measurement - diameter) / diameter < 0.5:
                        diameter = matched_dim.measurement

                depth_nums = re.findall(r'[\d.]+', dim_text)
                if len(depth_nums) >= 2:
                    try:
                        potential_depth = float(depth_nums[-1])
                        if 3.0 < potential_depth < 500.0 and potential_depth != diameter:
                            depth = potential_depth
                            depth_inferred = False
                    except ValueError as depth_err:
                        # 深度候选解析失败时回退到推断深度，记录以便排查
                        logger.debug(
                            "Failed to parse hole depth candidate %r: %s",
                            dim_text,
                            depth_err,
                            exc_info=True,
                        )

                if "通孔" in dim_text or "THRU" in dim_text.upper():
                    hole_type = "through_hole"
                    depth = result.overall_height
                    depth_inferred = True
                elif "盲孔" in dim_text or "BLIND" in dim_text.upper():
                    hole_type = "blind_hole"
                elif is_counterbore_text(dim_text) or "沉头" in dim_text:
                    hole_type = "counterbore"

                _tolerance = extract_tolerance_from_text(dim_text)
                if _tolerance:
                    tolerance_grade = _tolerance

            hole = HoleFeatureInfo(
                hole_id=hole_id,
                center_x=circle.center[0],
                center_y=circle.center[1],
                diameter=round(diameter, 4),
                depth=round(depth, 4),
                depth_inferred=depth_inferred,
                tolerance_grade=tolerance_grade,
                hole_type=hole_type,
                surface="A",
                layer=circle.layer,
                associated_dim_handle=dim_handle,
                dimension_text=dim_text,
            )
            result.holes.append(hole)

        if not result.holes:
            result.warnings.append("未识别到任何孔特征")
        else:
            holes_with_dim = sum(1 for h in result.holes if h.associated_dim_handle)
            if holes_with_dim < len(result.holes):
                result.warnings.append(
                    f"{len(result.holes) - holes_with_dim}个孔缺少尺寸标注，"
                    f"使用几何测量值作为孔径"
                )
            inferred_depth_count = sum(1 for h in result.holes if h.depth_inferred)
            if inferred_depth_count > 0:
                result.warnings.append(
                    f"{inferred_depth_count}个孔的深度为推断值，"
                    f"建议在DXF中添加深度标注"
                )

    def _build_dimension_proximity_map(
        self, parse_result: DxfParseResult
    ) -> dict[str, DxfDimension]:
        """建立圆实体与尺寸标注的空间关联映射。

        对每个圆，在其邻域范围内搜索最近的尺寸标注，
        使用KD树风格的空间分配策略避免多圆配对冲突。
        """
        if not parse_result.dimensions or not parse_result.circles:
            return {}

        circle_positions: dict[str, tuple[float, float]] = {}
        for c in parse_result.circles:
            circle_positions[c.handle] = (c.center[0], c.center[1])

        assignments: dict[str, DxfDimension] = {}
        used_dims: set[str] = set()

        sorted_circles = sorted(
            parse_result.circles, key=lambda c: c.radius, reverse=True
        )

        for circle in sorted_circles:
            cx, cy = circle.center[0], circle.center[1]
            best_dim = None
            best_dist = float("inf")

            for dim in parse_result.dimensions:
                if dim.handle in used_dims:
                    continue
                dx, dy = dim.position[0], dim.position[1]
                dist = math.sqrt((cx - dx) ** 2 + (cy - dy) ** 2)
                threshold = max(PROXIMITY_THRESHOLD, circle.radius * 3)
                if dist < threshold and dist < best_dist:
                    best_dist = dist
                    best_dim = dim

            if best_dim is not None:
                assignments[circle.handle] = best_dim
                used_dims.add(best_dim.handle)

        return assignments

    def _extract_plane_features(
        self,
        parse_result: DxfParseResult,
        result: FeatureExtractionResult,
    ) -> None:
        """检测矩形轮廓作为平面特征。

        算法：
        1. 从线条中找出闭合矩形（4条边，相对边平行且等长）
        2. 使用直角检测和长度匹配来识别矩形
        """
        if len(parse_result.lines) < 4:
            return

        rectangles = []
        lines = parse_result.lines
        used_lines: set[int] = set()

        for i in range(len(lines)):
            if i in used_lines:
                continue
            rect = self._try_form_rectangle(i, lines, used_lines)
            if rect is not None:
                rectangles.append(rect)

        for idx, (length, width, cx, cy, layer) in enumerate(rectangles, 1):
            plane = PlaneFeatureInfo(
                plane_id=f"PLANE_{idx:03d}",
                center_x=cx,
                center_y=cy,
                length=length,
                width=width,
                surface="A",
                layer=layer,
            )
            result.planes.append(plane)

            if length > result.overall_length * 0.8 or width > result.overall_width * 0.8:
                result.overall_length = max(result.overall_length, length)
                result.overall_width = max(result.overall_width, width)

    def _try_form_rectangle(
        self,
        start_idx: int,
        lines: list[DxfLine],
        used_lines: set[int],
    ) -> tuple[float, float, float, float, str] | None:
        """尝试从起始线条构建矩形轮廓。

        矩形的判定条件：
        - 4条线段首尾相连
        - 相邻边接近正交（90°±允许偏差）
        - 相对边长度一致（允许误差）

        Returns:
            (length, width, center_x, center_y, layer) 或 None
        """
        l1 = lines[start_idx]
        p1, p2 = l1.start[:2], l1.end[:2]
        len1 = math.hypot(p2[0] - p1[0], p2[1] - p1[1])
        if len1 < 0.01:
            return None

        dir1 = ((p2[0] - p1[0]) / len1, (p2[1] - p1[1]) / len1)

        candidates: list[tuple[int, float]] = []
        for j, lj in enumerate(lines):
            if j == start_idx or j in used_lines:
                continue
            p3, p4 = lj.start[:2], lj.end[:2]
            dist_start = math.hypot(p3[0] - p2[0], p3[1] - p2[1])
            dist_end = math.hypot(p4[0] - p2[0], p4[1] - p2[1])

            conn_pt = p3 if dist_start < dist_end else p4
            conn_dist = min(dist_start, dist_end)
            other_pt = p4 if dist_start < dist_end else p3

            d2 = (other_pt[0] - conn_pt[0], other_pt[1] - conn_pt[1])
            len2 = math.hypot(d2[0], d2[1])
            if len2 < 0.01:
                continue

            dot = abs(d2[0] * dir1[0] + d2[1] * dir1[1]) / len2
            if dot > math.cos(math.radians(90 - RECTANGLE_ANGLE_TOLERANCE)):
                candidates.append((j, conn_dist))

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[1])
        best_j, _ = candidates[0]

        l2 = lines[best_j]
        p3, p4 = l2.start[:2], l2.end[:2]

        dist_s = math.hypot(p3[0] - p2[0], p3[1] - p2[1])
        dist_e = math.hypot(p4[0] - p2[0], p4[1] - p2[1])
        l2_start = p3 if dist_s < dist_e else p4
        l2_end = p4 if dist_s < dist_e else p3
        len2 = math.hypot(l2_end[0] - l2_start[0], l2_end[1] - l2_start[1])

        third_candidates = []
        for k, lk in enumerate(lines):
            if k in (start_idx, best_j) or k in used_lines:
                continue
            p5, p6 = lk.start[:2], lk.end[:2]
            dist_s = math.hypot(p5[0] - l2_end[0], p5[1] - l2_end[1])
            dist_e = math.hypot(p6[0] - l2_end[0], p6[1] - l2_end[1])
            third_candidates.append((k, min(dist_s, dist_e)))

        if not third_candidates:
            return None

        third_candidates.sort(key=lambda x: x[1])
        best_k, _ = third_candidates[0]

        l3 = lines[best_k]
        p5, p6 = l3.start[:2], l3.end[:2]
        dist_s = math.hypot(p5[0] - l2_end[0], p5[1] - l2_end[1])
        dist_e = math.hypot(p6[0] - l2_end[0], p6[1] - l2_end[1])
        l3_start = p5 if dist_s < dist_e else p6
        l3_end = p6 if dist_s < dist_e else p5
        len3 = math.hypot(l3_end[0] - l3_start[0], l3_end[1] - l3_start[1])

        if abs(len3 - len1) > RECTANGLE_LENGTH_TOLERANCE:
            return None

        fourth_candidates = []
        for m, lm in enumerate(lines):
            if m in (start_idx, best_j, best_k) or m in used_lines:
                continue
            p7, p8 = lm.start[:2], lm.end[:2]
            d1 = math.hypot(p7[0] - l3_end[0], p7[1] - l3_end[1])
            d2_ = math.hypot(p8[0] - l3_end[0], p8[1] - l3_end[1])
            fourth_candidates.append((m, min(d1, d2_)))

        if not fourth_candidates:
            return None

        fourth_candidates.sort(key=lambda x: x[1])
        best_m, last_dist = fourth_candidates[0]

        if last_dist > RECTANGLE_LENGTH_TOLERANCE:
            return None

        l4 = lines[best_m]
        p7, p8 = l4.start[:2], l4.end[:2]
        d1 = math.hypot(p7[0] - l3_end[0], p7[1] - l3_end[1])
        d2_ = math.hypot(p8[0] - l3_end[0], p8[1] - l3_end[1])
        l4_start = p7 if d1 < d2_ else p8
        l4_end = p8 if d1 < d2_ else p7
        len4 = math.hypot(l4_end[0] - l4_start[0], l4_end[1] - l4_start[1])

        if abs(len4 - len2) > RECTANGLE_LENGTH_TOLERANCE:
            return None

        close_dist = math.hypot(l4_end[0] - p1[0], l4_end[1] - p1[1])
        if close_dist > RECTANGLE_LENGTH_TOLERANCE:
            return None

        used_lines.update([start_idx, best_j, best_k, best_m])

        length = max(len1, len2)
        width_val = min(len1, len2)
        cx = (p1[0] + l2_end[0] + l3_end[0] + l4_end[0]) / 4.0
        cy = (p1[1] + l2_end[1] + l3_end[1] + l4_end[1]) / 4.0

        return (length, width_val, cx, cy, l1.layer)


def is_counterbore_text(text: str) -> bool:
    """判断尺寸标注文本是否指示沉头孔。"""
    if "通孔" in text or "通" in text:
        return False
    keywords = ["沉头", "C'BORE", "CBORE", "COUNTERBORE"]
    return any(kw in text.upper() for kw in keywords)


def extract_tolerance_from_text(text: str) -> str:
    """从标注文本中提取公差等级指示。"""
    import re
    match = re.search(r'IT(\d{1,2})', text, re.IGNORECASE)
    if match:
        grade = int(match.group(1))
        if 1 <= grade <= 18:
            return f"IT{grade}"

    match = re.search(r'H(\d{1,2})', text)
    if match:
        grade = int(match.group(1))
        if 5 <= grade <= 14:
            return f"IT{grade}"

    if "±" in text:
        tol_match = re.search(r'±\s*([\d.]+)', text)
        if tol_match:
            try:
                tol_val = float(tol_match.group(1))
                if tol_val <= 0.01:
                    return "IT5"
                elif tol_val <= 0.03:
                    return "IT6"
                elif tol_val <= 0.05:
                    return "IT7"
                elif tol_val <= 0.1:
                    return "IT8"
                elif tol_val <= 0.2:
                    return "IT9"
                elif tol_val <= 0.5:
                    return "IT10"
            except ValueError as tol_err:
                # 公差数值解析失败时返回空字符串，调用方按空等级处理
                logger.debug(
                    "Failed to parse tolerance value from text %r: %s",
                    text,
                    tol_err,
                    exc_info=True,
                )

    return ""
