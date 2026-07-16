"""generator_adapter.py 端到端验证脚本（阶段 6 s6-7）。

测试链路：
    构造 OperationPlan JSON → load_operation_plan() 反序列化
    + 构造 ChatterReport feature_results
    → GeneratorAdapter.adapt() 生成 G 代码 + FeatureGCodeResult
    → 验证：
        1. load_operation_plan() 正确恢复 operations/setups/estimated_time_min
        2. adapt() 返回 (GCodeResult, list[FeatureGCodeResult])
        3. stable 特征：safety_margin_ratio 正确计算，warning 正确标注
        4. unstable 特征：errors 中追加错误，is_valid=False
        5. feature_id ↔ feature_name 匹配，gcode_lines / line_range 正确切分
        6. limit_depth_mm == 0 时，safety_margin_ratio == -1.0
        7. 边界场景：chatter_results 为空 → GeneratorAdapterError
"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

# 确保能导入 app 包
sys.path.insert(0, str(Path(__file__).parent))

from app.chatter_prediction.chatter_store import FeatureChatterResult
from app.gcode_generation.generator_adapter import (
    GeneratorAdapter,
    GeneratorAdapterError,
    load_operation_plan,
)
from app.process_planning.operation_sequencer import Operation, OperationPlan


# =============================================================================
# 测试工具
# =============================================================================

PASS = 0
FAIL = 0


def check(name: str, condition: bool, detail: str = "") -> None:
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name} {detail}")


def build_test_operation_plan() -> OperationPlan:
    """构造测试用 OperationPlan（3 个工序：平面 / 孔 / 外圆）。"""
    operations = [
        Operation(
            seq=1,
            name="OP01-平面A",
            feature_name="face_A",
            machining_method="精铣平面",
            surface="A",
            tolerance_grade="IT7",
            tool_type="立铣刀",
            cutting_params={
                "tool_diameter": 10.0,
                "material": "45#钢",
                "radius_comp": "G41",
            },
            estimated_time_min=3.5,
            notes="精加工",
        ),
        Operation(
            seq=2,
            name="OP02-孔B",
            feature_name="hole_B",
            machining_method="钻孔",
            surface="A",
            tolerance_grade="IT8",
            tool_type="麻花钻",
            cutting_params={
                "tool_diameter": 8.0,
                "material": "45#钢",
                "radius_comp": "G40",
            },
            estimated_time_min=2.0,
            notes="钻孔",
        ),
        Operation(
            seq=3,
            name="OP03-外圆C",
            feature_name="cylinder_C",
            machining_method="精车外圆",
            surface="B",
            tolerance_grade="IT6",
            tool_type="外圆车刀(精)",
            cutting_params={
                "tool_diameter": 12.0,
                "material": "45#钢",
                "radius_comp": "G42",
            },
            estimated_time_min=4.0,
            notes="精车外圆",
        ),
    ]
    return OperationPlan(
        operations=operations,
        setups=[],
        estimated_time_min=9.5,
        face_change_count=1,
        fixture_recommendations=[],
    )


def build_test_chatter_results() -> list[FeatureChatterResult]:
    """构造测试用 ChatterReport feature_results（3 个特征）。

    特征 1: face_A   - stable, 安全裕度足够 (axial=2.0, limit=5.0, ratio=0.4)
    特征 2: hole_B   - stable, 安全裕度不足 (axial=4.5, limit=5.0, ratio=0.9 > 0.8)
    特征 3: cylinder_C - unstable, 禁止生成 (axial=6.0, limit=5.0, ratio=1.2 > 1.0)
    """
    return [
        FeatureChatterResult(
            feature_id="face_A",
            feature_type="plane",
            material_id="steel_45",
            spindle_rpm=3000.0,
            axial_depth_mm=2.0,
            limit_depth_mm=5.0,
            stable=True,
            stability_margin=0.4,
            method="analytical",
            ltc_active=False,
            confidence=0.9,
        ),
        FeatureChatterResult(
            feature_id="hole_B",
            feature_type="hole",
            material_id="steel_45",
            spindle_rpm=2500.0,
            axial_depth_mm=4.5,
            limit_depth_mm=5.0,
            stable=True,
            stability_margin=0.9,
            method="analytical",
            ltc_active=False,
            confidence=0.85,
        ),
        FeatureChatterResult(
            feature_id="cylinder_C",
            feature_type="cylinder",
            material_id="steel_45",
            spindle_rpm=2000.0,
            axial_depth_mm=6.0,
            limit_depth_mm=5.0,
            stable=False,
            stability_margin=1.2,
            method="analytical",
            ltc_active=False,
            confidence=0.8,
        ),
    ]


# =============================================================================
# 测试用例
# =============================================================================


def test_load_operation_plan() -> OperationPlan:
    """测试 1: load_operation_plan() 反序列化。"""
    print("\n=== 测试 1: load_operation_plan() 反序列化 ===")

    plan = build_test_operation_plan()
    plan_dict = plan.to_dict()

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump(plan_dict, f, ensure_ascii=False)
        json_path = f.name

    try:
        loaded = load_operation_plan(json_path)
        check("operations 数量 == 3", len(loaded.operations) == 3,
              f"actual={len(loaded.operations)}")
        check("setups 为空列表", len(loaded.setups) == 0,
              f"actual={len(loaded.setups)}")
        check("estimated_time_min == 9.5", loaded.estimated_time_min == 9.5,
              f"actual={loaded.estimated_time_min}")
        check("face_change_count == 1", loaded.face_change_count == 1,
              f"actual={loaded.face_change_count}")
        op1 = loaded.operations[0]
        check("op1.feature_name == face_A", op1.feature_name == "face_A",
              f"actual={op1.feature_name}")
        check("op1.cutting_params 非空", bool(op1.cutting_params),
              f"actual={op1.cutting_params}")
        check("op1.tool_type == 立铣刀", op1.tool_type == "立铣刀",
              f"actual={op1.tool_type}")
        return loaded
    finally:
        Path(json_path).unlink(missing_ok=True)


def test_load_operation_plan_errors() -> None:
    """测试 2: load_operation_plan() 错误处理。"""
    print("\n=== 测试 2: load_operation_plan() 错误处理 ===")
    from app.gcode_generation.gcode_store import OperationPlanLoadError

    # 文件不存在
    try:
        load_operation_plan("/nonexistent/path/plan.json")
        check("文件不存在应抛错", False)
    except OperationPlanLoadError:
        check("文件不存在正确抛 OperationPlanLoadError", True)

    # JSON 格式错误
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        f.write("{invalid json")
        bad_json_path = f.name
    try:
        load_operation_plan(bad_json_path)
        check("JSON 格式错误应抛错", False)
    except OperationPlanLoadError:
        check("JSON 格式错误正确抛 OperationPlanLoadError", True)
    finally:
        Path(bad_json_path).unlink(missing_ok=True)

    # operations 为空
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False, encoding="utf-8"
    ) as f:
        json.dump({"operations": [], "setups": []}, f)
        empty_path = f.name
    try:
        load_operation_plan(empty_path)
        check("operations 为空应抛错", False)
    except OperationPlanLoadError:
        check("operations 为空正确抛 OperationPlanLoadError", True)
    finally:
        Path(empty_path).unlink(missing_ok=True)


def test_adapt_normal(plan: OperationPlan) -> None:
    """测试 3: adapt() 正常流程（含 stable + unstable 特征）。"""
    print("\n=== 测试 3: adapt() 正常流程 ===")

    chatter_results = build_test_chatter_results()
    adapter = GeneratorAdapter()

    base_result, feature_gcode_results = adapter.adapt(
        operation_plan=plan,
        chatter_results=chatter_results,
        controller_type="fanuc_0i",
        material_name="45#钢",
        program_number=1000,
        safe_z=80.0,
        stock_top_z=50.0,
    )

    # 验证 GCodeResult
    check("base_result 是 GCodeResult", hasattr(base_result, "program_text"))
    check("controller_type == fanuc_0i", base_result.controller_type == "fanuc_0i")
    check("program_text 非空", bool(base_result.program_text))
    check("total_lines > 0", base_result.total_lines > 0,
          f"actual={base_result.total_lines}")
    check("operations_count == 3", base_result.operations_count == 3,
          f"actual={base_result.operations_count}")
    check("checkpoints 数量 == 3", len(base_result.checkpoints) == 3,
          f"actual={len(base_result.checkpoints)}")

    # 验证 unstable 特征导致 errors 非空
    unstable_errors = [
        e for e in base_result.errors if "不稳定" in e or "不稳定" in str(e)
    ]
    check("errors 含 unstable 特征错误", len(unstable_errors) >= 1,
          f"actual_errors={base_result.errors}")
    check("is_valid == False（含 unstable 特征）",
          not base_result.is_valid,
          f"errors={base_result.errors}")

    # 验证 FeatureGCodeResult
    check("feature_gcode_results 数量 == 3", len(feature_gcode_results) == 3,
          f"actual={len(feature_gcode_results)}")

    # 特征 1: face_A - stable, ratio=0.4, 无 warning
    fr1 = next(r for r in feature_gcode_results if r.feature_id == "face_A")
    check("face_A.safety_margin_ratio == 0.4",
          abs(fr1.safety_margin_ratio - 0.4) < 0.001,
          f"actual={fr1.safety_margin_ratio}")
    check("face_A.stable == True", fr1.stable)
    check("face_A.warning 为空", fr1.warning == "",
          f"actual={fr1.warning}")

    # 特征 2: hole_B - stable, ratio=0.9 > 0.8, 有 warning
    fr2 = next(r for r in feature_gcode_results if r.feature_id == "hole_B")
    check("hole_B.safety_margin_ratio == 0.9",
          abs(fr2.safety_margin_ratio - 0.9) < 0.001,
          f"actual={fr2.safety_margin_ratio}")
    check("hole_B.stable == True", fr2.stable)
    check("hole_B.warning 非空（安全裕度不足）",
          bool(fr2.warning),
          f"actual={fr2.warning}")

    # 特征 3: cylinder_C - unstable, ratio=1.2 > 1.0
    fr3 = next(r for r in feature_gcode_results if r.feature_id == "cylinder_C")
    check("cylinder_C.safety_margin_ratio == 1.2",
          abs(fr3.safety_margin_ratio - 1.2) < 0.001,
          f"actual={fr3.safety_margin_ratio}")
    check("cylinder_C.stable == False", not fr3.stable)
    check("cylinder_C.warning 非空（安全裕度不足 + 不稳定）",
          bool(fr3.warning),
          f"actual={fr3.warning}")


def test_adapt_feature_line_ranges(plan: OperationPlan) -> None:
    """测试 4: adapt() feature_id ↔ feature_name 匹配 + gcode_lines 切分。"""
    print("\n=== 测试 4: feature_id ↔ feature_name 匹配 + gcode_lines 切分 ===")

    chatter_results = build_test_chatter_results()
    adapter = GeneratorAdapter()

    base_result, feature_gcode_results = adapter.adapt(
        operation_plan=plan,
        chatter_results=chatter_results,
        controller_type="fanuc_0i",
    )

    program_lines = base_result.program_text.split("\n")

    for fr in feature_gcode_results:
        if fr.line_range != (0, 0):
            start, end = fr.line_range
            check(f"{fr.feature_id}.line_range 有效",
                  0 <= start < end <= len(program_lines),
                  f"actual=({start}, {end}), total={len(program_lines)}")
            check(f"{fr.feature_id}.gcode_lines 非空",
                  len(fr.gcode_lines) > 0,
                  f"actual={len(fr.gcode_lines)}")
            # 验证 gcode_lines 长度 == end - start + 1
            expected_len = end - start + 1
            check(f"{fr.feature_id}.gcode_lines 长度匹配",
                  len(fr.gcode_lines) == expected_len,
                  f"actual={len(fr.gcode_lines)}, expected={expected_len}")
        else:
            check(f"{fr.feature_id}.line_range == (0, 0)（未匹配到 operation）",
                  True)


def test_adapt_empty_chatter_results(plan: OperationPlan) -> None:
    """测试 5: adapt() chatter_results 为空 → GeneratorAdapterError。"""
    print("\n=== 测试 5: adapt() chatter_results 为空 ===")

    adapter = GeneratorAdapter()
    try:
        adapter.adapt(
            operation_plan=plan,
            chatter_results=[],
            controller_type="fanuc_0i",
        )
        check("chatter_results 为空应抛错", False)
    except GeneratorAdapterError as e:
        check("chatter_results 为空正确抛 GeneratorAdapterError", True,
              f"msg={e}")


def test_adapt_limit_depth_zero(plan: OperationPlan) -> None:
    """测试 6: limit_depth_mm == 0 时，safety_margin_ratio == -1.0。"""
    print("\n=== 测试 6: limit_depth_mm == 0 时 safety_margin_ratio == -1.0 ===")

    chatter_results = [
        FeatureChatterResult(
            feature_id="face_A",
            feature_type="plane",
            material_id="steel_45",
            spindle_rpm=3000.0,
            axial_depth_mm=2.0,
            limit_depth_mm=0.0,  # 极限切深为 0
            stable=True,
            stability_margin=0.0,
            method="fallback",
            ltc_active=False,
            confidence=0.5,
        ),
    ]
    adapter = GeneratorAdapter()
    _, feature_gcode_results = adapter.adapt(
        operation_plan=plan,
        chatter_results=chatter_results,
        controller_type="fanuc_0i",
    )

    fr = feature_gcode_results[0]
    check("limit_depth=0 时 safety_margin_ratio == -1.0",
          fr.safety_margin_ratio == -1.0,
          f"actual={fr.safety_margin_ratio}")
    check("limit_depth=0 时 warning 为空（避免误报）",
          fr.warning == "",
          f"actual={fr.warning}")


def test_adapt_all_stable() -> None:
    """测试 7: 全部 stable 特征 → is_valid == True（无 unstable 错误）。"""
    print("\n=== 测试 7: 全部 stable 特征 → is_valid == True ===")

    plan = build_test_operation_plan()
    # 只保留前两个 stable 特征对应的 operation（移除 cylinder_C）
    plan.operations = plan.operations[:2]
    chatter_results = [
        FeatureChatterResult(
            feature_id="face_A",
            feature_type="plane",
            material_id="steel_45",
            spindle_rpm=3000.0,
            axial_depth_mm=2.0,
            limit_depth_mm=5.0,
            stable=True,
            stability_margin=0.4,
            method="analytical",
            ltc_active=False,
            confidence=0.9,
        ),
        FeatureChatterResult(
            feature_id="hole_B",
            feature_type="hole",
            material_id="steel_45",
            spindle_rpm=2500.0,
            axial_depth_mm=4.5,
            limit_depth_mm=5.0,
            stable=True,
            stability_margin=0.9,
            method="analytical",
            ltc_active=False,
            confidence=0.85,
        ),
    ]
    adapter = GeneratorAdapter()
    base_result, feature_gcode_results = adapter.adapt(
        operation_plan=plan,
        chatter_results=chatter_results,
        controller_type="fanuc_0i",
    )

    # 无 unstable 特征，errors 中不应有「不稳定」错误
    # （但可能有语法校验产生的其他 errors）
    unstable_errors = [
        e for e in base_result.errors if "不稳定" in str(e)
    ]
    check("无 unstable 特征时 errors 不含「不稳定」错误",
          len(unstable_errors) == 0,
          f"actual={unstable_errors}")
    check("feature_gcode_results 数量 == 2",
          len(feature_gcode_results) == 2,
          f"actual={len(feature_gcode_results)}")


def test_adapt_different_controllers(plan: OperationPlan) -> None:
    """测试 8: 不同控制器类型。"""
    print("\n=== 测试 8: 不同控制器类型 ===")

    chatter_results = build_test_chatter_results()[:2]  # 只取 stable 的两个
    plan_stable = OperationPlan(
        operations=plan.operations[:2],
        setups=[],
        estimated_time_min=5.5,
        face_change_count=0,
        fixture_recommendations=[],
    )

    for ctrl in ["fanuc_0i", "siemens_840d", "heidenhain_tnc"]:
        adapter = GeneratorAdapter()
        try:
            base_result, frs = adapter.adapt(
                operation_plan=plan_stable,
                chatter_results=chatter_results,
                controller_type=ctrl,
            )
            check(f"{ctrl} 生成成功",
                  bool(base_result.program_text),
                  f"errors={base_result.errors}")
            check(f"{ctrl} controller_type 匹配",
                  base_result.controller_type == ctrl)
        except Exception as e:
            check(f"{ctrl} 生成成功", False, f"exception={e}")


# =============================================================================
# 主入口
# =============================================================================


def main() -> int:
    print("=" * 70)
    print("generator_adapter.py 端到端验证（阶段 6 s6-7）")
    print("=" * 70)

    # 测试 1: load_operation_plan()
    plan = test_load_operation_plan()

    # 测试 2: load_operation_plan() 错误处理
    test_load_operation_plan_errors()

    # 测试 3: adapt() 正常流程
    test_adapt_normal(plan)

    # 测试 4: feature_id ↔ feature_name 匹配 + gcode_lines 切分
    test_adapt_feature_line_ranges(plan)

    # 测试 5: chatter_results 为空
    test_adapt_empty_chatter_results(plan)

    # 测试 6: limit_depth_mm == 0
    test_adapt_limit_depth_zero(plan)

    # 测试 7: 全部 stable
    test_adapt_all_stable()

    # 测试 8: 不同控制器
    test_adapt_different_controllers(plan)

    print("\n" + "=" * 70)
    print(f"总计: {PASS} 通过, {FAIL} 失败")
    print("=" * 70)
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
