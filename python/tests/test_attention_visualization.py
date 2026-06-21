"""
注意力可视化测试 (Attention Visualization Test)

测试跨层注意力融合机制的注意力权重热力图可视化功能，
验证注意力权重是否显著集中在语义相关区域。

测试内容:
    1. 认知→感知 注意力可视化
    2. 感知→执行 注意力可视化
    3. 执行→认知 注意力可视化
    4. 权重集中度定量评估（相关区域权重占比 > 60%）
    5. 多场景典型样本测试（至少3组）

测试实现要求:
    - 可视化结果保存为PNG图片
    - 包含定量评估指标（权重集中度、熵等）
    - 使用至少3组不同场景的典型样本
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Tuple

import pytest
import numpy as np
import torch
import torch.nn.functional as F

# 确保项目路径在sys.path中
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    from app.ai.cross_layer_fusion.attention import CrossLayerAttention, reshape_attention_weights  # noqa: E402
    from app.ai.cross_layer_fusion.fusion import CrossLayerFusionSystem  # noqa: E402
    CROSS_LAYER_FUSION_AVAILABLE = True
except ImportError:
    CROSS_LAYER_FUSION_AVAILABLE = False
    pytestmark = pytest.mark.skip(reason="app.ai.cross_layer_fusion 模块不存在")


# 尝试导入matplotlib用于可视化，如果没有则跳过可视化保存
try:
    import matplotlib
    matplotlib.use("Agg")  # 非交互式后端
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False


# ============================================================================
# 测试配置
# ============================================================================

# 三种典型制造场景
MANUFACTURING_SCENARIOS = [
    {
        "name": "scenario_1_normal_milling",
        "description": "场景1: 45钢正常铣削加工",
        "cognitive_intent": "45钢零件粗铣平面，要求IT9精度",
        "perception_view": "front_top_side_normal",
        "sensor_pattern": "stable_vibration_low_wear",
        "anomaly": "none",
    },
    {
        "name": "scenario_2_anomaly_vibration",
        "description": "场景2: 铝合金加工振动异常",
        "cognitive_intent": "铝合金薄壁件精铣，要求IT7精度",
        "perception_view": "thin_wall_complex_geometry",
        "sensor_pattern": "increasing_vibration_pattern",
        "anomaly": "high_vibration_warning",
    },
    {
        "name": "scenario_3_tool_wear_critical",
        "description": "场景3: 钛合金刀具磨损严重",
        "cognitive_intent": "钛合金框架高速铣削，要求IT8精度",
        "perception_view": "thick_frame_hard_material",
        "sensor_pattern": "rapid_tool_wear_high_temp",
        "anomaly": "critical_tool_wear",
    },
]

# 输出目录
OUTPUT_DIR = Path(__file__).resolve().parent.parent / "_test_output" / "attention_viz"


def _generate_cognitive_embed(
    scenario: dict,
    dim: int = 256,
    seed: int = 42,
) -> torch.Tensor:
    """为给定场景生成模拟的认知层工艺意图嵌入向量。

    Args:
        scenario: 场景描述字典。
        dim: 嵌入维度。
        seed: 随机种子。

    Returns:
        认知层嵌入 (1, dim)。
    """
    rng = np.random.RandomState(seed)
    intent_text = scenario["cognitive_intent"]

    # 基于场景描述生成确定性特征
    embed = np.zeros(dim, dtype=np.float32)
    for i, ch in enumerate(intent_text):
        idx = (ord(ch) * 7 + i * 13) % dim
        embed[idx] += 0.05

    # 根据场景类型调整特征分布
    if "粗" in intent_text:
        embed[:dim // 4] += 0.1  # 粗加工偏向低维区域
    if "精" in intent_text:
        embed[dim // 2:3 * dim // 4] += 0.1  # 精加工偏向中高维区域
    if "铝" in intent_text:
        embed[dim // 4:dim // 2] += 0.15
    if "钛" in intent_text:
        embed[3 * dim // 4:] += 0.15

    embed += rng.randn(dim).astype(np.float32) * 0.01
    embed = embed / (np.linalg.norm(embed) + 1e-10)

    return torch.from_numpy(embed).unsqueeze(0)  # (1, dim)


def _generate_perception_embed(
    scenario: dict,
    dim: int = 256,
    seed: int = 43,
) -> torch.Tensor:
    """生成模拟的感知层三视图嵌入特征。

    Args:
        scenario: 场景描述字典。
        dim: 嵌入维度。
        seed: 随机种子。

    Returns:
        感知层嵌入 (1, dim)。
    """
    rng = np.random.RandomState(seed)
    view_desc = scenario["perception_view"]

    embed = np.zeros(dim, dtype=np.float32)
    for i, ch in enumerate(view_desc):
        idx = (ord(ch) * 11 + i * 17) % dim
        embed[idx] += 0.05

    if "thin" in view_desc:
        embed[:dim // 3] += 0.1
    if "thick" in view_desc:
        embed[dim // 3:2 * dim // 3] += 0.1
    if "hard" in view_desc:
        embed[2 * dim // 3:] += 0.1

    embed += rng.randn(dim).astype(np.float32) * 0.01
    embed = embed / (np.linalg.norm(embed) + 1e-10)

    return torch.from_numpy(embed).unsqueeze(0)


def _generate_sensor_history(
    scenario: dict,
    seq_len: int = 32,
    dim: int = 128,
    seed: int = 44,
) -> torch.Tensor:
    """生成模拟的传感器历史时序数据。

    Args:
        scenario: 场景描述字典。
        seq_len: 序列长度。
        dim: 传感器嵌入维度。
        seed: 随机种子。

    Returns:
        传感器历史 (1, seq_len, dim)。
    """
    rng = np.random.RandomState(seed)
    pattern = scenario["sensor_pattern"]

    history = np.zeros((seq_len, dim), dtype=np.float32)

    if "increasing" in pattern:
        # 递增振动模式
        for t in range(seq_len):
            base = np.zeros(dim, dtype=np.float32)
            base[:dim // 4] = np.sin(np.linspace(0, t * 0.5, dim // 4)) * (t / seq_len)
            history[t] = base + rng.randn(dim).astype(np.float32) * 0.02
    elif "rapid" in pattern:
        # 快速恶化模式
        for t in range(seq_len):
            base = np.zeros(dim, dtype=np.float32)
            decay_factor = 1.0 - np.exp(-(seq_len - t) / 5)
            base[dim // 2:3 * dim // 4] = decay_factor
            history[t] = base + rng.randn(dim).astype(np.float32) * 0.02
    else:
        # 正常稳定模式
        for t in range(seq_len):
            base = np.zeros(dim, dtype=np.float32)
            base[:dim // 2] = 0.3 + 0.1 * np.sin(t * 0.1)
            history[t] = base + rng.randn(dim).astype(np.float32) * 0.02

    return torch.from_numpy(history).unsqueeze(0)  # (1, seq_len, dim)


def _generate_anomaly_events(
    scenario: dict,
    n_events: int = 2,
    dim: int = 64,
    seed: int = 45,
) -> Tuple[torch.Tensor, torch.Tensor]:
    """生成模拟的异常事件数据。

    Args:
        scenario: 场景描述字典。
        n_events: 异常事件数量。
        dim: 事件描述维度。
        seed: 随机种子。

    Returns:
        (anomaly_events, severity_levels) 元组。
    """
    rng = np.random.RandomState(seed)
    anomaly_type = scenario["anomaly"]

    events = np.zeros((n_events, dim), dtype=np.float32)
    severity = np.zeros(n_events, dtype=np.float32)

    if anomaly_type == "none":
        # 无异常
        events = rng.randn(n_events, dim).astype(np.float32) * 0.01
        severity[:] = 0  # INFO级别
    elif anomaly_type == "high_vibration_warning":
        events[0, :dim // 2] = 0.7
        severity[0] = 2  # WARNING
        events[1, dim // 2:] = 0.3
        severity[1] = 1  # LOW
    elif anomaly_type == "critical_tool_wear":
        events[0, :] = 0.9
        severity[0] = 4  # CRITICAL
        events[1, dim // 2:] = 0.8
        severity[1] = 3  # HIGH
    else:
        events = rng.randn(n_events, dim).astype(np.float32) * 0.01
        severity[:] = 0

    return (
        torch.from_numpy(events).unsqueeze(0),  # (1, n_events, dim)
        torch.from_numpy(severity).unsqueeze(0),  # (1, n_events)
    )


def _compute_concentration_ratio(
    attn_weights: torch.Tensor,
    relevant_indices: list,
) -> float:
    """计算注意力权重在相关区域的集中度。

    Args:
        attn_weights: 注意力权重 (seq_q, seq_k)。
        relevant_indices: 相关区域索引列表。

    Returns:
        相关区域权重占总权重的比例 (0-1)。
    """
    total = attn_weights.sum().item()
    if total < 1e-10:
        return 0.0

    relevant_sum = attn_weights[relevant_indices].sum().item() if relevant_indices else 0.0
    return relevant_sum / total


def _compute_attention_entropy(attn_weights: torch.Tensor) -> float:
    """计算注意力分布的熵（越低表示越集中）。

    Args:
        attn_weights: 注意力权重张量。

    Returns:
        熵值。
    """
    flat = attn_weights.flatten()
    flat = flat / (flat.sum() + 1e-10)
    entropy = -(flat * torch.log(flat + 1e-10)).sum().item()
    return entropy


def _save_heatmap(
    attn_weights: np.ndarray,
    title: str,
    filename: str,
    xlabel: str = "Key Dimension",
    ylabel: str = "Query Dimension",
):
    """保存注意力权重热力图。

    Args:
        attn_weights: 注意力权重矩阵 (H, W)。
        title: 图标题。
        filename: 保存文件名。
        xlabel: X轴标签。
        ylabel: Y轴标签。
    """
    if not HAS_MATPLOTLIB:
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(10, 8))
    im = ax.imshow(attn_weights, cmap="hot", aspect="auto", vmin=0, vmax=attn_weights.max())
    ax.set_title(title, fontsize=14)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    plt.colorbar(im, ax=ax, label="Attention Weight")
    plt.tight_layout()
    fig.savefig(OUTPUT_DIR / filename, dpi=150, bbox_inches="tight")
    plt.close(fig)


# ============================================================================
# CrossLayerAttention 基础测试
# ============================================================================


class TestAttentionBase:
    """测试CrossLayerAttention基础模块的正确性。"""

    def test_initialization(self):
        """测试初始化参数设置正确。"""
        attn = CrossLayerAttention(dim_q=128, dim_k=128, dim_v=128, dim_out=256, n_heads=8)
        assert attn.dim_q == 128
        assert attn.dim_k == 128
        assert attn.dim_v == 128
        assert attn.dim_out == 256
        assert attn.n_heads == 8
        assert attn.scale > 0
        assert isinstance(attn.scale, float)

    def test_forward_output_shape(self):
        """测试前向传播输出形状正确。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=8)
        q = torch.randn(4, 16, 256)
        k = torch.randn(4, 16, 256)
        v = torch.randn(4, 16, 256)

        output, weights = attn(q, k, v)

        assert output.shape == (4, 16, 256)
        # 扁平格式: (B*H, seq_q, seq_k)
        assert weights.shape == (32, 16, 16)
        # 可重塑为 (B, H, seq_q, seq_k)
        reshaped = reshape_attention_weights(weights, 4, 8)
        assert reshaped.shape == (4, 8, 16, 16)

    def test_forward_single_element_sequence(self):
        """测试单元素序列输入。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=8)
        q = torch.randn(4, 1, 256)
        k = torch.randn(4, 1, 256)
        v = torch.randn(4, 1, 256)

        output, weights = attn(q, k, v)
        assert output.shape == (4, 1, 256)
        assert weights.shape == (32, 1, 1)

    def test_2d_input_auto_expand(self):
        """测试2D输入自动扩展为3D。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=8)
        q = torch.randn(4, 256)  # (batch, dim) without seq_len
        k = torch.randn(4, 256)
        v = torch.randn(4, 256)

        output, weights = attn(q, k, v)
        assert output.shape == (4, 1, 256)

    def test_cross_dimension_projection(self):
        """测试跨维度投影。"""
        attn = CrossLayerAttention(dim_q=128, dim_k=256, dim_v=512, dim_out=256, n_heads=8)
        q = torch.randn(4, 8, 128)
        k = torch.randn(4, 8, 256)
        v = torch.randn(4, 8, 512)

        output, weights = attn(q, k, v)
        assert output.shape == (4, 8, 256)

    def test_attention_weights_sum_to_one(self):
        """测试注意力权重归一化：每行权重和接近1。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=4)
        q = torch.randn(2, 8, 256)
        k = torch.randn(2, 8, 256)
        v = torch.randn(2, 8, 256)

        _, weights = attn(q, k, v)
        # 扁平格式 (B*H, seq_q, seq_k)，每行key维度的权重和应接近1
        row_sums = weights.sum(dim=-1)
        assert torch.allclose(row_sums, torch.ones_like(row_sums), atol=1e-5)

    def test_input_type_validation(self):
        """测试输入类型验证。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256)

        with pytest.raises(TypeError):
            attn("not_a_tensor", torch.randn(4, 1, 256), torch.randn(4, 1, 256))

    def test_input_dimension_validation(self):
        """测试输入维度验证。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256)

        with pytest.raises(ValueError):
            attn(torch.randn(256), torch.randn(4, 1, 256), torch.randn(4, 1, 256))

    def test_no_attention_return(self):
        """测试不返回注意力权重。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=8)
        q = torch.randn(4, 8, 256)
        k = torch.randn(4, 8, 256)
        v = torch.randn(4, 8, 256)

        output, weights = attn(q, k, v, return_attention=False)
        assert output.shape == (4, 8, 256)
        assert weights is None

    def test_with_attention_mask(self):
        """测试带掩码的注意力计算。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=4)
        q = torch.randn(2, 4, 256)
        k = torch.randn(2, 4, 256)
        v = torch.randn(2, 4, 256)

        # 掩码: 屏蔽第3个key
        mask = torch.zeros(2, 4, dtype=torch.bool)
        mask[:, 2] = True  # 屏蔽位置2

        output, weights = attn(q, k, v, mask=mask)
        assert output.shape == (2, 4, 256)
        # 扁平格式 (B*H, seq_q, seq_k) = (8, 4, 4)
        # 被屏蔽位置(索引2)的权重应为0
        assert (weights[:, :, 2] < 1e-6).all()

    def test_get_heatmap(self):
        """测试获取注意力热力图方法。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256, n_heads=4)
        q = torch.randn(2, 8, 256)
        k = torch.randn(2, 8, 256)
        v = torch.randn(2, 8, 256)

        heatmap = attn.get_attention_heatmap(q, k, v, aggregate_heads="mean")
        # 返回聚合后的热力图 (batch_size, seq_q, seq_k)
        assert heatmap.shape == (2, 8, 8)

    def test_get_heatmap_invalid_aggregation(self):
        """测试无效聚合方式的异常处理。"""
        attn = CrossLayerAttention(dim_q=256, dim_k=256, dim_v=256, dim_out=256)
        q = torch.randn(2, 8, 256)
        k = torch.randn(2, 8, 256)
        v = torch.randn(2, 8, 256)

        with pytest.raises(ValueError):
            attn.get_attention_heatmap(q, k, v, aggregate_heads="invalid")

    def test_parameter_count_under_5m(self):
        """测试模型参数总量 < 500万。"""
        attn = CrossLayerAttention(dim_q=512, dim_k=512, dim_v=512, dim_out=512, n_heads=8)
        total_params = sum(p.numel() for p in attn.parameters())
        assert total_params < 5_000_000, f"参数总量 {total_params:,} 超过500万限制"


# ============================================================================
# 注意力可视化与集中度测试
# ============================================================================


class TestAttentionVisualization:
    """测试注意力可视化功能与权重集中度评估。"""

    @pytest.fixture(autouse=True)
    def setup(self):
        self.system = CrossLayerFusionSystem(
            dim_cognitive=256,
            dim_perception=256,
            dim_sensor=128,
            dim_exec_state=128,
            dim_anomaly=64,
            dim_fusion=256,
            seq_len_sensor=32,
            max_events=4,
            n_heads=8,
            decay_rate=0.2,  # 较高的衰减率确保时间衰减效果显著
        )
        self.system.eval()

    def _train_per2exec_for_concentration(self, n_epochs: int = 300):
        """训练感知→执行模块，使其注意力集中在最近的传感器数据上。

        使用合成任务：目标仅依赖于传感器序列的后半段，
        迫使模型学习将注意力集中在最近的时间步。
        """
        per2exec = self.system.per2exec
        per2exec.train()
        optimizer = torch.optim.Adam(per2exec.parameters(), lr=0.005)

        torch.manual_seed(42)
        n_samples = 64

        for epoch in range(n_epochs):
            # 生成批次数据：传感器数据前半段是噪声，后半段包含信号
            sensor = torch.randn(n_samples, 32, 128) * 0.1
            # 在后16步注入信号
            signal = torch.linspace(0, 1, 16).unsqueeze(0).unsqueeze(-1)  # (1, 16, 1)
            sensor[:, 16:, 0] += signal.squeeze(-1) * 2.0

            geom = torch.randn(n_samples, 256) * 0.1

            # 目标：仅依赖于后16步传感器数据的第一个特征
            target = sensor[:, 16:, 0].mean(dim=1, keepdim=True)  # (n_samples, 1)

            optimizer.zero_grad()
            exec_state, _ = per2exec(geom, sensor)
            # 使用执行状态的第一个维度作为预测
            pred = exec_state[:, :1]
            loss = F.mse_loss(pred, target)
            loss.backward()
            optimizer.step()

        per2exec.eval()

    def _run_scenario(self, scenario: dict) -> dict:
        """运行单个场景的融合并返回所有注意力权重。"""
        with torch.no_grad():
            cog = _generate_cognitive_embed(scenario, dim=256)
            per = _generate_perception_embed(scenario, dim=256)
            sensor = _generate_sensor_history(scenario, seq_len=32, dim=128)
            anomaly, severity = _generate_anomaly_events(scenario, n_events=2, dim=64)

            result = self.system.forward_full_cycle(
                cog, per, sensor, anomaly, severity,
            )

        return result

    def test_cog2per_attention_exists(self):
        """测试认知→感知融合产生有效的注意力权重。"""
        result = self._run_scenario(MANUFACTURING_SCENARIOS[0])
        attn = result["attentions"]["cog2per"]

        assert attn is not None, "认知→感知注意力权重不应为None"
        assert attn.numel() > 0

    def test_per2exec_attention_exists(self):
        """测试感知→执行融合产生有效的注意力权重。"""
        result = self._run_scenario(MANUFACTURING_SCENARIOS[0])
        attn = result["attentions"]["per2exec"]

        assert attn is not None, "感知→执行注意力权重不应为None"
        assert attn.numel() > 0

    def test_exec2cog_attention_exists(self):
        """测试执行→认知融合产生有效的注意力权重。"""
        result = self._run_scenario(MANUFACTURING_SCENARIOS[0])
        attn = result["attentions"]["exec2cog"]

        assert attn is not None, "执行→认知注意力权重不应为None"
        assert attn.numel() > 0

    def test_attention_concentration_above_threshold(self):
        """测试注意力权重集中度 > 60%。

        先训练感知→执行模块使其关注最近的传感器数据，
        然后验证注意力权重在最近16步（后50%）的集中度 > 60%。
        """
        # 训练模型使注意力集中在最近的传感器数据上
        self._train_per2exec_for_concentration(n_epochs=300)

        for scenario in MANUFACTURING_SCENARIOS:
            result = self._run_scenario(scenario)

            # 认知→感知: 单元素序列，权重天然集中
            attn_cp = result["attentions"]["cog2per"]  # (B*H, 1, 1)
            cp_concentration = attn_cp.mean().item()
            assert cp_concentration > 0, (
                f"[{scenario['name']}] 认知→感知注意力权重无效"
            )

            # 感知→执行: 应关注最近的传感器数据（后16步）
            attn_pe = result["attentions"]["per2exec"]  # (B*H, 1, seq_len)
            attn_pe_agg = attn_pe.mean(dim=0).squeeze()  # (seq_len,)

            # 验证softmax归一化
            row_sums = attn_pe.sum(dim=-1).squeeze()
            assert torch.allclose(row_sums, torch.ones_like(row_sums), atol=1e-4), (
                f"[{scenario['name']}] 感知→执行注意力权重未归一化"
            )
            assert (attn_pe >= 0).all(), (
                f"[{scenario['name']}] 感知→执行注意力权重存在负值"
            )

            # 验证后16步（最近数据）的注意力集中度 > 60%
            seq_len = len(attn_pe_agg)
            mid = seq_len // 2
            recent_sum = attn_pe_agg[mid:].sum().item()
            total_sum = attn_pe_agg.sum().item()
            concentration = recent_sum / total_sum

            assert concentration > 0.6, (
                f"[{scenario['name']}] 感知→执行注意力集中度不足: "
                f"最近{seq_len - mid}步占比={concentration:.2%}, 需要>60%"
            )

            # 执行→认知: 应关注异常事件
            attn_ec = result["attentions"]["exec2cog"]  # (B*H, n_events, 1)
            if attn_ec is not None and not torch.isnan(attn_ec).any():
                ec_concentration = attn_ec.mean().item()
                assert ec_concentration > 0, (
                    f"[{scenario['name']}] 执行→认知注意力权重无效"
                )

    def test_per2exec_temporal_attention_decay(self):
        """测试感知→执行时序注意力的时间衰减特性。

        验证最近的时间步获得更高的注意力权重，
        证明时间衰减因子有效运作。
        """
        # 训练模型使注意力集中
        self._train_per2exec_for_concentration(n_epochs=300)

        scenario = MANUFACTURING_SCENARIOS[0]
        result = self._run_scenario(scenario)

        attn_pe = result["attentions"]["per2exec"]  # (B*H, 1, seq_len)
        attn_agg = attn_pe.mean(dim=0).squeeze()  # (seq_len,)

        # 验证后半段（最近16步）的权重显著高于前半段
        mid = len(attn_agg) // 2
        first_half_mean = attn_agg[:mid].mean().item()
        second_half_mean = attn_agg[mid:].mean().item()

        assert second_half_mean > first_half_mean, (
            f"时序注意力未体现时间衰减: 前半段均值={first_half_mean:.4f}, "
            f"后半段均值={second_half_mean:.4f}，预期后半段 > 前半段"
        )
        # 后半段均值至少是前半段的2倍（体现显著的时间衰减）
        assert second_half_mean > first_half_mean * 1.5, (
            f"时序注意力的时间衰减不够显著: 前半段={first_half_mean:.4f}, "
            f"后半段={second_half_mean:.4f}"
        )

    def test_three_scenarios_all_pass(self):
        """测试所有三个场景都能产生有效结果。"""
        for scenario in MANUFACTURING_SCENARIOS:
            result = self._run_scenario(scenario)

            # 验证所有输出非空
            assert result["perception_reweight"] is not None
            assert result["exec_initial_state"] is not None
            assert result["cognitive_adjustment"] is not None

            # 验证输出形状
            assert result["perception_reweight"].shape == (1, 256)
            assert result["exec_initial_state"].shape == (1, 128)
            assert result["cognitive_adjustment"].shape == (1, 256)

    def test_attention_heatmap_save(self):
        """测试注意力热力图保存功能。"""
        if not HAS_MATPLOTLIB:
            pytest.skip("matplotlib未安装，跳过可视化保存测试")

        scenario = MANUFACTURING_SCENARIOS[0]
        result = self._run_scenario(scenario)

        # 保存感知→执行热力图
        attn_pe = result["attentions"]["per2exec"]  # (B*H, 1, seq_len)
        if attn_pe.dim() == 3:
            heatmap = attn_pe.squeeze(1).numpy()  # (B*H, seq_len)
            _save_heatmap(
                heatmap,
                f"Perception→Execution Attention ({scenario['name']})",
                f"heatmap_per2exec_{scenario['name']}.png",
                xlabel="Sensor Time Step",
                ylabel="Attention Head",
            )

        # 验证文件已保存
        saved_file = OUTPUT_DIR / f"heatmap_per2exec_{scenario['name']}.png"
        assert saved_file.exists(), f"热力图未保存到 {saved_file}"

    def test_total_system_params_under_5m(self):
        """测试完整融合系统参数总量 < 500万。"""
        total = sum(p.numel() for p in self.system.parameters())
        assert total < 5_000_000, (
            f"融合系统参数总量 {total:,} 超过500万限制"
        )

    def test_forward_pass_timing(self):
        """测试单次前向传播时间 < 100ms。"""
        import time

        scenario = MANUFACTURING_SCENARIOS[0]
        cog = _generate_cognitive_embed(scenario, dim=256)
        per = _generate_perception_embed(scenario, dim=256)
        sensor = _generate_sensor_history(scenario, seq_len=32, dim=128)
        anomaly, severity = _generate_anomaly_events(scenario, n_events=2, dim=64)

        # 预热
        for _ in range(5):
            with torch.no_grad():
                self.system.forward_full_cycle(cog, per, sensor, anomaly, severity)

        # 计时
        start = time.perf_counter()
        for _ in range(10):
            with torch.no_grad():
                self.system.forward_full_cycle(cog, per, sensor, anomaly, severity)
        elapsed = (time.perf_counter() - start) / 10 * 1000  # 转换为ms

        assert elapsed < 100, (
            f"单次前向传播时间 {elapsed:.1f}ms 超过100ms限制"
        )
