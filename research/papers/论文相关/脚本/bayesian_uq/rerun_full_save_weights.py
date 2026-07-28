"""
Full 配置权重补跑脚本（贝叶斯 LNN 路线前置依赖）
==================================================

用途：
    v4 消融实验的 ablation_experiment.py 只保存 metrics，不保存模型权重。
    本脚本单独训练 Full 配置，保存 state_dict + target 归一化统计量，
    供 bayesian_uq_experiment.py 加载后做 MC Dropout 不确定性量化。

与 v4 消融实验的关系：
    - 复用完全相同的 Full 配置（lambda_phys=0.5, lambda_pcc=0.1, 两阶段训练）
    - 复用相同的 DLLNNTrainer / data_generator / 模型架构
    - 不依赖 v4 的 checkpoint，可独立运行

运行方式：
    cd 项目根目录
    python research/papers/论文相关/脚本/bayesian_uq/rerun_full_save_weights.py

输出：
    research/papers/论文相关/脚本/bayesian_uq/results/full_weights.pt
"""

import os
import sys
import json
import time
import types
import warnings
from pathlib import Path

# === WinSock 损坏绕过补丁（必须在 import torch 之前）===
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 模块加载失败，已注入空实现绕过 WinSock 损坏。")

import numpy as np
import torch
from torch.utils.data import DataLoader

warnings.filterwarnings("ignore")

# === 路径设置（复用 ablation_experiment.py 的路径逻辑）===
_current = Path(__file__).resolve()
PROJECT_ROOT = _current
for _ in range(6):
    if (PROJECT_ROOT / "research" / "training" / "reproducibility.py").exists():
        break
    PROJECT_ROOT = PROJECT_ROOT.parent
else:
    PROJECT_ROOT = _current.parents[5]

RESEARCH_DIR = PROJECT_ROOT / "research"
EXPERIMENTS_DIR = RESEARCH_DIR / "experiments"
ENGINEERING_PYTHON_DIR = PROJECT_ROOT / "engineering" / "python"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ENGINEERING_PYTHON_DIR))
sys.path.insert(0, str(RESEARCH_DIR))
sys.path.insert(0, str(EXPERIMENTS_DIR))

# 复用主实验模块
from research.training.reproducibility import set_global_seed
from experiments.config import get_config
from experiments.data_generator import (
    TlustyAnalyticalModel,
    build_physics_features_7d,
    SyntheticChatterDataset,
)
from experiments.trainer import DLLNNTrainer
from experiments.metrics import ChatterMetrics

# 复用 ablation_experiment 的数据加载和 Full 配置
_ablation_dir = PROJECT_ROOT / "research" / "papers" / "论文相关" / "脚本"
if str(_ablation_dir) not in sys.path:
    sys.path.insert(0, str(_ablation_dir))
from ablation_experiment import (
    get_ablation_specs,
    load_ablation_dataset,
    _SimpleDataset,
)

# 与 v4 消融实验完全一致的训练轮数（v4 实际运行使用 30/60）
# ablation_experiment.py 的 argparse 默认值是 100/200，但 v4 通过命令行参数传入 30/60
STAGE1_EPOCHS = 30
STAGE2_EPOCHS = 60


def main():
    # === 输出路径 ===
    output_dir = Path(__file__).parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)
    weights_path = output_dir / "full_weights.pt"

    if weights_path.exists():
        print(f"[跳过] Full 权重已存在: {weights_path}")
        print("       如需重跑，请先删除该文件。")
        return

    # === 1. 获取 Full 配置 ===
    specs = get_ablation_specs()
    full_spec = specs["Full"]
    print("=" * 70)
    print("Full 配置权重补跑（贝叶斯 LNN 路线前置依赖）")
    print("=" * 70)
    print(f"配置: {full_spec.description}")
    print(f"  lambda_phys = 0.5 (config 默认)")
    print(f"  lambda_pcc  = 0.1 (config 默认)")
    print(f"  两阶段训练")
    print()

    # === 2. 加载数据 ===
    seed = 42
    set_global_seed(seed)
    data = load_ablation_dataset("synthetic", seed=seed)

    train_ds = _SimpleDataset(data["X_train"], data["y_train"], data["y_phys_train"])
    val_ds = _SimpleDataset(data["X_val"], data["y_val"], data["y_phys_val"])
    test_ds = _SimpleDataset(data["X_test"], data["y_test"], data["y_phys_test"])

    train_loader = DataLoader(
        train_ds, batch_size=32, shuffle=True,
        generator=torch.Generator().manual_seed(seed),
    )
    val_loader = DataLoader(val_ds, batch_size=32, shuffle=False)
    test_loader = DataLoader(test_ds, batch_size=32, shuffle=False)

    # === 3. 创建 Trainer ===
    config = get_config()
    config.model.num_epochs_stage1 = STAGE1_EPOCHS
    config.model.num_epochs_stage2 = STAGE2_EPOCHS
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    config.model.device = str(device)

    trainer = DLLNNTrainer(config, device=str(device))

    # === 4. 两阶段训练 ===
    print(f"设备: {device}")
    print(f"训练样本: {len(train_ds)}, 验证: {len(val_ds)}, 测试: {len(test_ds)}")
    print()
    t0 = time.time()

    # 中间 checkpoint 路径（防止训练完成后保存失败导致权重丢失）
    ckpt_dir = output_dir / "checkpoints"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    stage1_ckpt = ckpt_dir / "stage1_done.pt"
    stage2_ckpt = ckpt_dir / "stage2_done.pt"

    print("===== 阶段一：解析预训练 =====")
    trainer.train_stage1(train_loader, val_loader, num_epochs=STAGE1_EPOCHS)

    # 保存阶段一完成后的状态（用于调试和恢复）
    torch.save({
        "model_state_dict": trainer.model.state_dict(),
        "best_model_state": trainer.best_model_state,
        "target_mean": trainer.target_mean,
        "target_std": trainer.target_std,
    }, stage1_ckpt)
    print(f"[checkpoint] 阶段一完成状态已保存: {stage1_ckpt}")

    print("\n===== 阶段二：PCC Loss 微调 =====")
    trainer.train_stage2(train_loader, val_loader, num_epochs=STAGE2_EPOCHS)

    # 保存阶段二完成后的状态（best_model_state 已被加载回 model）
    torch.save({
        "model_state_dict": trainer.model.state_dict(),
        "best_model_state": trainer.best_model_state,
        "target_mean": trainer.target_mean,
        "target_std": trainer.target_std,
    }, stage2_ckpt)
    print(f"[checkpoint] 阶段二完成状态已保存: {stage2_ckpt}")

    elapsed = time.time() - t0
    print(f"\n训练完成，耗时 {elapsed/3600:.2f} 小时")

    # === 5. 评估 ===
    # 必须传入归一化后的 physics_pred 才能激活门控融合逻辑，
    # 否则 model.forward 会走 None 分支仅返回 ltc_pred（bug 修复）。
    trainer.model.eval()
    all_preds, all_targets, all_phys = [], [], []
    with torch.no_grad():
        for batch in test_loader:
            x, y_true, y_phys = batch
            x = x.to(trainer.device)
            # 应用 target 归一化（与训练时 _unpack_batch 一致）
            if trainer._target_stats_computed:
                y_phys_norm = (y_phys - trainer.target_mean) / trainer.target_std
            else:
                y_phys_norm = y_phys
            y_phys_norm = y_phys_norm.to(trainer.device)
            y_pred, _ = trainer.model(x, physics_pred=y_phys_norm)
            all_preds.append(y_pred.cpu().numpy())
            all_targets.append(y_true.numpy())
            all_phys.append(y_phys.numpy())

    all_preds = np.concatenate(all_preds, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)
    all_phys = np.concatenate(all_phys, axis=0)

    # 反归一化
    if hasattr(trainer, "denormalize"):
        all_preds_denorm = trainer.denormalize(all_preds)
    else:
        all_preds_denorm = all_preds

    metrics_calc = ChatterMetrics()
    metrics = metrics_calc.compute_all(all_preds_denorm, all_targets, all_phys)

    print("\n===== 评估结果 =====")
    for k, v in metrics.items():
        print(f"  {k}: {v:.6f}")

    # === 6. 保存权重 + target 归一化统计量 ===
    save_obj = {
        "model_state_dict": trainer.model.state_dict(),
        "target_mean": trainer.target_mean,
        "target_std": trainer.target_std,
        "config": {
            "input_dim": 7,
            "hidden_dim": config.model.hidden_dim,
            "num_layers": config.model.num_layers,
            "output_dim": 1,
            "dt": config.model.ltc_dt,  # ModelConfig 用 ltc_dt，DLLNNWithPhysics 用 dt
            "dropout": config.model.dropout,
            "lambda_phys": config.model.lambda_phys,
            "lambda_pcc": config.model.lambda_pcc,
        },
        "metrics": {k: float(v) for k, v in metrics.items()},
        "train_history": {
            "stage1_epochs": STAGE1_EPOCHS,
            "stage2_epochs": STAGE2_EPOCHS,
            "final_val_loss": float(trainer.best_val_loss),
        },
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "elapsed_sec": round(elapsed, 1),
    }

    torch.save(save_obj, weights_path)
    print(f"\n[已保存] 权重文件: {weights_path}")
    print(f"  target_mean = {trainer.target_mean:.4f}")
    print(f"  target_std  = {trainer.target_std:.4f}")
    print(f"  文件大小: {weights_path.stat().st_size / 1024 / 1024:.1f} MB")


if __name__ == "__main__":
    main()
