"""规划效率测试。

测试方法：测量从初始状态到目标状态的完整规划时间。
评估指标：规划耗时。
合格标准：< 5秒。
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.jepa_world_model.config import JEPAWorldModelConfig  # noqa: E402
from app.ai.jepa_world_model.state import ManufacturingState  # noqa: E402
from app.ai.jepa_world_model.action import ManufacturingAction  # noqa: E402
from app.ai.jepa_world_model.predictor import JEPAPredictor  # noqa: E402
from app.ai.jepa_world_model.planner import CEMPlanner  # noqa: E402
from app.ai.jepa_world_model.trainer import WorldModelTrainer  # noqa: E402


@pytest.fixture(scope="module")
def efficiency_planner():
    """创建训练好的规划器用于效率测试。"""
    config = JEPAWorldModelConfig(
        epochs=15,
        batch_size=64,
        cem_planning_horizon=5,
        cem_population_size=50,
        cem_max_iterations=5,
        cem_elite_fraction=0.15,
    )
    model = JEPAPredictor(config)
    trainer = WorldModelTrainer(config, model)
    trainer.train_on_synthetic_data(num_samples=300, verbose=False)
    return CEMPlanner(config, model), config


@pytest.fixture
def test_state():
    """创建测试用初始状态。"""
    geometry = np.random.randn(512).astype(np.float32)
    geometry = geometry / (np.linalg.norm(geometry) + 1e-10)
    return ManufacturingState(
        geometry=geometry,
        material="45#钢",
        precision=0.05,
        tool_wear=0.1,
        spindle_temp=30.0,
        vibration=1.5,
        current_operation=0,
        completed_operations=[],
    )


class TestPlanningEfficiency:
    """规划效率测试套件。"""

    def test_full_planning_under_5_seconds(
        self, efficiency_planner, test_state,
    ):
        """验证完整规划在合理时间内完成。"""
        planner, config = efficiency_planner

        start = time.perf_counter()
        result = planner.plan(test_state)
        elapsed = time.perf_counter() - start

        # 使用较小的CEM参数时，规划应在5秒内完成
        assert elapsed < 5.0, (
            f"规划耗时 {elapsed:.2f}s 超过5秒限制"
        )
        assert result.planning_time_ms < 5000, (
            f"报告规划时间 {result.planning_time_ms:.0f}ms 超过5000ms"
        )

    def test_single_step_prediction_speed(
        self, efficiency_planner, test_state,
    ):
        """验证单步预测速度。"""
        planner, config = efficiency_planner
        model = planner.predictor

        action = ManufacturingAction(
            operation_type="rough_milling",
            tool_id="T01",
            parameters={
                "spindle_speed": 8000,
                "feed_rate": 500.0,
                "depth_of_cut": 2.0,
                "coolant": True,
            },
        )

        # 预热
        for _ in range(5):
            model.predict_step(test_state.state_embedding, action.action_embedding)

        # 计时
        num_iterations = 100
        start = time.perf_counter()
        for _ in range(num_iterations):
            model.predict_step(test_state.state_embedding, action.action_embedding)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / num_iterations * 1000
        assert avg_time < 50, (
            f"单步预测平均耗时 {avg_time:.1f}ms 过高"
        )

    def test_trajectory_prediction_speed(
        self, efficiency_planner, test_state,
    ):
        """验证完整轨迹预测速度。"""
        planner, config = efficiency_planner
        model = planner.predictor

        # 生成10步动作序列
        actions = []
        for i in range(10):
            actions.append(
                ManufacturingAction(
                    operation_type="rough_milling",
                    tool_id=f"T{i:02d}",
                    parameters={
                        "spindle_speed": 8000,
                        "feed_rate": 500.0,
                        "depth_of_cut": 2.0,
                        "coolant": True,
                    },
                )
            )
        action_embeddings = np.stack([a.action_embedding for a in actions])

        # 预热
        model.predict_trajectory(test_state.state_embedding, action_embeddings)

        # 计时
        num_iterations = 20
        start = time.perf_counter()
        for _ in range(num_iterations):
            model.predict_trajectory(test_state.state_embedding, action_embeddings)
        elapsed = time.perf_counter() - start

        avg_time = elapsed / num_iterations * 1000
        assert avg_time < 100, (
            f"轨迹预测平均耗时 {avg_time:.1f}ms 过高"
        )

    def test_planning_scales_reasonably(
        self, efficiency_planner, test_state,
    ):
        """验证不同规划参数下的性能可接受。"""
        planner, base_config = efficiency_planner

        # 测试不同horizon的规划时间
        horizons = [5, 10]
        times = []

        for horizon in horizons:
            config = JEPAWorldModelConfig(
                cem_planning_horizon=horizon,
                cem_population_size=100,
                cem_max_iterations=5,
            )
            model = planner.predictor
            cem = CEMPlanner(config, model)

            start = time.perf_counter()
            _ = cem.plan(test_state)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        # 更长的horizon应花费更多时间（或至少相近）
        assert times[-1] < 10.0, (
            f"10步规划耗时 {times[-1]:.2f}s 过高"
        )

    def test_multiple_plans_average_time(
        self, efficiency_planner, test_state,
    ):
        """验证多次规划的平均时间在合理范围。"""
        planner, config = efficiency_planner

        num_runs = 3
        times = []

        for _ in range(num_runs):
            start = time.perf_counter()
            planner.plan(test_state)
            elapsed = time.perf_counter() - start
            times.append(elapsed)

        avg_time = np.mean(times)
        max_time = np.max(times)

        assert avg_time < 5.0, (
            f"平均规划时间 {avg_time:.2f}s 超过5秒"
        )
        assert max_time < 10.0, (
            f"最大规划时间 {max_time:.2f}s 超过10秒"
        )

    def test_counterfactual_comparison_speed(
        self, efficiency_planner, test_state,
    ):
        """验证反事实推理比较的速度。"""
        planner, config = efficiency_planner

        action_a = ManufacturingAction(
            operation_type="rough_milling",
            tool_id="T01",
            parameters={
                "spindle_speed": 8000,
                "feed_rate": 500.0,
                "depth_of_cut": 2.0,
                "coolant": True,
            },
        )

        action_b = ManufacturingAction(
            operation_type="finish_milling",
            tool_id="T02",
            parameters={
                "spindle_speed": 12000,
                "feed_rate": 300.0,
                "depth_of_cut": 0.5,
                "coolant": True,
            },
        )

        start = time.perf_counter()
        comparison = planner.counterfactual_compare(
            test_state, action_a, action_b,
        )
        elapsed = time.perf_counter() - start

        assert elapsed < 1.0, (
            f"反事实推理耗时 {elapsed:.2f}s 过高"
        )
        assert "differences" in comparison
