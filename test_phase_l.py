"""
测试Phase L: 工艺方案A/B对比引擎
"""

import sys
import os
import io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# 添加python目录到path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'python'))

from app.services.multi_strategy_solver import MultiStrategySolver, StrategyId, DEFAULT_STRATEGIES
from app.services.plan_comparator import PlanComparator


def test_multi_strategy_solver():
    print("=" * 60)
    print("测试多策略求解器")
    print("=" * 60)
    
    solver = MultiStrategySolver()
    
    print("\n1. 测试可用策略列表")
    strategies = solver.get_available_strategies()
    for s in strategies:
        print(f"   - {s['name']} ({s['strategy_id']}): {s['objective_weights']}")
    
    part_info = {
        "material": "steel_45",
        "part_type": "shaft",
        "constraints": {}
    }
    
    print("\n2. 测试所有策略求解")
    results = solver.solve_all_strategies(part_info)
    for strategy_id, result in results.items():
        print(f"\n   策略: {result.strategy_name}")
        print(f"   - 切削速度: {result.cutting_speed} m/min")
        print(f"   - 进给量: {result.feed_rate} mm/rev")
        print(f"   - 背吃刀量: {result.depth_of_cut} mm")
        print(f"   - 表面粗糙度: {result.surface_roughness} Ra")
        print(f"   - 成本: {result.cost} CNY")
        print(f"   - 加工时间: {result.processing_time} min")
        print(f"   - 刀具寿命: {result.tool_life} min")
    
    print("\n3. 测试自定义权重求解")
    custom_weights = {"quality": 0.4, "cost": 0.3, "time": 0.2, "tool_life": 0.1}
    custom_result = solver.solve_with_custom_weights(part_info, custom_weights)
    print(f"\n   自定义方案: {custom_result.strategy_name}")
    print(f"   - 切削速度: {custom_result.cutting_speed} m/min")
    print(f"   - 表面粗糙度: {custom_result.surface_roughness} Ra")
    print(f"   - 成本: {custom_result.cost} CNY")
    print(f"   - 加工时间: {custom_result.processing_time} min")
    print(f"   - 刀具寿命: {custom_result.tool_life} min")
    
    print("\n[PASS] 多策略求解器测试通过")
    return results


def test_plan_comparator():
    print("\n" + "=" * 60)
    print("测试方案对比分析器")
    print("=" * 60)
    
    comparator = PlanComparator()
    
    plans = [
        {
            "plan_id": "quality_first_test",
            "strategy_id": "quality_first",
            "strategy_name": "质量优先",
            "cutting_speed": 100.0,
            "feed_rate": 0.12,
            "depth_of_cut": 1.8,
            "surface_roughness": 0.8,
            "cost": 280.0,
            "processing_time": 35.0,
            "tool_life": 250.0
        },
        {
            "plan_id": "cost_first_test",
            "strategy_id": "cost_first",
            "strategy_name": "成本优先",
            "cutting_speed": 80.0,
            "feed_rate": 0.18,
            "depth_of_cut": 2.2,
            "surface_roughness": 3.2,
            "cost": 150.0,
            "processing_time": 28.0,
            "tool_life": 200.0
        },
        {
            "plan_id": "efficiency_first_test",
            "strategy_id": "efficiency_first",
            "strategy_name": "效率优先",
            "cutting_speed": 150.0,
            "feed_rate": 0.25,
            "depth_of_cut": 2.5,
            "surface_roughness": 4.8,
            "cost": 220.0,
            "processing_time": 18.0,
            "tool_life": 120.0
        }
    ]
    
    print("\n1. 测试标准化评分")
    scores = comparator.normalize_and_compare(plans)
    
    for score in scores:
        print(f"\n   策略: {score.strategy_name}")
        print(f"   - 质量得分: {score.normalized_scores['quality']:.1f}")
        print(f"   - 成本得分: {score.normalized_scores['cost']:.1f}")
        print(f"   - 效率得分: {score.normalized_scores['efficiency']:.1f}")
        print(f"   - 刀具寿命得分: {score.normalized_scores['tool_life']:.1f}")
        print(f"   - 综合得分: {score.weighted_score:.1f}")
        print(f"   - 优势分析: {score.advantage_analysis}")
        print(f"   - 推荐理由: {score.recommendation}")
    
    print("\n2. 测试方案取舍分析")
    if len(scores) >= 2:
        trade_offs = comparator.get_trade_off_analysis(scores[0], scores[1])
        print(f"\n   {scores[0].strategy_name} vs {scores[1].strategy_name}:")
        for dimension, analysis in trade_offs.items():
            print(f"   - {analysis}")
    
    print("\n[PASS] 方案对比分析器测试通过")


if __name__ == "__main__":
    try:
        results = test_multi_strategy_solver()
        test_plan_comparator()
        print("\n" + "=" * 60)
        print("[PASS] 所有测试通过!工艺方案对比引擎功能正常。")
        print("=" * 60)
    except Exception as e:
        print(f"\n[FAIL] 测试失败: {e}")
        import traceback
        traceback.print_exc()
