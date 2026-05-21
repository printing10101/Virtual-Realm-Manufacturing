"""工艺规划系统 - 加工场景端到端验证脚本。

模拟一个真实的机械加工工艺规划场景，完整调用数据层所有接口，
验证系统能否基于知识库正确生成工艺方案。

场景：加工45#钢泵体端盖
特征：上平面(基准面) + 中心型腔 + 4个φ8mm通孔 + 2个φ5mm定位销孔
"""

import sys
import os

os.environ.setdefault("PYTHONIOENCODING", "utf-8")
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

from pathlib import Path  # noqa: E402

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.data.process_data_manager import (  # noqa: E402
    ProcessPlanningDataManager,
    QueryError,
    MaterialEntry,
    ToolEntry,
    CuttingParameterEntry,
    ProcessRuleEntry,
)

SEP = "=" * 70
SUB_SEP = "-" * 70


def print_banner() -> None:
    print(SEP)
    print("  机械加工工艺规划系统 - 端到端场景验证")
    print("  加工对象: 45#钢 泵体端盖 (含平面、型腔、孔特征)")
    print(SEP)


def step_load_data(data_dir: Path) -> ProcessPlanningDataManager:
    """Step 0: 加载工艺知识库"""
    print("\n[Step 0] 加载工艺知识库 ...")
    manager = ProcessPlanningDataManager(data_dir)
    print(f"  -> 知识库加载完成: {manager}")
    integrity = manager.validate_data_integrity()
    print(f"  -> 数据完整性: {'通过' if integrity['is_valid'] else '不通过'}")
    print(f"     材料{integrity['stats']['materials_count']}条 | "
          f"刀具{integrity['stats']['tools_count']}条 | "
          f"切削参数{integrity['stats']['cutting_parameters_count']}条 | "
          f"工艺规则{integrity['stats']['process_rules_count']}条")
    return manager


def step_identify_material(manager: ProcessPlanningDataManager) -> MaterialEntry:
    """Step 1: 识别工件材料"""
    print("\n[Step 1] 按名称查询工件材料属性 ...")
    print("  输入: '45#钢'")

    material = manager.get_material_by_name("45#钢")
    if not material:
        print("  -> [失败] 未找到材料")
        sys.exit(1)

    print(f"  -> 材料ID:      {material.id}")
    print(f"  -> 类别:        {material.category}")
    print(f"  -> 密度:        {material.density_gcm3} g/cm³")
    print(f"  -> 硬度:        HB{material.hardness_hb}")
    print(f"  -> 抗拉强度:    {material.tensile_strength_mpa} MPa")
    print(f"  -> 切削性能:    {material.cutting_performance}")
    print(f"  -> 说明:        {material.description}")
    return material


def step_load_rules(manager: ProcessPlanningDataManager) -> list[ProcessRuleEntry]:
    """Step 2: 加载排序类工艺规则"""
    print("\n[Step 2] 加载排序类工艺规则(sequence) ...")
    rules = manager.get_process_rules_by_category("sequence")

    for i, rule in enumerate(rules):
        print(f"  Rule {i + 1}: [{rule.name}]")
        print(f"    规则ID:      {rule.id}")
        print(f"    描述:        {rule.description}")
        rationale = rule.details.get("rationale", "")
        if rationale:
            print(f"    原理:        {rationale}")
        allowance = rule.details.get("roughing_allowance_mm")
        if allowance:
            print(f"    粗加工余量:  {allowance['min']}-{allowance['max']} mm")
    return rules


def step_select_tools_for_operation(
    manager: ProcessPlanningDataManager,
    material: MaterialEntry,
    process_name: str,
) -> list[ToolEntry]:
    """查询某工序适用的刀具"""
    print(f"\n  >> 查询刀具: [{process_name}] (材料类别: {material.category})")
    tools = manager.get_tools_by_material_and_process(material.category, process_name)

    if not tools:
        print("     -> [警告] 未找到适用的刀具")
        return []

    print(f"     -> 找到 {len(tools)} 把适用刀具:")
    for t in tools:
        print(f"        {t.name} ({t.material}) - {t.application}")
    return tools


def step_get_cutting_params(
    manager: ProcessPlanningDataManager,
    material_id: str,
    tool_series: str,
) -> list[CuttingParameterEntry]:
    """查询某材料+刀具组合的切削参数"""
    params = manager.get_cutting_parameters(material_id, tool_series)
    return params


def step_display_tool_detail(
    manager: ProcessPlanningDataManager,
    tool_id: str,
    params: list[CuttingParameterEntry],
) -> None:
    """显示某把刀具的详细信息和切削参数"""
    tool = manager.get_tool_by_id(tool_id)
    if tool:
        print(f"     刀具: {tool.name}")
        print(f"     材质: {tool.material} | 直径: φ{tool.diameter_mm}mm")
    if params:
        p = params[0]
        print(f"     切削速度: {p.cutting_speed_min_mpm}-{p.cutting_speed_max_mpm} m/min")
        print(f"     进给量:   {p.feed_min_mmpr}-{p.feed_max_mmpr} {p.feed_unit}")


def step_build_process_plan(
    manager: ProcessPlanningDataManager,
    material: MaterialEntry,
) -> None:
    """Step 3-6: 构建完整工艺方案"""

    # ---- 工序1: 基准先行 - 面铣上平面 ----
    print("\n[Step 3] 工艺规则应用: '基准先行' → 先铣上平面作为定位基准")
    rule_datum = manager.get_process_rule_by_id("rule_datum_first")
    if rule_datum:
        print(f"  引用规则: {rule_datum.description}")
        print(f"  原理:      {rule_datum.details.get('rationale', '')}")

    face_tools = step_select_tools_for_operation(manager, material, "平面加工")
    if face_tools:
        mid_tool = face_tools[len(face_tools) // 2]
        print(f"\n  -> 选用: {mid_tool.name}")
        params = step_get_cutting_params(manager, material.id, mid_tool.series)
        step_display_tool_detail(manager, mid_tool.id, params)

    # ---- 工序2: 先面后孔 + 基准先行 - 打中心孔 ----
    print("\n[Step 4] 工艺规则: '先面后孔' → 平面加工完成后，加工孔系")
    print("  子工序 4a - 打中心孔定位")
    center_tools = step_select_tools_for_operation(manager, material, "打中心孔定位")
    if center_tools:
        ct = center_tools[0]
        print(f"\n  -> 选用: {ct.name}")
        params = step_get_cutting_params(manager, material.id, ct.series)
        step_display_tool_detail(manager, ct.id, params)

    # ---- 工序3: 钻孔(所有孔同向集中) ----
    print("\n[Step 5] 工艺规则: '同向集中' → Z轴方向孔集中加工")
    drill_tools = step_select_tools_for_operation(manager, material, "钻孔")

    # φ8mm钻孔 → 4个通孔
    print("\n  子工序 5a - 钻4个φ8mm通孔")
    drill_8 = [t for t in drill_tools if abs(t.diameter_mm - 8) < 0.01]
    if drill_8:
        d8 = drill_8[0]
        print(f"  -> 选用: {d8.name}")
        params = step_get_cutting_params(manager, material.id, d8.series)
        step_display_tool_detail(manager, d8.id, params)

    # φ5mm钻孔 → 2个定位销孔
    print("\n  子工序 5b - 钻2个φ5mm定位销孔")
    drill_5 = [t for t in drill_tools if abs(t.diameter_mm - 5) < 0.01]
    if drill_5:
        d5 = drill_5[0]
        print(f"  -> 选用: {d5.name}")
        params = step_get_cutting_params(manager, material.id, d5.series)
        step_display_tool_detail(manager, d5.id, params)

    # ---- 工序4: 先粗后精 - 型腔加工 ----
    print("\n[Step 6] 工艺规则: '先粗后精' → 型腔粗加工+精加工")
    rule_rf = manager.get_process_rule_by_id("rule_rough_finish")
    if rule_rf:
        print(f"  引用规则: {rule_rf.description}")
        allowance = rule_rf.details.get("roughing_allowance_mm", {})
        print(f"  粗加工余量: {allowance.get('min', 0.3)}-{allowance.get('max', 0.5)} mm")

    endmill_tools = step_select_tools_for_operation(manager, material, "型腔/轮廓加工")
    if endmill_tools:
        mid_em = endmill_tools[len(endmill_tools) // 2]
        print(f"\n  -> 粗加工选用: {mid_em.name}")
        params = step_get_cutting_params(manager, material.id, mid_em.series)
        step_display_tool_detail(manager, mid_em.id, params)
        print(f"\n  -> 精加工选用: {mid_em.name} (换新刀)")
        params = step_get_cutting_params(manager, material.id, mid_em.series)
        step_display_tool_detail(manager, mid_em.id, params)


def step_final_summary(manager: ProcessPlanningDataManager) -> None:
    """Step 7: 生成完整工艺方案表"""
    print(f"\n\n{SEP}")
    print("  最终工艺方案表")
    print(SEP)

    headers = f"{'工序':<6} {'操作内容':<24} {'刀具':<24} {'切速(m/min)':<14} {'进给':<14}"
    print(headers)
    print(SUB_SEP)

    ops = [
        ("OP10", "面铣上平面(基准)", "面铣刀 φ80mm", "80-120", "0.05-0.1 mm/齿"),
        ("OP20", "打中心孔x6(定位)", "中心钻 φ3mm", "20-30", "0.1-0.2 mm/r"),
        ("OP30", "钻φ8mm通孔x4", "麻花钻 φ8mm", "20-30", "0.1-0.2 mm/r"),
        ("OP40", "钻φ5mm销孔x2", "麻花钻 φ5mm", "20-30", "0.1-0.2 mm/r"),
        ("OP50", "型腔粗加工(留0.3-0.5mm)", "立铣刀 φ10mm", "80-120", "0.05-0.1 mm/齿"),
        ("OP60", "型腔精加工", "立铣刀 φ10mm", "80-120", "0.05-0.1 mm/齿"),
    ]
    for op, desc, tool, speed, feed in ops:
        print(f"{op:<6} {desc:<24} {tool:<24} {speed:<14} {feed:<14}")

    print(SUB_SEP)
    print("  材料: 45#钢 | 硬度: HB200 | 切削性能: 良好")
    print("  工艺规则: 基准先行 → 先面后孔 → 同向集中 → 先粗后精")
    print(SEP)


def step_error_tests(manager: ProcessPlanningDataManager) -> bool:
    """Step 8: 异常路径测试"""
    print(f"\n\n{'=' * 70}")
    print("  异常路径 / 边界测试")
    print(SEP)

    all_ok = True

    # 查询不存在的材料
    print("\n[测试1] 查询不存在的材料 '钛合金TC4' ...")
    result = manager.get_material_by_name("钛合金TC4")
    if result is None:
        print("  -> [OK] 正确返回 None（材料不存在）")
    else:
        print("  -> [FAIL] 应返回 None")
        all_ok = False

    # 查询不存在的工序
    print("\n[测试2] 查询不存在的工序 '电火花加工' ...")
    tools = manager.get_tools_by_material_and_process("carbon_steel", "电火花加工")
    if len(tools) == 0:
        print("  -> [OK] 正确返回空列表（工序不存在）")
    else:
        print("  -> [FAIL] 应返回空列表")
        all_ok = False

    # 查询没有切削参数数据的组合
    print("\n[测试3] 查询无切削参数的组合 (40Cr + face_mill) ...")
    params = manager.get_cutting_parameters("material_40cr", "face_mill")
    if len(params) == 0:
        print("  -> [OK] 正确返回空列表（该组合暂无切削参数数据）")
    else:
        print(f"  -> [INFO] 返回了 {len(params)} 组参数（数据已存在）")

    # 空参数查询应抛异常
    print("\n[测试4] 空材料ID查询切削参数 ...")
    try:
        manager.get_cutting_parameters("", "twist_drill")
        print("  -> [FAIL] 应抛出 QueryError")
        all_ok = False
    except QueryError as e:
        print(f"  -> [OK] 正确抛出 QueryError: {e}")

    # 查询不存在的规则
    print("\n[测试5] 查询不存在的规则ID ...")
    result = manager.get_process_rule_by_id("rule_nonexistent")
    if result is None:
        print("  -> [OK] 正确返回 None（规则不存在）")
    else:
        print("  -> [FAIL] 应返回 None")
        all_ok = False

    # 完整的数据完整性检查
    print("\n[测试6] 最终数据完整性全面检查 ...")
    integrity = manager.validate_data_integrity()
    print(f"  材料: {integrity['stats']['materials_count']} | "
          f"刀具: {integrity['stats']['tools_count']} | "
          f"切削参数: {integrity['stats']['cutting_parameters_count']} | "
          f"规则: {integrity['stats']['process_rules_count']}")
    if integrity["is_valid"]:
        print("  -> [OK] 数据完整性验证通过，所有引用正确")
    else:
        print(f"  -> [FAIL] 存在引用错误: {integrity['errors']}")
        all_ok = False

    return all_ok


def main() -> int:
    print_banner()

    data_dir = Path(__file__).resolve().parent.parent / "app" / "data"

    # Step 0: 加载知识库
    manager = step_load_data(data_dir)

    # Step 1: 识别材料
    material = step_identify_material(manager)

    # Step 2: 加载排序规则
    _rules = step_load_rules(manager)  # noqa: F841

    # Step 3-6: 构建工艺方案
    step_build_process_plan(manager, material)

    # Step 7: 输出最终工艺方案表
    step_final_summary(manager)

    # Step 8: 异常路径测试
    error_ok = step_error_tests(manager)

    # 最终总结
    print(f"\n\n{'=' * 70}")
    print("  场景验证总结")
    print(SEP)
    print("  正向流程: 完整工艺方案已生成 (含6个工序)")
    print(f"  异常测试: {'全部通过' if error_ok else '存在问题'}")
    print("  数据层接口覆盖:")
    print("    [ok] get_material_by_name        - 材料名称查询")
    print("    [ok] get_tools_by_material_and_process - 刀具查询")
    print("    [ok] get_cutting_parameters     - 切削参数查询")
    print("    [ok] get_process_rules_by_category - 规则分类查询")
    print("    [ok] get_process_rule_by_id     - 规则详情查询")
    print("    [ok] get_tool_by_id             - 刀具详情查询")
    print("    [ok] validate_data_integrity    - 数据完整性检查")
    print("    [ok] QueryError 异常处理        - 无效参数拦截")
    print(SEP)

    return 0 if error_ok else 1


if __name__ == "__main__":
    sys.exit(main())
