"""
GP 基线修复验证脚本
验证 BaselineGP 修复后（optimizer=None + Optuna 超参注入）不再发散。
"""

import sys
import os
import json
import types

# === WinSock 损坏绕过补丁 ===
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

# 添加项目路径
_EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_EXPERIMENTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _EXPERIMENTS_DIR)

from experiments.config import get_config
from experiments.data_generator import SyntheticChatterDataset, IndustrialChatterDataset
from experiments.models import create_model
from experiments.trainer import SklearnBaselineTrainer
from experiments.metrics import ChatterMetrics


def test_gp_on_dataset(config, dataset_name, dataset_class, dataset_kwargs):
    """在单个数据集上测试 GP 修复效果"""
    print(f"\n{'='*60}")
    print(f"测试 GP 修复 - 数据集: {dataset_name}")
    print(f"{'='*60}")

    # 创建数据集
    full_dataset = dataset_class(**dataset_kwargs)

    # 划分
    train_size = int(0.7 * len(full_dataset))
    val_size = int(0.15 * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size

    split_generator = torch.Generator().manual_seed(42)
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size, test_size], generator=split_generator
    )

    train_loader = DataLoader(train_dataset, batch_size=32, shuffle=True,
                              generator=torch.Generator().manual_seed(42))
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

    # 创建 GP 模型（应通过 config.gp_best_params 注入 Optuna 超参）
    trainer = SklearnBaselineTrainer("GP", config, device="cpu")
    trainer.train(train_loader, val_loader, num_epochs=1)
    model = trainer.model

    # 评估
    model.eval()
    metrics_calculator = ChatterMetrics()
    all_preds = []
    all_targets = []

    with torch.no_grad():
        for batch in test_loader:
            if len(batch) == 3:
                x, y_true, _ = batch
            else:
                x, y_true = batch
            x_numpy = x.cpu().numpy()
            y_pred = model.predict(x_numpy)
            all_preds.append(y_pred)
            all_targets.append(y_true.numpy())

    all_preds = np.concatenate(all_preds, axis=0)
    all_targets = np.concatenate(all_targets, axis=0)
    metrics = metrics_calculator.compute_all(all_preds, all_targets)

    print(f"\n{dataset_name} GP 评估结果:")
    for metric_name, value in metrics.items():
        print(f"  {metric_name}: {value:.4f}")

    return metrics


def main():
    config = get_config("main_experiment")
    config.model.device = "cpu"

    # 加载 Optuna GP 超参并挂载到 config
    best_params_path = os.path.join(_EXPERIMENTS_DIR, "results", "best_hyperparams.json")
    with open(best_params_path, "r", encoding="utf-8") as f:
        best_params = json.load(f)

    config.gp_best_params = best_params["GP"]
    print(f"GP 最佳超参: {config.gp_best_params}")

    # 验证 create_model 是否正确读取超参
    test_model = create_model("GP", config)
    gpr = test_model.sklearn_model
    kernel = gpr.kernel
    print(f"\n验证 GP 核参数:")
    print(f"  optimizer: {gpr.optimizer}")
    print(f"  kernel: {kernel}")
    print(f"  alpha: {gpr.alpha}")

    # 测试 Synthetic
    synth_metrics = test_gp_on_dataset(
        config, "Synthetic", SyntheticChatterDataset,
        {"num_samples": 1000, "spindle_speed_range": (1000, 10000),
         "axial_depth_range": (0.1, 10.0), "noise_level": 0.02}
    )

    # 测试 Industrial
    ind_metrics = test_gp_on_dataset(
        config, "Industrial", IndustrialChatterDataset,
        {"num_samples": 500, "num_conditions": 30, "material": "6061-T6"}
    )

    # 汇总
    print(f"\n{'='*60}")
    print("GP 修复验证汇总")
    print(f"{'='*60}")
    print(f"Synthetic  - MAE: {synth_metrics['mae']:.4f}, R2: {synth_metrics['r2']:.4f}")
    print(f"Industrial - MAE: {ind_metrics['mae']:.4f}, R2: {ind_metrics['r2']:.4f}")

    if synth_metrics['mae'] < 1.0 and ind_metrics['mae'] < 1.0:
        print("\n✓ GP 修复成功！MAE 已降至合理范围（< 1.0），不再发散。")
    else:
        print("\n✗ GP 仍然发散，需进一步排查。")

    # 保存结果供后续更新使用
    results = {
        "Synthetic": {k: float(v) for k, v in synth_metrics.items()},
        "Industrial": {k: float(v) for k, v in ind_metrics.items()},
    }
    output_path = os.path.join(_EXPERIMENTS_DIR, "results", "gp_fixed_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\n结果保存至: {output_path}")


if __name__ == "__main__":
    main()
