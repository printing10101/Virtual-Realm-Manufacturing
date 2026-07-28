"""验证 ablation_experiment.py 的 import 链是否全部跑通。"""
import sys
import types
from pathlib import Path

# 模拟 ablation_experiment.py 的路径设置
PROJECT_ROOT = Path(__file__).resolve().parents[4]
EXPERIMENTS_DIR = PROJECT_ROOT / "research" / "experiments"
ENGINEERING_PYTHON_DIR = PROJECT_ROOT / "engineering" / "python"

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(ENGINEERING_PYTHON_DIR))

# WinSock 绕过补丁
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 模块加载失败，已注入空实现绕过 WinSock 损坏。")

print("[1/6] _overlapped / WinSock 绕过 OK")

from research.training.reproducibility import set_global_seed
print("[2/6] research.training.reproducibility OK")

from experiments.config import get_config, ExperimentConfig, ModelConfig
print("[3/6] experiments.config OK")

from experiments.data_generator import (
    TlustyAnalyticalModel,
    build_physics_features_7d,
    SyntheticChatterDataset,
    IndustrialChatterDataset,
    PHM2010Dataset,
)
print("[4/6] experiments.data_generator OK")

from experiments.models import create_model
print("[5/6] experiments.models OK")

from experiments.trainer import DLLNNTrainer, BaselineTrainer, SklearnBaselineTrainer, SKLEARN_BASELINE_MODELS
print("[6/6] experiments.trainer OK")

from experiments.metrics import ChatterMetrics
print("[extra] experiments.metrics OK")

print()
print("=" * 60)
print("ALL IMPORTS OK — ablation_experiment.py 可以启动")
print("=" * 60)
