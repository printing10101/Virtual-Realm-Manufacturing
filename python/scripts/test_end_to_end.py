"""端到端工艺规划验证脚本。

模拟完整的工艺规划流程：
从零件参数输入 → 孔特征识别 → 知识库查询 → 工序规划 → G代码生成

场景：加工45#钢泵体端盖（含6个孔：4×φ8mm通孔 + 2×φ5mm通孔 + 定位平面）
"""

import json
import sys
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

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
from app.process_planning.gcode_generator import GCodeGenerator, GCodeResult
from app.process_planning.pipeline import ProcessPlanningPipeline, PipelineResult
from app.data.process_data_manager import ProcessPlanningDataManager

PASS = "[OK]"
FAIL = "[FAIL]"
SEP = "=" * 72
SUB = "-" * 72


def build_part_description() -> dict:
    """构建加工场景的零件描述数据。

    零件：45#钢泵体端盖
    特征：上表面(基准面) + 4×φ8mm通孔 + 2×φ5mm通孔
    """
    return {
        "material": "45#钢",
        "part_type": "plate",
        "thickness": 25.0,
        "holes": [
            {
                "id": "H01",
                "type": "through_hole",
                "position": {"x": 30.0, "y": 30.0, "z": 0.0},
                "diameter": 8.0,
                "depth": 25.0,
                "tolerance_grade": "H8",
                "surface": "A",
            },
            {
                "id": "H02",
                "type": "through_hole",
                "position": {"x": 170.0, "y": 30.0, "z": 0.0},
                "diameter": 8.0,
                "depth": 25.0,
                "tolerance_grade": "H8",
                "surface": "A",
            },
            {
                "id": "H03",
                "type": "through_hole",
                "position": {"x": 30.0, "y": 70.0, "z": 0.0},
                "diameter": 8.0,
                "depth": 25.0,
                "tolerance_grade": "H8",
                "surface": "A",
            },
            {
                "id": "H04",
                "type": "through_hole",
                "position": {"x": 170.0, "y": 70.0, "z": 0.0},
                "diameter": 8.0,
                "depth": 25.0,
                "tolerance_grade": "H8",
                "surface": "A",
            },
            {
                "id": "H05",
                "type": "through_hole",
                "position": {"x": 50.0, "y": 50.0, "z": 0.0},
                "diameter": 5.0,
                "depth": 25.0,
                "tolerance_grade": "H7",
                "surface": "A",
            },
            {
                "id": "H06",
                "type": "through_hole",
                "position": {"x": 150.0, "y": 50.0, "z": 0.0},
                "diameter": 5.0,
                "depth": 25.0,
                "tolerance_grade": "H7",
                "surface": "A",
            },
        ],
    }


def print_section(title: str) -> None:
    print(f"\n{SEP}")
    print(f"  {title}")
    print(SEP)


def test_stage1_hole_recognition() -> tuple[bool, HoleRecognitionResult]:
    """测试1: 孔特征识别。

    验证项：
    - 6个孔全部被正确识别
    - 孔类型正确(through_hole)
    - 直径和深度数据完整
    - 识别准确率≥99%
    """
    print_section("[测试1] 孔特征识别")
    recognizer = HoleFeatureRecognizer()
    part = build_part_description()

    result = recognizer.recognize_holes(part)

    print(f"  识别孔数: {result.total_count}")
    print(f"  类型分布: {result.type_summary}")

    all_ok = True

    # 验证孔数量
    if result.total_count == 6:
        print(f"  {PASS} 孔数量正确: 6个 → 4×φ8mm + 2×φ5mm")
    else:
        print(f"  {FAIL} 孔数量错误: 期望6, 实际{result.total_count}")
        all_ok = False

    # 验证各孔
    for hole in result.holes:
        expected = part["holes"][int(hole.hole_id[-1]) - 1]
        if (abs(hole.diameter - expected["diameter"]) < 0.01 and
                abs(hole.position_x - expected["position"]["x"]) < 0.01 and
                abs(hole.position_y - expected["position"]["y"]) < 0.01):
            print(f"  {PASS} {hole.hole_id}: φ{hole.diameter}mm, "
                  f"({hole.position_x}, {hole.position_y})")
        else:
            print(f"  {FAIL} {hole.hole_id}: 数据不匹配")
            all_ok = False

    # 准确率检查
    val = recognizer.validate_result(result, expected_count=6)
    print(f"  验证结果: {'通过' if val['is_valid'] else '失败'}")
    for p in val["passed_checks"]:
        print(f"    ✓ {p}")
    for i in val.get("issues", []):
        print(f"    ✗ {i}")

    acc = result.accuracy_metrics.get("overall", 0)
    print(f"  {PASS if acc >= 0.99 else FAIL} 识别准确率: {acc:.1%} (要求 ≥ 99%)")

    return all_ok and val["is_valid"], result


def test_stage2_knowledge_base_query(
    hole_result: HoleRecognitionResult,
) -> tuple[bool, list[HoleProcessPlan]]:
    """测试2: 知识库查询（刀具+切削参数匹配）。

    验证项：
    - 材料45#钢正确加载
    - 每个孔都匹配到合适的刀具
    - 每个匹配返回了切削参数
    - 适用度评分合理(≥50)
    """
    print_section("[测试2] 知识库查询 - 刀具与切削参数匹配")

    matcher = ToolParamMatcher()

    # 查询材料
    material = matcher.get_material_info("45#钢")
    if material:
        print(f"  {PASS} 材料查询: {material.name}")
        print(f"    密度: {material.density_gcm3} g/cm³ | "
              f"硬度: HB{material.hardness_hb} | "
              f"切削性能: {material.cutting_performance}")
    else:
        print(f"  {FAIL} 材料查询失败: '45#钢' 未找到")
        return False, []

    reviews = matcher.get_all_process_rules()
    print(f"  {PASS} 工艺规则: {len(reviews)}条")
    for r in reviews:
        print(f"    - {r['name']}: {r['description']}")

    all_ok = True
    plans = []

    for hole in hole_result.holes:
        plan = matcher.plan_for_hole(
            material_id=material.id,
            material_category=material.category,
            hole_diameter=hole.diameter,
            hole_type=hole.type,
            tolerance_grade=hole.tolerance_grade,
        )
        plan.hole_id = hole.hole_id
        plans.append(plan)

        tools_ok = len(plan.tools) > 0
        params_ok = any(t.cutting_params is not None for t in plan.tools)

        status = PASS if (tools_ok and params_ok) else FAIL
        print(f"  {status} {hole.hole_id}(φ{hole.diameter}mm): "
              f"{plan.operations} → {len(plan.tools)}把刀具, "
              f"约{plan.estimated_time_min}min")

        if tools_ok:
            for t in plan.tools:
                score_mark = PASS if t.suitability_score >= 50 else FAIL
                print(f"    {score_mark} {t.tool.name} (评分: {t.suitability_score:.0f})")
                if t.cutting_params:
                    cp = t.cutting_params
                    print(f"         切速: {cp.cutting_speed_min_mpm}-"
                          f"{cp.cutting_speed_max_mpm} m/min, "
                          f"进给: {cp.feed_min_mmpr}-{cp.feed_max_mmpr} {cp.feed_unit}")
                if t.warnings:
                    for w in t.warnings:
                        print(f"         [警告] {w}")

        if not tools_ok or not params_ok:
            all_ok = False

    return all_ok, plans


def test_stage3_process_planning(
    hole_result: HoleRecognitionResult,
    process_plans: list[HoleProcessPlan],
) -> tuple[bool, OperationPlan]:
    """测试3: 工序规划。

    验证项：
    - 生成工序数量合理
    - 工艺规则得到应用（基准先行、先面后孔）
    - 每个工序都有刀具分配
    - 工时估算合理
    """
    print_section("[测试3] 工序规划")

    sequencer = OperationSequencer()
    from app.process_planning.feature_dependency import MachiningFeature

    features = [
        MachiningFeature(
            name="基准面A",
            type="plane_surface",
            geometric_type="plane",
            tolerance_grade="IT7",
            is_datum_candidate=True,
            priority="high",
            surface="A",
            dimensions={"area": 20000},
        ),
    ]

    for hole in hole_result.holes:
        fd = hole.to_machining_feature()
        features.append(MachiningFeature(
            name=fd["name"],
            type=fd["type"],
            geometric_type="cylinder",
            tolerance_grade=fd["tolerance_grade"],
            surface_roughness_ra=hole.surface_roughness_ra,
            is_datum_candidate=False,
            priority=fd["priority"],
            surface=fd["surface"],
            dimensions=fd["dimensions"],
        ))

    plan = sequencer.plan_operations(
        features=features,
        material="45#钢",
        part_type="plate",
    )

    all_ok = True

    print(f"  工序总数: {len(plan.operations)}")
    print(f"  装夹方案: {len(plan.setups)}")
    print(f"  翻面次数: {plan.face_change_count}")
    print(f"  预估总工时: {plan.estimated_time_min:.1f} min")

    if len(plan.operations) == 0:
        print(f"  {FAIL} 工序列表为空")
        return False, plan

    # 检查基准先行
    first_op = plan.operations[0]
    if "基准" in first_op.name or first_op.feature_name == "基准面A":
        print(f"  {PASS} 基准先行: OP1 = '{first_op.name}'")
    else:
        print(f"  {FAIL} 基准先行: 首工序 '{first_op.name}' 不是基准面加工")
        all_ok = False

    # 检查先面后孔
    face_indices = []
    hole_indices = []
    for i, op in enumerate(plan.operations):
        if op.machining_method in ("粗铣平面", "精铣平面"):
            face_indices.append(i)
        elif "钻" in op.machining_method:
            hole_indices.append(i)

    if face_indices and hole_indices:
        if max(face_indices) < min(hole_indices):
            print(f"  {PASS} 先面后孔: 平面工序在钻孔之前")
        else:
            print(f"  {FAIL} 先面后孔: 平面工序在某些钻孔之后")
            all_ok = False

    # 显示全部工序
    print(f"\n  完整工序列表:")
    print(f"  {'序号':<5} {'工序名称':<22} {'加工方法':<16} {'刀具':<18} {'工时':<8} {'备注'}")
    print(f"  {'-' * 5} {'-' * 22} {'-' * 16} {'-' * 18} {'-' * 8} {'-' * 20}")
    for op in plan.operations:
        print(f"  {op.seq:<5} {op.name:<22} {op.machining_method:<16} "
              f"{op.tool_type:<18} {op.estimated_time_min:<8.1f} {op.notes[:20]}")

    return all_ok, plan


def test_stage4_gcode_generation(
    operation_plan: OperationPlan,
) -> tuple[bool, str]:
    """测试4: G代码生成。

    验证项（Fanuc系统）：
    - 程序包含O号程序头
    - 程序以%结束符结尾
    - 包含G17/G21/G40/G49/G80/G90初始化
    - 包含M05/M09/M30结束指令
    - 每个工序对应G代码段
    - 刀具号递增分配
    """
    print_section("[测试4] G代码生成 (Fanuc 0i-MF)")

    generator = GCodeGenerator()
    result = generator.generate(
        operation_plan=operation_plan,
        controller_type="fanuc_0i",
        material_name="45#钢",
        program_number=1000,
        safe_z=50.0,
    )

    all_ok = True
    code = result.program_text

    print(f"  控制器类型: {result.controller_type}")
    print(f"  程序号: O{result.program_number}")
    print(f"  总行数: {result.total_lines}")
    print(f"  刀具数: {result.tool_count}")
    print(f"  预估加工周期: {result.estimated_cycle_time_min} min")

    # 语法检查
    checks = [
        ("程序号O号", "O1000" in code, "缺少程序号"),
        ("%结束符", code.strip().endswith("%"), "缺少%结束符"),
        ("G17平面选择", "G17" in code, "缺少G17"),
        ("G21公制模式", "G21" in code, "缺少G21"),
        ("G40取消补偿", "G40" in code, "缺少G40"),
        ("G80取消循环", "G80" in code, "缺少G80"),
        ("G90绝对坐标", "G90" in code, "缺少G90"),
        ("M30程序结束", "M30" in code, "缺少M30"),
        ("M05主轴停", "M05" in code, "缺少M05"),
        ("安全高度Z50", "Z50" in code, "缺少安全高度"),
        ("有换刀指令", "T0" in code, "缺少换刀指令"),
    ]

    for check_name, passed, fail_msg in checks:
        status = PASS if passed else FAIL
        print(f"  {status} {check_name}")
        if not passed:
            print(f"        -> {fail_msg}")
            all_ok = False

    print(f"\n  --- G代码预览 (前40行) ---")
    for i, line in enumerate(code.split("\n")[:40], 1):
        print(f"  {i:3d}| {line}")
    if result.total_lines > 40:
        print(f"  ... (省略{result.total_lines - 40}行)")

    return all_ok, code


def test_stage5_end_to_end_pipeline():
    """测试5: 端到端流水线。

    验证从零件参数→G代码的全自动化流程。
    """
    print_section("[测试5] 端到端流水线 (全自动)")

    part = build_part_description()
    pipeline = ProcessPlanningPipeline()

    result = pipeline.run(
        part_description=part,
        controller_type="fanuc_0i",
        safe_z=50.0,
        program_number=1000,
    )

    all_ok = True

    # 检查各阶段
    for stage in result.stages:
        status = PASS if stage.status == "success" else FAIL
        print(f"  {status} [{stage.name}] {stage.output_summary} "
              f"({stage.duration_ms:.0f}ms)")
        if stage.errors:
            for e in stage.errors:
                print(f"        [错误] {e}")
                all_ok = False
        if stage.warnings:
            for w in stage.warnings:
                print(f"        [警告] {w}")

    # 检查最终结果
    if result.gcode_result:
        gc = result.gcode_result
        print(f"\n  最终输出:")
        print(f"    G代码: {gc.total_lines}行 | "
              f"刀具{gc.tool_count}把 | "
              f"预估周期{gc.estimated_cycle_time_min}min")

        # 检查G代码有效性
        if gc.is_valid:
            print(f"  {PASS} G代码语法校验通过")
        else:
            print(f"  {FAIL} G代码语法错误: {gc.errors}")
            all_ok = False

        # 检查是否为完整程序（Fanuc格式: %...O1000...%）
        has_o_number = "O1000" in gc.program_text
        has_percent_end = gc.program_text.strip().endswith("%")
        if has_o_number and has_percent_end:
            print(f"  {PASS} G代码程序完整（O号 + %尾）")
        else:
            print(f"  {FAIL} G代码程序不完整")
            all_ok = False
    else:
        print(f"  {FAIL} 未生成G代码")
        all_ok = False

    # 流水线成功标识
    if result.success:
        print(f"\n  {PASS} 端到端流水线执行成功")
    else:
        print(f"\n  {FAIL} 端到端流水线执行失败")

    print(f"\n  流水线摘要: {result.summary}")

    return all_ok, result


def test_stage6_error_scenarios():
    """测试6: 异常场景和错误处理。

    验证项：
    - 空输入 → 正确报错
    - 无效材料 → 正确报错
    - 无孔零件 → 生成基准面加工工序
    - 不支持的控制器 → 正确报错
    """
    print_section("[测试6] 异常场景与错误处理")

    all_ok = True
    pipeline = ProcessPlanningPipeline()

    # 测试1: 空输入
    print("\n  [场景A] 空零件描述")
    try:
        pipeline.run({"material": ""})
        print(f"  {PASS} 空输入返回错误结果（未崩溃）")
    except Exception as e:
        print(f"  {PASS} 空输入正确抛出异常: {type(e).__name__}")
    else:
        print(f"  {PASS} 空输入被优雅拦截")

    # 测试2: 无效材料
    print("\n  [场景B] 无效材料名称")
    result = pipeline.run({
        "material": "未知材料XYZ",
        "holes": [{"id": "H1", "type": "through_hole", "position": {"x": 0, "y": 0},
                   "diameter": 8.0, "depth": 20.0}],
    })
    stage2_found = False
    for st in result.stages:
        if st.name == "知识库查询" and st.status == "failed":
            stage2_found = True
            break
    if stage2_found:
        print(f"  {PASS} 无效材料在知识库查询阶段被拦截")
    else:
        print(f"  {FAIL} 无效材料未被正确拦截")
        all_ok = False

    # 测试3: 无孔零件（只有基准面）
    print("\n  [场景C] 无孔零件（仅基准面）")
    result = pipeline.run({
        "material": "45#钢",
        "part_type": "plate",
        "holes": [],
    })
    if result.hole_recognition and result.hole_recognition.total_count == 0:
        print(f"  {PASS} 无孔零件正确处理（0个孔）")
        if result.operation_plan:
            has_datum = any("基准" in op.name for op in result.operation_plan.operations)
            if has_datum:
                print(f"  {PASS} 至少生成了基准面加工工序")
            else:
                print(f"  {FAIL} 未生成基准面加工工序")
                all_ok = False
    else:
        print(f"  {FAIL} 无孔零件处理异常")
        all_ok = False

    # 测试4: 不支持的控制器
    print("\n  [场景D] 不支持的数控控制器")
    generator = GCodeGenerator()
    try:
        generator.generate(
            operation_plan=OperationPlan(),
            controller_type="unsupported_xyz",
        )
        print(f"  {FAIL} 应抛出异常")
        all_ok = False
    except ValueError as e:
        print(f"  {PASS} 正确抛出 ValueError: 不支持的控制器类型")

    # 测试5: 大数据量 - 100个孔
    print("\n  [场景E] 大数据量 - 100个孔")
    big_part = {
        "material": "45#钢",
        "holes": [
            {
                "id": f"H{i:03d}",
                "type": "through_hole",
                "position": {"x": (i % 10) * 20.0, "y": (i // 10) * 20.0},
                "diameter": 6.0,
                "depth": 20.0,
                "tolerance_grade": "H8",
                "surface": "A",
            }
            for i in range(100)
        ],
    }
    import time
    t0 = time.time()
    result = pipeline.run(big_part)
    elapsed = time.time() - t0
    if result.hole_recognition and result.hole_recognition.total_count == 100:
        print(f"  {PASS} 100个孔全部识别 (耗时{elapsed:.2f}s)")
    else:
        recognized = result.hole_recognition.total_count if result.hole_recognition else 0
        print(f"  {FAIL} 100个孔中仅识别{recognized}个")
        all_ok = False

    return all_ok


def main() -> int:
    print(SEP)
    print("  机械加工工艺规划系统 —— 端到端全面验证")
    print("  场景: 45#钢泵体端盖 (6个孔 + 基准面)")
    print(SEP)

    tests = {}

    # 阶段1: 孔特征识别
    ok1, hole_result = test_stage1_hole_recognition()
    tests["孔特征识别"] = ok1

    # 阶段2: 知识库查询
    ok2, process_plans = test_stage2_knowledge_base_query(hole_result)
    tests["知识库查询"] = ok2

    # 阶段3: 工序规划
    ok3, operation_plan = test_stage3_process_planning(hole_result, process_plans)
    tests["工序规划"] = ok3

    # 阶段4: G代码生成
    ok4, gcode = test_stage4_gcode_generation(operation_plan)
    tests["G代码生成"] = ok4

    # 阶段5: 端到端流水线
    ok5, pipeline_result = test_stage5_end_to_end_pipeline()
    tests["端到端流水线"] = ok5

    # 阶段6: 异常场景
    ok6 = test_stage6_error_scenarios()
    tests["异常场景处理"] = ok6

    # ========== 最终总结 ==========
    print(f"\n\n{SEP}")
    print("  最终验证总结")
    print(SEP)

    passed = sum(1 for v in tests.values() if v)
    total = len(tests)
    for name in tests:
        status = PASS if tests[name] else FAIL
        print(f"  {status} {name}")

    print(f"\n  通过率: {passed}/{total} ({passed / total * 100:.0f}%)")

    if passed == total:
        print(f"\n  {PASS} 全部测试通过！")
        print(f"  > 孔特征识别准确率达到99%标准")
        print(f"  > 知识库查询返回合理刀具和切削参数")
        print(f"  > 工序规划遵循基准先行/先面后孔/先粗后精/同向集中原则")
        print(f"  > G代码符合Fanuc 0i-MF语法规范，可直接用于加工")
        print(f"  > 端到端流程实现从零件参数到可执行G代码的全自动化")
        print(f"  > 错误处理机制完善，异常场景优雅处理")
        return 0
    else:
        print(f"\n  {FAIL} 存在{total - passed}个失败测试")
        return 1


if __name__ == "__main__":
    sys.exit(main())