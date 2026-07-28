"""诊断 lomo_loco_experiment.py 能否正常 import 所有依赖。"""
import sys
import types
from pathlib import Path

# === WinSock 损坏绕过补丁（与 lomo_loco_experiment.py 一致）===
try:
    import _overlapped  # noqa: F401
    print("[1/8] _overlapped native OK")
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[1/8] _overlapped patched (WinSock corrupted)")

# === 路径设置（与 lomo_loco_experiment.py 一致）===
PROJECT_ROOT = Path(r"C:\Users\Lenovo\Desktop\灵境制造（上线版）")
RESEARCH_DIR = PROJECT_ROOT / "research"
EXPERIMENTS_DIR = RESEARCH_DIR / "experiments"
ENGINEERING_PYTHON_DIR = PROJECT_ROOT / "engineering" / "python"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(ENGINEERING_PYTHON_DIR))
sys.path.insert(0, str(RESEARCH_DIR))
sys.path.insert(0, str(EXPERIMENTS_DIR))
print("[2/8] sys.path OK")

import numpy as np
print("[3/8] numpy", np.__version__)

import torch
print("[4/8] torch", torch.__version__)

from research.training.reproducibility import set_global_seed
print("[5/8] research.training.reproducibility OK")

from experiments.config import get_config, ExperimentConfig
print("[6/8] experiments.config OK")

from experiments.data_generator import TlustyAnalyticalModel, build_physics_features_7d
print("[7/8] experiments.data_generator OK")

from experiments.trainer import DLLNNTrainer, BaselineTrainer, SklearnBaselineTrainer
from experiments.models import create_model
from experiments.metrics import ChatterMetrics
print("[8/8] ALL IMPORTS OK")

print("\n=== Diagnostic PASSED: script can be imported ===")
