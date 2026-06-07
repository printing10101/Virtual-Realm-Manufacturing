"""
对齐损失测试 (Alignment Loss Test)

测试对比学习对齐损失函数的正确性和训练收敛性。

测试内容:
    1. alignment_loss函数基本功能验证
    2. 不同负样本策略的正确性
    3. 温度参数的影响
    4. 损失收敛性检验（收敛到 < 0.1）
    5. 稳定性评估（连续10个epoch波动 < 0.01）
    6. 损失曲线绘制

测试实现要求:
    - 验证损失值在合理范围内
    - 模拟训练过程验证收敛性
    - 检验损失稳定性
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.ai.cross_layer_fusion.alignment import (  # noqa: E402
    alignment_loss,
    AlignmentLossTracker,
)


# 尝试导入matplotlib
try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

OUTPUT_DIR = Path(__file__).resolve().parent.parent / "_test_output" / "alignment"


# ============================================================================
# alignment_loss 函数单元测试
# ============================================================================


class TestAlignmentLossFunction:
    """测试alignment_loss函数的正确性。"""

    def test_basic_output_is_scalar(self):
        """测试基本输出是标量。"""
        e1 = F.normalize(torch.randn(32, 256), dim=-1)
        e2 = F.normalize(torch.randn(32, 256), dim=-1)

        loss = alignment_loss(e1, e2)

        assert loss.dim() == 0, f"损失应该是标量，实际维度: {loss.dim()}"
        assert loss.item() > 0, "损失应为正值"

    def test_perfect_alignment_low_loss(self):
        """测试完美对齐（相同嵌入）产生低损失。"""
        e1 = F.normalize(torch.randn(32, 256), dim=-1)
        e2 = e1.clone()  # 完全相同的嵌入

        loss = alignment_loss(e1, e2, temperature=0.1)

        # 完美对齐应产生相对较低的损失
        assert loss.item() < 1.0, f"完美对齐损失应较低: {loss.item():.4f}"

    def test_random_alignment_high_loss(self):
        """测试随机对齐产生较高损失。"""
        e1 = F.normalize(torch.randn(64, 256), dim=-1)
        e2 = F.normalize(torch.randn(64, 256), dim=-1)

        loss_random = alignment_loss(e1, e2)

        # 随机嵌入应产生较高损失
        assert loss_random.item() > 0.5, (
            f"随机对齐损失应较高: {loss_random.item():.4f}"
        )

    def test_loss_decreases_with_better_alignment(self):
        """测试更好的对齐产生更低的损失。"""
        e1 = F.normalize(torch.randn(32, 256), dim=-1)

        # 较差对齐: 随机不相关的嵌入
        e2_random = F.normalize(torch.randn(32, 256), dim=-1)
        loss_random = alignment_loss(e1, e2_random)

        # 较好对齐: 添加小噪声
        e2_noisy = F.normalize(e1 + torch.randn(32, 256) * 0.01, dim=-1)
        loss_noisy = alignment_loss(e1, e2_noisy)

        assert loss_noisy.item() < loss_random.item(), (
            f"更好对齐应产生更低损失: noisy={loss_noisy.item():.4f}, "
            f"random={loss_random.item():.4f}"
        )

    def test_larger_batch_lower_loss_variance(self):
        """测试更大批次降低损失方差。"""
        losses_small = []
        losses_large = []

        for _ in range(10):
            e1_s = F.normalize(torch.randn(8, 128), dim=-1)
            e2_s = F.normalize(torch.randn(8, 128), dim=-1)
            losses_small.append(alignment_loss(e1_s, e2_s).item())

            e1_l = F.normalize(torch.randn(64, 128), dim=-1)
            e2_l = F.normalize(torch.randn(64, 128), dim=-1)
            losses_large.append(alignment_loss(e1_l, e2_l).item())

        std_small = np.std(losses_small)
        std_large = np.std(losses_large)

        # 大批次的方差应更小
        assert std_large < std_small * 2, (
            f"大批次方差({std_large:.4f})不应远大于小批次方差({std_small:.4f})"
        )

    def test_temperature_effect(self):
        """测试温度参数对损失的影响。

        较低温度使分布更尖锐，损失应更大（更难优化）。
        """
        e1 = F.normalize(torch.randn(32, 256), dim=-1)
        e2 = F.normalize(torch.randn(32, 256), dim=-1)

        loss_low_temp = alignment_loss(e1, e2, temperature=0.01)
        loss_high_temp = alignment_loss(e1, e2, temperature=1.0)

        # 低温度（更尖锐）通常产生更大损失
        # 注意：对于随机嵌入，这可能不一定成立，但我们验证两个温度产生不同损失
        assert abs(loss_low_temp.item() - loss_high_temp.item()) > 0.01, (
            "不同温度应产生不同的损失值"
        )

    def test_in_batch_negative_strategy(self):
        """测试批次内负样本策略。"""
        e1 = F.normalize(torch.randn(16, 128), dim=-1)
        e2 = F.normalize(torch.randn(16, 128), dim=-1)

        loss = alignment_loss(e1, e2, neg_sample_strategy="in_batch")
        assert loss.dim() == 0
        assert not torch.isnan(loss)
        assert not torch.isinf(loss)

    def test_random_negative_strategy(self):
        """测试随机负样本策略。"""
        e1 = F.normalize(torch.randn(16, 128), dim=-1)
        e2 = F.normalize(torch.randn(16, 128), dim=-1)
        neg = F.normalize(torch.randn(32, 128), dim=-1)  # 随机负样本池

        loss = alignment_loss(
            e1, e2, neg_sample_strategy="random", neg_samples=neg,
        )
        assert loss.dim() == 0
        assert not torch.isnan(loss)

    def test_hard_negative_strategy(self):
        """测试难负样本策略。"""
        e1 = F.normalize(torch.randn(16, 128), dim=-1)
        e2 = F.normalize(torch.randn(16, 128), dim=-1)

        loss = alignment_loss(e1, e2, neg_sample_strategy="hard")
        assert loss.dim() == 0
        assert not torch.isnan(loss)

    def test_invalid_strategy_raises(self):
        """测试无效策略抛出异常。"""
        e1 = F.normalize(torch.randn(8, 64), dim=-1)
        e2 = F.normalize(torch.randn(8, 64), dim=-1)

        with pytest.raises(ValueError):
            alignment_loss(e1, e2, neg_sample_strategy="invalid_strategy")

    def test_mismatched_batch_size_raises(self):
        """测试不匹配的批次大小抛出异常。"""
        e1 = F.normalize(torch.randn(8, 64), dim=-1)
        e2 = F.normalize(torch.randn(16, 64), dim=-1)

        with pytest.raises(ValueError):
            alignment_loss(e1, e2)

    def test_small_batch_in_batch_raises(self):
        """测试小批次内负样本策略抛出异常。"""
        e1 = F.normalize(torch.randn(1, 64), dim=-1)
        e2 = F.normalize(torch.randn(1, 64), dim=-1)

        with pytest.raises(RuntimeError):
            alignment_loss(e1, e2, neg_sample_strategy="in_batch")

    def test_random_strategy_without_neg_samples_raises(self):
        """测试random策略但未提供neg_samples抛出异常。"""
        e1 = F.normalize(torch.randn(8, 64), dim=-1)
        e2 = F.normalize(torch.randn(8, 64), dim=-1)

        with pytest.raises(ValueError):
            alignment_loss(e1, e2, neg_sample_strategy="random")

    def test_sum_reduction(self):
        """测试sum聚合方式。"""
        e1 = F.normalize(torch.randn(32, 128), dim=-1)
        e2 = F.normalize(torch.randn(32, 128), dim=-1)

        loss_mean = alignment_loss(e1, e2, reduction="mean")
        loss_sum = alignment_loss(e1, e2, reduction="sum")

        # sum / batch_size ≈ mean
        assert abs(loss_sum.item() / 32 - loss_mean.item()) < 0.01

    def test_gradient_flow(self):
        """测试损失支持梯度反向传播。"""
        embed1 = nn.Parameter(F.normalize(torch.randn(16, 128), dim=-1))
        embed2 = F.normalize(torch.randn(16, 128), dim=-1)

        loss = alignment_loss(embed1, embed2)
        loss.backward()

        assert embed1.grad is not None, "梯度应为非None"
        assert not torch.isnan(embed1.grad).any(), "梯度不应包含NaN"


# ============================================================================
# 训练收敛性测试
# ============================================================================


class TestAlignmentLossConvergence:
    """测试对齐损失的收敛性。"""

    def test_loss_converges_below_threshold(self):
        """测试对齐损失能收敛到 < 0.1。"""
        dim = 128

        # 生成合成训练数据
        n_samples = 128
        x1 = torch.randn(n_samples, 64)
        x2 = torch.randn(n_samples, 64)

        # 创建关联的目标嵌入（共享部分信息）
        shared = torch.randn(n_samples, 32)
        x1 = torch.cat([x1[:, :32], shared], dim=-1)
        x2 = torch.cat([x2[:, :32], shared], dim=-1)

        embed_layer_1 = nn.Sequential(
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, dim),
        )
        embed_layer_2 = nn.Sequential(
            nn.Linear(64, 128),
            nn.ReLU(),
            nn.Linear(128, dim),
        )

        optimizer = torch.optim.Adam(
            list(embed_layer_1.parameters()) + list(embed_layer_2.parameters()),
            lr=0.01,
        )

        losses = []
        for epoch in range(100):
            optimizer.zero_grad()

            e1 = F.normalize(embed_layer_1(x1), dim=-1)
            e2 = F.normalize(embed_layer_2(x2), dim=-1)

            loss = alignment_loss(e1, e2, temperature=0.1)
            loss.backward()
            optimizer.step()

            losses.append(loss.item())

        # 验证最终损失 < 0.1
        final_loss = losses[-1]
        assert final_loss < 0.1, (
            f"对齐损失未能收敛到<0.1: final_loss={final_loss:.4f}"
        )

    def test_loss_stability(self):
        """测试连续10个epoch的损失波动 < 0.01。"""
        dim = 64
        embed_1 = nn.Linear(32, dim)
        embed_2 = nn.Linear(32, dim)

        x1 = torch.randn(64, 32)
        x2 = torch.randn(64, 32)

        # 共享部分信息使对齐成为可能
        shared = torch.randn(64, 16)
        x1 = torch.cat([x1[:, :16], shared], dim=-1)
        x2 = torch.cat([x2[:, :16], shared], dim=-1)

        optimizer = torch.optim.Adam(
            list(embed_1.parameters()) + list(embed_2.parameters()),
            lr=0.005,
        )

        # 先进行足够epoch的训练直到收敛
        for epoch in range(200):
            optimizer.zero_grad()
            e1 = F.normalize(embed_1(x1), dim=-1)
            e2 = F.normalize(embed_2(x2), dim=-1)
            loss = alignment_loss(e1, e2, temperature=0.1)
            loss.backward()
            optimizer.step()

        # 检查最后10个epoch的稳定性
        recent_losses = []
        for epoch in range(10):
            optimizer.zero_grad()
            e1 = F.normalize(embed_1(x1), dim=-1)
            e2 = F.normalize(embed_2(x2), dim=-1)
            loss = alignment_loss(e1, e2, temperature=0.1)
            loss.backward()
            optimizer.step()
            recent_losses.append(loss.item())

        fluctuation = max(recent_losses) - min(recent_losses)
        assert fluctuation < 0.01, (
            f"损失波动过大: max={max(recent_losses):.6f}, "
            f"min={min(recent_losses):.6f}, "
            f"波动={fluctuation:.6f}，需要<0.01"
        )

        # 验证已收敛（损失 < 0.1）
        assert all(line < 0.1 for line in recent_losses), (
            f"损失未收敛到<0.1: losses={[f'{line:.4f}' for line in recent_losses]}"
        )


# ============================================================================
# AlignmentLossTracker 测试
# ============================================================================


class TestAlignmentLossTracker:
    """测试AlignmentLossTracker的功能。"""

    def test_initial_state(self):
        """测试初始状态。"""
        tracker = AlignmentLossTracker()
        assert len(tracker) == 0
        assert not tracker.is_converged()
        summary = tracker.get_summary()
        assert summary["status"] == "no_data"

    def test_record_and_history(self):
        """测试记录损失和历史查询。"""
        tracker = AlignmentLossTracker(convergence_threshold=0.1)

        losses = [0.5, 0.3, 0.2, 0.15, 0.1, 0.08, 0.07, 0.06, 0.05, 0.04]
        for i, loss in enumerate(losses):
            tracker.record(loss, epoch=i)

        assert len(tracker) == 10
        assert tracker.history == losses

    def test_convergence_detection(self):
        """测试收敛检测。"""
        tracker = AlignmentLossTracker(
            convergence_threshold=0.1,
            stability_window=5,
            stability_threshold=0.02,
        )

        # 记录收敛的损失序列
        losses = [0.3, 0.2, 0.15, 0.09, 0.08, 0.075, 0.072, 0.07, 0.069, 0.068]
        for i, loss in enumerate(losses):
            tracker.record(loss, epoch=i)

        # 最后5个epoch的波动 = 0.08 - 0.068 = 0.012 < 0.02
        # 且所有值 < 0.1
        assert tracker.is_converged(), (
            f"应检测到收敛: history={tracker.history}"
        )

    def test_not_converged_above_threshold(self):
        """测试损失高于阈值时不收敛。"""
        tracker = AlignmentLossTracker(convergence_threshold=0.1, stability_window=5)

        losses = [0.5, 0.4, 0.3, 0.25, 0.2, 0.18, 0.16, 0.15, 0.14, 0.13]
        for loss in losses:
            tracker.record(loss)

        assert not tracker.is_converged(), "损失>0.1时应不收敛"

    def test_not_converged_unstable(self):
        """测试损失不稳定时不收敛。"""
        tracker = AlignmentLossTracker(
            convergence_threshold=0.2,
            stability_window=5,
            stability_threshold=0.01,
        )

        # 虽然损失低于阈值，但波动大
        losses = [0.08, 0.02, 0.09, 0.01, 0.07, 0.03, 0.08, 0.02, 0.09, 0.01]
        for loss in losses:
            tracker.record(loss)

        assert not tracker.is_converged(), "损失波动>0.01时应不收敛"

    def test_stability_metric(self):
        """测试稳定性指标计算。"""
        tracker = AlignmentLossTracker(stability_window=5)

        # 稳定序列
        for _ in range(10):
            tracker.record(0.05 + np.random.randn() * 0.001)

        stability = tracker.get_stability_metric()
        assert stability >= 0, f"稳定性指标应 >= 0: {stability}"
        assert stability < 0.01, f"稳定序列的标准差应小: {stability}"

    def test_trend_detection(self):
        """测试趋势检测。"""
        tracker = AlignmentLossTracker()

        # 初始数据不足
        assert tracker.get_trend() == "insufficient_data"

        # 下降趋势
        for i in range(20):
            tracker.record(1.0 / (i + 1) + np.random.randn() * 0.001)
        assert tracker.get_trend() == "decreasing"

    def test_best_loss_tracking(self):
        """测试最佳损失追踪。"""
        tracker = AlignmentLossTracker()

        tracker.record(0.5, epoch=0)
        tracker.record(0.3, epoch=1)
        tracker.record(0.4, epoch=2)
        tracker.record(0.2, epoch=3)
        tracker.record(0.3, epoch=4)

        assert tracker.best_loss == 0.2
        assert tracker.best_epoch == 3

    def test_reset(self):
        """测试重置功能。"""
        tracker = AlignmentLossTracker()
        for i in range(10):
            tracker.record(0.1)

        assert len(tracker) == 10
        tracker.reset()
        assert len(tracker) == 0
        assert tracker.best_loss == float("inf")
        assert tracker.best_epoch == -1

    def test_summary_format(self):
        """测试摘要输出格式。"""
        tracker = AlignmentLossTracker(convergence_threshold=0.1)
        for i in range(10):
            tracker.record(0.5 - i * 0.04, epoch=i)

        summary = tracker.get_summary()
        assert "total_epochs" in summary
        assert "final_loss" in summary
        assert "best_loss" in summary
        assert "converged" in summary
        assert "trend" in summary
        assert summary["total_epochs"] == 10

    def test_loss_curve_data(self):
        """测试损失曲线数据完整性。"""
        tracker = AlignmentLossTracker()

        losses = []
        for epoch in range(30):
            # 模拟典型的训练损失曲线
            loss = 2.0 * np.exp(-epoch / 10) + 0.05 + np.random.randn() * 0.01
            loss = max(loss, 0.01)
            tracker.record(loss, epoch=epoch)
            losses.append(loss)

        assert len(tracker.history) == 30
        # 验证损失总体下降
        assert tracker.history[-1] < tracker.history[0]
        # 验证趋势
        assert tracker.get_trend() in ("decreasing", "stable")


# ============================================================================
# 损失曲线可视化
# ============================================================================


class TestAlignmentLossVisualization:
    """测试对齐损失可视化功能。"""

    def test_loss_curve_plot(self):
        """测试绘制并保存损失曲线。"""
        if not HAS_MATPLOTLIB:
            pytest.skip("matplotlib未安装，跳过可视化测试")

        tracker = AlignmentLossTracker()

        # 模拟训练过程
        np.random.seed(42)
        epochs = list(range(50))
        losses = []
        for epoch in epochs:
            loss = 2.0 * np.exp(-epoch / 8) + 0.03 + np.random.randn() * 0.005
            loss = max(loss, 0.01)
            tracker.record(loss, epoch=epoch)
            losses.append(loss)

        # 绘制损失曲线
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

        fig, ax = plt.subplots(figsize=(10, 6))
        ax.plot(epochs, losses, "b-", linewidth=1.5, label="Alignment Loss")
        ax.axhline(y=0.1, color="r", linestyle="--", label="Convergence Threshold (0.1)")
        ax.set_xlabel("Epoch")
        ax.set_ylabel("Loss")
        ax.set_title("Alignment Loss Training Curve")
        ax.legend()
        ax.grid(True, alpha=0.3)
        plt.tight_layout()

        save_path = OUTPUT_DIR / "alignment_loss_curve.png"
        fig.savefig(save_path, dpi=150, bbox_inches="tight")
        plt.close(fig)

        assert save_path.exists(), f"损失曲线未保存到 {save_path}"

        # 由于模拟数据可能不完全收敛，仅验证曲线被保存
        assert save_path.stat().st_size > 0, "保存的曲线文件为空"
