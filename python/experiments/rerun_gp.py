"""
临时脚本：仅重跑 GP 基线（已修复 optimizer=None）
完成后自动删除本文件。
"""
import sys
import os
import json
import types

# === WinSock 损坏绕过补丁（与 run_experiment.py 一致）===
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

_EXPERIMENTS_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_EXPERIMENTS_DIR)
sys.path.insert(0, _PROJECT_ROOT)
sys.path.insert(0, _EXPERIMENTS_DIR)

from app.ai.lnn.training.reproducibility import set_global_seed, get_worker_init_fn
from experiments.config import get_config
from experiments.data_generator import SyntheticChatterDataset, IndustrialChatterDataset
from experiments.models import BaselineGP
from experiments.trainer import SklearnBaselineTrainer
from experiments.metrics import ChatterMetrics

# 加载 Optuna 最佳超参
best_params_path = os.path.join(_EXPERIMENTS_DIR, "results", "best_hyperparams.json")
with open(best_params_path, "r", encoding="utf-8") as f:
    best_params = json.load(f)
gp_p = best_params["GP"]
print(f"[GP] Optuna 最佳超参: {gp_p}")

# 应用修复后的 monkey-patch（optimizer=None）
import experiments.models as _models_mod
def _patched_gp_init(self, input_dim=7, alpha=gp_p.get("alpha", 1e-6),
                     random_state=42, **kwargs):
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, ConstantKernel
    kernel = (ConstantKernel(gp_p.get("constant_value", 1.0))
              * RBF(length_scale=gp_p.get("length_scale", 1.0)))
    super(_models_mod.BaselineGP, self).__init__(
        GaussianProcessRegressor(
            kernel=kernel, alpha=alpha,
            random_state=random_state, optimizer=None, **kwargs
        ),
        input_dim=input_dim,
    )
_models_mod.BaselineGP.__init__ = _patched_gp_init

config = get_config("main_experiment")
config.model.device = "cpu"
set_global_seed(42)

def run_gp_on_dataset(dataset_name, dataset_class, dataset_kwargs):
    print(f"\n{'='*60}")
    print(f"重跑 GP - 数据集: {dataset_name}")
    print(f"{'='*60}")

    full_dataset = dataset_class(**dataset_kwargs)
    train_size = int(0.7 * len(full_dataset))
    val_size = int(0.15 * len(full_dataset))
    test_size = len(full_dataset) - train_size - val_size
    split_generator = torch.Generator().manual_seed(42)
    train_dataset, val_dataset, test_dataset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size, test_size], generator=split_generator
    )
    train_loader = DataLoader(
        train_dataset, batch_size=32, shuffle=True,
        generator=torch.Generator().manual_seed(42),
        worker_init_fn=get_worker_init_fn(42)
    )
    val_loader = DataLoader(val_dataset, batch_size=32, shuffle=False)
    test_loader = DataLoader(test_dataset, batch_size=32, shuffle=False)

    trainer = SklearnBaselineTrainer("GP", config, device="cpu")
    trainer.train(train_loader, val_loader, num_epochs=1)
    model = trainer.model

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
    for k, v in metrics.items():
        print(f"  {k}: {v:.4f}")
    return metrics

# 运行两个数据集
synthetic_metrics = run_gp_on_dataset(
    "Synthetic", SyntheticChatterDataset,
    {"num_samples": 1000, "spindle_speed_range": (1000, 10000),
     "axial_depth_range": (0.1, 10.0), "noise_level": 0.02}
)
industrial_metrics = run_gp_on_dataset(
    "Industrial", IndustrialChatterDataset,
    {"num_samples": 500, "num_conditions": 30, "material": "6061-T6"}
)

# 更新结果文件
results_path = os.path.join(_EXPERIMENTS_DIR, "results", "all_experiments_results.json")
with open(results_path, "r", encoding="utf-8") as f:
    all_results = json.load(f)

all_results["Synthetic"]["GP"] = {k: float(v) for k, v in synthetic_metrics.items()}
all_results["Industrial"]["GP"] = {k: float(v) for k, v in industrial_metrics.items()}

with open(results_path, "w", encoding="utf-8") as f:
    json.dump(all_results, f, indent=2, ensure_ascii=False)

print(f"\n{'='*60}")
print(f"GP 结果已更新至: {results_path}")
print(f"{'='*60}")
print(f"\n最终 GP 结果:")
print(f"  Synthetic  - MAE: {synthetic_metrics['mae']:.4f}, R²: {synthetic_metrics['r2']:.4f}")
print(f"  Industrial - MAE: {industrial_metrics['mae']:.4f}, R²: {industrial_metrics['r2']:.4f}")
