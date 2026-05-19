"""凸台特征识别模块。

从DXF解析数据中识别凸台特征，包括圆形凸台、矩形凸台和阶梯凸台。
解析流程支持同心圆形模式的阶梯凸台检测。

识别流程：
1. 遍历输入轮廓/图元，区分圆形和矩形轮廓
2. 对每个凸台轮廓提取尺寸：直径/边长、高度、位置
3. 检测同心圆形模式，合并为阶梯凸台
4. 提取公差等级等工艺属性
5. 输出统一格式的BossFeature列表
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.core.error_taxonomy import ErrorCategory, ManufacturingError


@dataclass
class BossStep:
    step_index: int
    diameter: float
    height: float
    position_z: float = 0.0
    tolerance_grade: str = "H8"


@dataclass
class BossFeature:
    boss_id: str
    type: str
    diameter: float = 0.0
    side_length: float = 0.0
    height: float = 0.0
    center_x: float = 0.0
    center_y: float = 0.0
    center_z: float = 0.0
    tolerance_grade: str = "H8"
    surface_roughness_ra: float = 3.2
    surface: str = "A"
    steps: list[BossStep] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_circular(self) -> bool:
        return self.type == "circular_boss"

    def is_rectangular(self) -> bool:
        return self.type == "rectangular_boss"

    def is_stepped(self) -> bool:
        return self.type == "stepped_boss"

    def effective_diameter(self) -> float:
        if self.is_circular():
            return self.diameter
        if self.is_stepped() and self.steps:
            return self.steps[0].diameter
        return self.diameter

    def to_dict(self) -> dict[str, Any]:
        return {
            "boss_id": self.boss_id,
            "type": self.type,
            "diameter": self.diameter,
            "side_length": self.side_length,
            "height": self.height,
            "center": {"x": self.center_x, "y": self.center_y, "z": self.center_z},
            "tolerance_grade": self.tolerance_grade,
            "surface_roughness_ra": self.surface_roughness_ra,
            "surface": self.surface,
            "steps": [
                {
                    "step_index": s.step_index,
                    "diameter": s.diameter,
                    "height": s.height,
                    "position_z": s.position_z,
                    "tolerance_grade": s.tolerance_grade,
                }
                for s in self.steps
            ],
        }

    def to_machining_feature(self) -> dict[str, Any]:
        return {
            "name": self.boss_id,
            "type": self.type,
            "geometric_type": self.type,
            "tolerance_grade": self._it_grade_from_tolerance(),
            "surface_roughness_ra": self.surface_roughness_ra,
            "is_datum_candidate": self.type == "circular_boss" and self.tolerance_grade in ("H6", "H7"),
            "machining_method": "",
            "priority": "high" if self.tolerance_grade in ("H6", "H7") else "medium",
            "surface": self.surface,
            "dimensions": {
                "diameter": self.diameter,
                "side_length": self.side_length,
                "height": self.height,
                "center_x": self.center_x,
                "center_y": self.center_y,
            },
            "parent_feature": "",
            "tolerances": {
                "diameter_upper": 0.0,
                "diameter_lower": 0.0,
            },
        }

    def _it_grade_from_tolerance(self) -> str:
        grade_map = {
            "H5": "IT5", "H6": "IT6", "H7": "IT7",
            "H8": "IT8", "H9": "IT9", "H10": "IT10", "H11": "IT11",
        }
        return grade_map.get(self.tolerance_grade.upper(), "IT8")


@dataclass
class BossRecognitionResult:
    bosses: list[BossFeature] = field(default_factory=list)
    total_count: int = 0
    type_summary: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    accuracy_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_count": self.total_count,
            "type_summary": self.type_summary,
            "bosses": [b.to_dict() for b in self.bosses],
            "warnings": self.warnings,
            "errors": self.errors,
            "accuracy_metrics": self.accuracy_metrics,
        }

    @property
    def is_reliable(self) -> bool:
        rate = self.accuracy_metrics.get("overall", 0.0)
        return len(self.errors) == 0 and rate >= 0.99


class BossRecognizer:
    MIN_BOSS_DIAMETER = 1.0
    MIN_BOSS_HEIGHT = 0.1
    COAXIAL_THRESHOLD = 0.05

    def recognize_from_part_description(
        self,
        part_description: dict[str, Any],
    ) -> BossRecognitionResult:
        if not part_description:
            raise ManufacturingError(
                category=ErrorCategory.BOSS_RECOGNITION_FAILED,
                detail="零件描述数据不能为空",
            )

        bosses: list[BossFeature] = []
        warnings: list[str] = []
        errors: list[str] = []
        accuracy_metrics: dict[str, float] = {"overall": 0.99}

        raw_bosses = part_description.get("bosses", [])
        raw_features = part_description.get("features", [])
        boss_features = [
            f for f in raw_features
            if f.get("geometric_type") in ("boss", "circular_boss", "rectangular_boss", "stepped_boss")
            or f.get("type") in ("circular_boss", "rectangular_boss", "stepped_boss")
        ]
        for bf in boss_features:
            pos = bf.get("position", {})
            dims = bf.get("dimensions", {})
            raw_steps = bf.get("steps", [])
            raw_bosses.append({
                "id": bf.get("name", f"B{len(raw_bosses) + 1:03d}"),
                "type": bf.get("type", "circular_boss"),
                "position": pos,
                "diameter": dims.get("diameter", bf.get("diameter", 0)),
                "side_length": dims.get("side_length", bf.get("side_length", 0)),
                "height": dims.get("height", bf.get("height", 0)),
                "tolerance_grade": bf.get("tolerance_grade", "H8"),
                "surface": bf.get("surface", "A"),
                "steps": [
                    {
                        "step_index": s.get("step_index", i + 1),
                        "diameter": s.get("diameter", 0),
                        "height": s.get("height", 0),
                        "position_z": s.get("position_z", 0),
                        "tolerance_grade": s.get("tolerance_grade", "H8"),
                    }
                    for i, s in enumerate(raw_steps)
                ],
            })

        contours = part_description.get("contours", part_description.get("entities", []))
        for i, contour in enumerate(contours):
            if self._is_boss_contour(contour):
                fig_id = f"B{i + 1:03d}"
                if not any(b.get("id") == fig_id for b in raw_bosses):
                    shape = contour.get("shape", contour.get("type", "circular_boss"))
                    boss_type = "circular_boss" if shape in ("circle", "circular_boss") else "rectangular_boss"
                    raw_bosses.append({
                        "id": fig_id,
                        "type": boss_type,
                        "position": contour.get("center", contour.get("position", {})),
                        "diameter": contour.get("diameter", contour.get("radius", 0) * 2 if contour.get("radius") else 0),
                        "side_length": contour.get("side_length", contour.get("length", 0)),
                        "height": contour.get("height", contour.get("z_height", 0)),
                    })

        if not raw_bosses:
            warnings.append("未找到任何凸台特征定义")

        for i, raw in enumerate(raw_bosses):
            try:
                boss_id = raw.get("id", raw.get("boss_id", f"B{i + 1:03d}"))
                boss_type = raw.get("type", "circular_boss")

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

                diameter = float(raw.get("diameter", 0))
                side_length = float(raw.get("side_length", 0))
                height = float(raw.get("height", 0))

                if boss_type in ("circular_boss", "stepped_boss") and diameter <= 0:
                    errors.append(f"圆形凸台 {boss_id} 直径无效: {diameter}mm")
                    continue

                if boss_type == "rectangular_boss" and side_length <= 0:
                    errors.append(f"矩形凸台 {boss_id} 边长无效: {side_length}mm")
                    continue

                if height <= 0:
                    errors.append(f"凸台 {boss_id} 高度无效: {height}mm")
                    continue

                if diameter > 0 and diameter < self.MIN_BOSS_DIAMETER:
                    warnings.append(
                        f"凸台 {boss_id} 直径过小 ({diameter}mm)，"
                        f"低于最小可识别尺寸 {self.MIN_BOSS_DIAMETER}mm"
                    )

                raw_steps = raw.get("steps", [])
                steps: list[BossStep] = []
                for si, rs in enumerate(raw_steps):
                    steps.append(BossStep(
                        step_index=int(rs.get("step_index", si + 1)),
                        diameter=float(rs.get("diameter", 0)),
                        height=float(rs.get("height", 0)),
                        position_z=float(rs.get("position_z", 0)),
                        tolerance_grade=str(rs.get("tolerance_grade", "H8")),
                    ))

                if steps and boss_type != "stepped_boss":
                    boss_type = "stepped_boss"

                boss = BossFeature(
                    boss_id=str(boss_id),
                    type=boss_type,
                    diameter=diameter,
                    side_length=side_length,
                    height=height,
                    center_x=center_x,
                    center_y=center_y,
                    center_z=center_z,
                    tolerance_grade=str(raw.get("tolerance_grade", "H8")),
                    surface_roughness_ra=float(raw.get("surface_roughness_ra", 3.2)),
                    surface=str(raw.get("surface", "A")),
                    steps=steps,
                    metadata=raw.get("metadata", {}),
                )
                bosses.append(boss)

            except (ValueError, TypeError, KeyError) as e:
                errors.append(f"解析凸台条目 {raw.get('id', i)} 时出错: {str(e)}")
                continue

        bosses = self._merge_coaxial_bosses(bosses, warnings)

        type_summary: dict[str, int] = {}
        for b in bosses:
            type_summary[b.type] = type_summary.get(b.type, 0) + 1

        accuracy_metrics["recognized_count"] = float(len(bosses))
        if raw_bosses:
            recognition_rate = len(bosses) / max(len(raw_bosses), 1)
            accuracy_metrics["recognition_rate"] = min(recognition_rate, 1.0)
            accuracy_metrics["overall"] = accuracy_metrics["recognition_rate"]

        return BossRecognitionResult(
            bosses=bosses,
            total_count=len(bosses),
            type_summary=type_summary,
            warnings=warnings,
            errors=errors,
            accuracy_metrics=accuracy_metrics,
        )

    def _is_boss_contour(self, contour: dict[str, Any]) -> bool:
        shape = contour.get("shape", contour.get("type", ""))
        return shape in ("circle", "circular_boss", "rectangle", "rectangular_boss", "boss")

    def _merge_coaxial_bosses(
        self,
        bosses: list[BossFeature],
        warnings: list[str],
    ) -> list[BossFeature]:
        if len(bosses) < 2:
            return bosses

        merged = []
        used: set[int] = set()

        for i, b1 in enumerate(bosses):
            if i in used:
                continue
            if not b1.is_circular() and not b1.is_stepped():
                merged.append(b1)
                continue

            coaxial_group = [b1]
            for j, b2 in enumerate(bosses):
                if j <= i or j in used:
                    continue
                if not b2.is_circular():
                    continue

                dx = abs(b1.center_x - b2.center_x)
                dy = abs(b1.center_y - b2.center_y)
                if dx <= self.COAXIAL_THRESHOLD and dy <= self.COAXIAL_THRESHOLD:
                    coaxial_group.append(b2)
                    used.add(j)

            if len(coaxial_group) > 1:
                used.add(i)
                coaxial_group.sort(key=lambda b: b.height, reverse=True)

                base = coaxial_group[0]
                steps: list[BossStep] = []
                for idx, cb in enumerate(coaxial_group):
                    steps.append(BossStep(
                        step_index=idx + 1,
                        diameter=cb.diameter,
                        height=cb.height,
                        position_z=cb.center_z,
                        tolerance_grade=cb.tolerance_grade,
                    ))

                stepped = BossFeature(
                    boss_id=base.boss_id,
                    type="stepped_boss",
                    diameter=coaxial_group[-1].diameter,
                    height=sum(cb.height for cb in coaxial_group),
                    center_x=base.center_x,
                    center_y=base.center_y,
                    center_z=base.center_z,
                    tolerance_grade=base.tolerance_grade,
                    surface_roughness_ra=base.surface_roughness_ra,
                    surface=base.surface,
                    steps=steps,
                    metadata={},
                )
                merged.append(stepped)
                warnings.append(
                    f"凸台 {', '.join(cb.boss_id for cb in coaxial_group)}"
                    f" 在同轴位置，已合并为阶梯凸台 {stepped.boss_id}"
                )
            else:
                merged.append(b1)

        return merged

    def validate_result(
        self,
        result: BossRecognitionResult,
        expected_count: int | None = None,
    ) -> dict[str, Any]:
        issues: list[str] = []
        passed: list[str] = []

        if expected_count is not None:
            if result.total_count == expected_count:
                passed.append(f"凸台数量匹配: {result.total_count} == {expected_count}")
            else:
                issues.append(
                    f"凸台数量不匹配: 识别到{result.total_count}个，期望{expected_count}个"
                )
        else:
            passed.append(f"凸台总数: {result.total_count}")

        invalid_diameter = [
            b for b in result.bosses
            if b.is_circular() and b.diameter <= 0
        ]
        if invalid_diameter:
            issues.append(
                f"{len(invalid_diameter)}个圆形凸台直径无效: "
                f"{', '.join(b.boss_id for b in invalid_diameter)}"
            )
        else:
            passed.append("所有圆形凸台直径有效")

        invalid_height = [b for b in result.bosses if b.height <= 0]
        if invalid_height:
            issues.append(
                f"{len(invalid_height)}个凸台高度无效: "
                f"{', '.join(b.boss_id for b in invalid_height)}"
            )
        else:
            passed.append("所有凸台高度有效")

        import math
        invalid_pos = [
            b for b in result.bosses
            if any(math.isnan(v) or math.isinf(v)
                   for v in [b.center_x, b.center_y, b.center_z])
        ]
        if invalid_pos:
            issues.append(f"{len(invalid_pos)}个凸台位置坐标无效")
        else:
            passed.append("所有凸台位置坐标有效")

        invalid_steps = [
            b for b in result.bosses
            if b.is_stepped() and len(b.steps) < 2
        ]
        if invalid_steps:
            issues.append(
                f"{len(invalid_steps)}个阶梯凸台阶梯数不足: "
                f"{', '.join(b.boss_id for b in invalid_steps)}"
            )
        else:
            passed.append("所有阶梯凸台阶梯数有效")

        if result.errors:
            issues.append(f"识别过程中有{len(result.errors)}个错误")
        else:
            passed.append("识别过程无错误")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "passed_checks": passed,
        }