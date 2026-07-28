"""诊断 predict_batch 为何返回 std=0."""
import sys, types
from pathlib import Path

try:
    import _overlapped  # noqa
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch

import torch
import torch.nn as nn
import numpy as np

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
for p in [str(PROJECT_ROOT), str(ENGINEERING_PYTHON_DIR),
          str(RESEARCH_DIR), str(EXPERIMENTS_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

_bayes_dir = Path(__file__).parent
if str(_bayes_dir) not in sys.path:
    sys.path.insert(0, str(_bayes_dir))

_lomo_script_dir = PROJECT_ROOT / "research" / "papers" / "论文相关" / "脚本"
if str(_lomo_script_dir) not in sys.path:
    sys.path.insert(0, str(_lomo_script_dir))

from bayesian_dllnn_wrapper import load_bayesian_dllnn
from lomo_loco_experiment import MATERIALS_CONFIG, CONDITIONS_CONFIG, LomoLocoDataset

weights_path = Path(__file__).parent / "results" / "full_weights.pt"
model = load_bayesian_dllnn(weights_path, device="cpu", mc_dropout_prob=0.1)

# 生成 LOMO 数据
dataset = LomoLocoDataset(
    samples_per_group=200,
    materials=list(MATERIALS_CONFIG.keys()),
    conditions=list(CONDITIONS_CONFIG.keys()),
    noise_level=0.02,
    seed=42,
)

# 取 45_Steel 的 50 个样本
mask = dataset.sample_materials == "45_Steel"
idx = np.where(mask)[0][:50]
X = dataset.data["features"][idx]
y_phys = dataset.data["a_lim_clean"][idx]
ks = dataset.sample_ks_scale[idx]

print(f"X shape: {X.shape}, y_phys shape: {y_phys.shape}, ks shape: {ks.shape}")
print(f"y_phys 前5个: {y_phys[:5]}")

# === 测试 1: 直接调用 predict_with_uncertainty ===
print("\n=== 测试 1: 直接调用 predict_with_uncertainty ===")
x_t = torch.from_numpy(X.astype(np.float32))
phys_t = torch.from_numpy(y_phys.astype(np.float32))
print(f"x_t shape: {x_t.shape}, phys_t shape: {phys_t.shape}")

result1 = model.predict_with_uncertainty(x_t, physics_pred=phys_t, n_samples=50, return_components=True)
print(f"  mean shape: {result1['mean'].shape}")
print(f"  std mean: {result1['std'].mean().item():.6f}")
print(f"  std max: {result1['std'].max().item():.6f}")
print(f"  ltc_std mean: {result1['ltc_std'].mean().item():.6f}")
print(f"  ltc_std max: {result1['ltc_std'].max().item():.6f}")

# === 测试 2: 调用 predict_batch ===
print("\n=== 测试 2: 调用 predict_batch ===")
result2 = model.predict_batch(X, physics_pred=y_phys, n_samples=50, device="cpu", batch_size=50, return_components=True)
print(f"  mean shape: {result2['mean'].shape}")
print(f"  std mean: {result2['std'].mean().item():.6f}")
print(f"  std max: {result2['std'].max().item():.6f}")
print(f"  ltc_std mean: {result2['ltc_std'].mean().item():.6f}")
print(f"  ltc_std max: {result2['ltc_std'].max().item():.6f}")

# === 测试 3: 检查 predict_batch 内部的 physics_pred 维度 ===
print("\n=== 测试 3: 检查 physics_pred 维度处理 ===")
# 模拟 predict_batch 内部
model.train()
phys_batch = torch.from_numpy(y_phys[:50].astype(np.float32))
print(f"phys_batch shape (原始): {phys_batch.shape}")
print(f"phys_batch dim: {phys_batch.dim()}")

# 在 predict_with_uncertainty 中的处理
physics_pred_norm = (phys_batch - model.target_mean) / model.target_std
print(f"physics_pred_norm shape: {physics_pred_norm.shape}")
print(f"physics_pred_norm dim: {physics_pred_norm.dim()}")
if physics_pred_norm.dim() == 1:
    physics_pred_norm = physics_pred_norm.unsqueeze(-1)
print(f"unsqueeze 后 shape: {physics_pred_norm.shape}")

# === 测试 4: 直接调用 base_model，检查输出 ===
print("\n=== 测试 4: 直接调用 base_model 50次 ===")
model.train()
outs, ltcs = [], []
with torch.no_grad():
    for _ in range(50):
        out, ltc = model.base_model(x_t, physics_pred=physics_pred_norm)
        outs.append(out)
        ltcs.append(ltc)
outs_stack = torch.stack(outs)
ltcs_stack = torch.stack(ltcs)
print(f"  final std: {outs_stack.std(0).mean().item():.6f}")
print(f"  ltc std: {ltcs_stack.std(0).mean().item():.6f}")

# === 测试 5: 检查 predict_with_uncertainty 中 torch.no_grad() 的影响 ===
print("\n=== 测试 5: 在 no_grad 上下文中调用 predict_with_uncertainty ===")
# predict_with_uncertainty 内部使用 torch.no_grad()
# 让我们手动复制其逻辑
model.train()
batch_size = x_t.shape[0]
final_outputs = []
ltc_outputs = []
physics_pred_norm2 = (phys_t - model.target_mean) / model.target_std
if physics_pred_norm2.dim() == 1:
    physics_pred_norm2 = physics_pred_norm2.unsqueeze(-1)

with torch.no_grad():
    for _ in range(50):
        final_pred, ltc_pred = model.base_model(x_t, physics_pred=physics_pred_norm2)
        final_outputs.append(final_pred)
        ltc_outputs.append(ltc_pred)

final_stack = torch.stack(final_outputs)
ltc_stack = torch.stack(ltc_outputs)
print(f"  final std: {final_stack.std(0).mean().item():.6f}")
print(f"  ltc std: {ltc_stack.std(0).mean().item():.6f}")

print("\n=== 诊断完成 ===")
