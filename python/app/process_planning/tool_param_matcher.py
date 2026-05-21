"""刀具与切削参数匹配模块。

基于知识库(ProcessPlanningDataManager)实现刀具推荐和切削参数匹配。
根据工件材料和加工特征(孔特征)，查询知识库返回最优刀具和切削参数。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

from app.data.process_data_manager import (
    ProcessPlanningDataManager,
    MaterialEntry,
    ToolEntry,
    CuttingParameterEntry,
    QueryError,
)


@dataclass
class MatchedTool:
    """匹配的刀具推荐结果。

    Attributes:
        tool: 匹配到的刀具条目
        cutting_params: 匹配到的切削参数
        suitability_score: 适用度评分(0-100) - 基于直径匹配、材质匹配等
        match_reason: 匹配原因说明
        warnings: 使用注意事项
    """
    tool: ToolEntry
    cutting_params: Optional[CuttingParameterEntry] = None
    suitability_score: float = 80.0
    match_reason: str = ""
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the matched tool result to a dictionary representation.

        Returns:
            A dictionary containing tool details, suitability score, match
            reason, warnings, and cutting parameters (if available).
        """
        result: dict[str, Any] = {
            "tool_id": self.tool.id,
            "tool_name": self.tool.name,
            "tool_series": self.tool.series,
            "tool_material": self.tool.material,
            "diameter_mm": self.tool.diameter_mm,
            "application": self.tool.application,
            "suitability_score": round(self.suitability_score, 1),
            "match_reason": self.match_reason,
            "warnings": self.warnings,
        }
        if self.cutting_params:
            result["cutting_parameters"] = {
                "cutting_speed_m_per_min": (
                    f"{self.cutting_params.cutting_speed_min_mpm}-"
                    f"{self.cutting_params.cutting_speed_max_mpm}"
                ),
                "feed_rate": (
                    f"{self.cutting_params.feed_min_mmpr}-"
                    f"{self.cutting_params.feed_max_mmpr} "
                    f"{self.cutting_params.feed_unit}"
                ),
                "description": self.cutting_params.description,
            }
        return result


@dataclass
class HoleProcessPlan:
    """单个孔的加工工艺方案。

    Attributes:
        hole_id: 孔标识符
        hole_type: 孔类型(through_hole/blind_hole/counterbore/center_hole)
        operations: 该孔的加工工序列表
            例如对于通孔：["打中心孔", "钻孔"]
            对于精密通孔：["打中心孔", "钻孔", "铰孔"]
    """
    hole_id: str
    hole_type: str
    operations: list[str] = field(default_factory=list)
    tools: list[MatchedTool] = field(default_factory=list)
    estimated_time_min: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Convert the process plan to a dictionary representation.

        Returns:
            A dictionary containing hole ID, type, operations list,
            matched tools, and estimated time.
        """
        return {
            "hole_id": self.hole_id,
            "hole_type": self.hole_type,
            "operations": self.operations,
            "tools": [t.to_dict() for t in self.tools],
            "estimated_time_min": round(self.estimated_time_min, 2),
        }


class ToolParamMatcher:
    """刀具与参数匹配器。

    根据工件材料和孔特征信息，查询知识库返回优化的刀具选择和加工参数。

    匹配策略（三级优先级）：
    1. 精确匹配：材料ID + 刀具系列完全匹配 → 直接返回知识库中的切削参数
    2. 近似匹配：材料类别匹配 + 刀具系列匹配 → 使用同类材料的参数
    3. 通用匹配：仅刀具系列匹配 → 返回该系列刀具列表，使用默认参数

    使用示例:
        matcher = ToolParamMatcher()
        # 为45#钢的φ8mm通孔匹配刀具和参数
        plan = matcher.plan_for_hole(
            material_id="material_45steel",
            material_category="carbon_steel",
            hole_diameter=8.0,
            hole_type="through_hole",
            tolerance_grade="H8"
        )
    """

    # 钻孔工序序列模板
    # 格式: {孔类型: [工序名称, 对应的process查询名]}
    HOLE_PROCESS_TEMPLATES: dict[str, list[tuple[str, str]]] = {
        "through_hole": [
            ("打中心孔定位", "打中心孔定位"),
            ("钻孔", "钻孔"),
        ],
        "blind_hole": [
            ("打中心孔定位", "打中心孔定位"),
            ("钻孔(盲孔)", "钻孔"),
        ],
        "counterbore": [
            ("打中心孔定位", "打中心孔定位"),
            ("钻通孔", "钻孔"),
            ("锪沉头孔", "钻孔"),
        ],
        "center_hole": [
            ("打中心孔定位", "打中心孔定位"),
        ],
        "threaded_hole": [
            ("打中心孔定位", "打中心孔定位"),
            ("钻底孔", "钻孔"),
            ("攻螺纹", "钻孔"),
        ],
    }

    def __init__(self, data_manager: ProcessPlanningDataManager | None = None) -> None:
        """初始化匹配器。

        Args:
            data_manager: 工艺数据管理器实例。若为None则自动创建
        """
        self._data = data_manager or ProcessPlanningDataManager()

    def match_tool_for_hole(
        self,
        material_id: str,
        material_category: str,
        hole_diameter: float,
        process_name: str,
    ) -> MatchedTool:
        """为指定孔特征匹配刀具和切削参数。

        Args:
            material_id: 材料ID（如 'material_45steel'）
            material_category: 材料类别（如 'carbon_steel'）
            hole_diameter: 孔的公称直径 (mm)
            process_name: 加工工序名称（如 '钻孔', '打中心孔定位'）

        Returns:
            MatchedTool: 匹配结果，包含刀具和切削参数

        Raises:
            QueryError: 当任一查询参数无效时
        """
        if not material_id or not material_id.strip():
            raise QueryError("材料ID不能为空")
        if not process_name or not process_name.strip():
            raise QueryError("加工工序名称不能为空")

        # Step 1: 查询该工序适用的所有刀具
        all_tools = self._data.get_tools_by_material_and_process(
            material_category,
            process_name,
        )

        if not all_tools:
            return MatchedTool(
                tool=ToolEntry(
                    id="fallback",
                    series="twist_drill",
                    name=f"麻花钻 φ{hole_diameter}mm(通用)",
                    diameter_mm=hole_diameter,
                    material="HSS",
                    application=process_name,
                ),
                suitability_score=30.0,
                match_reason=(
                    f"知识库中未找到 {material_category}+{process_name} 的刀具，"
                    f"返回通用刀具建议"
                ),
                warnings=["建议向知识库添加该组合的专用刀具数据"],
            )

        # Step 2: 按直径匹配最佳刀具
        # 选择直径最接近hole_diameter的刀具（优先选择大于等于孔直径的，其次选最大的）
        best_tool = self._select_best_diameter(all_tools, hole_diameter)

        # Step 3: 查询该材料+刀具系列的切削参数
        cutting_params = None
        cp_list = self._data.get_cutting_parameters(material_id, best_tool.series)
        if cp_list:
            cutting_params = cp_list[0]  # 取第一个匹配的参数组

        # Step 4: 计算适用度评分
        score = self._calculate_suitability(
            best_tool,
            hole_diameter,
            cutting_params,
        )

        # Step 5: 生成匹配说明
        match_reason = self._build_match_reason(best_tool, hole_diameter, cutting_params)

        # Step 6: 生成使用注意事项
        warnings = self._generate_warnings(best_tool, hole_diameter, cutting_params)

        return MatchedTool(
            tool=best_tool,
            cutting_params=cutting_params,
            suitability_score=score,
            match_reason=match_reason,
            warnings=warnings,
        )

    def plan_for_hole(
        self,
        material_id: str,
        material_category: str,
        hole_diameter: float,
        hole_type: str = "through_hole",
        tolerance_grade: str = "H8",
    ) -> HoleProcessPlan:
        """为单个孔生成完整的加工工艺方案。

        包括：所有工序的刀具选择、切削参数匹配。
        遵循工艺规则：基准先行(假定已完成) → 先面后孔(假定已完成) →
        中心孔定位 → 钻孔。

        Args:
            material_id: 材料ID
            material_category: 材料类别
            hole_diameter: 孔直径 (mm)
            hole_type: 孔类型(through_hole/blind_hole/counterbore/center_hole)
            tolerance_grade: 公差等级(H7/H8/H9等)

        Returns:
            HoleProcessPlan: 包含完整工序列表和刀具匹配结果
        """
        process_template = self.HOLE_PROCESS_TEMPLATES.get(
            hole_type,
            self.HOLE_PROCESS_TEMPLATES["through_hole"],
        )

        plan = HoleProcessPlan(
            hole_id="",
            hole_type=hole_type,
        )
        matched_tools: list[MatchedTool] = []
        operations: list[str] = []
        total_time = 0.0

        for op_name, process_query_name in process_template:
            operations.append(op_name)

            matched = self.match_tool_for_hole(
                material_id=material_id,
                material_category=material_category,
                hole_diameter=hole_diameter,
                process_name=process_query_name,
            )
            matched_tools.append(matched)

            # 估算加工时间
            op_time = self._estimate_drilling_time(
                hole_diameter=hole_diameter,
                tool=matched.tool,
                params=matched.cutting_params,
                is_center_drill=("中心" in op_name),
            )
            total_time += op_time

        plan.operations = operations
        plan.tools = matched_tools
        plan.estimated_time_min = total_time
        return plan

    def get_material_info(self, material_name: str) -> Optional[MaterialEntry]:
        """查询材料基本信息。

        Args:
            material_name: 材料名称（支持模糊匹配）

        Returns:
            MaterialEntry: 材料信息，未找到返回None
        """
        return self._data.get_material_by_name(material_name)

    def get_all_process_rules(self) -> list[dict[str, Any]]:
        """获取所有工艺规则。

        Returns:
            规则字典列表
        """
        rules = self._data.get_all_process_rules()
        return [
            {
                "id": r.id,
                "name": r.name,
                "category": r.category,
                "description": r.description,
                "details": r.details,
            }
            for r in rules
        ]

    def get_available_tools(self, series: str) -> list[dict[str, Any]]:
        """获取指定系列的可用刀具列表。

        Args:
            series: 刀具系列(twist_drill/endmill/face_mill/center_drill)

        Returns:
            刀具信息列表
        """
        tools = self._data.get_tools_by_series(series)
        return [
            {
                "id": t.id,
                "name": t.name,
                "series": t.series,
                "diameter_mm": t.diameter_mm,
                "material": t.material,
                "application": t.application,
            }
            for t in sorted(tools, key=lambda t: t.diameter_mm)
        ]

    def _select_best_diameter(
        self,
        tools: list[ToolEntry],
        target_diameter: float,
    ) -> ToolEntry:
        """从刀具列表中选择直径最接近目标直径的。

        优先级：
        1. 直径 ≥ 目标直径（确保能加工出所需孔）
        2. 在≥目标直径的刀具中选最小的（减少余量）

        Args:
            tools: 候选刀具列表
            target_diameter: 目标直径 (mm)

        Returns:
            最优匹配的刀具
        """
        # 筛选直径≥目标直径的刀具
        oversize = [t for t in tools if t.diameter_mm >= target_diameter]
        if oversize:
            # 选择最接近目标直径的（即最小的≥目标直径的刀具）
            return min(oversize, key=lambda t: t.diameter_mm - target_diameter)

        # 若无≥目标直径的刀具，选择直径最大的作为备选
        return max(tools, key=lambda t: t.diameter_mm)

    def _calculate_suitability(
        self,
        tool: ToolEntry,
        target_diameter: float,
        params: Optional[CuttingParameterEntry],
    ) -> float:
        """计算刀具适用度评分 (0-100)。

        评分维度：
        - 直径匹配度（50分）：直径越接近目标 → 分数越高
        - 切削参数可用性（30分）：有切削参数 → +30
        - 刀具材质适配（20分）：硬质合金优于HSS

        Args:
            tool: 匹配的刀具
            target_diameter: 目标直径
            params: 切削参数（可为None）

        Returns:
            适用度评分
        """
        score = 50.0

        # 直径匹配评分
        dia_diff = abs(tool.diameter_mm - target_diameter)
        if dia_diff == 0:
            score += 20  # 完美匹配
        elif dia_diff <= 1.0:
            score += 15  # 偏差 ≤ 1mm
        elif dia_diff <= 3.0:
            score += 10  # 偏差 ≤ 3mm
        else:
            score += 5   # 偏差较大

        # 切削参数评分
        if params:
            score += 20

        # 材质评分
        if tool.material == "carbide":
            score += 10  # 硬质合金适用于高速高效加工

        return min(score, 100.0)

    def _build_match_reason(
        self,
        tool: ToolEntry,
        target_diameter: float,
        params: Optional[CuttingParameterEntry],
    ) -> str:
        """生成刀具匹配原因说明。

        详细解释为何推荐该刀具，包括：
        - 直径选择依据
        - 刀具材质理由
        - 切削参数来源
        """
        dia_diff = abs(tool.diameter_mm - target_diameter)

        if dia_diff == 0:
            dia_reason = f"刀具直径φ{tool.diameter_mm}mm与孔直径φ{target_diameter}mm精确匹配"
        else:
            dia_reason = (
                f"刀具直径φ{tool.diameter_mm}mm覆盖目标直径φ{target_diameter}mm"
                f"(偏差{dia_diff:.1f}mm)"
            )

        mat_reason = {
            "carbide": "硬质合金材质，适用于高效高速钻孔",
            "HSS": "高速钢材质，适用于一般材料钻孔",
            "ceramic": "陶瓷材质，适用于硬材料高速加工",
        }.get(tool.material, f"{tool.material}材质")

        if params:
            param_reason = (
                f"，切削参数来自知识库: "
                f"{params.cutting_speed_min_mpm}-{params.cutting_speed_max_mpm} m/min"
            )
        else:
            param_reason = "，建议根据经验设定切削参数"

        return f"{dia_reason}。{mat_reason}{param_reason}。"

    def _generate_warnings(
        self,
        tool: ToolEntry,
        target_diameter: float,
        params: Optional[CuttingParameterEntry],
    ) -> list[str]:
        """生成刀具使用注意事项。

        检测项：
        - 直径偏差过大 (≥2mm): 需确认余量是否可接受
        - 缺少切削参数: 需人工设定
        - HSS加工硬材料: 需降低切削速度
        """
        warnings: list[str] = []
        dia_diff = abs(tool.diameter_mm - target_diameter)

        if dia_diff >= 2.0:
            warnings.append(
                f"刀具直径偏差{dia_diff:.1f}mm较大，"
                f"建议检查孔加工余量是否可接受"
            )

        if params is None:
            warnings.append(
                "该组合暂无切削参数数据，请根据实际工况设定"
                "切削速度和进给量"
            )

        return warnings

    def _estimate_drilling_time(
        self,
        hole_diameter: float,
        tool: ToolEntry,
        params: Optional[CuttingParameterEntry],
        is_center_drill: bool = False,
        depth: float = 20.0,
    ) -> float:
        """估算单个孔的加工时间 (分钟)。

        计算公式:
        - 主轴转速 rpm = 1000 * vc / (π * d)
        - 进给速度 mm/min = rpm * fz
        - 加工时间 = (钻进深度 + 安全距离) / 进给速度 + 辅助时间

        Args:
            hole_diameter: 孔直径 (mm)
            tool: 刀具信息
            params: 切削参数
            is_center_drill: 是否为中心钻工序
            depth: 钻孔深度 (mm)

        Returns:
            估算加工时间 (分钟)
        """
        import math

        # 切削速度 (m/min) - 取推荐范围的中值
        if params:
            vc = (params.cutting_speed_min_mpm + params.cutting_speed_max_mpm) / 2
            feed = (params.feed_min_mmpr + params.feed_max_mmpr) / 2
            if "齿" in params.feed_unit:
                # 立铣刀进给按每齿计算
                rpm = 1000 * vc / (math.pi * tool.diameter_mm) if tool.diameter_mm > 0 else 2000
                feed_rate = rpm * feed * 2  # 2刃钻头
            else:
                # 钻头进给按每转计算
                rpm = 1000 * vc / (math.pi * tool.diameter_mm) if tool.diameter_mm > 0 else 2000
                feed_rate = rpm * feed
        else:
            # 无切削参数时使用经验值
            vc = 20.0  # HSS钻45#钢 ~20m/min
            rpm = 1000 * vc / (math.pi * tool.diameter_mm) if tool.diameter_mm > 0 else 2000
            feed_rate = rpm * 0.15  # 默认进给0.15mm/r

        if is_center_drill:
            # 中心钻工序时间：短距离钻进
            drilling_depth = 3.0  # 中心孔深度通常3-5mm
            safe_distance = 2.0  # 安全接近距离
        else:
            drilling_depth = depth
            safe_distance = 5.0  # 钻孔安全接近距离 + 啄钻回退

        # 加工时间 = 切削行程 / 进给速度
        cutting_length = drilling_depth + safe_distance
        cutting_time = cutting_length / max(feed_rate, 1.0)  # 避免除零

        # 辅助时间：换刀/进退刀
        auxiliary_time = 0.3 if is_center_drill else 0.5

        return round(cutting_time + auxiliary_time, 2)
