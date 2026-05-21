"""工艺规划数据层质量检验脚本。

验证JSON数据文件、Schema验证、数据访问类和查询接口的正确性。
"""

import json
import sys
import os

# Force UTF-8 output on Windows
os.environ.setdefault('PYTHONIOENCODING', 'utf-8')
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from pathlib import Path  # noqa: E402

project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from app.data.process_data_manager import (  # noqa: E402
    ProcessPlanningDataManager,
    QueryError,
)

PASS = "[PASS]"
FAIL = "[FAIL]"


def print_section(title: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")


def get_data_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "app" / "data"


def test_json_files_exist() -> bool:
    print_section("1. JSON文件存在性检查")
    data_dir = get_data_dir()
    files = [
        "materials.json",
        "tools.json",
        "cutting_parameters.json",
        "process_rules.json",
    ]
    all_exist = True
    for filename in files:
        filepath = data_dir / filename
        exists = filepath.exists()
        status = PASS if exists else FAIL
        print(f"  {status} {filename}")
        if not exists:
            all_exist = False
    return all_exist


def test_json_valid_format() -> bool:
    print_section("2. JSON格式验证")
    data_dir = get_data_dir()
    files = [
        "materials.json",
        "tools.json",
        "cutting_parameters.json",
        "process_rules.json",
    ]
    all_valid = True
    for filename in files:
        filepath = data_dir / filename
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, list):
                print(f"  {PASS} {filename}: 格式正确，包含 {len(data)} 条记录")
            else:
                print(f"  {FAIL} {filename}: 格式错误，应为数组")
                all_valid = False
        except json.JSONDecodeError as e:
            print(f"  {FAIL} {filename}: JSON解析失败 - {e}")
            all_valid = False
    return all_valid


def test_data_manager_load() -> bool:
    print_section("3. 数据管理器加载测试")
    try:
        data_dir = get_data_dir()
        manager = ProcessPlanningDataManager(data_dir)
        print(f"  {PASS} 数据管理器初始化成功")
        print(f"    {manager}")
        return True
    except Exception as e:
        print(f"  {FAIL} 数据管理器初始化失败: {e}")
        return False


def test_material_queries() -> bool:
    print_section("4. 材料查询接口测试")
    data_dir = get_data_dir()
    manager = ProcessPlanningDataManager(data_dir)
    all_passed = True

    test_cases = [
        ("45#钢", "material_45steel"),
        ("铝合金6061", "material_al6061"),
        ("不锈钢304", "material_ss304"),
        ("40Cr", "material_40cr"),
    ]

    for name, expected_id in test_cases:
        result = manager.get_material_by_name(name)
        if result and result.id == expected_id:
            print(f"  {PASS} 查询 '{name}': 成功 (ID: {result.id})")
            print(f"    密度: {result.density_gcm3} g/cm3, 硬度: HB{result.hardness_hb}")
        else:
            print(f"  {FAIL} 查询 '{name}': 失败")
            all_passed = False

    try:
        manager.get_material_by_name("")
        print(f"  {FAIL} 空名称查询应抛出异常")
        all_passed = False
    except QueryError as e:
        print(f"  {PASS} 空名称查询正确抛出异常: {e}")

    return all_passed


def test_tool_queries() -> bool:
    print_section("5. 刀具查询接口测试")
    data_dir = get_data_dir()
    manager = ProcessPlanningDataManager(data_dir)
    all_passed = True

    test_cases = [
        ("carbon_steel", "钻孔", "twist_drill", 7),
        ("aluminum", "型腔/轮廓加工", "endmill", 7),
        ("stainless_steel", "平面加工", "face_mill", 4),
    ]

    for material_cat, process, expected_series, expected_count in test_cases:
        results = manager.get_tools_by_material_and_process(material_cat, process)
        if len(results) == expected_count and all(t.series == expected_series for t in results):
            print(f"  {PASS} 查询 {material_cat} + {process}: 成功，找到 {len(results)} 把刀具")
        else:
            print(f"  {FAIL} 查询 {material_cat} + {process}: 失败，期望 {expected_count} 把，实际 {len(results)} 把")
            all_passed = False

    return all_passed


def test_cutting_parameter_queries() -> bool:
    print_section("6. 切削参数查询接口测试")
    data_dir = get_data_dir()
    manager = ProcessPlanningDataManager(data_dir)
    all_passed = True

    test_cases = [
        ("material_45steel", "twist_drill", "param_45steel_hss_drill"),
        ("material_45steel", "endmill", "param_45steel_carbide_endmill"),
        ("material_al6061", "endmill", "param_al6061_carbide_endmill"),
        ("material_ss304", "twist_drill", "param_ss304_hss_drill"),
    ]

    for material_id, tool_series, expected_id in test_cases:
        results = manager.get_cutting_parameters(material_id, tool_series)
        if results and results[0].id == expected_id:
            param = results[0]
            print(f"  {PASS} 查询 {material_id} + {tool_series}: 成功")
            print(f"    切削速度: {param.cutting_speed_min_mpm}-{param.cutting_speed_max_mpm} m/min")
            print(f"    进给: {param.feed_min_mmpr}-{param.feed_max_mmpr} {param.feed_unit}")
        else:
            print(f"  {FAIL} 查询 {material_id} + {tool_series}: 失败")
            all_passed = False

    return all_passed


def test_data_integrity() -> bool:
    print_section("7. 数据完整性验证")
    data_dir = get_data_dir()
    manager = ProcessPlanningDataManager(data_dir)
    result = manager.validate_data_integrity()
    all_passed = True

    print("  统计信息:")
    for key, value in result["stats"].items():
        print(f"    {key}: {value}")

    if result["is_valid"]:
        print(f"  {PASS} 数据完整性验证通过")
    else:
        print(f"  {FAIL} 数据完整性验证失败:")
        for error in result["errors"]:
            print(f"    - {error}")
        all_passed = False

    return all_passed


def test_error_handling() -> bool:
    print_section("8. 错误处理机制测试")
    data_dir = get_data_dir()
    manager = ProcessPlanningDataManager(data_dir)
    all_passed = True

    error_tests = [
        ("空材料名称", lambda: manager.get_material_by_name("")),
        ("空材料类型", lambda: manager.get_tools_by_material_and_process("", "钻孔")),
        ("空加工工序", lambda: manager.get_tools_by_material_and_process("carbon_steel", "")),
        ("空材料ID", lambda: manager.get_cutting_parameters("", "twist_drill")),
        ("空刀具系列", lambda: manager.get_cutting_parameters("material_45steel", "")),
    ]

    for test_name, test_func in error_tests:
        try:
            test_func()
            print(f"  {FAIL} {test_name}: 应抛出异常但未抛出")
            all_passed = False
        except QueryError:
            print(f"  {PASS} {test_name}: 正确抛出 QueryError")

    return all_passed


def main() -> int:
    print("=" * 60)
    print("  机械加工工艺规划系统 - 数据层质量检验")
    print("=" * 60)

    tests = [
        ("JSON文件存在性", test_json_files_exist),
        ("JSON格式验证", test_json_valid_format),
        ("数据管理器加载", test_data_manager_load),
        ("材料查询接口", test_material_queries),
        ("刀具查询接口", test_tool_queries),
        ("切削参数查询接口", test_cutting_parameter_queries),
        ("数据完整性验证", test_data_integrity),
        ("错误处理机制", test_error_handling),
    ]

    results = {}
    for name, test_func in tests:
        try:
            results[name] = test_func()
        except Exception as e:
            print(f"\n  {FAIL} 测试 {name} 发生异常: {e}")
            results[name] = False

    print_section("测试总结")
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    print(f"  通过: {passed}/{total}")

    for name, result in results.items():
        status = PASS if result else FAIL
        print(f"  {status} {name}")

    if passed == total:
        print("\n  所有测试通过，数据层质量检验合格！")
        return 0
    else:
        print(f"\n  {total - passed} 个测试未通过，需要修复")
        return 1


if __name__ == "__main__":
    sys.exit(main())
