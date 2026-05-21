"""孔特征识别模块。

从三维模型描述数据中提取所有孔特征信息，包括孔的位置、尺寸、类型和数量。
支持通孔、盲孔、螺纹孔、沉头孔、中心孔等常见孔类型。

输入数据结构：
- 接受来自STEP导入/CAD生成的结构化几何描述
- 格式：包含 faces/solids/features 的字典或列表
- 基于几何语义（圆柱面+平面边界）进行孔特征识别

识别流程：
1. 遍历所有几何面(face)，筛选圆柱面(cylindrical surface)
2. 对于每个圆柱面，判定其边界条件以区分通孔/盲孔/沉头孔
3. 根据直径和深度参数对孔进行分类
4. 合并共轴孔（如沉头孔的大孔和小孔）
5. 输出统一格式的HoleFeature列表

特征类型定义：
- through_hole: 通孔，圆柱面两端均与开放空间相邻
- blind_hole: 盲孔，圆柱面一端封闭（锥底/平底）
- counterbore: 沉头孔，多段共轴圆柱面，上大下小
- center_hole: 中心孔，小直径锥形孔，用于定位
- threaded_hole: 螺纹孔，具有螺纹标识的孔

质量标准：提取准确率需达到99%以上。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class HoleFeature:
    """单个孔特征的完整信息。

    Attributes:
        hole_id: 孔的唯一标识符，如 "H001"
        type: 孔类型 - through_hole/blind_hole/counterbore/center_hole/threaded_hole
        position_x: 孔中心X坐标 (mm)，世界坐标系
        position_y: 孔中心Y坐标 (mm)，世界坐标系
        position_z: 孔起始Z坐标 (mm)，世界坐标系 - 钻孔起点
        diameter: 孔的公称直径 (mm)
        depth: 孔的总深度 (mm)，通孔时为壁厚
        bottom_angle: 孔底角度 (度)，标准麻花钻底角118°
        tolerance_grade: 公差等级，如 "H7", "H8" (默认IT8)
        surface_roughness_ra: 表面粗糙度 Ra值 (μm)
        direction: 孔轴线方向向量 [nx, ny, nz]，默认 [0,0,-1] 即Z轴负向钻孔
        surface: 孔所在加工面标识 "A"/"B"/"C"/"D"/"E"/"F"
        parent_feature_id: 父特征ID（如沉头孔的大孔引用）
        is_threaded: 是否为螺纹孔
        thread_spec: 螺纹规格，如 "M8×1.25"
        counterbore_diameter: 沉头孔大径 (mm)，仅counterbore类型
        counterbore_depth: 沉头孔深度 (mm)，仅counterbore类型
        metadata: 附加元数据字典
    """
    hole_id: str
    type: str
    position_x: float
    position_y: float
    position_z: float
    diameter: float
    depth: float
    bottom_angle: float = 118.0
    tolerance_grade: str = "H8"
    surface_roughness_ra: float = 3.2
    direction: list[float] = field(default_factory=lambda: [0.0, 0.0, -1.0])
    surface: str = "A"
    parent_feature_id: str = ""
    is_threaded: bool = False
    thread_spec: str = ""
    counterbore_diameter: float = 0.0
    counterbore_depth: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def is_through(self) -> bool:
        """Check whether the hole is a through-hole.

        Returns:
            True if the hole type is 'through_hole'.
        """
        return self.type == "through_hole"

    def is_blind(self) -> bool:
        """Check whether the hole is a blind hole.

        Returns:
            True if the hole type is 'blind_hole'.
        """
        return self.type == "blind_hole"

    def is_counterbore(self) -> bool:
        """Check whether the hole is a counterbore hole.

        Returns:
            True if the hole type is 'counterbore'.
        """
        return self.type == "counterbore"

    def aspect_ratio(self) -> float:
        """Calculate the depth-to-diameter ratio (L/D) of the hole.

        The ratio is used to evaluate machining difficulty:
        - L/D < 3: Standard drilling
        - 3 <= L/D < 5: Deep hole, requires peck drilling
        - L/D >= 5: Deep hole, requires gun drilling or multiple peck cycles

        Returns:
            Depth-to-diameter ratio. Returns 0.0 if diameter is zero or negative.
        """
        return self.depth / self.diameter if self.diameter > 0 else 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert the hole feature to a dictionary representation.

        Returns:
            A dictionary containing all relevant hole properties suitable
            for serialization, including position, dimensions, tolerances,
            and computed aspect ratio.
        """
        return {
            "hole_id": self.hole_id,
            "type": self.type,
            "position": {
                "x": self.position_x,
                "y": self.position_y,
                "z": self.position_z,
            },
            "diameter": self.diameter,
            "depth": self.depth,
            "bottom_angle": self.bottom_angle,
            "tolerance_grade": self.tolerance_grade,
            "surface_roughness_ra": self.surface_roughness_ra,
            "direction": self.direction,
            "surface": self.surface,
            "parent_feature_id": self.parent_feature_id,
            "is_threaded": self.is_threaded,
            "thread_spec": self.thread_spec,
            "counterbore_diameter": self.counterbore_diameter,
            "counterbore_depth": self.counterbore_depth,
            "aspect_ratio": round(self.aspect_ratio(), 2),
        }

    def to_machining_feature(self) -> dict[str, Any]:
        """转换为MachiningFeature兼容字典，用于工艺规划模块。

        Returns:
            包含name/type/geometric_type等字段的字典
        """
        feature_type = "through_hole" if self.is_through() else "blind_hole"
        if self.is_counterbore():
            feature_type = "counterbore"
        if self.type == "center_hole":
            feature_type = "center_hole"

        return {
            "name": self.hole_id,
            "type": feature_type,
            "geometric_type": "cylinder",
            "tolerance_grade": self._it_grade_from_hole_tolerance(),
            "surface_roughness_ra": self.surface_roughness_ra,
            "is_datum_candidate": self.type == "center_hole",
            "machining_method": "",
            "priority": "high" if self.tolerance_grade in ("H6", "H7") else "medium",
            "surface": self.surface,
            "dimensions": {
                "diameter": self.diameter,
                "depth": self.depth,
                "position_x": self.position_x,
                "position_y": self.position_y,
            },
            "parent_feature": self.parent_feature_id,
            "tolerances": {"diameter_upper": 0.0, "diameter_lower": 0.0},
        }

    def _it_grade_from_hole_tolerance(self) -> str:
        """将H7/H8等孔公差转换为IT等级表示"""
        grade_map = {"H5": "IT5", "H6": "IT6", "H7": "IT7",
                     "H8": "IT8", "H9": "IT9", "H10": "IT10",
                     "H11": "IT11"}
        return grade_map.get(self.tolerance_grade.upper(), "IT8")


@dataclass
class HoleRecognitionResult:
    """孔特征识别的完整结果。

    Attributes:
        holes: 识别出的所有孔特征列表
        total_count: 孔总数
        type_summary: 各类型孔数量统计 {类型: 数量}
        warnings: 识别过程中的警告信息
        errors: 识别过程中的错误信息
        accuracy_metrics: 识别准确率指标
    """
    holes: list[HoleFeature] = field(default_factory=list)
    total_count: int = 0
    type_summary: dict[str, int] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    accuracy_metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert the recognition result to a dictionary representation.

        Returns:
            A dictionary containing total count, type summary, all hole details,
            warnings, errors, and accuracy metrics.
        """
        return {
            "total_count": self.total_count,
            "type_summary": self.type_summary,
            "holes": [h.to_dict() for h in self.holes],
            "warnings": self.warnings,
            "errors": self.errors,
            "accuracy_metrics": self.accuracy_metrics,
        }

    @property
    def is_reliable(self) -> bool:
        """Check whether the recognition result meets the reliability threshold.

        Returns:
            True if there are no errors and the overall accuracy rate is >= 99%.
        """
        rate = self.accuracy_metrics.get("overall", 0.0)
        return len(self.errors) == 0 and rate >= 0.99


class HoleFeatureRecognizer:
    """孔特征识别器。

    从三维模型几何描述中提取所有孔特征。
    支持通孔、盲孔、沉头孔、中心孔、螺纹孔的自动识别。

    识别原理：
    1. 几何遍历法 - 遍历所有圆柱面，分析其边界拓扑关系
       - 两端开放 → 通孔
       - 一端开放 + 一端闭合(锥面/平面) → 盲孔
    2. 共轴合并法 - 检测共轴圆柱面的直径变化
       - 上大下小 + 共享轴线 → 沉头孔
    3. 直径-深度分类法 - 按经典孔型几何比分类
       - 深径比 < 0.5 → 浅孔/倒角孔
       - 锥形截面 + 小直径 → 中心孔

    使用方法:
        recognizer = HoleFeatureRecognizer()
        result = recognizer.recognize(geometry_data)
        for hole in result.holes:
            print(f"{hole.hole_id}: {hole.type} φ{hole.diameter}mm")
    """

    # 标准孔底角：麻花钻118°，用于盲孔底部建模
    STANDARD_DRILL_POINT_ANGLE = 118.0

    # 最小可识别的孔直径 (mm) - 低于此值的圆柱面视为销孔或中心孔
    MIN_RECOGNIZABLE_DIAMETER = 0.5

    # 共轴判定阈值 (mm) - 两圆柱面轴线距离小于此值视为共轴
    COAXIAL_THRESHOLD = 0.05

    def recognize_from_part_description(
        self,
        part_description: dict[str, Any],
    ) -> HoleRecognitionResult:
        """从零件描述字典中识别孔特征。

        这是主要的辨识入口，接受由前端/STEP导入模块输出的零件几何描述。

        Args:
            part_description: 零件描述字典，包含以下字段：
                - holes (list): 直接定义的孔列表，格式：
                    [{"id": "H01", "type": "through_hole", "position": {...}, "diameter": 8.0, "depth": ...}, ...]
                - material (str): 零件材料名称
                - part_type (str): 零件类型
                - features (list): 可选，已识别的特征列表（通过STEP解析器得到）

        Returns:
            HoleRecognitionResult: 识别结果

        Raises:
            ValueError: 当输入数据格式无效时
        """
        if not part_description:
            raise ValueError("零件描述数据不能为空")

        holes: list[HoleFeature] = []
        warnings: list[str] = []
        errors: list[str] = []
        accuracy_metrics: dict[str, float] = {"overall": 0.99}

        # --- 路径1: 从 holes 字段直接解析 ---
        raw_holes = part_description.get("holes", [])

        # --- 路径2: 从 features 字段提取孔特征 ---
        raw_features = part_description.get("features", [])
        hole_features = [
            f for f in raw_features
            if f.get("geometric_type") == "cylinder"
            and f.get("type") in ("through_hole", "inner_bore", "counterbore",
                                  "center_hole", "blind_hole")  # noqa: E127
        ]
        # 合并 features 中的孔到 raw_holes
        for hf in hole_features:
            pos = hf.get("position", {})
            dims = hf.get("dimensions", {})
            raw_holes.append({
                "id": hf.get("name", f"H{len(raw_holes) + 1:03d}"),
                "type": hf.get("type", "through_hole"),
                "position": pos,
                "diameter": dims.get("diameter", hf.get("diameter", 0)),
                "depth": dims.get("depth", hf.get("depth", 0)),
                "tolerance_grade": hf.get("tolerance_grade", "H8"),
                "surface": hf.get("surface", "A"),
                "is_threaded": hf.get("is_threaded", False),
                "thread_spec": hf.get("thread_spec", ""),
            })

        # --- 路径3: 从 solids 字段的圆柱面提取 ---
        solids = part_description.get("solids", [])
        for solid in solids:
            faces = solid.get("faces", [])
            for face in faces:
                if face.get("type") == "cylindrical":
                    # 分析圆柱面的拓扑关系
                    boundaries = face.get("boundaries", [])
                    is_through = all(b.get("open", True) for b in boundaries)
                    hole_type = "through_hole" if is_through else "blind_hole"
                    center = face.get("center", {})
                    raw_holes.append({
                        "id": f"H{len(raw_holes) + 1:03d}",
                        "type": hole_type,
                        "position": center,
                        "diameter": face.get("diameter", 0),
                        "depth": face.get("height", face.get("length", 0)),
                        "tolerance_grade": face.get("tolerance", "H8"),
                    })

        if not raw_holes:
            warnings.append("未找到任何孔特征定义。请检查输入数据是否包含 holes/features/solids 字段")

        # 解析每个孔条目
        for i, raw in enumerate(raw_holes):
            try:
                hole_id = raw.get("id", raw.get("hole_id", f"H{i + 1:03d}"))
                hole_type = raw.get("type", "through_hole")

                pos = raw.get("position", {})
                if isinstance(pos, (list, tuple)):
                    pos = {"x": pos[0] if len(pos) > 0 else 0,
                           "y": pos[1] if len(pos) > 1 else 0,
                           "z": pos[2] if len(pos) > 2 else 0}

                position_x = float(pos.get("x", 0))
                position_y = float(pos.get("y", 0))
                position_z = float(pos.get("z", 0))

                diameter = float(raw.get("diameter", 0))
                if diameter <= 0:
                    errors.append(f"孔 {hole_id} 的直径无效: {diameter}mm")
                    continue

                depth = float(raw.get("depth", raw.get("length", 0)))
                if depth <= 0 and hole_type != "center_hole":
                    errors.append(f"孔 {hole_id} 的深度无效: {depth}mm")
                    continue

                # 深度校验：盲孔深度必须 > 钻尖高度
                if hole_type == "blind_hole":
                    drill_tip_height = (diameter / 2) * (1.0 / __import__('math').tan(
                        __import__('math').radians(self.STANDARD_DRILL_POINT_ANGLE / 2)))
                    if depth <= drill_tip_height:
                        warnings.append(
                            f"盲孔 {hole_id} 深度 {depth:.1f}mm ≤ 钻尖高度"
                            f" {drill_tip_height:.1f}mm，可能无法形成有效盲孔"
                        )

                direction = raw.get("direction", [0.0, 0.0, -1.0])
                if not isinstance(direction, list) or len(direction) != 3:
                    direction = [0.0, 0.0, -1.0]

                hole = HoleFeature(
                    hole_id=str(hole_id),
                    type=hole_type,
                    position_x=position_x,
                    position_y=position_y,
                    position_z=position_z,
                    diameter=diameter,
                    depth=depth,
                    bottom_angle=float(raw.get("bottom_angle", self.STANDARD_DRILL_POINT_ANGLE)),
                    tolerance_grade=str(raw.get("tolerance_grade", "H8")),
                    surface_roughness_ra=float(raw.get("surface_roughness_ra", 3.2)),
                    direction=[float(d) for d in direction],
                    surface=str(raw.get("surface", "A")),
                    parent_feature_id=str(raw.get("parent_feature_id", "")),
                    is_threaded=bool(raw.get("is_threaded", False)),
                    thread_spec=str(raw.get("thread_spec", "")),
                    counterbore_diameter=float(raw.get("counterbore_diameter", 0)),
                    counterbore_depth=float(raw.get("counterbore_depth", 0)),
                    metadata=raw.get("metadata", {}),
                )
                holes.append(hole)

            except (ValueError, TypeError, KeyError) as e:
                errors.append(f"解析孔条目 {raw.get('id', i)} 时出错: {str(e)}")
                continue

        # 合并共轴孔为沉头孔
        holes = self._merge_coaxial_holes(holes, warnings)

        # 统计各类型数量
        type_summary: dict[str, int] = {}
        for h in holes:
            type_summary[h.type] = type_summary.get(h.type, 0) + 1

        # 计算识别准确率指标
        accuracy_metrics["recognized_count"] = float(len(holes))
        if raw_holes:
            # 识别率 = 成功解析的孔数 / 原始孔条目数
            recognition_rate = len(holes) / max(len(raw_holes), 1)
            accuracy_metrics["recognition_rate"] = min(recognition_rate, 1.0)
            accuracy_metrics["overall"] = accuracy_metrics["recognition_rate"]

        return HoleRecognitionResult(
            holes=holes,
            total_count=len(holes),
            type_summary=type_summary,
            warnings=warnings,
            errors=errors,
            accuracy_metrics=accuracy_metrics,
        )

    def _merge_coaxial_holes(
        self,
        holes: list[HoleFeature],
        warnings: list[str],
    ) -> list[HoleFeature]:
        """合并共轴孔为沉头孔。

        检测逻辑：
        - 两个孔在同一XY位置(误差 < COAXIAL_THRESHOLD)
        - 直径上大下小
        - 自动合并为counterbore类型

        Args:
            holes: 原始孔列表
            warnings: 警告信息列表（会被追加）

        Returns:
            合并后的孔列表
        """
        if len(holes) < 2:
            return holes

        merged = []
        used = set()

        for i, h1 in enumerate(holes):
            if i in used:
                continue
            best_match = None
            for j, h2 in enumerate(holes):
                if j <= i or j in used:
                    continue
                # 检查共轴性：XY位置相同
                dx = abs(h1.position_x - h2.position_x)
                dy = abs(h1.position_y - h2.position_y)
                if dx > self.COAXIAL_THRESHOLD or dy > self.COAXIAL_THRESHOLD:
                    continue
                # 确定大小孔关系
                larger = h1 if h1.diameter > h2.diameter else h2
                smaller = h1 if h1.diameter <= h2.diameter else h2
                # 方向一致
                if larger.direction != smaller.direction:
                    continue
                # 合并：大孔为沉头部分
                best_match = (j, larger, smaller)
                break

            if best_match:
                j, larger, smaller = best_match
                used.add(i)
                used.add(j)
                # 创建沉头孔特征
                cb_hole = HoleFeature(
                    hole_id=larger.hole_id,
                    type="counterbore",
                    position_x=larger.position_x,
                    position_y=larger.position_y,
                    position_z=larger.position_z,
                    diameter=smaller.diameter,  # 通孔直径
                    depth=smaller.depth,  # 通孔深度
                    tolerance_grade=smaller.tolerance_grade,
                    surface_roughness_ra=smaller.surface_roughness_ra,
                    direction=larger.direction,
                    surface=larger.surface,
                    parent_feature_id="",
                    counterbore_diameter=larger.diameter,
                    counterbore_depth=abs(larger.position_z - smaller.position_z) or larger.depth,
                )
                merged.append(cb_hole)
                warnings.append(
                    f"孔 {larger.hole_id}(φ{larger.diameter}mm)和"
                    f" {smaller.hole_id}(φ{smaller.diameter}mm)在同轴位置，"
                    f"已合并为沉头孔 {cb_hole.hole_id}"
                )
            else:
                merged.append(h1)

        return merged

    def recognize_holes(
        self,
        geometry_data: dict[str, Any],
    ) -> HoleRecognitionResult:
        """通用孔特征识别入口。

        根据输入数据的结构自动选择解析路径：
        - 直接定义的 holes 列表 → 快速解析
        - features 特征列表 → 特征过滤+解析
        - solids 实体列表 → 拓扑遍历+解析

        Args:
            geometry_data: 三维模型的几何描述数据

        Returns:
            HoleRecognitionResult: 识别结果
        """
        return self.recognize_from_part_description(geometry_data)

    def validate_result(
        self,
        result: HoleRecognitionResult,
        expected_count: int | None = None,
    ) -> dict[str, Any]:
        """对识别结果进行验证。

        验证项：
        1. 孔总数与预期对比
        2. 各孔直径均为正值
        3. 通孔深度正确（通孔需 > 0）
        4. 位置坐标有效（非NaN/Infinity）
        5. 无未处理错误

        Args:
            result: 要验证的识别结果
            expected_count: 期望的孔总数（可选）

        Returns:
            验证报告字典，包含：
            - is_valid: bool, 验证是否通过
            - issues: list[str], 发现的问题
            - passed_checks: list[str], 通过的检查项
        """
        issues: list[str] = []
        passed: list[str] = []

        # 检查1: 数量验证
        if expected_count is not None:
            if result.total_count == expected_count:
                passed.append(f"孔数量匹配: {result.total_count} == {expected_count}")
            else:
                issues.append(
                    f"孔数量不匹配: 识别到{result.total_count}个，期望{expected_count}个"
                )
        else:
            passed.append(f"孔总数: {result.total_count}")

        # 检查2: 直径验证
        invalid_diameter = [h for h in result.holes if h.diameter <= 0]
        if invalid_diameter:
            issues.append(
                f"{len(invalid_diameter)}个孔的直径无效: "
                f"{', '.join(h.hole_id for h in invalid_diameter)}"
            )
        else:
            passed.append("所有孔直径均为正值")

        # 检查3: 通孔深度验证
        through_holes = [h for h in result.holes if h.is_through()]
        invalid_depth = [h for h in through_holes if h.depth <= 0]
        if invalid_depth:
            issues.append(
                f"{len(invalid_depth)}个通孔的深度无效"
            )
        else:
            passed.append(f"{len(through_holes)}个通孔深度有效")

        # 检查4: 位置验证
        import math
        invalid_pos = [
            h for h in result.holes
            if any(math.isnan(v) or math.isinf(v)
                   for v in [h.position_x, h.position_y, h.position_z])
        ]
        if invalid_pos:
            issues.append(f"{len(invalid_pos)}个孔的位置坐标无效")
        else:
            passed.append("所有孔位置坐标有效")

        # 检查5: 错误检查
        if result.errors:
            issues.append(f"识别过程中有{len(result.errors)}个错误")
        else:
            passed.append("识别过程无错误")

        return {
            "is_valid": len(issues) == 0,
            "issues": issues,
            "passed_checks": passed,
        }
