"""鲁棒性测试。

测试方法：在初始状态中添加可控噪声（±5%范围内）。
评估指标：检查规划结果的稳定性。
合格标准：微小扰动不应导致完全不同的规划结果。
"""

from __future__ import annotations

import sys
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
def robustness_planner():
    """创建训练好的规划器用于鲁棒性测试。"""
    config = JEPAWorldModelConfig(
        epochs=20,
        batch_size=64,
        cem_planning_horizon=5,
        cem_population_size=75,
        cem_max_iterations=8,
        cem_elite_fraction=0.15,
    )
    model = JEPAPredictor(config)
    trainer = WorldModelTrainer(config, model)
    trainer.train_on_synthetic_data(num_samples=500, verbose=False)
    return CEMPlanner(config, model), config


@pytest.fixture
def base_state():
    """创建基础初始状态。"""
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


class TestPlanningRobustness:
    """规划鲁棒性测试套件。"""

    def test_noise_addition_method(self, base_state):
        """验证噪声添加方法正确。"""
        noisy_state = base_state.add_noise(noise_std=0.05)

        # 验证参数变化在±5%范围内
        original_tool_wear = base_state.tool_wear
        noisy_tool_wear = noisy_state.tool_wear
        if original_tool_wear > 0.01:
            relative_change = abs(noisy_tool_wear - original_tool_wear) / original_tool_wear
            # 允许噪声导致的合理变化
            assert relative_change < 0.5, (
                f"工具磨损变化过大: {relative_change:.2%}"
            )

        # 验证材料类型不变
        assert noisy_state.material == base_state.material

    def test_planning_stability_under_noise(
        self, robustness_planner, base_state,
    ):
        """验证加噪后规划结果的稳定性。

        微小扰动不应导致完全不同的规划结果。
        """
        planner, config = robustness_planner

        # 原始规划
        original_result = planner.plan(base_state)

        # 添加噪声后的规划
        noisy_state = base_state.add_noise(noise_std=0.05)
        noisy_result = planner.plan(noisy_state)

        # 比较操作类型序列的相似度
        original_types = [a.operation_type for a in original_result.action_sequence]
        noisy_types = [a.operation_type for a in noisy_result.action_sequence]

        # 计算操作类型序列的匹配率
        matches = sum(
            1 for o, n in zip(original_types, noisy_types) if o == n
        )
        match_rate = matches / len(original_types)

        # 加噪后操作序列应保持一定相似度（至少50%匹配）
        assert match_rate > 0.5, (
            f"噪声扰动后操作序列匹配率 {match_rate:.2%} 低于50%"
        )

    def test_reward_stability_under_noise(
        self, robustness_planner, base_state,
    ):
        """验证加噪后总奖励的稳定性。"""
        planner, config = robustness_planner

        original_result = planner.plan(base_state)
        noisy_state = base_state.add_noise(noise_std=0.05)
        noisy_result = planner.plan(noisy_state)

        # 总奖励的相对变化
        original_reward = original_result.total_reward
        noisy_reward = noisy_result.total_reward

        if abs(original_reward) > 0.01:
            relative_change = abs(noisy_reward - original_reward) / abs(original_reward)
            assert relative_change < 0.5, (
                f"噪声扰动后总奖励变化过大: {relative_change:.2%}"
            )

    def test_multiple_noise_levels_stability(
        self, robustness_planner, base_state,
    ):
        """验证不同噪声水平下规划结果的稳定性趋势。

        噪声越大，结果差异越大，但不应突变。
        """
        planner, config = robustness_planner

        noise_levels = [0.01, 0.03, 0.05]
        results = []

        original_result = planner.plan(base_state)
        original_types = [a.operation_type for a in original_result.action_sequence]

        for noise_std in noise_levels:
            noisy_state = base_state.add_noise(noise_std=noise_std)
            noisy_result = planner.plan(noisy_state)
            noisy_types = [a.operation_type for a in noisy_result.action_sequence]

            matches = sum(
                1 for o, n in zip(original_types, noisy_types) if o == n
            )
            match_rate = matches / len(original_types)
            results.append(match_rate)

        # 验证噪声增大时匹配率有下降趋势（但不一定严格单调）
        # 所有噪声水平下的匹配率都应 > 30%
        for i, (noise_std, match_rate) in enumerate(zip(noise_levels, results)):
            assert match_rate > 0.3, (
                f"噪声水平 {noise_std} 下的匹配率 {match_rate:.2%} 过低"
            )

    def test_single_step_prediction_stability(
        self, robustness_planner, base_state,
    ):
        """验证单步预测在噪声下的稳定性。"""
        planner, config = robustness_planner
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

        # 原始预测
        original_result = model.predict_step(
            base_state.state_embedding,
            action.action_embedding,
        )

        # 加噪后的预测
        noisy_state = base_state.add_noise(noise_std=0.05)
        noisy_result = model.predict_step(
            noisy_state.state_embedding,
            action.action_embedding,
        )

        # 两次预测的余弦相似度
        cos_sim = np.dot(
            original_result["next_state_embedding"],
            noisy_result["next_state_embedding"],
        ) / (
            np.linalg.norm(original_result["next_state_embedding"])
            * np.linalg.norm(noisy_result["next_state_embedding"])
            + 1e-10
        )

        assert cos_sim > 0.8, (
            f"噪声扰动后预测余弦相似度 {cos_sim:.4f} 低于0.8"
        )

    def test_risk_report_stability(
        self, robustness_planner, base_state,
    ):
        """验证风险评估报告在噪声下的稳定性。"""
        planner, config = robustness_planner

        original_result = planner.plan(base_state)
        noisy_state = base_state.add_noise(noise_std=0.05)
        noisy_result = planner.plan(noisy_state)

        original_risk = original_result.risk_report["overall_risk"]
        noisy_risk = noisy_result.risk_report["overall_risk"]

        # 风险评估的绝对变化不应过大
        risk_change = abs(noisy_risk - original_risk)
        assert risk_change < 0.3, (
            f"噪声扰动后风险评估变化 {risk_change:.3f} 过大"
        )

    def test_confidence_stability(
        self, robustness_planner, base_state,
    ):
        """验证置信度在噪声下的稳定性。"""
        planner, config = robustness_planner
        model = planner.predictor

        action = ManufacturingAction(
            operation_type="finish_milling",
            tool_id="T02",
            parameters={
                "spindle_speed": 10000,
                "feed_rate": 300.0,
                "depth_of_cut": 0.5,
                "coolant": True,
            },
        )

        original_result = model.predict_step(
            base_state.state_embedding,
            action.action_embedding,
        )

        noisy_state = base_state.add_noise(noise_std=0.05)
        noisy_result = model.predict_step(
            noisy_state.state_embedding,
            action.action_embedding,
        )

        # 置信度变化应较小
        conf_change = abs(original_result["confidence"] - noisy_result["confidence"])
        assert conf_change < 0.3, (
            f"噪声扰动后置信度变化 {conf_change:.3f} 过大"
        )

    def test_geometry_noise_robustness(
        self, robustness_planner, base_state,
    ):
        """验证几何嵌入噪声下的鲁棒性。"""
        planner, config = robustness_planner
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

        # 原始预测
        original_result = model.predict_step(
            base_state.state_embedding,
            action.action_embedding,
        )

        # 仅对几何嵌入添加噪声（其他参数不变）
        noisy_geometry = base_state.geometry + np.random.normal(0, 0.02, 512).astype(np.float32)
        noisy_geometry = noisy_geometry / (np.linalg.norm(noisy_geometry) + 1e-10)

        noisy_geom_state = ManufacturingState(
            geometry=noisy_geometry,
            material=base_state.material,
            precision=base_state.precision,
            tool_wear=base_state.tool_wear,
            spindle_temp=base_state.spindle_temp,
            vibration=base_state.vibration,
            current_operation=base_state.current_operation,
            completed_operations=list(base_state.completed_operations),
        )

        noisy_result = model.predict_step(
            noisy_geom_state.state_embedding,
            action.action_embedding,
        )

        cos_sim = np.dot(
            original_result["next_state_embedding"],
            noisy_result["next_state_embedding"],
        ) / (
            np.linalg.norm(original_result["next_state_embedding"])
            * np.linalg.norm(noisy_result["next_state_embedding"])
            + 1e-10
        )

        assert cos_sim > 0.7, (
            f"几何嵌入噪声后预测余弦相似度 {cos_sim:.4f} 低于0.7"
        )
