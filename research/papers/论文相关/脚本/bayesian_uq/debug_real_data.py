"""
用真实 LOMO 数据诊断 MC Dropout
检查 alpha 门控值和各分量不确定性
"""
import sys
import types
from pathlib import Path

try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch

import torch
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

print("=" * 70)
print("真实数据 MC Dropout 诊断")
print("=" * 70)

# 加载模型
weights_path = Path(__file__).parent / "results" / "full_weights.pt"
model = load_bayesian_dllnn(weights_path, device="cpu", mc_dropout_prob=0.1)

# 生成 LOMO 数据（修正调用方式）
print("\n[生成 LOMO 数据集...]")
dataset = LomoLocoDataset(
    samples_per_group=200,
    materials=list(MATERIALS_CONFIG.keys()),
    conditions=list(CONDITIONS_CONFIG.keys()),
    noise_level=0.02,
    seed=42,
)
X_all = dataset.data["features"]
y_all = dataset.data["a_lim"]
y_phys_all = dataset.data["a_lim_clean"]
materials_all = dataset.sample_materials
ks_all = dataset.sample_ks_scale
print(f"  总样本: {len(X_all)}, 材料列表: {list(MATERIALS_CONFIG.keys())}")

# 对 45_Steel 和 6061-T6 各取 100 样本测试
for mat_name in ["45_Steel", "6061-T6"]:
    mask = materials_all == mat_name
    if mask.sum() == 0:
        print(f"\n[{mat_name}] 无样本，跳过")
        continue
    idx = np.where(mask)[0][:100]
    X = X_all[idx]
    y_true = y_all[idx]
    y_phys = y_phys_all[idx]
    ks = ks_all[idx]
    # 同时取标量 ks 用于打印
    ks_scalar = float(np.mean(ks))
    hardness = MATERIALS_CONFIG[mat_name]["hardness"]

    print(f"\n[{mat_name}] 硬度={hardness:.0f}, ks={ks_scalar:.4f}")
    print(f"  X shape: {X.shape}, y_phys shape: {y_phys.shape}")

    # 检查 alpha 门控值
    model.eval()
    with torch.no_grad():
        x_t = torch.from_numpy(X.astype(np.float32))
        # 物理预测需要归一化（与训练一致）
        y_phys_t = torch.from_numpy(y_phys.astype(np.float32)).unsqueeze(-1)
        physics_pred_norm = (y_phys_t - model.target_mean) / model.target_std
        alpha = model.base_model.gate(x_t)
        print(f"  alpha 门控: mean={alpha.mean().item():.4f}, min={alpha.min().item():.4f}, max={alpha.max().item():.4f}")
        print(f"  alpha<0.01 的比例: {(alpha < 0.01).float().mean().item():.2%}")
        print(f"  alpha>0.99 的比例: {(alpha > 0.99).float().mean().item():.2%}")

    # MC Dropout 测试
    uq_result = model.predict_batch(
        X, physics_pred=y_phys, n_samples=50, device="cpu",
        batch_size=100, return_components=True,
    )

    mean_denorm = uq_result["mean_denorm"].flatten()
    std_denorm = uq_result["std_denorm"].flatten()
    ltc_std_denorm = uq_result["ltc_std_denorm"].flatten()

    # ks 是 [N] 数组，注意广播
    std_orig = std_denorm / ks
    ltc_std_orig = ltc_std_denorm / ks

    print(f"\n  MC Dropout 结果（50次采样）:")
    print(f"    mean_denorm: mean={mean_denorm.mean():.4f}, std={mean_denorm.std():.4f}")
    print(f"    std_denorm:  mean={std_denorm.mean():.6f}, max={std_denorm.max():.6f}")
    print(f"    std_orig (除以ks): mean={std_orig.mean():.6f}, max={std_orig.max():.6f}")
    print(f"    ltc_std_denorm: mean={ltc_std_denorm.mean():.6f}, max={ltc_std_denorm.max():.6f}")
    print(f"    ltc_std_orig: mean={ltc_std_orig.mean():.6f}, max={ltc_std_orig.max():.6f}")

    # 检查 physics_scale 和 physics_bias
    ps = model.base_model.physics_scale.item()
    pb = model.base_model.physics_bias.item()
    print(f"\n  physics_scale={ps:.4f}, physics_bias={pb:.4f}")

    # 门控融合公式：final = alpha * ltc + (1-alpha) * (ps * phys_norm + pb)
    # 如果 alpha ≈ 0，final ≈ ps * phys_norm + pb（确定性）
    # 如果 alpha ≈ 1，final ≈ ltc（有 Dropout 随机性）

    # 计算 final_pred 的理论 std
    # final = alpha * ltc + (1-alpha) * phys_fixed
    # std(final) = alpha * std(ltc)  （phys_fixed 是确定性的）
    print(f"\n  理论分析:")
    print(f"    std(final) ≈ alpha * std(ltc)")
    print(f"    若 alpha≈0, std(final)≈0 → MC Dropout 失效")

print("\n" + "=" * 70)
print("诊断完成")
