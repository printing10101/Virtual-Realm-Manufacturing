"""检查 DLLNNWithPhysics 模型的 Dropout 层布局."""
import sys, types
from pathlib import Path

# WinSock 绕过
try:
    import _overlapped  # noqa
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch

import torch
import torch.nn as nn

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

from experiments.models import DLLNNWithPhysics

# 构造与权重文件一致的模型
ckpt = torch.load(
    PROJECT_ROOT / "research/papers/论文相关/脚本/bayesian_uq/results/full_weights.pt",
    map_location="cpu", weights_only=False,
)
cfg = ckpt["config"]
print("config:", cfg)

model = DLLNNWithPhysics(
    input_dim=cfg["input_dim"],
    hidden_dim=cfg["hidden_dim"],
    num_layers=cfg["num_layers"],
    output_dim=cfg["output_dim"],
    dt=cfg["dt"],
    dropout=cfg["dropout"],
)
model.load_state_dict(ckpt["model_state_dict"])

print("\n=== 模型中所有 Dropout 层 ===")
for name, module in model.named_modules():
    if isinstance(module, nn.Dropout):
        print(f"  {name}: Dropout(p={module.p})")
    elif "drop" in name.lower():
        print(f"  {name}: {module}")

print("\n=== ltc_branch 子模块 ===")
if hasattr(model, "ltc_branch"):
    for name, module in model.ltc_branch.named_modules():
        print(f"  ltc_branch.{name}: {type(module).__name__}")
        if isinstance(module, (nn.Dropout, nn.Identity)):
            print(f"    -> {module}")

print("\n=== 完整模型结构（前 30 行）===")
print(model)
