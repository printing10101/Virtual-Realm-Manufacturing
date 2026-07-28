"""诊断真实数据下 Dropout 层前后激活值分布."""
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

# 真实数据
dataset = LomoLocoDataset(
    samples_per_group=200,
    materials=list(MATERIALS_CONFIG.keys()),
    conditions=list(CONDITIONS_CONFIG.keys()),
    noise_level=0.02,
    seed=42,
)

mask = dataset.sample_materials == "45_Steel"
idx = np.where(mask)[0][:50]
X_real = dataset.data["features"][idx]
y_phys_real = dataset.data["a_lim_clean"][idx]

# 随机数据对比
torch.manual_seed(42)
X_rand = torch.randn(50, 7).numpy()
y_phys_rand = np.random.RandomState(42).randn(50) * 7.6 + 12.6

print("=" * 70)
print("输入数据统计对比")
print("=" * 70)
print(f"真实 X: mean={X_real.mean():.4f}, std={X_real.std():.4f}, min={X_real.min():.4f}, max={X_real.max():.4f}")
print(f"随机 X: mean={X_rand.mean():.4f}, std={X_rand.std():.4f}, min={X_rand.min():.4f}, max={X_rand.max():.4f}")
print(f"真实 y_phys: mean={y_phys_real.mean():.4f}, std={y_phys_real.std():.4f}")
print(f"随机 y_phys: mean={y_phys_rand.mean():.4f}, std={y_phys_rand.std():.4f}")

# 检查 ltc_branch 结构
print("\n" + "=" * 70)
print("ltc_branch 结构")
print("=" * 70)
print(model.base_model.ltc_branch)

# 注册 forward hook 到 Dropout 层
dropout_layer = model.base_model.ltc_branch.output_proj[2]
print(f"\nDropout 层: {dropout_layer}, p={dropout_layer.p}, training={dropout_layer.training}")

# 检查 output_proj 各子层
print(f"\noutput_proj 子层:")
for i, m in enumerate(model.base_model.ltc_branch.output_proj):
    print(f"  [{i}] {m}")

# 注册 hook 捕获 Dropout 层输入和输出
activations = {}
def hook_fn(module, inp, out, name):
    activations[name + "_input"] = inp[0].detach().clone()
    activations[name + "_output"] = out.detach().clone()

h1 = dropout_layer.register_forward_hook(lambda m, i, o: hook_fn(m, i, o, "dropout"))

# 在真实数据上运行 5 次
print("\n" + "=" * 70)
print("真实数据下 Dropout 层前后激活值（5次采样）")
print("=" * 70)
model.train()
x_t = torch.from_numpy(X_real.astype(np.float32))
phys_t = torch.from_numpy(y_phys_real.astype(np.float32))
physics_pred_norm = (phys_t - model.target_mean) / model.target_std
if physics_pred_norm.dim() == 1:
    physics_pred_norm = physics_pred_norm.unsqueeze(-1)

for i in range(5):
    with torch.no_grad():
        out, ltc = model.base_model(x_t, physics_pred=physics_pred_norm)
    di = activations["dropout_input"]
    do = activations["dropout_output"]
    print(f"  采样{i+1}: dropout_in mean={di.mean():.6f}, std={di.std():.6f}, "
          f"非零比例={(di != 0).float().mean():.4f}")
    print(f"        dropout_out mean={do.mean():.6f}, std={do.std():.6f}, "
          f"非零比例={(do != 0).float().mean():.4f}")

# 在随机数据上运行 5 次
print("\n" + "=" * 70)
print("随机数据下 Dropout 层前后激活值（5次采样）")
print("=" * 70)
x_r = torch.from_numpy(X_rand.astype(np.float32))
phys_r = torch.from_numpy(y_phys_rand.astype(np.float32))
physics_pred_norm_r = (phys_r - model.target_mean) / model.target_std
if physics_pred_norm_r.dim() == 1:
    physics_pred_norm_r = physics_pred_norm_r.unsqueeze(-1)

for i in range(5):
    with torch.no_grad():
        out, ltc = model.base_model(x_r, physics_pred=physics_pred_norm_r)
    di = activations["dropout_input"]
    do = activations["dropout_output"]
    print(f"  采样{i+1}: dropout_in mean={di.mean():.6f}, std={di.std():.6f}, "
          f"非零比例={(di != 0).float().mean():.4f}")
    print(f"        dropout_out mean={do.mean():.6f}, std={do.std():.6f}, "
          f"非零比例={(do != 0).float().mean():.4f}")

# 检查 ltc_cells 的输出
print("\n" + "=" * 70)
print("LTC cells 输出 h 的统计")
print("=" * 70)

# 注册 hook 到 ltc_cells 的最后一个 cell
last_cell = model.base_model.ltc_branch.ltc_cells[-1]
h_cell = {}
def cell_hook(module, inp, out, name):
    h_cell[name + "_out"] = out.detach().clone()

h2 = last_cell.register_forward_hook(lambda m, i, o: cell_hook(m, i, o, "last_cell"))

# 真实数据
model.train()
with torch.no_grad():
    out, ltc = model.base_model(x_t, physics_pred=physics_pred_norm)
h_real = h_cell["last_cell_out"]
print(f"真实数据: h shape={h_real.shape}")
print(f"  mean={h_real.mean():.6f}, std={h_real.std():.6f}")
print(f"  min={h_real.min():.6f}, max={h_real.max():.6f}")
print(f"  非零比例={(h_real != 0).float().mean():.4f}")
print(f"  前5个样本的第1维: {h_real[:5, 0]}")

# 随机数据
with torch.no_grad():
    out, ltc = model.base_model(x_r, physics_pred=physics_pred_norm_r)
h_rand = h_cell["last_cell_out"]
print(f"\n随机数据: h shape={h_rand.shape}")
print(f"  mean={h_rand.mean():.6f}, std={h_rand.std():.6f}")
print(f"  min={h_rand.min():.6f}, max={h_rand.max():.6f}")
print(f"  非零比例={(h_rand != 0).float().mean():.4f}")
print(f"  前5个样本的第1维: {h_rand[:5, 0]}")

# 检查 output_proj 第一层线性层的权重
print("\n" + "=" * 70)
print("output_proj 第一层 Linear 权重统计")
print("=" * 70)
linear1 = model.base_model.ltc_branch.output_proj[0]
W1 = linear1.weight
b1 = linear1.bias
print(f"  weight shape: {W1.shape}")
print(f"  weight mean={W1.mean():.6f}, std={W1.std():.6f}")
print(f"  weight abs mean={W1.abs().mean():.6f}, max={W1.abs().max():.6f}")
print(f"  bias mean={b1.mean():.6f}, std={b1.std():.6f}")

# 检查第三层（Dropout 后的 Linear）
linear3 = model.base_model.ltc_branch.output_proj[-1]
W3 = linear3.weight
b3 = linear3.bias
print(f"\noutput_proj 最后层 Linear 权重统计")
print(f"  weight shape: {W3.shape}")
print(f"  weight mean={W3.mean():.6f}, std={W3.std():.6f}")
print(f"  weight abs mean={W3.abs().mean():.6f}, max={W3.abs().max():.6f}")
print(f"  bias mean={b3.mean():.6f}, std={b3.std():.6f}")

h1.remove()
h2.remove()

print("\n=== 诊断完成 ===")
