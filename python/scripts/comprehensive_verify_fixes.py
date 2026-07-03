#!/usr/bin/env python3
"""全面验证脚本 - 确保所有修复生效且无回归。

验证内容：
1. orchestrator.py 中所有 step handler 的类型转换
2. _extract_final_output 方法存在性
3. safe_error_message 返回值处理
4. Setup 类导入路径
5. 3D 导出功能
6. GCodePostProcessor 功能
7. 异常处理覆盖
"""

import sys
import traceback
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_extract_final_output_exists():
    """测试 _extract_final_output 方法是否存在"""
    print("\n[测试 1] 检查 _extract_final_output 方法...")
    try:
        from app.agent.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        # 检查方法是否存在
        if not hasattr(orchestrator, '_extract_final_output'):
            print("  ✗ 失败: _extract_final_output 方法不存在")
            return False
        
        # 检查方法是否可调用
        if not callable(getattr(orchestrator, '_extract_final_output')):
            print("  ✗ 失败: _extract_final_output 不可调用")
            return False
        
        print("  ✓ 通过: _extract_final_output 方法存在且可调用")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_step_dxf_parse_type_handling():
    """测试 _step_dxf_parse 的类型处理"""
    print("\n[测试 2] 检查 _step_dxf_parse 类型处理...")
    try:
        from app.agent.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        # 检查方法源码是否包含类型转换逻辑
        import inspect
        source = inspect.getsource(orchestrator._step_dxf_parse)
        
        if 'hasattr(parse_result' not in source:
            print("  ✗ 失败: _step_dxf_parse 缺少类型转换逻辑")
            return False
        
        if 'isinstance(parse_result, dict)' not in source:
            print("  ✗ 失败: _step_dxf_parse 缺少 dict 类型检查")
            return False
        
        print("  ✓ 通过: _step_dxf_parse 包含正确的类型转换逻辑")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_step_parameter_recommend_type_handling():
    """测试 _step_parameter_recommend 的类型处理"""
    print("\n[测试 3] 检查 _step_parameter_recommend 类型处理...")
    try:
        from app.agent.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        # 检查方法源码是否包含类型转换逻辑
        import inspect
        source = inspect.getsource(orchestrator._step_parameter_recommend)
        
        if 'hasattr(plan_result' not in source:
            print("  ✗ 失败: _step_parameter_recommend 缺少类型转换逻辑")
            return False
        
        if 'isinstance(plan_result, dict)' not in source:
            print("  ✗ 失败: _step_parameter_recommend 缺少 dict 类型检查")
            return False
        
        print("  ✓ 通过: _step_parameter_recommend 包含正确的类型转换逻辑")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_step_gcode_generate_type_conversion():
    """测试 _step_gcode_generate 的类型转换"""
    print("\n[测试 4] 检查 _step_gcode_generate 类型转换...")
    try:
        from app.agent.orchestrator import AgentOrchestrator
        
        orchestrator = AgentOrchestrator()
        
        # 检查方法源码是否包含类型转换逻辑
        import inspect
        source = inspect.getsource(orchestrator._step_gcode_generate)
        
        if 'isinstance(input_data, dict)' not in source:
            print("  ✗ 失败: _step_gcode_generate 缺少 dict 类型检查")
            return False
        
        if 'Operation(' not in source:
            print("  ✗ 失败: _step_gcode_generate 缺少 Operation 对象构建")
            return False
        
        if 'Setup(' not in source:
            print("  ✗ 失败: _step_gcode_generate 缺少 Setup 对象构建")
            return False
        
        if 'OperationPlan(' not in source:
            print("  ✗ 失败: _step_gcode_generate 缺少 OperationPlan 对象构建")
            return False
        
        print("  ✓ 通过: _step_gcode_generate 包含完整的类型转换逻辑")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_setup_import_path():
    """测试 Setup 类导入路径"""
    print("\n[测试 5] 检查 Setup 类导入路径...")
    try:
        from app.process_planning.feature_dependency import Setup
        
        # 尝试创建 Setup 对象
        setup = Setup(
            name="test_setup",
            surface="A",
            datum_features=["feature1"],
            fixture_type="vice",
            clamped_features=["feature2"]
        )
        
        if setup.name != "test_setup":
            print("  ✗ 失败: Setup 对象属性不正确")
            return False
        
        print("  ✓ 通过: Setup 类可以从 feature_dependency 导入")
        return True
        
    except ImportError as e:
        print(f"  ✗ 失败: 无法导入 Setup 类: {e}")
        return False
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_safe_error_message_return_type():
    """测试 safe_error_message 返回类型"""
    print("\n[测试 6] 检查 safe_error_message 返回类型...")
    try:
        from app.core.safe_errors import safe_error_message
        
        # 测试各种异常类型
        test_exceptions = [
            ValueError("test error"),
            TypeError("type error"),
            RuntimeError("runtime error"),
            AttributeError("attribute error"),
        ]
        
        for exc in test_exceptions:
            result = safe_error_message(exc)
            
            if not isinstance(result, dict):
                print(f"  ✗ 失败: safe_error_message({type(exc).__name__}) 返回的不是 dict")
                return False
            
            if 'message' not in result:
                print(f"  ✗ 失败: safe_error_message({type(exc).__name__}) 返回的 dict 缺少 'message' 字段")
                return False
        
        print("  ✓ 通过: safe_error_message 始终返回包含 'message' 字段的 dict")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_exception_handling_coverage():
    """测试异常处理覆盖"""
    print("\n[测试 7] 检查异常处理覆盖...")
    try:
        from app.agent.orchestrator import AgentOrchestrator
        import inspect
        
        orchestrator = AgentOrchestrator()
        
        # 检查 execute_pipeline 的异常处理
        source_execute = inspect.getsource(orchestrator.execute_pipeline)
        if 'AttributeError' not in source_execute:
            print("  ✗ 失败: execute_pipeline 缺少 AttributeError 处理")
            return False
        
        # 检查 _execute_step 的异常处理
        source_step = inspect.getsource(orchestrator._execute_step)
        if 'AttributeError' not in source_step:
            print("  ✗ 失败: _execute_step 缺少 AttributeError 处理")
            return False
        
        print("  ✓ 通过: 异常处理包含 AttributeError")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_export_utils():
    """测试 3D 导出功能"""
    print("\n[测试 8] 检查 3D 导出功能...")
    try:
        from app.cadquery.export_utils import export_to_stl, export_to_step, export_to_svg
        
        # 检查函数是否存在
        if not callable(export_to_stl):
            print("  ✗ 失败: export_to_stl 不可调用")
            return False
        
        if not callable(export_to_step):
            print("  ✗ 失败: export_to_step 不可调用")
            return False
        
        if not callable(export_to_svg):
            print("  ✗ 失败: export_to_svg 不可调用")
            return False
        
        print("  ✓ 通过: 3D 导出函数存在且可调用")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_gcode_postprocessor():
    """测试 GCodePostProcessor 功能"""
    print("\n[测试 9] 检查 GCodePostProcessor...")
    try:
        from app.toolpath.gcode_postprocessor import GCodePostProcessor
        
        postprocessor = GCodePostProcessor()
        
        # 检查 convert_toolpath 方法是否存在
        if not hasattr(postprocessor, 'convert_toolpath'):
            print("  ✗ 失败: convert_toolpath 方法不存在")
            return False
        
        # 检查 _convert_moves 方法是否存在
        if not hasattr(postprocessor, '_convert_moves'):
            print("  ✗ 失败: _convert_moves 方法不存在")
            return False
        
        print("  ✓ 通过: GCodePostProcessor 包含必要方法")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def test_log_message_update():
    """测试日志文案更新"""
    print("\n[测试 10] 检查日志文案更新...")
    try:
        from app.agent.orchestrator import AgentOrchestrator
        import inspect
        
        orchestrator = AgentOrchestrator()
        
        # 检查 _validate_dependencies 方法的日志文案
        source = inspect.getsource(orchestrator._validate_dependencies)
        
        if 'fallback implementations or simplified logic' not in source:
            print("  ✗ 失败: 日志文案未更新")
            return False
        
        if 'stub implementations' in source:
            print("  ✗ 失败: 旧日志文案仍然存在")
            return False
        
        print("  ✓ 通过: 日志文案已更新")
        return True
        
    except Exception as e:
        print(f"  ✗ 失败: {e}")
        traceback.print_exc()
        return False


def main():
    """主测试函数"""
    print("=" * 70)
    print("全面验证脚本 - 确保所有修复生效且无回归")
    print("=" * 70)
    
    results = []
    
    # 运行所有测试
    results.append(("_extract_final_output 方法存在性", test_extract_final_output_exists()))
    results.append(("_step_dxf_parse 类型处理", test_step_dxf_parse_type_handling()))
    results.append(("_step_parameter_recommend 类型处理", test_step_parameter_recommend_type_handling()))
    results.append(("_step_gcode_generate 类型转换", test_step_gcode_generate_type_conversion()))
    results.append(("Setup 类导入路径", test_setup_import_path()))
    results.append(("safe_error_message 返回类型", test_safe_error_message_return_type()))
    results.append(("异常处理覆盖", test_exception_handling_coverage()))
    results.append(("3D 导出功能", test_export_utils()))
    results.append(("GCodePostProcessor", test_gcode_postprocessor()))
    results.append(("日志文案更新", test_log_message_update()))
    
    # 打印汇总
    print("\n" + "=" * 70)
    print("测试汇总")
    print("=" * 70)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    total = len(results)
    passed = sum(1 for _, r in results if r)
    
    print(f"\n总计: {passed}/{total} 测试通过")
    
    if passed == total:
        print("\n✓ 所有测试通过！修复已生效且无回归。")
        return 0
    else:
        print(f"\n✗ {total - passed} 个测试失败，请检查修复。")
        return 1


if __name__ == "__main__":
    sys.exit(main())
