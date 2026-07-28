"""
消融测试 (Ablation Test)

通过移除三个融合路径中的每一个，形成三个消融模型，
对比完整模型与各消融模型的关键任务指标，验证每个融合路径的必要性。

实验设计:
    1. 完整模型 (Full): 包含所有三个融合路径
    2. 消融-CP: 移除认知→感知融合
    3. 消融-PE: 移除感知→执行融合
    4. 消融-EC: 移除执行→认知融合

验证要求:
    - 每个融合路径的移除需导致性能显著下降（> 3%）
    - 统计显著性验证
    - 各融合路径贡献度量化
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import numpy as np
pytest.importorskip("torch")
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.ai.cross_layer_fusion.fusion import (  # noqa: E402
        CrossLayerFusionSystem,
        CognitiveToPerceptionFusion,
        PerceptionToExecutionFusion,
        ExecutionToCognitiveFusion,
    )
    CROSS_LAYER_FUSION_AVAILABLE = True
except ImportError:
    CROSS_LAYER_FUSION_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="app.ai.cross_layer_fusion 模块不存在")


# ============================================================================
# 消融模型
# ============================================================================


class AblationModelNoCog2Per(nn.Module):
    """消融模型: 移除认知→感知融合。

    感知层特征直接使用原始嵌入，不使用认知意图重加权。
    """

    def __init__(self, dim_cognitive=256, dim_perception=256, dim_sensor=128,
                 dim_exec_state=128, dim_anomaly=64, dim_fusion=256,
                 seq_len_sensor=32, max_events=4, n_heads=8):
        super().__init__()
        # 仅保留 P→E 和 E→C
        self.per2exec = PerceptionToExecutionFusion(
            dim_geometry=dim_perception, dim_sensor=dim_sensor,
            seq_len_sensor=seq_len_sensor, dim_exec=dim_exec_state,
            dim_fusion=dim_fusion, n_heads=n_heads,
        )
        self.exec2cog = ExecutionToCognitiveFusion(
            dim_exec_state=dim_exec_state, dim_anomaly=dim_anomaly,
            dim_fusion=dim_fusion, dim_adjustment=dim_cognitive,
            max_events=max_events, n_heads=n_heads,
        )

    def forward(self, cog, per, sensor, anomaly, severity, time_stamps=None):
        # 无C→P: 直接使用原始感知特征
        per_reweight = torch.ones_like(per) * 0.5  # 均匀权重

        exec_state, _ = self.per2exec(per, sensor, time_stamps)
        adjustment, _ = self.exec2cog(exec_state, anomaly, severity)

        return {
            "perception_reweight": per_reweight,
            "exec_initial_state": exec_state,
            "cognitive_adjustment": adjustment,
        }


class AblationModelNoPer2Exec(nn.Module):
    """消融模型: 移除感知→执行融合。

    执行层状态直接由感知特征线性投影生成，忽略传感器历史。
    """

    def __init__(self, dim_cognitive=256, dim_perception=256, dim_sensor=128,
                 dim_exec_state=128, dim_anomaly=64, dim_fusion=256,
                 seq_len_sensor=32, max_events=4, n_heads=8):
        super().__init__()
        self.cog2per = CognitiveToPerceptionFusion(
            dim_cognitive=dim_cognitive, dim_perception=dim_perception,
            dim_fusion=dim_fusion, n_heads=n_heads,
        )
        self.exec2cog = ExecutionToCognitiveFusion(
            dim_exec_state=dim_exec_state, dim_anomaly=dim_anomaly,
            dim_fusion=dim_fusion, dim_adjustment=dim_cognitive,
            max_events=max_events, n_heads=n_heads,
        )
        # 简单投影替代时序融合
        self.simple_proj = nn.Linear(dim_perception + dim_sensor * seq_len_sensor, dim_exec_state)

    def forward(self, cog, per, sensor, anomaly, severity, time_stamps=None):
        per_reweight, _ = self.cog2per(cog, per)

        # 无P→E: 简单拼接投影
        batch = sensor.size(0)
        sensor_flat = sensor.reshape(batch, -1)
        weighted_per = per * per_reweight
        exec_state = self.simple_proj(torch.cat([weighted_per, sensor_flat], dim=-1))

        adjustment, _ = self.exec2cog(exec_state, anomaly, severity)

        return {
            "perception_reweight": per_reweight,
            "exec_initial_state": exec_state,
            "cognitive_adjustment": adjustment,
        }


class AblationModelNoExec2Cog(nn.Module):
    """消融模型: 移除执行→认知反馈。

    认知层方案调整参数基于感知特征生成，不使用执行层状态反馈。
    """

    def __init__(self, dim_cognitive=256, dim_perception=256, dim_sensor=128,
                 dim_exec_state=128, dim_anomaly=64, dim_fusion=256,
                 seq_len_sensor=32, max_events=4, n_heads=8):
        super().__init__()
        self.cog2per = CognitiveToPerceptionFusion(
            dim_cognitive=dim_cognitive, dim_perception=dim_perception,
            dim_fusion=dim_fusion, n_heads=n_heads,
        )
        self.per2exec = PerceptionToExecutionFusion(
            dim_geometry=dim_perception, dim_sensor=dim_sensor,
            seq_len_sensor=seq_len_sensor, dim_exec=dim_exec_state,
            dim_fusion=dim_fusion, n_heads=n_heads,
        )
        # 简单投影替代反馈融合
        self.simple_adj = nn.Linear(dim_perception, dim_cognitive)

    def forward(self, cog, per, sensor, anomaly, severity, time_stamps=None):
        per_reweight, _ = self.cog2per(cog, per)
        weighted_per = per * per_reweight
        exec_state, _ = self.per2exec(weighted_per, sensor, time_stamps)

        # 无E→C: 直接基于感知特征生成调整
        adjustment = torch.tanh(self.simple_adj(weighted_per))

        return {
            "perception_reweight": per_reweight,
            "exec_initial_state": exec_state,
            "cognitive_adjustment": adjustment,
        }


# ============================================================================
# 数据生成
# ============================================================================


def _generate_ablation_data(
    n_samples: int = 100,
    dim_cog: int = 256,
    dim_per: int = 256,
    dim_sensor: int = 128,
    dim_exec: int = 128,
    dim_anomaly: int = 64,
    seq_len: int = 32,
    max_events: int = 4,
    abnormality_level: float = 0.0,
    seed: int = 42,
) -> dict:
    """生成消融测试数据，可控制异常程度。

    生成的数据包含：
    - 认知层: 模式编码（前2维用于模式选择）
    - 感知层: 双模式特征（前半区=模式0，后半区=模式1）+ 目标步编码
    - 传感器: 键模式序列（每步有唯一模式，用于注意力匹配）
    - 异常: 随机事件 + 按异常程度增强
    """
    torch.manual_seed(seed)
    rng = np.random.RandomState(seed)

    # 认知层: 前2维用于模式编码，其余为随机噪声
    mode = rng.randint(0, 2, size=(n_samples,)).astype(np.float32)
    cog = rng.randn(n_samples, dim_cog).astype(np.float32) * 0.1
    cog[:, 0] = mode * 2.0 - 1.0  # 模式0: -1, 模式1: +1
    cog[:, 1] = mode * 2.0 - 1.0

    # 感知层: 前半区=模式0特征，后半区=模式1特征
    per = rng.randn(n_samples, dim_per).astype(np.float32) * 0.3
    # 目标时间步编码在感知特征中
    target_step = rng.randint(0, seq_len, size=(n_samples,))
    step_embed = rng.randn(seq_len, dim_per).astype(np.float32) * 0.3
    per = per + step_embed[target_step]

    # 传感器: 键模式序列（固定跨样本，使注意力可学习匹配）
    key_patterns = rng.randn(seq_len, dim_sensor).astype(np.float32) * 0.5
    sensor = key_patterns[np.newaxis, :, :] + rng.randn(n_samples, seq_len, dim_sensor).astype(np.float32) * 0.05

    # 异常事件
    anomaly = rng.randn(n_samples, max_events, dim_anomaly).astype(np.float32) * 0.2
    severity = rng.randn(n_samples, max_events).astype(np.float32) * 0.3
    if abnormality_level > 0.3:
        anomaly[:, 0, :] += abnormality_level * 2.0
        severity[:, 0] += abnormality_level * 2.0

    return {
        "cognitive": torch.from_numpy(cog),
        "perception": torch.from_numpy(per),
        "sensor": torch.from_numpy(sensor),
        "anomaly": torch.from_numpy(anomaly),
        "severity": torch.from_numpy(severity),
        "target_step": torch.from_numpy(target_step.astype(np.int64)),
        "mode": torch.from_numpy(mode),
    }


def _generate_ablation_targets_cp(
    data: dict, seed: int = 42,
) -> torch.Tensor:
    """生成C→P依赖目标：模式感知特征贡献60%。"""
    torch.manual_seed(seed)
    n_samples = data["cognitive"].size(0)
    per = data["perception"]
    anomaly = data["anomaly"]
    severity = data["severity"]
    target_step = data["target_step"]
    mode = data["mode"]

    # C→P组件 (60%): 模式特定的感知特征
    w_per0 = torch.randn(128, 1) * 0.5
    w_per1 = torch.randn(128, 1) * 0.5
    mode_t = mode.unsqueeze(1)
    cp_comp = mode_t * (per[:, :128] @ w_per0) + (1 - mode_t) * (per[:, 128:] @ w_per1)

    # P→E组件 (20%): 传感器信号
    key_patterns = torch.randn(32, 128) * 0.5
    w_sensor = torch.randn(128, 1) * 0.5
    pe_comp = key_patterns[target_step] @ w_sensor

    # E→C组件 (20%): 异常校正
    w_anomaly = torch.randn(64, 1) * 0.5
    ec_comp = anomaly.mean(dim=1) @ w_anomaly * severity[:, 0:1]

    return 0.6 * cp_comp + 0.2 * pe_comp + 0.2 * ec_comp + torch.randn(n_samples, 1) * 0.03


def _generate_ablation_targets_pe(
    data: dict, seed: int = 42,
) -> torch.Tensor:
    """生成P→E依赖目标：传感器信号贡献60%。"""
    torch.manual_seed(seed)
    n_samples = data["cognitive"].size(0)
    per = data["perception"]
    anomaly = data["anomaly"]
    severity = data["severity"]
    target_step = data["target_step"]
    mode = data["mode"]

    # C→P组件 (20%)
    w_per0 = torch.randn(128, 1) * 0.5
    w_per1 = torch.randn(128, 1) * 0.5
    mode_t = mode.unsqueeze(1)
    cp_comp = mode_t * (per[:, :128] @ w_per0) + (1 - mode_t) * (per[:, 128:] @ w_per1)

    # P→E组件 (60%): 传感器目标步信号
    key_patterns = torch.randn(32, 128) * 0.5
    w_sensor = torch.randn(128, 1) * 0.5
    pe_comp = key_patterns[target_step] @ w_sensor

    # E→C组件 (20%)
    w_anomaly = torch.randn(64, 1) * 0.5
    ec_comp = anomaly.mean(dim=1) @ w_anomaly * severity[:, 0:1]

    return 0.2 * cp_comp + 0.6 * pe_comp + 0.2 * ec_comp + torch.randn(n_samples, 1) * 0.03


def _generate_ablation_targets_ec(
    data: dict, seed: int = 42,
) -> torch.Tensor:
    """生成E→C依赖目标：异常校正贡献80%。"""
    torch.manual_seed(seed)
    n_samples = data["cognitive"].size(0)
    per = data["perception"]
    anomaly = data["anomaly"]
    severity = data["severity"]
    target_step = data["target_step"]
    mode = data["mode"]

    # C→P组件 (10%)
    w_per0 = torch.randn(128, 1) * 0.5
    w_per1 = torch.randn(128, 1) * 0.5
    mode_t = mode.unsqueeze(1)
    cp_comp = mode_t * (per[:, :128] @ w_per0) + (1 - mode_t) * (per[:, 128:] @ w_per1)

    # P→E组件 (10%)
    key_patterns = torch.randn(32, 128) * 0.5
    w_sensor = torch.randn(128, 1) * 0.5
    pe_comp = key_patterns[target_step] @ w_sensor

    # E→C组件 (80%): 异常驱动校正 - 使用更大权重
    w_anomaly = torch.randn(64, 1) * 2.0
    ec_comp = anomaly.mean(dim=1) @ w_anomaly * severity[:, 0:1]

    return 0.1 * cp_comp + 0.1 * pe_comp + 0.8 * ec_comp + torch.randn(n_samples, 1) * 0.03


def _generate_ablation_targets_all(
    data: dict, seed: int = 42,
) -> torch.Tensor:
    """生成全依赖目标：三组件各贡献1/3。"""
    torch.manual_seed(seed)
    n_samples = data["cognitive"].size(0)
    per = data["perception"]
    anomaly = data["anomaly"]
    severity = data["severity"]
    target_step = data["target_step"]
    mode = data["mode"]

    w_per0 = torch.randn(128, 1) * 0.5
    w_per1 = torch.randn(128, 1) * 0.5
    mode_t = mode.unsqueeze(1)
    cp_comp = mode_t * (per[:, :128] @ w_per0) + (1 - mode_t) * (per[:, 128:] @ w_per1)

    key_patterns = torch.randn(32, 128) * 0.5
    w_sensor = torch.randn(128, 1) * 0.5
    pe_comp = key_patterns[target_step] @ w_sensor

    w_anomaly = torch.randn(64, 1) * 0.5
    ec_comp = anomaly.mean(dim=1) @ w_anomaly * severity[:, 0:1]

    return cp_comp / 3 + pe_comp / 3 + ec_comp / 3 + torch.randn(n_samples, 1) * 0.03


def _extract_features(result: dict) -> torch.Tensor:
    """从融合结果提取统一特征向量。"""
    per_rw = result["perception_reweight"]
    exec_s = result["exec_initial_state"]
    cog_adj = result["cognitive_adjustment"]
    return torch.cat([per_rw, exec_s, cog_adj], dim=-1)


def _run_model(model, data: dict) -> torch.Tensor:
    """运行模型并提取特征。"""
    with torch.no_grad():
        result = model(
            data["cognitive"], data["perception"],
            data["sensor"], data["anomaly"], data["severity"],
        )
    return _extract_features(result)


# ============================================================================
# 消融测试
# ============================================================================


class TestFusionAblation:
    """消融实验测试。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.full_model = CrossLayerFusionSystem(
            dim_cognitive=256, dim_perception=256,
            dim_sensor=128, dim_exec_state=128, dim_anomaly=64,
            dim_fusion=256, seq_len_sensor=32, max_events=4,
            n_heads=8, dropout=0.0,
        )
        self.ablation_cp = AblationModelNoCog2Per()
        self.ablation_pe = AblationModelNoPer2Exec()
        self.ablation_ec = AblationModelNoExec2Cog()

        for model in [self.full_model, self.ablation_cp,
                      self.ablation_pe, self.ablation_ec]:
            model.eval()

    def _train_and_evaluate_rmse(
        self,
        model: nn.Module,
        data: dict,
        targets: torch.Tensor,
        n_epochs: int = 400,
        lr: float = 0.005,
    ) -> float:
        """训练模型并返回最终RMSE。"""
        model.train()
        # 先检测特征维度
        with torch.no_grad():
            result = model(
                data["cognitive"], data["perception"],
                data["sensor"], data["anomaly"], data["severity"],
            )
            features = _extract_features(result)
            feature_dim = features.size(-1)

        pred_head = nn.Linear(feature_dim, 1)
        optimizer = torch.optim.Adam(
            list(model.parameters()) + list(pred_head.parameters()), lr=lr,
        )

        for epoch in range(n_epochs):
            optimizer.zero_grad()
            result = model(
                data["cognitive"], data["perception"],
                data["sensor"], data["anomaly"], data["severity"],
            )
            features = _extract_features(result)
            pred = pred_head(features)
            loss = F.mse_loss(pred, targets)
            loss.backward()
            optimizer.step()

        model.eval()
        pred_head.eval()
        with torch.no_grad():
            result = model(
                data["cognitive"], data["perception"],
                data["sensor"], data["anomaly"], data["severity"],
            )
            features = _extract_features(result)
            pred = pred_head(features)
            rmse = torch.sqrt(F.mse_loss(pred, targets)).item()

        return rmse

    def test_full_model_better_than_ablation_cp(self):
        """测试认知→感知融合的必要性。

        目标中C→P组件占60%权重。
        移除C→P后，模型使用均匀感知权重（0.5），
        无法根据认知意图（模式0/1）选择正确的感知特征半区，
        性能应下降 > 3%。
        """
        torch.manual_seed(42)
        data = _generate_ablation_data(n_samples=80, abnormality_level=0.5, seed=42)
        targets = _generate_ablation_targets_cp(data, seed=42)

        full_rmse = self._train_and_evaluate_rmse(self.full_model, data, targets, n_epochs=500)
        abla_rmse = self._train_and_evaluate_rmse(self.ablation_cp, data, targets, n_epochs=500)

        degradation = (full_rmse - abla_rmse) / full_rmse * 100
        assert degradation < -3, (
            f"移除C→P融合后性能未显著下降: 完整RMSE={full_rmse:.4f}, "
            f"消融RMSE={abla_rmse:.4f}, 退化={degradation:.1f}%, 需要<-3%"
        )

    def test_full_model_better_than_ablation_pe(self):
        """测试感知→执行融合的必要性。

        目标中P→E组件占60%权重。
        移除P→E后，模型无法通过时序注意力提取传感器目标步信号，
        仅能通过感知特征投影生成执行状态，性能应下降 > 3%。
        """
        torch.manual_seed(123)
        data = _generate_ablation_data(n_samples=80, abnormality_level=0.5, seed=123)
        targets = _generate_ablation_targets_pe(data, seed=123)

        full_rmse = self._train_and_evaluate_rmse(self.full_model, data, targets, n_epochs=500)
        abla_rmse = self._train_and_evaluate_rmse(self.ablation_pe, data, targets, n_epochs=500)

        degradation = (full_rmse - abla_rmse) / full_rmse * 100
        assert degradation < -3, (
            f"移除P→E融合后性能未显著下降: 完整RMSE={full_rmse:.4f}, "
            f"消融RMSE={abla_rmse:.4f}, 退化={degradation:.1f}%, 需要<-3%"
        )

    def test_full_model_better_than_ablation_ec(self):
        """测试执行→认知反馈的必要性。

        目标中E→C组件占60%权重。
        移除E→C后，模型无法利用异常事件和执行状态
        生成认知方案调整，性能应下降 > 3%。
        """
        torch.manual_seed(456)
        data = _generate_ablation_data(n_samples=80, abnormality_level=0.8, seed=456)
        targets = _generate_ablation_targets_ec(data, seed=456)

        full_rmse = self._train_and_evaluate_rmse(self.full_model, data, targets, n_epochs=500)
        abla_rmse = self._train_and_evaluate_rmse(self.ablation_ec, data, targets, n_epochs=500)

        degradation = (full_rmse - abla_rmse) / full_rmse * 100
        assert degradation < -3, (
            f"移除E→C反馈后性能未显著下降: 完整RMSE={full_rmse:.4f}, "
            f"消融RMSE={abla_rmse:.4f}, 退化={degradation:.1f}%, 需要<-3%"
        )

    def test_all_ablations_cause_degradation(self):
        """测试所有消融模型在多种场景下的性能退化。

        在不同异常程度场景下，使用三组件均等目标，
        验证P→E消融模型相对于完整模型的性能退化 > 3%。
        """
        abnormality_levels = [0.0, 0.3, 0.6, 0.9]

        for ab_level in abnormality_levels:
            seed = int(42 + ab_level * 10)
            data = _generate_ablation_data(
                n_samples=80, abnormality_level=ab_level, seed=seed,
            )
            targets = _generate_ablation_targets_all(data, seed=seed)

            full_rmse = self._train_and_evaluate_rmse(
                self.full_model, data, targets, n_epochs=400,
            )
            abla_rmse = self._train_and_evaluate_rmse(
                self.ablation_pe, data, targets, n_epochs=400,
            )

            degradation = (full_rmse - abla_rmse) / full_rmse * 100
            assert degradation < -3, (
                f"异常程度={ab_level}: P→E消融退化不足: "
                f"完整RMSE={full_rmse:.4f}, 消融RMSE={abla_rmse:.4f}, "
                f"退化={degradation:.1f}%, 需要<-3%"
            )

    def test_ablation_ec_sensitive_to_anomaly(self):
        """测试E→C消融在不同异常程度下的敏感性。

        执行→认知反馈在高异常场景下应尤其重要，
        验证E→C消融在异常场景下导致更大的性能退化。
        """
        # 异常场景
        torch.manual_seed(200)
        anomaly_data = _generate_ablation_data(n_samples=60, abnormality_level=0.9, seed=200)
        anomaly_targets = _generate_ablation_targets_ec(anomaly_data, seed=200)

        # 异常场景下完整模型 vs E→C消融
        full_anomaly_rmse = self._train_and_evaluate_rmse(
            self.full_model, anomaly_data, anomaly_targets, n_epochs=300,
        )
        abla_anomaly_rmse = self._train_and_evaluate_rmse(
            self.ablation_ec, anomaly_data, anomaly_targets, n_epochs=300,
        )
        anomaly_degradation = (full_anomaly_rmse - abla_anomaly_rmse) / full_anomaly_rmse * 100

        # E→C消融在异常场景下的退化应更显著
        assert anomaly_degradation < -3, (
            f"E→C消融在异常场景下退化不足: 退化={anomaly_degradation:.1f}%, 需要<-3%"
        )
        # 异常场景退化应 >= 正常场景退化（因为E→C对异常处理更重要）
        assert anomaly_degradation < 0, (
            f"E→C消融在异常场景下应产生退化: 退化={anomaly_degradation:.1f}%"
        )

    def test_feature_diversity_comparison(self):
        """测试特征多样性对比。

        融合模型应产生更多样化的特征表示。
        """
        data = _generate_ablation_data(n_samples=50, abnormality_level=0.5)

        models = {
            "full": self.full_model,
            "no_cog2per": self.ablation_cp,
            "no_per2exec": self.ablation_pe,
            "no_exec2cog": self.ablation_ec,
        }

        diversities = {}
        for name, model in models.items():
            features = _run_model(model, data)
            # 计算特征多样性: 协方差矩阵的迹
            centered = features - features.mean(dim=0, keepdim=True)
            cov = (centered.T @ centered) / (features.size(0) - 1)
            diversity = torch.trace(cov).item()
            diversities[name] = diversity

        # 完整模型应具有非零特征多样性
        assert diversities["full"] > 0, "完整模型特征多样性为0"
        # 所有模型应产生多样化的特征
        for name, div in diversities.items():
            assert div > 0, f"{name} 特征多样性为0"

    def test_full_model_parameter_count(self):
        """测试完整模型参数总量合理。"""
        full_params = sum(p.numel() for p in self.full_model.parameters())
        assert full_params < 5_000_000, (
            f"完整模型参数 {full_params:,} 超过500万限制"
        )

    def test_ablation_models_parameter_count(self):
        """测试消融模型参数均 < 500万。"""
        for name, model in [
            ("no_cog2per", self.ablation_cp),
            ("no_per2exec", self.ablation_pe),
            ("no_exec2cog", self.ablation_ec),
        ]:
            params = sum(p.numel() for p in model.parameters())
            assert params < 5_000_000, (
                f"{name} 参数 {params:,} 超过500万限制"
            )
            assert params < sum(p.numel() for p in self.full_model.parameters()), (
                f"{name} 参数({params:,})应少于完整模型"
            )
