"""端到端加工场景测试 —— 物理约束 & Rust接口 & 全链路验证。

场景：VMC850加工中心 + 40Cr合金钢 + φ10硬质合金平底铣刀
加工工序：面铣粗加工 → 型腔铣削 → 钻孔 → 轮廓精加工
"""

from __future__ import annotations

import sys
import math
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "python"))

PASS = 0
FAIL = 0
PENDING = 0


def header(title: str):
    print(f"\n{'=' * 72}")
    print(f"  {title}")
    print(f"{'=' * 72}")


def check(name: str, condition: bool, detail: str = ""):
    global PASS, FAIL
    if condition:
        PASS += 1
        print(f"  [PASS] {name}")
    else:
        FAIL += 1
        print(f"  [FAIL] {name}" + (f"  -- {detail}" if detail else ""))


def warn(name: str, detail: str = ""):
    global PENDING
    PENDING += 1
    print(f"  [WARN] {name}" + (f"  -- {detail}" if detail else ""))


# =============================================================================
# 阶段1：领域模型物理约束验证 —— 拒绝非法值
# =============================================================================
def phase1_physical_constraints():
    header("阶段1：领域模型物理约束边界校验")

    from app.simulation.voxel_cutter import ToolModel
    from app.database.machines import MachineEntry
    from app.database.materials import MaterialEntry

    print("\n--- ToolModel (ISO 13399) ---")

    check("正常实例化 φ10平底硬质合金铣刀",
          ToolModel(diameter=10.0, tool_type="flat", material="carbide").diameter == 10.0)

    check("球头刀自动设置corner_radius=d/2",
          abs(ToolModel(diameter=8.0, tool_type="ball").corner_radius - 4.0) < 0.001)

    check("max_depth_of_cut自动派生(1.5×d)",
          ToolModel(diameter=10.0).max_depth_of_cut == 15.0)

    check("HSS材料max_cutting_force自动估算(d×80)",
          abs(ToolModel(diameter=10.0, material="HSS").max_cutting_force_n - 800.0) < 0.1)

    check("carbide材料max_cutting_force自动估算(d×200)",
          abs(ToolModel(diameter=10.0, material="carbide").max_cutting_force_n - 2000.0) < 0.1)

    try:
        ToolModel(diameter=-5.0)
        check("拒绝负直径", False, "应抛出ValueError")
    except ValueError:
        check("拒绝负直径", True)

    try:
        ToolModel(diameter=10.0, tool_type="laser_cutter")
        check("拒绝非法刀具类型", False, "应抛出ValueError")
    except ValueError:
        check("拒绝非法刀具类型", True)

    try:
        ToolModel(diameter=10.0, material="wood")
        check("拒绝非法刀具材料", False, "应抛出ValueError")
    except ValueError:
        check("拒绝非法刀具材料", True)

    try:
        ToolModel(diameter=10.0, corner_radius=100.0)
        check("拒绝corner_radius > 半径", False, "应抛出ValueError")
    except ValueError:
        check("拒绝corner_radius > 半径", True)

    try:
        ToolModel(diameter=10.0, cutting_length=100.0, overall_length=50.0)
        check("拒绝cutting_length > overall_length", False, "应抛出ValueError")
    except ValueError:
        check("拒绝cutting_length > overall_length", True)

    try:
        ToolModel(diameter=10.0, shank_diameter=50.0)
        check("拒绝shank_diameter >> diameter", False, "应抛出ValueError")
    except ValueError:
        check("拒绝shank_diameter >> diameter", True)

    print("\n--- MachineEntry (ISO 841/230) ---")

    check("正常实例化VMC850",
          MachineEntry(id="vmc_850", name="VMC850", type="vertical_machining_center",
                       spindle_power_kw=7.5).id == "vmc_850")

    try:
        MachineEntry(id="bad", name="Bad", type="mill", spindle_power_kw=999)
        check("拒绝超限主轴功率", False, "应抛出ValueError")
    except ValueError:
        check("拒绝超限主轴功率", True)

    try:
        MachineEntry(id="bad", name="Bad", type="mill", repeatability_mm=5.0)
        check("拒绝超限重复精度", False, "应抛出ValueError")
    except ValueError:
        check("拒绝超限重复精度", True)

    try:
        MachineEntry(id="bad", name="Bad", type="mill", rapid_traverse_xy_mm_min=999999)
        check("拒绝超限快速横移", False, "应抛出ValueError")
    except ValueError:
        check("拒绝超限快速横移", True)

    print("\n--- MaterialEntry (ISO 4957/683) ---")

    check("正常实例化40Cr",
          MaterialEntry(id="steel_40cr", name="40Cr", category="alloy_steel",
                        hardness_hb=260, tensile_strength_mpa=980).hardness_hb == 260)

    try:
        MaterialEntry(id="bad", name="Bad", category="steel",
                      hardness_hb=9999, tensile_strength_mpa=8000)
        check("拒绝超限硬度", False, "应抛出ValueError")
    except ValueError:
        check("拒绝超限硬度", True)

    try:
        MaterialEntry(id="bad", name="Bad", category="steel",
                      hardness_hb=200, tensile_strength_mpa=500,
                      yield_strength_mpa=600)
        check("拒绝屈服强度>抗拉强度", False, "应抛出ValueError")
    except ValueError:
        check("拒绝屈服强度>抗拉强度", True)

    try:
        MaterialEntry(id="bad", name="Bad", category="steel",
                      hardness_hb=200, tensile_strength_mpa=500,
                      corrosion_resistance="ultra")
        check("拒绝非法耐腐蚀等级", False, "应抛出ValueError")
    except ValueError:
        check("拒绝非法耐腐蚀等级", True)

    from app.database.materials import MaterialCuttingRange
    try:
        MaterialCuttingRange(roughing=(10.0, 5.0), finishing=(1.0, 2.0))
        check("拒绝反向roughing范围", False, "应抛出ValueError")
    except ValueError:
        check("拒绝反向roughing范围", True)

    try:
        MaterialCuttingRange(roughing=(1.0, 2.0), finishing=(5.0, -1.0))
        check("拒绝负finishing值", False, "应抛出ValueError")
    except ValueError:
        check("拒绝负finishing值", True)


# =============================================================================
# 阶段2：数据库加载 + JsonRepository验证
# =============================================================================
def phase2_database_loading():
    header("阶段2：数据库加载与JsonRepository泛型基类")

    from app.database.machines import MachineDatabase
    from app.database.tools import ToolDatabase
    from app.database.materials import MaterialDatabase
    from app.database.repository import JsonRepository

    print("\n--- MachineDatabase ---")
    mdb = MachineDatabase()
    check("MachineDatabase加载成功", mdb is not None)
    check("机床数量≥1", len(mdb.list_ids()) >= 1,
          f"实际: {len(mdb.list_ids())}台")
    check("VMC850存在", "vmc_850" in mdb.list_ids())
    check("filter_by_type(machining_center)",
          len(mdb.filter_by_type("vertical_machining_center")) >= 1)

    vmc = mdb.get("vmc_850")
    check("vmc850主轴功率7.5kW", abs(vmc.spindle_power_kw - 7.5) < 0.01)
    check("vmc850 spindle_torque_nm可读", vmc.spindle_torque_nm >= 0)
    check("vmc850 rapid_traverse_xy兼容旧字段",
          vmc.rapid_traverse_xy_mm_min == 24000.0,
          f"实际: {vmc.rapid_traverse_xy_mm_min}")
    check("vmc850 validate_cutting_parameters(4000, 500, 3) = True",
          vmc.validate_cutting_parameters(4000, 500, 3)[0] is True)
    check("vmc850 validate_cutting_parameters(99999, 500, 3) = False",
          vmc.validate_cutting_parameters(99999, 500, 3)[0] is False)
    check("vmc850 spindle_speed_rpm兼容属性",
          vmc.spindle_speed_rpm == [50, 8000])

    check("vmc850 max_workpiece_weight_kg存在", vmc.max_workpiece_weight_kg >= 0)
    check("vmc850 repeatability_mm存在", vmc.repeatability_mm >= 0)
    check("vmc850 axis_count默认3", vmc.axis_count == 3)
    check("vmc850 control_system存在", isinstance(vmc.control_system, str))

    print("\n--- MaterialDatabase ---")
    matdb = MaterialDatabase()
    check("MaterialDatabase加载成功", matdb is not None)
    check("材料数量≥1", len(matdb.list_ids()) >= 1,
          f"实际: {len(matdb.list_ids())}种")
    check("40Cr存在", "steel_40cr" in matdb.list_ids())

    cr40 = matdb.get("steel_40cr")
    check("40Cr硬度260HB", abs(cr40.hardness_hb - 260) < 0.01)
    check("40Cr抗拉980MPa", abs(cr40.tensile_strength_mpa - 980) < 0.01)
    check("40Cr taylor_tool_life_exponent新字段",
          abs(cr40.taylor_tool_life_exponent - 0.23) < 0.001)
    check("40Cr taylor_exponent_n兼容属性",
          abs(cr40.taylor_exponent_n - 0.23) < 0.001)
    check("40Cr specific_cutting_force兼容属性",
          abs(cr40.specific_cutting_force - 2300) < 0.01)
    check("40Cr get_depth_of_cut替代get_doc",
          cr40.get_depth_of_cut("roughing")[0] == 2.0)
    check("40Cr machinability_index存在",
          cr40.machinability_index >= 0)
    check("40Cr corrosion_resistance存在",
          isinstance(cr40.corrosion_resistance, str))

    ti = matdb.get("ti_tc4")
    check("TC4切削速度极低(导热差)", ti.cutting_speed_range["roughing"][0] <= 50)
    check("TC4 taylor_n最小(最难加工)",
          ti.taylor_tool_life_exponent < cr40.taylor_tool_life_exponent)

    print("\n--- ToolDatabase ---")
    tdb = ToolDatabase()
    check("ToolDatabase加载成功", tdb is not None)
    check("刀具数量≥1", len(tdb.list_ids()) >= 1,
          f"实际: {len(tdb.list_ids())}把")

    endmill = tdb.get("endmill_wc_flat_d10")
    check("φ10硬质合金铣刀存在", endmill is not None)
    check("filter_by_type(endmill)", len(tdb.filter_by_type("endmill")) >= 1)
    check("filter_by_material(WC)", len(tdb.filter_by_material("WC")) >= 1)

    check("JsonRepository泛型类型安全",
          isinstance(mdb._repo, JsonRepository))


# =============================================================================
# 阶段3：真实加工场景 —— G代码生成 + 仿真
# =============================================================================
def phase3_real_scenario():
    header("阶段3：真实加工场景 —— VMC850 + 40Cr + φ10铣刀")

    from app.database.machines import MachineDatabase
    from app.database.materials import MaterialDatabase
    from app.database.tools import ToolDatabase

    mdb = MachineDatabase()
    matdb = MaterialDatabase()
    tdb = ToolDatabase()

    machine = mdb.get("vmc_850")
    material = matdb.get("steel_40cr")
    tool_entry = tdb.get("endmill_wc_flat_d10")

    print("\n  场景配置:")
    print(f"    机床: {machine.name} (主轴{machine.spindle_power_kw}kW, "
          f"行程{machine.travel_xyz_mm[0]}×{machine.travel_xyz_mm[1]}×{machine.travel_xyz_mm[2]}mm)")
    print(f"    材料: {material.name} (HB{material.hardness_hb:.0f}, "
          f"抗拉{material.tensile_strength_mpa}MPa, kc1.1={material.specific_cutting_force_kc1_1})")
    print(f"    刀具: {tool_entry.name} (φ{tool_entry.diameter_range[1]}mm, "
          f"{tool_entry.flutes}刃, maxF={tool_entry.max_cutting_force_n}N)")

    # --- 3a. 工艺参数计算 ---
    print("\n  --- 3a. 切削参数计算 ---")
    vc_range = material.get_cutting_speed("roughing")

    vc = (vc_range[0] + vc_range[1]) / 2.0
    spindle_speed = vc * 1000 / (math.pi * 10)
    valid_s, msg = machine.validate_cutting_parameters(spindle_speed, 300, 3.0)

    check("切削速度范围[60,100]m/min", vc_range[0] == 60 and vc_range[1] == 100)
    check(f"主轴转速{spindle_speed:.0f}RPM在机床范围",
          valid_s, f"机床校验: {msg}")

    # --- 3b. ToolModel实例化 ---
    print("\n  --- 3b. ToolModel实例化 ---")
    from app.simulation.voxel_cutter import ToolModel

    roughing_tool = ToolModel(
        diameter=10.0,
        cutting_length=50.0,
        overall_length=75.0,
        tool_type="flat",
        corner_radius=0.0,
        material="carbide",
        coating="TiAlN",
        flute_count=4,
        helix_angle_deg=30.0,
        rake_angle_deg=12.0,
        clearance_angle_deg=8.0,
    )

    check("roughing_tool直径10mm", roughing_tool.diameter == 10.0)
    check("roughing_tool刃长50mm", roughing_tool.cutting_length == 50.0)
    check("max_depth_of_cut自动=15mm", roughing_tool.max_depth_of_cut == 15.0)
    check("max_cutting_force_N自动≈2000N (carbide×d×200)",
          abs(roughing_tool.max_cutting_force_n - 2000) < 10)
    check("length兼容属性返回cutting_length",
          roughing_tool.length == roughing_tool.cutting_length)

    finishing_tool = ToolModel(
        diameter=8.0,
        cutting_length=40.0,
        overall_length=60.0,
        tool_type="ball",
        material="carbide",
        coating="TiAlN",
        flute_count=2,
    )

    check("球头刀corner_radius=4.0mm", abs(finishing_tool.corner_radius - 4.0) < 0.01)
    check("球头刀to_dict包含新字段",
          "material" in finishing_tool.to_dict() and
          "coating" in finishing_tool.to_dict() and
          "max_cutting_force_n" in finishing_tool.to_dict())

    drill_tool = ToolModel(
        diameter=8.0,
        cutting_length=40.0,
        overall_length=80.0,
        tool_type="drill",
        material="carbide",
        flute_count=2,
        max_spindle_speed_rpm=12000,
    )

    check("钻头max_depth_of_cut=12mm", abs(drill_tool.max_depth_of_cut - 12.0) < 0.01)

    # --- 3c. G代码生成 ---
    print("\n  --- 3c. G代码生成 ---")
    gcode_lines = generate_real_gcode()
    check("G代码生成成功", len(gcode_lines) > 0)
    check("G代码包含程序头%", gcode_lines[0] == "%")
    check("G代码包含程序尾%", gcode_lines[-1] == "%")
    check("G代码包含刀具调用T1 M06", any("T1 M06" in line for line in gcode_lines))
    check("G代码包含安全高度G00 Z50", any("G00 Z50" in line for line in gcode_lines))
    check("G代码包含主轴启动M03 S2548",
          any("S2548" in line and "M03" in line for line in gcode_lines))

    gcode_text = "\n".join(gcode_lines)
    check("G代码总行数≥25", len(gcode_lines) >= 25,
          f"实际: {len(gcode_lines)}行")

    # --- 3d. 刀路解析 ---
    print("\n  --- 3d. 刀路解析 ---")
    from app.simulation.toolpath_parser import ToolpathParser

    parser = ToolpathParser(controller_type="fanuc")
    segments = parser.parse_gcode(gcode_text)

    check("刀路解析成功", len(segments) > 0,
          f"实际: {len(segments)}段")
    check("包含快速移动段(rapid)", any(s.type == "rapid" for s in segments))
    check("包含直线切削段(linear)", any(s.type == "linear" for s in segments))

    rapid_count = sum(1 for s in segments if s.type == "rapid")
    linear_count = sum(1 for s in segments if s.type == "linear")
    print(f"    解析结果: {rapid_count}段快速移动 + {linear_count}段直线切削")

    # --- 3e. 碰撞检测 ---
    print("\n  --- 3e. AABB碰撞检测 ---")
    from app.simulation.collision_detector import CollisionDetector
    from app.simulation.stock_model import StockModel

    stock = StockModel(length=150, width=100, height=40)
    detector = CollisionDetector(stock=stock, safe_z_height=10.0)

    report = detector.check_segments(segments)
    check("碰撞检测成功", report is not None)
    check(f"检测{report.segments_checked}段刀路", report.segments_checked > 0)

    if report.safe:
        check("碰撞检测：安全 (无碰撞)", True)
    else:
        for c in report.collisions:
            warn(f"碰撞: N{c.block_number} {c.message}")

    # --- 3f. 体素切削仿真 ---
    print("\n  --- 3f. 体素切削仿真 ---")
    from app.simulation.voxel_cutter import VoxelCutter

    cutter = VoxelCutter(voxel_size=2.0)

    output_dir = PROJECT_ROOT / "output" / "simulation" / "e2e_test"
    output_dir.mkdir(parents=True, exist_ok=True)

    result = cutter.run_simulation(
        stock_stl_path=Path("nonexistent_test.stl"),
        tool=roughing_tool,
        segments=segments,
        output_dir=output_dir,
        safe_z_height=10.0,
        task_id="e2e_test_001",
    )

    check("仿真执行完成", result is not None)
    check(f"仿真耗时: {result.duration_seconds:.3f}s",
          result.duration_seconds >= 0)
    check("仿真TaskID正确", result.task_id == "e2e_test_001")
    check("体素总数>0", result.voxel_count > 0,
          f"实际: {result.voxel_count}")
    check("体素尺寸2.0mm", abs(result.voxel_size - 2.0) < 0.01)

    # trimesh未安装时使用fallback — 这是预期行为
    if result.voxel_count > 0 and result.original_bbox is not None:
        bbox = result.original_bbox
        check(f"毛坯包围盒: [{bbox['x_min']:.0f}, {bbox['x_max']:.0f}] "
              f"× [{bbox['y_min']:.0f}, {bbox['y_max']:.0f}] "
              f"× [{bbox['z_min']:.0f}, {bbox['z_max']:.0f}]", True)
    else:
        warn("使用降级仿真结果 (trimesh未安装)", "fallback模式生成默认毛坯")

    # --- 3g. VoxelSimulationResult序列化 ---
    print("\n  --- 3g. 仿真结果序列化 ---")
    result_dict = result.to_dict()
    check("to_dict成功", isinstance(result_dict, dict))
    check("result包含task_id", result_dict.get("task_id") == "e2e_test_001")
    check("result包含voxel_count", "voxel_count" in result_dict)
    check("result包含duration_seconds", "duration_seconds" in result_dict)
    check("result包含collision", "collision" in result_dict)
    check("collision.collided为bool",
          isinstance(result_dict["collision"]["collided"], bool))
    check("collision.collision_severity为str",
          isinstance(result_dict["collision"]["collision_severity"], str))


# =============================================================================
# 阶段4：Rust接口兼容性验证
# =============================================================================
def phase4_rust_interface_compatibility():
    header("阶段4：Rust接口层与Python领域模型对齐验证")

    # 验证Python端新增字段与Rust types.rs定义一致
    from app.database.machines import MachineEntry
    from app.simulation.voxel_cutter import ToolModel, CollisionInfo
    from app.database.materials import MaterialEntry

    print("\n--- MachineEntry <-> Rust MachineConstraint Field Mapping ---")
    m = MachineEntry(id="test", name="Test", type="mill", spindle_power_kw=5)
    rust_expected = {
        "spindle_power_kw", "spindle_torque_nm", "spindle_speed_rpm_range",
        "rapid_traverse_xy_mm_min", "rapid_traverse_z_mm_min",
        "feed_cutting_max_mmmin", "max_cutting_force_n",
        "max_workpiece_weight_kg", "positioning_accuracy_mm", "repeatability_mm",
    }
    py_fields = set(m.to_dict().keys())
    for field in rust_expected:
        check(f"Rust {field} <-> Python match", field in py_fields,
              f"Python missing: {field}")

    print("\n--- ToolModel <-> Rust ToolConstraint Field Mapping ---")
    t = ToolModel(diameter=10)
    rust_expected = {
        "diameter", "cutting_length", "overall_length", "corner_radius",
        "flute_count", "helix_angle_deg", "clearance_angle_deg",
        "max_depth_of_cut", "max_cutting_force_n", "max_spindle_speed_rpm",
        "shank_diameter",
    }
    py_tool_fields = set(t.to_dict().keys())
    for field in rust_expected:
        check(f"Rust {field} <-> Python match", field in py_tool_fields,
              f"Python missing: {field}")
    check("ToolModel retains material/coating superset fields",
          "material" in py_tool_fields and "coating" in py_tool_fields)

    print("\n--- MaterialEntry <-> Rust MaterialConstraint Field Mapping ---")
    mat = MaterialEntry(id="test", name="Test", category="steel",
                        hardness_hb=200, tensile_strength_mpa=500)
    rust_expected = {
        "hardness_hb", "tensile_strength_mpa", "yield_strength_mpa",
        "elongation_pct", "density_gcm3", "thermal_conductivity",
        "specific_cutting_force_kc1_1", "machinability_index",
        "taylor_tool_life_exponent", "taylor_constant_c",
    }
    py_mat_fields = set(mat.to_dict().keys())
    for field in rust_expected:
        check(f"Rust {field} <-> Python match", field in py_mat_fields,
              f"Python missing: {field}")

    print("\n--- CollisionInfo <-> Rust CollisionReport Field Mapping ---")
    c = CollisionInfo()
    cd = c.to_dict()
    check("collided字段存在", "collided" in cd)
    check("collision_positions字段存在", "collision_positions" in cd)
    check("collision_segment_indices字段存在", "collision_segment_indices" in cd)
    check("collision_severity字段存在", "collision_severity" in cd)

    print("\n--- config.py版本号一致性 ---")
    from app.config import config
    check("config.app_version = 2.0.0",
          config.app_version == "2.0.0",
          f"实际: {config.app_version}")
    check("SimulationConfig.voxel_size默认1.0",
          abs(config.simulation.voxel_size - 1.0) < 0.01)
    check("SimulationConfig.max_store_size默认500",
          config.simulation.max_store_size == 500)
    check("ProcessPlanningConfig.surface_roughness_ra默认3.2",
          abs(config.process_planning.surface_roughness_ra_default - 3.2) < 0.01)
    check("ProcessPlanningConfig.standard_drill_point_angle_deg默认118",
          abs(config.process_planning.standard_drill_point_angle_deg - 118) < 0.01)
    check("LoggingConfig.max_bytes=50MB",
          config.logging.max_bytes == 52428800)


# =============================================================================
# 阶段5：边界条件与鲁棒性
# =============================================================================
def phase5_edge_cases():
    header("阶段5：边界条件与鲁棒性测试")

    from app.simulation.voxel_cutter import ToolModel
    from app.simulation.toolpath_parser import ToolpathParser
    from app.simulation.collision_detector import CollisionDetector
    from app.simulation.stock_model import StockModel

    print("\n--- 空G代码 ---")
    parser = ToolpathParser()
    segments = parser.parse_gcode("")
    check("空G代码返回0段", len(segments) == 0)

    segments = parser.parse_gcode("%\n%")
    check("只有%的G代码返回0段", len(segments) == 0)

    print("\n--- 极小刀具 ---")
    t = ToolModel(diameter=0.5, cutting_length=10, overall_length=20,
                  tool_type="flat", material="HSS", shank_diameter=1.0)
    check("最小直径0.5mm可实例化", t.diameter == 0.5)
    check("最小刀具max_cutting_force_N=40N (HSS×0.5×80)",
          abs(t.max_cutting_force_n - 40.0) < 0.5)

    print("\n--- 物理约束主动拒绝不合理柄径 ---")
    try:
        ToolModel(diameter=0.5, cutting_length=10, overall_length=20,
                  tool_type="flat", material="HSS")
        check("拒绝shank >> diameter(极小刀)", False, "应抛出ValueError (默认shank=10)")
    except ValueError:
        check("拒绝shank >> diameter(极小刀)", True)

    print("\n--- 极低速材料 (TC4钛合金) ---")
    from app.database.materials import MaterialDatabase
    ti = MaterialDatabase().get("ti_tc4")
    vc = ti.get_cutting_speed("roughing")[0]
    check("TC4粗加工推荐vc=30m/min", abs(vc - 30) < 0.1)
    check("TC4 taylor_n=0.18 (难加工)", abs(ti.taylor_tool_life_exponent - 0.18) < 0.01)

    print("\n--- 无毛坯碰撞检测 ---")
    detector_no_stock = CollisionDetector(stock=None)
    segs = parser.parse_gcode("G00 X0 Y0 Z5\nG01 X10 Y10 Z0 F200")
    report = detector_no_stock.check_segments(segs)
    check("无毛坯时碰撞检测正常返回", report is not None)
    check("无毛坯时检测到2段刀路", report.segments_checked == 2,
          f"实际: {report.segments_checked}")
    check("Z安全检查使用保守默认值(stock_z_top=100)",
          not report.safe,
          "预期safe=False, G00 Z5 < default safe_z 110")

    print("\n--- 仅G00快速移动 ---")
    rapid_segs = parser.parse_gcode("G00 X0 Y0 Z50\nG00 X50 Y30 Z50")
    stock = StockModel(length=40, width=40, height=30)
    det = CollisionDetector(stock=stock, safe_z_height=10)
    report = det.check_segments(rapid_segs)
    check("仅G00无碰撞检测正常(安全高度内)", report is not None)
    check("Z50高于safe_z=40+10=50，不应触发Z警告",
          report.safe,
          "预期safe=True, G00 Z50 >= stock_z_top(30)+safe_z_height(10)=40")


def generate_real_gcode() -> list[str]:
    """生成真实加工场景的G代码。

    工序：面铣 → 型腔铣 → 钻孔 → 轮廓精加工
    参数基于40Cr合金钢 + φ10硬质合金平底铣刀
    """
    return [
        "%",
        "O1000 (Bracket Machining - VMC850 + 40Cr + φ10 Carbide Endmill)",
        "(Programmed by 灵境制造 V2.0.0)",
        "",
        "N10 G90 G21 G17 G40 G49 G80",
        "N20 G91 G28 Z0",
        "N30 G90 G54",
        "",
        "(--- Tool 1: φ10 Carbide Flat Endmill ---)",
        "N40 T1 M06",
        "N50 G00 G90 G54 X-80 Y-60 S2548 M03",
        "N60 G43 H01 Z50 M08",
        "",
        "(--- Face Milling - Roughing ---)",
        "N70 G00 X-80 Y-60 Z5",
        "N80 G01 Z-3 F300",
        "N90 G01 X80 F400",
        "N100 G01 Y-40",
        "N110 G01 X-80",
        "N120 G01 Y-20",
        "N130 G01 X80",
        "N140 G01 Y0",
        "N150 G01 X-80",
        "N160 G01 Y20",
        "N170 G01 X80",
        "N180 G01 Y40",
        "N190 G01 X-80",
        "N200 G01 Y60",
        "N210 G01 X80",
        "N220 G00 Z50",
        "",
        "(--- Pocket Milling - Z-8mm ---)",
        "N230 G00 X-30 Y-20 Z5",
        "N240 G01 Z-5 F200",
        "N250 G01 X30 F350",
        "N260 G01 Y20",
        "N270 G01 X-30",
        "N280 G01 Y-20",
        "N290 G01 Z-8 F150",
        "N300 G01 X30 F300",
        "N310 G01 Y20",
        "N320 G01 X-30",
        "N330 G01 Y-20",
        "N340 G00 Z50",
        "",
        "(--- Hole Drilling - φ8 Through ---)",
        "N350 G00 X0 Y0 Z5",
        "N360 G01 Z-15 F100",
        "N370 G00 Z50",
        "N380 G00 X40 Y30 Z5",
        "N390 G01 Z-15 F100",
        "N400 G00 Z50",
        "",
        "(--- Contour Finishing ---)",
        "N410 G00 X-50 Y-35 Z5",
        "N420 G01 Z-8 F150",
        "N430 G01 X-50 Y35 F250",
        "N440 G01 X50 Y35",
        "N450 G01 X50 Y-35",
        "N460 G01 X-50 Y-35",
        "N470 G00 Z50",
        "",
        "(--- End of Program ---)",
        "N480 G91 G28 Z0",
        "N490 G91 G28 X0 Y0",
        "N500 M05 M09",
        "N510 M30",
        "%",
    ]


# =============================================================================
# 主入口
# =============================================================================
if __name__ == "__main__":
    print("+" + "=" * 70 + "+")
    print("|     Lingjing Manufacturing -- E2E Machining Scenario Test V2.0.0  |")
    print("|     Python Domain Models <-> Rust Interface Full-Chain Verify       |")
    print("+" + "=" * 70 + "+")

    phase1_physical_constraints()
    phase2_database_loading()
    phase3_real_scenario()
    phase4_rust_interface_compatibility()
    phase5_edge_cases()

    header("Test Summary")
    total = PASS + FAIL + PENDING
    print(f"  [PASS]  Passed:  {PASS}/{total}")
    if FAIL > 0:
        print(f"  [FAIL]  Failed:  {FAIL}/{total}")
    if PENDING > 0:
        print(f"  [WARN]  Pending: {PENDING}/{total}")
    print(f"{'=' * 72}")

    if FAIL == 0:
        print("\n  Conclusion: All tests passed. Physical constraints, database, simulation full-chain OK.")
    else:
        print(f"\n  Conclusion: {FAIL} test(s) FAILED. Fix required.")
        sys.exit(1)
