"""平面特征识别模块。

从DXF解析数据中识别平面区域特征，用于后续的基准面选择和加工策略规划。
支持同时识别多个平面特征，区分顶面/底面/侧面。

识别流程：
1. 遍历输入轮廓/图元，筛选平面类型轮廓
2. 提取每个平面的面积、法向量、边界轮廓
3. 通过法向量方向区分顶面/底面/侧面
4. 计算每个平面的名义尺寸（长、宽）
5. 输出统一格式的PlaneFeature列表
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.error_taxonomy import ErrorCategory, ManufacturingError


@dataclass
class PlaneFeature:
    plane_id: str
    type: str
    area: float = 0.0
    normal_x: float = 0.0
    normal_y: float = 0.0
    normal_z: float = 1.0
    length: float = 0.0
    width: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    boundary: list[list[float]] = field(default_factory=list)
    surface: str = "A"
    tolerance_grade: str = "IT8"
    surface_roughness_ra: float = 3.2
    is_datum_candidate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_top(self) -> bool:
        return self.type == "top_plane"

    def is_bottom(self) -> bool:
        return self.type == "bottom_plane"

    def is_side(self) -> bool:
        return self.type == "side_plane"

    def normal_vector(self) -> list[float]:
        return [self.normal_x, self.normal_y, self.normal_z]

    def to_dict(self) -> dict[str, Any]:
        return {
            "plane_id": self.plane_id,
            "type": self.type,
            "area": round(self.area, 2),
            "normal": self.normal_vector(),
            "length": self.length,
            "width": self.width,
            "center": {"x": self.center_x, "y": self.center_y, "z": self.center_z},
            "boundary_points": len(self.boundary),
            "surface": self.surface,
            "tolerance_grade": self.tolerance_grade,
            "surface_roughness_ra": self.surface_roughness_ra,
            "is_datum_candidate": self.is_datum_candidate,
        }

    def to_machining_feature(self) -> dict[str, Any]:
        return {
            "name": self.plane_id,
            "type": self.type,
            "geometric_type": "plane",
            "tolerance_grade": self.tolerance_grade,
            "surface_roughness_ra": self.surface_roughness_ra,
            "is_datum_candidate": self.is_datum_candidate,
            "machining_method": "milling",
            "priority": "high" if self.is_datum_candidate else "medium",
            "surface": self.surface,
            "dimensions": {
                "length": self.length,
                "width": self.width,
                "area": self.area,
                "center_x": self.center_x,
                "center_y": self.center_y,
            },
            "parent_feature": "",
            "tolerances": {
                "flatness": 0.0,
                "parallelism": 0.0,
            },
        }


@dataclass
class PlaneRecognitionResult:
    planes: list[PlaneFeature] = field(default_factory=list)
    total_count: int = 0
    type_summary: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    accuracy_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "type_summary": self.type_summary,
            "planes": [p.to_dict() for p in self.planes],
            "warnings": self.warnings,
            "errors": self.errors,
            "accuracy_metrics": self.accuracy_metrics,
        }

    @property
    def is_reliable(self) -> bool:
        rate = self.accuracy_metrics.get("overall", 0.0)
        return len(self.errors) == 0 and rate >= 0.99


class PlaneRecognizer:
    MIN_PLANE_AREA = 1.0
    MAX_PLANE_AREA = 1_000_000.0

    def recognize_from_part_description(
        self,
        part_description: dict[str, Any],
    ) -> PlaneRecognitionResult:
        if not part_description:
            raise ManufacturingError(
                category=ErrorCategory.PLANE_RECOGNITION_FAILED,
                detail="零件描述数据不能为空",
            )

        planes: list[PlaneFeature] = []
        warnings: list[str] = []
        errors: list[str] = []
        accuracy_metrics: dict[str, float] = {"overall": 0.99}

        raw_planes = part_description.get("planes", [])
        raw_features = part_description.get("features", [])
        plane_features = [
            f for f in raw_features
            if f.get("geometric_type") in ("plane", "planar_surface", "end_face")
            or f.get("type") in ("top_plane", "bottom_plane", "side_plane", "end_face", "plane")
        ]
        for pf in plane_features:
            pos = pf.get("position", {})
            dims = pf.get("dimensions", {})
            normal = pf.get("normal", pf.get("normal_vector", [0, 0, 1]))
            raw_planes.append({
                "id": pf.get("name", f"P{len(raw_planes) + 1:03d}"),
                "type": pf.get("type", "top_plane"),
                "position": pos,
                "length": dims.get("length", pf.get("length", 0)),
                "width": dims.get("width", pf.get("width", 0)),
                "area": dims.get("area", pf.get("area", 0)),
                "normal": normal,
                "tolerance_grade": pf.get("tolerance_grade", "IT8"),
                "surface": pf.get("surface", "A"),
                "is_datum_candidate": pf.get("is_datum_candidate", False),
                "boundary": pf.get("boundary", pf.get("boundary_contour", [])),
            })

        contours = part_description.get("contours", part_description.get("entities", []))
        for i, contour in enumerate(contours):
            if self._is_plane_contour(contour):
                fig_id = f"P{i + 1:03d}"
                if not any(p.get("id") == fig_id for p in raw_planes):
                    normal = contour.get("normal", contour.get("normal_vector", [0, 0, 1]))
                    if not isinstance(normal, list) or len(normal) != 3:
                        normal = [0, 0, 1]
                    plane_type = self._classify_plane_type(normal)

                    boundary = contour.get("boundary", contour.get("vertices", contour.get("points", [])))
                    length, width = self._estimate_dimensions(boundary)

                    raw_planes.append({
                        "id": fig_id,
                        "type": plane_type,
                        "position": contour.get("center", contour.get("position", {})),
                        "length": contour.get("length", length),
                        "width": contour.get("width", width),
                        "area": contour.get("area", length * width),
                        "normal": normal,
                        "boundary": boundary,
                        "surface": contour.get("surface", "A"),
                    })

        if not raw_planes:
            warnings.append("未找到任何平面特征定义")

        for i, raw in enumerate(raw_planes):
            try:
                plane_id = raw.get("id", raw.get("plane_id", f"P{i + 1:03d}"))
                plane_type = raw.get("type", "top_plane")

                pos = raw.get("position", {})
                if isinstance(pos, (list, tuple)):
                    pos = {
                        "x": pos[0] if len(pos) > 0 else 0,
                        "y": pos[1] if len(pos) > 1 else 0,
                        "z": pos[2] if len(pos) > 2 else 0,
                    }

                center_x = float(pos.get("x", 0))
                center_y = float(pos.get("y", 0))
                center_z = float(pos.get("z", 0))

                normal = raw.get("normal", raw.get("normal_vector", [0.0, 0.0, 1.0]))
                if not isinstance(normal, list) or len(normal) != 3:
                    normal = [0.0, 0.0, 1.0]

                normal_x = float(normal[0])
                normal_y = float(normal[1])
                normal_z = float(normal[2])

                area = float(raw.get("area", 0))
                length = float(raw.get("length", 0))
                width = float(raw.get("width", 0))

                if area <= 0 and length > 0 and width > 0:
                    area = length * width
                elif area > 0 and length <= 0 and width > 0:
                    length = area / width
                elif area > 0 and width <= 0 and length > 0:
                    width = area / length

                if area <= 0:
                    errors.append(f"平面 {plane_id} 面积无效: {area}mm²")
                    continue

                if area < self.MIN_PLANE_AREA:
                    warnings.append(
                        f"平面 {plane_id} 面积过小 ({area:.2f}mm²)，"
                        f"低于最小可识别面积 {self.MIN_PLANE_AREA}mm²"
                    )

                boundary = raw.get("boundary", raw.get("boundary_contour", []))
                if isinstance(boundary, list) and boundary and isinstance(boundary[0], dict):
                    boundary = [
                        [float(pt.get("x", 0)), float(pt.get("y", 0))]
                        for pt in boundary
                    ]

                if not isinstance(boundary, list):
                    boundary = []

                if plane_type not in ("top_plane", "bottom_plane", "side_plane"):
                    plane_type = self._classify_plane_type([normal_x, normal_y, normal_z])

                plane = PlaneFeature(
                    plane_id=str(plane_id),
                    type=plane_type,
                    area=area,
                    normal_x=normal_x,
                    normal_y=normal_y,
                    normal_z=normal_z,
                    length=length,
                    width=width,
                    center_x=center_x,
                    center_y=center_y,
                    center_z=center_z,
                    boundary=boundary,
                    surface=str(raw.get("surface", "A")),
                    tolerance_grade=str(raw.get("tolerance_grade", "IT8")),
                    surface_roughness_ra=float(raw.get("surface_roughness_ra", 3.2)),
                    is_datum_candidate=bool(raw.get("is_datum_candidate", False)),
                    metadata=raw.get("metadata", {}),
                )
                planes.append(plane)

            except (ValueError, TypeError, KeyError) as e:
                errors.append(f"解析平面条目 {raw.get('id', i)} 时出错: {str(e)}")
                continue

        type_summary: dict[str, int] = {}
        for p in planes:
            type_summary[p.type] = type_summary.get(p.type, 0) + 1

        accuracy_metrics["recognized_count"] = float(len(planes))
        if raw_planes:
            recognition_rate = len(planes) / max(len(raw_planes), 1)
            accuracy_metrics["recognition_rate"] = min(recognition_rate, 1.0)
            accuracy_metrics["overall"] = accuracy_metrics["recognition_rate"]

        return PlaneRecognitionResult(
            planes=planes,
            total_count=len(planes),
            type_summary=type_summary,
            warnings=warnings,
            errors=errors,
            accuracy_metrics=accuracy_metrics,
        )

    def recognize_from_contours(
        self,
        contours: list[dict[str, Any]],
    ) -> PlaneRecognitionResult:
        part_description = {"contours": contours}
        return self.recognize_from_part_description(part_description)

    def _is_plane_contour(self, contour: dict[str, Any]) -> bool:
        shape = contour.get("shape", contour.get("type", ""))
        if shape in ("plane", "planar_surface", "face", "rectangle"):
            return True
        normal = contour.get("normal", contour.get("normal_vector"))
        if normal is not None:
            return True
        return False

    def _classify_plane_type(self, normal: list[float]) -> str:
        if len(normal) < 3:
            return "top_plane"
        nz = abs(normal[2])
        nx = abs(normal[0])
        ny = abs(normal[1])

        if nz >= max(nx, ny) or nz > 0.9:
            return "top_plane" if normal[2] > 0 else "bottom_plane"
        return "side_plane"

    def _estimate_dimensions(
        self,
        boundary: list[list[float]] | list[dict[str, float]],
    ) -> tuple[float, float]:
        if not boundary:
            return 0.0, 0.0

        xs: list[float] = []
        ys: list[float] = []
        for pt in boundary:
            if isinstance(pt, (list, tuple)):
                xs.append(float(pt[0]) if len(pt) > 0 else 0.0)
                ys.append(float(pt[1]) if len(pt) > 1 else 0.0)
            elif isinstance(pt, dict):
                xs.append(float(pt.get("x", 0)))
                ys.append(float(pt.get("y", 0)))

        if not xs or not ys:
            return 0.0, 0.0

        length = max(xs) - min(xs)
        width = max(ys) - min(ys)
        return length, width

    def validate_result(
        self,
        result: PlaneRecognitionResult,
        expected_count: int | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        passed: list[str] = []

        if expected_count is not None:
            if result.total_count == expected_count:
                passed.append(f"平面数量匹配: {result.total_count} == {expected_count}")
            else:
                issues.append(
                    f"平面数量不匹配: 识别到{result.total_count}个，期望{expected_count}个"
                )
        else:
            passed.append(f"平面总数: {result.total_count}")

        invalid_area = [p for p in result.planes if p.area <= 0]
        if invalid_area:
            issues.append(
                f"{len(invalid_area)}个平面面积无效: "
                f"{', '.join(p.plane_id for p in invalid_area)}"
            )
        else:
            passed.append("所有平面面积有效")

        import math
        invalid_normal = [
            p for p in result.planes
            if all(abs(v) < 0.001 for v in [p.normal_x, p.normal_y, p.normal_z])
        ]
        if invalid_normal:
            issues.append(
                f"{len(invalid_normal)}个平面法向量为零: "
                f"{', '.join(p.plane_id for p in invalid_normal)}"
            )
        else:
            passed.append("所有平面法向量有效")

        invalid_pos = [
            p for p in result.planes
            if any(math.isnan(v) or math.isinf(v)
                   for v in [p.center_x, p.center_y, p.center_z])
        ]
        if invalid_pos:
            issues.append(f"{len(invalid_pos)}个平面位置坐标无效")
        else:
            passed.append("所有平面位置坐标有效")

        if result.errors:
            issues.append(f"识别过程中有{len(result.errors)}个错误")
        else:
            passed.append("识别过程无错误")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "passed_checks": passed,
        }