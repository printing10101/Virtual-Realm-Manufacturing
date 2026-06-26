"""端到端工艺规划流水线。

将孔特征识别、知识库匹配、工序规划、G代码生成整合为单一自动化流水线。
实现从零件参数输入到可执行G代码输出的全流程自动化处理。

流水线阶段（6步）：
┌─────────────────────────────────────────────────────────┐
│ Step 1: 输入验证 ─── 校验零件描述数据的完整性和有效性   │
│ Step 2: 孔特征识别 ─ 调用HoleFeatureRecognizer           │
│ Step 3: 知识库查询 ─ 调用ToolParamMatcher匹配刀具和参数  │
│ Step 4: 工艺规划 ─── 调用OperationSequencer生成工序序列  │
│ Step 5: G代码生成 ── 调用GCodeGenerator输出数控程序      │
│ Step 6: 结果验证 ─── 校验输出完整性和语法正确性           │
└─────────────────────────────────────────────────────────┘

质量标准：
- 端到端流程无人工干预即可完成
- 输出的G代码可直接用于实际数控加工
- 特征识别准确率 ≥ 99%
- G代码符合目标数控系统语法规范
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)

from app.process_planning.hole_recognizer import (
    HoleFeatureRecognizer,
    HoleRecognitionResult,
)
from app.process_planning.tool_param_matcher import (
    ToolParamMatcher,
    HoleProcessPlan,
)
from app.process_planning.operation_sequencer import (
    OperationSequencer,
    OperationPlan,
)
from app.process_planning.feature_dependency import MachiningFeature
from app.process_planning.gcode_generator import GCodeGenerator, GCodeResult
from app.process_planning.boss_recognizer import BossFeature
from app.process_planning.cavity_recognizer import CavityFeature
from app.process_planning.plane_recognizer import PlaneFeature
from app.process_planning.sim_integration import SimulationIntegration, SimulationResult
from app.data.process_data_manager import ProcessPlanningDataManager, DataLoadError, QueryError


@dataclass
class PipelineStage:
    """单个流水线阶段的执行记录。

    Attributes:
        name: 阶段名称
        status: 执行状态 (success/failed/skipped)
        duration_ms: 执行耗时(毫秒)
        input_summary: 输入摘要
        output_summary: 输出摘要
        errors: 该阶段的错误列表
        warnings: 该阶段的警告列表
    """
    name: str
    status: str = "pending"
    duration_ms: float = 0.0
    input_summary: str = ""
    output_summary: str = ""
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "duration_ms": round(self.duration_ms, 2),
            "input_summary": self.input_summary,
            "output_summary": self.output_summary,
            "errors": self.errors,
            "warnings": self.warnings,
        }


@dataclass
class PipelineResult:
    """端到端流水线的完整执行结果。

    Attributes:
        success: 整体是否成功
        stages: 各阶段执行记录
        hole_recognition: 孔特征识别结果
        process_plans: 每个孔的加工工艺方案
        operation_plan: 整体工序规划
        gcode_result: G代码生成结果
        total_duration_ms: 总耗时(毫秒)
        summary: 流水线执行摘要
    """
    success: bool = False
    stages: list[PipelineStage] = field(default_factory=list)
    hole_recognition: Optional[HoleRecognitionResult] = None
    process_plans: list[HoleProcessPlan] = field(default_factory=list)
    operation_plan: Optional[OperationPlan] = None
    gcode_result: Optional[GCodeResult] = None
    simulation: Optional[dict[str, Any]] = None
    total_duration_ms: float = 0.0
    summary: str = ""

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "success": self.success,
            "total_duration_ms": round(self.total_duration_ms, 2),
            "summary": self.summary,
            "stages": [s.to_dict() for s in self.stages],
        }
        if self.hole_recognition:
            result["hole_recognition"] = self.hole_recognition.to_dict()
        if self.process_plans:
            result["process_plans"] = [p.to_dict() for p in self.process_plans]
        if self.operation_plan:
            result["operation_plan"] = self.operation_plan.to_dict()
        if self.gcode_result:
            result["gcode"] = {
                "controller_type": self.gcode_result.controller_type,
                "program_number": self.gcode_result.program_number,
                "total_lines": self.gcode_result.total_lines,
                "operations_count": self.gcode_result.operations_count,
                "tool_count": self.gcode_result.tool_count,
                "estimated_cycle_time_min": self.gcode_result.estimated_cycle_time_min,
                "is_valid": self.gcode_result.is_valid,
                "program_text": self.gcode_result.program_text,
                "warnings": self.gcode_result.warnings,
                "errors": self.gcode_result.errors,
            }
        # 始终包含仿真字段，确保接口一致性
        result["simulation"] = self.simulation if self.simulation else {
            "status": "not_run",
            "score": 0.0,
            "passed": False,
            "recommendation": "not_recommended",
            "cutting_force": None,
            "chatter_stability": None,
            "duration_ms": 0.0,
            "error_message": "仿真未执行（流水线提前终止）",
        }
        return result


class ProcessPlanningPipeline:
    """端到端工艺规划流水线。

    将孔特征识别、知识库查询、工序规划和G代码生成集成到统一的
    自动化流水线中，实现从零件参数输入到可执行G代码输出的全流程。

    使用方式:
        pipeline = ProcessPlanningPipeline()
        result = pipeline.run(part_description)
        if result.success:
            gcode = result.gcode_result.program_text

    错误处理策略：
    - 输入验证失败 → 立即终止，返回详细错误
    - 孔识别警告 → 继续执行，警告记入结果
    - 知识库查询失败 → 使用默认参数继续
    - 工序规划失败 → 终止，无法生成后续工序
    - G代码语法错误 → 仍输出代码，错误记入结果
    """

    def __init__(self) -> None:
        """初始化流水线的所有子模块。

        初始化顺序：
        1. 加载工艺知识库（materials/tools/cutting_params/rules）
        2. 创建孔特征识别器
        3. 创建刀具参数匹配器（注入知识库）
        4. 创建工序排序器
        5. 创建G代码生成器
        """
        try:
            self._data_manager = ProcessPlanningDataManager()
            self._data_valid = True
        except (DataLoadError, Exception):
            self._data_manager = None
            self._data_valid = False

        self._hole_recognizer = HoleFeatureRecognizer()
        self._tool_matcher = ToolParamMatcher(self._data_manager)
        self._operation_sequencer = OperationSequencer()
        self._gcode_generator = GCodeGenerator()

    def run(
        self,
        part_description: dict[str, Any],
        controller_type: str = "fanuc_0i",
        safe_z: float = 50.0,
        program_number: int = 1000,
    ) -> PipelineResult:
        """执行完整的端到端工艺规划流水线。

        Args:
            part_description: 零件描述数据，必须至少包含:
                - holes (list): 孔列表 [{id, type, position, diameter, depth}, ...]
                - material (str): 材料名称，如 '45#钢'
                - part_type (str, optional): 零件类型，默认'general'
            controller_type: 目标数控系统类型
            safe_z: 安全Z高度 (mm)
            program_number: 数控程序号

        Returns:
            PipelineResult: 完整的流水线执行结果

        输入验证要求：
        - part_description 不能为 None 或空
        - 必须包含 material 字段
        - holes 字段应为列表（可以为空）
        """
        import time
        pipeline_start = time.time()

        result = PipelineResult()
        stages: list[PipelineStage] = []

        # ========== Stage 1: 输入验证 ==========
        stage1 = self._validate_input(part_description)
        stages.append(stage1)
        if stage1.status == "failed":
            result.stages = stages
            result.summary = f"流水线在输入验证阶段失败: {'; '.join(stage1.errors)}"
            return result

        material_name = part_description.get("material", "45#钢")
        part_type = part_description.get("part_type", "general")

        # ========== Stage 2: 孔特征识别 ==========
        stage2_start = time.time()
        hole_result = self._hole_recognizer.recognize_holes(part_description)

        stage2 = PipelineStage(
            name="孔特征识别",
            status="success" if not hole_result.errors else "failed",
            duration_ms=(time.time() - stage2_start) * 1000,
            input_summary=f"零件材料: {material_name}",
            output_summary=(
                f"识别孔数: {hole_result.total_count}, "
                f"类型分布: {hole_result.type_summary}"
            ),
            errors=hole_result.errors,
            warnings=hole_result.warnings,
        )

        # 孔识别失败 → 终止流水线
        if hole_result.errors:
            stage2.status = "failed"
            stages.extend([stage1, stage2])
            result.hole_recognition = hole_result
            result.stages = stages
            result.summary = f"流水线在孔识别阶段失败: {'; '.join(hole_result.errors)}"
            return result

        stages.append(stage2)
        result.hole_recognition = hole_result

        # ========== Stage 3: 知识库查询 (材料+刀具+参数匹配) ==========
        stage3_start = time.time()
        process_plans: list[HoleProcessPlan] = []

        # 查询材料信息
        material_info = self._tool_matcher.get_material_info(material_name)
        if not material_info:
            stage3 = PipelineStage(
                name="知识库查询",
                status="failed",
                duration_ms=(time.time() - stage3_start) * 1000,
                input_summary=f"材料查询: '{material_name}'",
                errors=[f"材料 '{material_name}' 在知识库中不存在"],
            )
            stages.extend([stage1, stage2, stage3])
            result.hole_recognition = hole_result
            result.stages = stages
            result.summary = f"流水线在知识库查询阶段失败: 材料 '{material_name}' 未找到"
            return result

        material_id = material_info.id
        material_category = material_info.category

        # 为每个孔匹配刀具和切削参数
        unmatched_holes = 0
        for hole in hole_result.holes:
            try:
                plan = self._tool_matcher.plan_for_hole(
                    material_id=material_id,
                    material_category=material_category,
                    hole_diameter=hole.diameter,
                    hole_type=hole.type,
                    tolerance_grade=hole.tolerance_grade,
                )
                plan.hole_id = hole.hole_id
                process_plans.append(plan)
            except QueryError as e:
                unmatched_holes += 1
                stage2.warnings.append(f"孔{hole.hole_id}刀具匹配失败: {e}")
                # 使用默认参数创建方案
                process_plans.append(HoleProcessPlan(
                    hole_id=hole.hole_id,
                    hole_type=hole.type,
                    operations=["钻中心孔", "钻孔"],
                    tools=[],
                    estimated_time_min=2.0,
                ))

        stage3 = PipelineStage(
            name="知识库查询",
            status="success",
            duration_ms=(time.time() - stage3_start) * 1000,
            input_summary=f"材料: {material_id}({material_category}), 孔数: {hole_result.total_count}",
            output_summary=(
                f"匹配方案: {len(process_plans)}个, "
                f"刀具总数: {sum(len(p.tools) for p in process_plans)}, "
                f"匹配失败: {unmatched_holes}"
            ),
            warnings=[f"{unmatched_holes}个孔使用默认刀具"] if unmatched_holes else [],
        )
        stages.append(stage3)
        result.process_plans = process_plans

        # ========== Stage 4: 工序规划 ==========
        stage4_start = time.time()

        features = self._build_features(
            hole_result,
            process_plans,
            part_description,
        )

        if not features:
            stage4 = PipelineStage(
                name="工序规划",
                status="failed",
                duration_ms=(time.time() - stage4_start) * 1000,
                errors=["无法构建加工特征列表——无有效特征"],
            )
            stages.append(stage4)
            result.stages = stages
            result.summary = "流水线在工序规划阶段失败: 无法构建特征列表"
            return result

        operation_plan = self._operation_sequencer.plan_operations(
            features=features,
            material=material_name,
            part_type=part_type,
        )

        stage4 = PipelineStage(
            name="工序规划",
            status="success",
            duration_ms=(time.time() - stage4_start) * 1000,
            input_summary=f"特征数: {len(features)}, 零件类型: {part_type}",
            output_summary=(
                f"规划工序: {len(operation_plan.operations)}个, "
                f"装夹方案: {len(operation_plan.setups)}个, "
                f"预估总工时: {operation_plan.estimated_time_min}min"
            ),
        )
        stages.append(stage4)
        result.operation_plan = operation_plan

        # ========== Stage 4.5: 仿真验证 ==========
        stage4_5_start = time.time()
        simulation_result = self._run_simulation(
            material=material_name,
            operation_plan=operation_plan,
        )

        stage4_5 = PipelineStage(
            name="仿真验证",
            status=simulation_result.get("status", "failed"),
            duration_ms=simulation_result.get("duration_ms", 0),
            input_summary=f"材料: {material_name}, 工序数: {len(operation_plan.operations)}",
            output_summary=(
                f"仿真评分: {simulation_result.get('score', 0):.1f}, "
                f"推荐级别: {simulation_result.get('recommendation', 'unknown')}"
            ),
            errors=[simulation_result.get("error_message")] if simulation_result.get("error_message") else [],
        )
        stages.append(stage4_5)
        result.simulation = simulation_result

        # ========== Stage 5: G代码生成 ==========
        stage5_start = time.time()

        try:
            gcode_result = self._gcode_generator.generate(
                operation_plan=operation_plan,
                controller_type=controller_type,
                material_name=material_name,
                program_number=program_number,
                safe_z=safe_z,
            )

            stage5 = PipelineStage(
                name="G代码生成",
                status="success" if gcode_result.is_valid else "completed_with_errors",
                duration_ms=(time.time() - stage5_start) * 1000,
                input_summary=f"工序数: {len(operation_plan.operations)}",
                output_summary=(
                    f"代码行数: {gcode_result.total_lines}, "
                    f"刀具数: {gcode_result.tool_count}, "
                    f"预估周期: {gcode_result.estimated_cycle_time_min}min"
                ),
                errors=gcode_result.errors,
                warnings=gcode_result.warnings,
            )
        except (OSError, ValueError, TypeError, KeyError, RuntimeError) as e:
            stage5 = PipelineStage(
                name="G代码生成",
                status="failed",
                duration_ms=(time.time() - stage5_start) * 1000,
                errors=[f"G代码生成异常: {type(e).__name__}"],
            )
            stages.append(stage5)
            result.stages = stages
            result.summary = f"流水线在G代码生成阶段失败: {type(e).__name__}"
            logger.error("G代码生成阶段失败: %s", e, exc_info=True)
            return result

        stages.append(stage5)
        result.gcode_result = gcode_result

        # ========== Stage 6: 结果验证 ==========
        stage6_start = time.time()

        validation_errors, validation_warnings = self._validate_pipeline_output(result)

        stage6 = PipelineStage(
            name="结果验证",
            status="success" if not validation_errors else "failed",
            duration_ms=(time.time() - stage6_start) * 1000,
            output_summary=(
                "验证通过" if not validation_errors
                else f"发现{len(validation_errors)}个错误"
            ),
            errors=validation_errors,
            warnings=validation_warnings,
        )
        stages.append(stage6)

        # ========== 汇总 ==========
        result.stages = stages
        result.success = all(s.status == "success" for s in stages)
        result.total_duration_ms = (time.time() - pipeline_start) * 1000

        # 构建摘要
        summary_parts = [
            f"流水线执行{'成功' if result.success else '部分失败'} ({result.total_duration_ms:.0f}ms)",
            f"零件: {material_name}({part_type})",
            f"孔识别: {hole_result.total_count}个孔 ({hole_result.type_summary})",
            f"工序规划: {len(operation_plan.operations)}个工序, "
            f"{operation_plan.estimated_time_min:.1f}min预估工时",
        ]
        if gcode_result:
            summary_parts.append(
                f"G代码: {gcode_result.total_lines}行 "
                f"({gcode_result.tool_count}把刀具, "
                f"{gcode_result.estimated_cycle_time_min:.1f}min预估周期)"
            )
        result.summary = " | ".join(summary_parts)

        return result

    def _validate_input(self, part_description: dict[str, Any]) -> PipelineStage:
        """验证输入数据的完整性和格式。

        校验项：
        1. part_description 不能为 None/空
        2. material 字段必须存在且非空
        3. holes 字段应为列表类型
        4. 知识库是否成功加载
        """
        stage = PipelineStage(name="输入验证")
        errors = []
        warnings = []

        if part_description is None:
            errors.append("零件描述数据为None")
            stage.status = "failed"
            stage.errors = errors
            return stage

        if not isinstance(part_description, dict):
            errors.append(f"零件描述数据类型无效: {type(part_description).__name__}, 应为dict")
            stage.status = "failed"
            stage.errors = errors
            return stage

        if not part_description:
            errors.append("零件描述数据为空字典")
            stage.status = "failed"
            stage.errors = errors
            return stage

        material = part_description.get("material", "")
        if not material:
            errors.append("缺少必需的'material'字段——请指定零件材料")
        else:
            stage.input_summary = f"材料: {material}"

        holes = part_description.get("holes", part_description.get("features", []))
        if not isinstance(holes, list):
            errors.append("'holes'字段应为数组类型")
        else:
            stage.input_summary += f", 孔数据: {len(holes)}条"

        if not self._data_valid:
            warnings.append(
                "工艺知识库加载失败，将使用内置默认值进行刀具和参数匹配"
            )

        stage.status = "success" if not errors else "failed"
        stage.errors = errors
        stage.warnings = warnings
        return stage

    def _build_features(
        self,
        hole_result: HoleRecognitionResult,
        process_plans: list[HoleProcessPlan],
        part_description: dict[str, Any],
    ) -> list[MachiningFeature]:
        features: list[MachiningFeature] = []

        features.append(MachiningFeature(
            name="基准面A-上表面",
            type="plane_surface",
            geometric_type="plane",
            tolerance_grade="IT7",
            surface_roughness_ra=1.6,
            is_datum_candidate=True,
            priority="high",
            surface="A",
            dimensions={"area": 20000, "length": 200, "width": 100},
        ))

        for hole, plan in zip(hole_result.holes, process_plans):
            hole_dict = hole.to_machining_feature()

            mf = MachiningFeature(
                name=hole.hole_id,
                type=hole_dict["type"],
                geometric_type="cylinder",
                tolerance_grade=hole_dict["tolerance_grade"],
                surface_roughness_ra=hole.surface_roughness_ra,
                is_datum_candidate=hole.type == "center_hole",
                priority=hole_dict["priority"],
                surface=hole.surface,
                dimensions={
                    "diameter": hole.diameter,
                    "depth": hole.depth,
                    "position_x": hole.position_x,
                    "position_y": hole.position_y,
                },
            )
            features.append(mf)

        cavity_features = part_description.get("cavities", [])
        for cav in cavity_features:
            if isinstance(cav, CavityFeature):
                d = cav.to_machining_feature()
            elif isinstance(cav, dict):
                d = cav
            else:
                continue
            features.append(MachiningFeature(
                name=d["name"],
                type=d["type"],
                geometric_type=d["geometric_type"],
                tolerance_grade=d["tolerance_grade"],
                surface_roughness_ra=d["surface_roughness_ra"],
                is_datum_candidate=d["is_datum_candidate"],
                priority=d["priority"],
                surface=d["surface"],
                dimensions=d["dimensions"],
                parent_feature=d["parent_feature"],
                tolerances=d["tolerances"],
            ))

        boss_features = part_description.get("bosses", [])
        for boss in boss_features:
            if isinstance(boss, BossFeature):
                d = boss.to_machining_feature()
            elif isinstance(boss, dict):
                d = boss
            else:
                continue
            features.append(MachiningFeature(
                name=d["name"],
                type=d["type"],
                geometric_type=d["geometric_type"],
                tolerance_grade=d["tolerance_grade"],
                surface_roughness_ra=d["surface_roughness_ra"],
                is_datum_candidate=d["is_datum_candidate"],
                priority=d["priority"],
                surface=d["surface"],
                dimensions=d["dimensions"],
                parent_feature=d["parent_feature"],
                tolerances=d["tolerances"],
            ))

        plane_features = part_description.get("planes", [])
        for plane in plane_features:
            if isinstance(plane, PlaneFeature):
                d = plane.to_machining_feature()
            elif isinstance(plane, dict):
                d = plane
            else:
                continue
            features.append(MachiningFeature(
                name=d["name"],
                type=d["type"],
                geometric_type=d["geometric_type"],
                tolerance_grade=d["tolerance_grade"],
                surface_roughness_ra=d["surface_roughness_ra"],
                is_datum_candidate=d["is_datum_candidate"],
                priority=d["priority"],
                surface=d["surface"],
                dimensions=d["dimensions"],
                parent_feature=d["parent_feature"],
                tolerances=d["tolerances"],
            ))

        return features

    def _validate_pipeline_output(
        self,
        result: PipelineResult,
    ) -> tuple[list[str], list[str]]:
        """校验流水线输出的完整性和正确性。

        校验项：
        1. G代码程序非空
        2. G代码程序语法校验通过
        3. 孔识别结果可靠（准确率达标）
        4. 工序规划至少包含1个工序
        """
        errors: list[str] = []
        warnings: list[str] = []

        if result.hole_recognition:
            hr = result.hole_recognition
            if not hr.is_reliable:
                warnings.append(
                    f"孔识别可靠性偏低: {hr.accuracy_metrics.get('overall', 0):.1%}"
                )
            if hr.warnings:
                warnings.extend(hr.warnings)

        if result.operation_plan:
            op_plan = result.operation_plan
            if not op_plan.operations:
                errors.append("工序规划结果为空")
            if len(op_plan.setups) == 0:
                warnings.append("未生成装夹方案")
        else:
            errors.append("缺少工序规划结果")

        if result.gcode_result:
            gc = result.gcode_result
            if not gc.program_text or len(gc.program_text.strip()) < 10:
                errors.append("G代码程序过短（可能生成失败）")
            if gc.errors:
                errors.extend(gc.errors)
            if gc.warnings:
                warnings.extend(gc.warnings)
            if gc.tool_count == 0:
                warnings.append("未使用任何刀具（可能为仅回零程序）")
        else:
            errors.append("缺少G代码生成结果")

        return errors, warnings

    def _run_simulation(
        self,
        material: str,
        operation_plan: OperationPlan,
    ) -> dict[str, Any]:
        """运行仿真验证。

        调用仿真集成器对工序规划结果进行切削力和颤振稳定性分析。

        Args:
            material: 材料名称
            operation_plan: 工序规划结果

        Returns:
            包含仿真结果的字典，包括：
            - status: 仿真状态 ('success', 'timeout', 'failed', 'not_run')
            - score: 仿真评分 (0-100)
            - passed: 是否通过仿真
            - recommendation: 推荐级别 ('recommended', 'acceptable', 'not_recommended')
            - cutting_force: 切削力预测结果
            - chatter_stability: 颤振稳定性分析结果
            - duration_ms: 仿真耗时(毫秒)
        """
        try:
            simulator = SimulationIntegration(timeout_seconds=5.0)

            # 从工序规划中提取典型加工参数
            # 使用第一个工序的参数作为代表（如有多个工序，可考虑加权平均）
            if operation_plan.operations:
                first_op = operation_plan.operations[0]
                # 从工序中提取切削参数（如果存在）
                cutting_params = first_op.get("cutting_params", {})
                spindle_rpm = cutting_params.get("spindle_rpm", 8000)
                feed_rate = cutting_params.get("feed_rate", 1200)
                depth_of_cut = cutting_params.get("depth_of_cut", 2.0)
                tool = first_op.get("tool", "endmill_d10")
            else:
                # 默认参数
                spindle_rpm = 8000
                feed_rate = 1200
                depth_of_cut = 2.0
                tool = "endmill_d10"

            # 运行仿真
            sim_result = simulator.run_simulation(
                material=material,
                tool=tool,
                spindle_rpm=spindle_rpm,
                feed_rate=feed_rate,
                depth_of_cut=depth_of_cut,
            )

            return sim_result.to_dict()

        except (OSError, RuntimeError, ValueError, TypeError, KeyError) as e:
            # 仿真失败时返回降级结果，不阻断主流程
            logger.error("仿真服务调用失败: %s", e, exc_info=True)
            return {
                "status": "failed",
                "score": 0.0,
                "passed": False,
                "recommendation": "not_recommended",
                "cutting_force": None,
                "chatter_stability": None,
                "duration_ms": 0.0,
                "error_message": f"仿真服务调用失败: {type(e).__name__}",
            }


def plan_process(
    feature: str = "pocket_cavity",
    material: str = "45steel",
    tool: str = "endmill_d10",
    **kwargs,
) -> dict[str, Any]:
    """工艺规划便捷函数。

    提供简化的工艺规划接口，支持端到端测试和快速调用。

    Args:
        feature: 加工特征类型 (如 'pocket_cavity', 'hole', 'slot')
        material: 材料名称 (如 '45steel', 'aluminum_6061')
        tool: 刀具标识 (如 'endmill_d10', 'drill_d8')
        **kwargs: 其他可选参数

    Returns:
        工艺规划结果字典，包含：
        - success: 是否成功
        - simulation: 仿真结果（包含 score, passed, recommendation 等）
        - operation_plan: 工序规划结果
        - gcode: G代码生成结果
        - 其他流水线输出字段
    """
    pipeline = ProcessPlanningPipeline()

    # 构建零件描述
    part_description = {
        "material": material,
        "part_type": kwargs.get("part_type", "general"),
        "holes": kwargs.get("holes", []),
        "features": kwargs.get("features", []),
    }

    # 如果指定了特征类型，添加到 features
    if feature:
        part_description["features"].append({
            "type": feature,
            "name": f"{feature}_001",
        })

    # 执行工艺规划流水线
    result = pipeline.run(
        part_description=part_description,
        controller_type=kwargs.get("controller_type", "fanuc_0i"),
        safe_z=kwargs.get("safe_z", 50.0),
        program_number=kwargs.get("program_number", 1000),
    )

    # 转换为字典格式返回
    return result.to_dict()
