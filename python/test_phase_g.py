"""
Phase G: 经验回放知识库测试脚本
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.models.experience import ProcessExperience, ExperienceStatus
from app.services.experience_store import ExperienceStore


def test_experience_model():
    """测试经验数据模型"""
    print("\n[1/5] 测试经验数据模型...")

    exp = ProcessExperience(
        status=ExperienceStatus.SUCCESS,
        scenario="consumer_electronics",
        material="45钢 HB200",
        tool="硬质合金YT15",
        operation="外圆车削",
        params={"v_c": 180, "f": 0.2, "a_p": 2.0},
        results={"cutting_force": 450, "surface_roughness": 1.2, "tool_life": 90},
        feedback="加工效果良好，表面粗糙度达标",
        extracted_rules=["当材料硬度>200HB时，切削速度上限下调20%"],
        similarity_key="45钢 HB200 硬质合金 外圆车削 中等切削深度"
    )

    assert exp.experience_id is not None
    assert exp.status == ExperienceStatus.SUCCESS
    assert exp.material == "45钢 HB200"

    exp_dict = exp.to_dict()
    assert exp_dict["status"] == "success"
    assert "v_c" in exp_dict["params"]

    jsonl = exp.to_jsonl()
    restored = ProcessExperience.from_jsonl(jsonl)
    assert restored.experience_id == exp.experience_id
    assert restored.material == exp.material

    print("   数据模型测试通过")
    return True


def test_experience_store():
    """测试经验存储"""
    print("\n[2/5] 测试经验存储...")

    test_dir = "./data/test_experiences"
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)

    store = ExperienceStore(data_dir=test_dir)

    exp1 = ProcessExperience(
        status=ExperienceStatus.SUCCESS,
        scenario="test_scenario",
        material="45钢",
        tool="硬质合金",
        operation="车削",
        params={"v_c": 150, "f": 0.2},
        results={"cutting_force": 400},
        feedback="加工成功",
        extracted_rules=["45钢车削时v_c不宜超过200m/min"],
        similarity_key="45钢 硬质合金 车削 中等参数"
    )

    exp_id = store.add_experience(exp1)
    assert exp_id == exp1.experience_id

    assert store.get_stats()["total_experiences"] == 1
    assert store.get_stats()["success_count"] == 1

    rules = store.get_rules("test_scenario")
    assert "test_scenario" in rules
    assert len(rules["test_scenario"]) == 1
    assert rules["test_scenario"][0]["rule"] == "45钢车削时v_c不宜超过200m/min"

    all_exps = store.get_all_experiences(scenario="test_scenario")
    assert len(all_exps) == 1

    found = store.get_experience_by_id(exp_id)
    assert found is not None

    import shutil
    shutil.rmtree(test_dir)

    print("   经验存储测试通过")
    return True


def test_constraint_mapping():
    """测试约束映射"""
    print("\n[3/5] 测试约束映射...")

    test_dir = "./data/test_constraints"
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)

    store = ExperienceStore(data_dir=test_dir)

    exp = ProcessExperience(
        status=ExperienceStatus.SUCCESS,
        scenario="constraint_test",
        material="45钢",
        tool="硬质合金",
        operation="车削",
        params={"v_c": 150, "f": 0.2},
        extracted_rules=["切削速度上限不宜超过180m/min", "进给量不宜超过0.25mm/rev"],
        similarity_key="45钢 硬质合金 车削"
    )
    store.add_experience(exp)

    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from app.agents.constraint_mapping_agent import ConstraintMappingAgent

    agent = ConstraintMappingAgent(experience_store=store)

    constraints = agent.get_experience_constraints(scenario="constraint_test")
    assert len(constraints) > 0

    base_params = {"v_c": 200, "f": 0.3, "a_p": 2.0}
    modified = agent.apply_experience_constraints(
        base_params,
        scenario="constraint_test"
    )

    assert modified["v_c"] <= 180
    assert modified["f"] <= 0.25

    import shutil
    shutil.rmtree(test_dir)

    print("   约束映射测试通过")
    return True


def test_vector_store():
    """测试向量检索"""
    print("\n[4/5] 测试向量检索...")

    test_dir = "./data/test_vector"
    if os.path.exists(test_dir):
        import shutil
        shutil.rmtree(test_dir)

    store = ExperienceStore(data_dir=test_dir)

    exps = [
        ProcessExperience(
            status=ExperienceStatus.SUCCESS,
            material="45钢",
            tool="硬质合金",
            operation="车削",
            params={"v_c": 150},
            similarity_key="45钢 硬质合金 外圆车削 中等切削深度"
        ),
        ProcessExperience(
            status=ExperienceStatus.FAILURE,
            material="不锈钢304",
            tool="高速钢",
            operation="铣削",
            params={"v_c": 80},
            similarity_key="不锈钢304 高速钢 平面铣削 高进给量"
        ),
        ProcessExperience(
            status=ExperienceStatus.SUCCESS,
            material="45钢",
            tool="陶瓷刀具",
            operation="车削",
            params={"v_c": 250},
            similarity_key="45钢 陶瓷刀具 精车 高切削速度"
        )
    ]

    for exp in exps:
        store.add_experience(exp)

    similar = store.query_similar(material="45钢", tool="硬质合金", operation="车削", top_k=2)

    assert "success_experiences" in similar
    assert "failure_experiences" in similar

    total = len(similar["success_experiences"]) + len(similar["failure_experiences"])
    assert total > 0

    import shutil
    shutil.rmtree(test_dir)

    print("   向量检索测试通过")
    return True


def test_api_routes_exist():
    """测试API路由存在"""
    print("\n[5/5] 测试API路由...")

    from app.api.v1 import experiences
    assert hasattr(experiences, 'router')

    routes = [r.path for r in experiences.router.routes]
    assert "" in routes
    assert "/stats" in routes
    assert "/rules" in routes
    assert "/{experience_id}" in routes

    print("   API路由测试通过")
    return True


def main():
    print("=" * 60)
    print("Phase G: 经验回放知识库 - 测试")
    print("=" * 60)

    tests = [
        ("数据模型", test_experience_model),
        ("经验存储", test_experience_store),
        ("约束映射", test_constraint_mapping),
        ("向量检索", test_vector_store),
        ("API路由", test_api_routes_exist)
    ]

    passed = 0
    failed = 0

    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
                print(f"   [FAIL] {name} 测试失败")
        except Exception as e:
            failed += 1
            print(f"   [ERROR] {name} 测试异常: {e}")

    print("\n" + "=" * 60)
    print(f"测试完成: {passed} 通过, {failed} 失败")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
