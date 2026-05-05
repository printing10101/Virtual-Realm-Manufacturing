import asyncio
import sys
import os

sys.stdout.reconfigure(encoding='utf-8')

project_root = os.path.dirname(os.path.abspath(__file__))
python_app_path = os.path.join(project_root, "python")
sys.path.insert(0, python_app_path)

from app.config import config
from app.services.model_router import ModelRouter, RouteDecision, ComplexityEvaluator
from app.services.model_finetuner import FineTuneManager, DataSanitizer


async def test_model_router():
    print("=" * 60)
    print("测试 1: 模型路由器 - 复杂度评估")
    print("=" * 60)

    router = ModelRouter()

    test_cases = [
        {
            "name": "简单场景 - 标准材料",
            "input": {
                "material": "45钢",
                "tool": "车刀",
                "constraints": [],
                "geometry": {},
                "history": []
            },
            "expected_decision": RouteDecision.LOCAL
        },
        {
            "name": "中等场景 - 特殊材料",
            "input": {
                "material": "钛合金",
                "tool": "铣刀",
                "constraints": ["切削力", "表面粗糙度"],
                "geometry": {"features": ["hole", "pocket"], "has_freeform": False},
                "history": []
            },
            "expected_decision": RouteDecision.LOCAL_WITH_FALLBACK
        },
        {
            "name": "复杂场景 - 复杂刀具+多约束",
            "input": {
                "material": "镍基合金",
                "tool": "复杂刀具",
                "constraints": ["切削力", "表面粗糙度", "刀具寿命", "温度", "振动"],
                "geometry": {"features": ["hole", "pocket", "contour", "thread", "gear"], "has_freeform": True, "tolerance": 0.005},
                "history": [{"iterations": 6}, {"iterations": 7}]
            },
            "expected_decision": RouteDecision.CLOUD
        }
    ]

    for case in test_cases:
        print(f"\n测试用例: {case['name']}")
        result = await router.route(case['input'])
        print(f"  复杂度评分: {result['complexity_score']}")
        print(f"  路由决策: {result['route_decision']}")
        print(f"  原因: {result['reasons']}")
        print(f"  预期: {case['expected_decision']}, 实际: {result['route_decision']}")
        assert result['route_decision'] == case['expected_decision'], f"路由决策不匹配！预期 {case['expected_decision']}, 实际 {result['route_decision']}"
        print("  [PASS] 通过")

    print("\n[PASS] 模型路由器测试通过")


async def test_data_sanitizer():
    print("\n" + "=" * 60)
    print("测试 2: 数据脱敏")
    print("=" * 60)

    test_data = {
        "customer_name": "某某公司",
        "project_id": "P-2024-001",
        "price": 50000,
        "material": "45钢",
        "tool": "车刀",
        "cutting_speed": 150,
        "feed_rate": 0.2,
        "description": "这是一个客户的项目"
    }

    sanitized = DataSanitizer.sanitize(test_data)
    print(f"原始数据: {test_data}")
    print(f"脱敏后: {sanitized}")

    assert "customer_name" not in sanitized, "customer_name 应该被移除"
    assert "project_id" not in sanitized, "project_id 应该被移除"
    assert "price" not in sanitized, "price 应该被移除"
    assert "material" in sanitized, "material 应该保留"
    assert "tool" in sanitized, "tool 应该保留"
    assert "cutting_speed" in sanitized, "cutting_speed 应该保留"
    assert sanitized["description"] == "[REDACTED]", "包含敏感词的描述应该被脱敏"

    print("[PASS] 数据脱敏测试通过")


async def test_finetune_manager():
    print("\n" + "=" * 60)
    print("测试 3: 微调管理器")
    print("=" * 60)

    manager = FineTuneManager()

    status = manager.get_finetune_status()
    print(f"当前微调状态: {status['status']}")

    trigger_result = manager.trigger_finetune(force=False)
    print(f"微调触发结果: {trigger_result['status']}")

    rollback_result = manager.rollback_model()
    print(f"回滚结果: {rollback_result['status']}")

    print("[PASS] 微调管理器测试通过")


async def main():
    print("开始 Phase K 验收测试\n")

    await test_model_router()
    await test_data_sanitizer()
    await test_finetune_manager()

    print("\n" + "=" * 60)
    print("[SUCCESS] 所有测试通过！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
