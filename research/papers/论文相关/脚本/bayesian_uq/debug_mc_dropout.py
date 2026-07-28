"""
快速诊断脚本：验证 MC Dropout 是否真的激活
"""
import sys
import types
from pathlib import Path

# WinSock 补丁
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch

import torch
import numpy as np

# 路径设置
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

# 添加 bayesian_uq 目录
_bayes_dir = Path(__file__).parent
if str(_bayes_dir) not in sys.path:
    sys.path.insert(0, str(_bayes_dir))

from bayesian_dllnn_wrapper import load_bayesian_dllnn

print("=" * 70)
print("MC Dropout 诊断")
print("=" * 70)

# 加载模型
weights_path = Path(__file__).parent / "results" / "full_weights.pt"
model = load_bayesian_dllnn(weights_path, device="cpu", mc_dropout_prob=0.1)

print("\n--- 模型中所有 Dropout 层 ---")
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Dropout):
        print(f"  {name}: Dropout(p={module.p})")

print("\n--- 模型训练模式检查 ---")
print(f"  model.training = {model.training}")
print(f"  base_model.training = {model.base_model.training}")

# 切换到训练模式
model.train()
print(f"\n--- 调用 model.train() 后 ---")
print(f"  model.training = {model.training}")
print(f"  base_model.training = {model.base_model.training}")
for name, module in model.named_modules():
    if isinstance(module, torch.nn.Dropout):
        print(f"  {name}: Dropout(p={module.p}, training={module.training})")

# 构造测试输入
torch.manual_seed(42)
x = torch.randn(32, 7)
physics_pred = torch.randn(32, 1) * 7.6 + 12.7  # 原始尺度

print("\n--- 单次前向传播测试（train 模式，10次）---")
outputs = []
with torch.no_grad():
    for i in range(10):
        out, ltc = model.base_model(x, physics_pred=(physics_pred - 12.6736) / 7.6180)
        outputs.append(out)
        print(f"  Run {i+1}: out[:3] = {out.flatten()[:3].tolist()}")

outputs_tensor = torch.stack(outputs, dim=0)  # [10, 32, 1]
std_per_sample = outputs_tensor.std(dim=0).flatten()
print(f"\n--- 10次运行的 std 统计 ---")
print(f"  std.mean = {std_per_sample.mean().item():.6f}")
print(f"  std.max = {std_per_sample.max().item():.6f}")
print(f"  std.min = {std_per_sample.min().item():.6f}")

if std_per_sample.mean().item() < 1e-6:
    print("\n[失败] MC Dropout 没有产生任何随机性！")
    print("\n--- 深度诊断：直接调用 LTC 分支 ---")
    model.train()
    ltc_outputs = []
    with torch.no_grad():
        for i in range(10):
            ltc_out = model.base_model.ltc_branch(x)
            ltc_outputs.append(ltc_out)
    ltc_stack = torch.stack(ltc_outputs, dim=0)
    ltc_std = ltc_stack.std(dim=0).flatten()
    print(f"  LTC 分支 std.mean = {ltc_std.mean().item():.6f}")
    print(f"  LTC 分支 std.max = {ltc_std.max().item():.6f}")

    print("\n--- 检查 output_proj 中 Dropout 是否被调用 ---")
    # 手动检查 output_proj 的中间输出
    model.train()
    h = model.base_model.ltc_branch.input_proj(x)
    for i, ltc_cell in enumerate(model.base_model.ltc_branch.ltc_cells):
        h_zeros = torch.zeros(h.shape[0], model.base_model.ltc_branch.hidden_dim)
        h = ltc_cell(h, h_zeros, model.base_model.ltc_branch.dt)

    print(f"  LTC 输出后 h[:3] = {h.flatten()[:3].tolist()}")
    print(f"  h.requires_grad = {h.requires_grad}")

    # 手动走 output_proj
    out_proj = model.base_model.ltc_branch.output_proj
    print(f"\n  output_proj 结构:")
    for j, layer in enumerate(out_proj):
        print(f"    [{j}] {layer}")

    # 两次前向 output_proj
    with torch.no_grad():
        out1 = out_proj(h)
        out2 = out_proj(h)
        print(f"\n  output_proj 两次输出差异: {((out1 - out2).abs().max()).item():.6f}")
else:
    print("\n[成功] MC Dropout 正常工作！")
    print("  问题可能在 predict_with_uncertainty 的批量处理逻辑中")
