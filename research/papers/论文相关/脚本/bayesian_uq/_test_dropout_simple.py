"""最简测试：验证 Dropout 层在 train 模式下是否产生随机性."""
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

from bayesian_dllnn_wrapper import load_bayesian_dllnn

weights_path = Path(__file__).parent / "results" / "full_weights.pt"
model = load_bayesian_dllnn(weights_path, device="cpu", mc_dropout_prob=0.1)

# 检查 Dropout 层状态
print("=== 检查 Dropout 层 ===")
for name, module in model.named_modules():
    if isinstance(module, nn.Dropout):
        print(f"  {name}: p={module.p}, training={module.training}")

# 手动构造输入
torch.manual_seed(42)
x = torch.randn(10, 7)
physics_pred = torch.randn(10, 1) * 7.6 + 12.6  # 模拟原始尺度
physics_pred_norm = (physics_pred - model.target_mean) / model.target_std

print("\n=== eval 模式 ===")
model.eval()
with torch.no_grad():
    out1, ltc1 = model.base_model(x, physics_pred=physics_pred_norm)
    out2, ltc2 = model.base_model(x, physics_pred=physics_pred_norm)
print(f"  final 输出差异: {(out1 - out2).abs().max().item():.6f}")
print(f"  ltc 输出差异: {(ltc1 - ltc2).abs().max().item():.6f}")

print("\n=== train 模式（Dropout 激活）===")
model.train()
with torch.no_grad():
    out1, ltc1 = model.base_model(x, physics_pred=physics_pred_norm)
    out2, ltc2 = model.base_model(x, physics_pred=physics_pred_norm)
print(f"  final 输出差异: {(out1 - out2).abs().max().item():.6f}")
print(f"  ltc 输出差异: {(ltc1 - ltc2).abs().max().item():.6f}")

print("\n=== train 模式 + 100次采样统计 ===")
model.train()
outs, ltcs = [], []
with torch.no_grad():
    for _ in range(100):
        out, ltc = model.base_model(x, physics_pred=physics_pred_norm)
        outs.append(out)
        ltcs.append(ltc)
outs_stack = torch.stack(outs)  # [100, 10, 1]
ltcs_stack = torch.stack(ltcs)
print(f"  final mean: {outs_stack.mean(0).flatten()[:3]}")
print(f"  final std:  {outs_stack.std(0).flatten()[:3]}")
print(f"  ltc mean:   {ltcs_stack.mean(0).flatten()[:3]}")
print(f"  ltc std:    {ltcs_stack.std(0).flatten()[:3]}")

print("\n=== 检查 ltc_branch.output_proj 是否被调用 ===")
# 直接调用 ltc_branch 看看
model.train()
with torch.no_grad():
    # 模拟 ltc_branch 的前向传播
    h = model.base_model.ltc_branch.input_proj(x)
    for cell in model.base_model.ltc_branch.ltc_cells:
        h = cell(h, dt=model.base_model.ltc_branch.dt)
    print(f"  ltc_cells 输出: mean={h.mean().item():.4f}, std={h.std().item():.4f}")

    # 通过 output_proj
    out_proj = model.base_model.ltc_branch.output_proj(h)
    print(f"  output_proj 输出: mean={out_proj.mean().item():.4f}, std={out_proj.std().item():.4f}")

    # 再来一次看差异
    out_proj2 = model.base_model.ltc_branch.output_proj(h)
    print(f"  output_proj 第二次: mean={out_proj2.mean().item():.4f}, std={out_proj2.std().item():.4f}")
    print(f"  两次差异: {(out_proj - out_proj2).abs().max().item():.6f}")

print("\n=== 检查 forward 完整流程 ===")
# 查看 DLLNNWithPhysics.forward 的实现
import inspect
from experiments.models import DLLNNWithPhysics
src = inspect.getsource(DLLNNWithPhysics.forward)
print(src[:2000])
