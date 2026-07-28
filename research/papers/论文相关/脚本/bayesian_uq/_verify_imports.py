"""一次性验证所有外部依赖和接口对接是否正确。

只验证 import 和接口签名，不实际训练或加载模型权重。
"""
import sys
import types
from pathlib import Path

# === WinSock 损坏绕过补丁（必须在 import torch 之前）===
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 模块加载失败，已注入空实现绕过 WinSock 损坏。")

# === 路径设置 ===
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
ABLATION_DIR = PROJECT_ROOT / "research" / "papers" / "论文相关" / "脚本"
BAYESIAN_DIR = PROJECT_ROOT / "research" / "papers" / "论文相关" / "脚本" / "bayesian_uq"

for p in [str(PROJECT_ROOT), str(ENGINEERING_PYTHON_DIR),
          str(RESEARCH_DIR), str(EXPERIMENTS_DIR),
          str(ABLATION_DIR), str(BAYESIAN_DIR)]:
    if p not in sys.path:
        sys.path.insert(0, p)

import inspect


def verify():
    print("=" * 70)
    print("贝叶斯 UQ 路线 import 与接口对接验证")
    print("=" * 70)
    print(f"PROJECT_ROOT = {PROJECT_ROOT}")
    print()

    # === 1. 主实验模块 ===
    print("[1/5] 验证主实验模块...")
    try:
        from research.training.reproducibility import set_global_seed
        from experiments.config import get_config, ExperimentConfig, ModelConfig
        from experiments.data_generator import (
            TlustyAnalyticalModel,
            build_physics_features_7d,
            SyntheticChatterDataset,
        )
        from experiments.models import DLLNNWithPhysics, create_model
        from experiments.trainer import DLLNNTrainer
        from experiments.metrics import ChatterMetrics
        from experiments.losses import PCC_Loss
        print("  [OK] research.training.reproducibility.set_global_seed")
        print("  [OK] experiments.config.get_config / ExperimentConfig / ModelConfig")
        print("  [OK] experiments.data_generator (TlustyAnalyticalModel 等)")
        print("  [OK] experiments.models.DLLNNWithPhysics")
        print("  [OK] experiments.trainer.DLLNNTrainer")
        print("  [OK] experiments.metrics.ChatterMetrics")
        print("  [OK] experiments.losses.PCC_Loss")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False

    # === 2. ablation_experiment 接口 ===
    print()
    print("[2/5] 验证 ablation_experiment 接口...")
    try:
        from ablation_experiment import (
            get_ablation_specs,
            load_ablation_dataset,
            _SimpleDataset,
        )
        sig = inspect.signature(load_ablation_dataset)
        print(f"  [OK] load_ablation_dataset signature: {sig}")
        sig2 = inspect.signature(_SimpleDataset.__init__)
        print(f"  [OK] _SimpleDataset.__init__ signature: {sig2}")
        specs = get_ablation_specs()
        print(f"  [OK] get_ablation_specs 返回 {len(specs)} 个配置")
        assert "Full" in specs, "Full 配置必须存在"
        print(f"  [OK] 'Full' 配置存在: {specs['Full'].description[:50]}...")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False

    # === 3. lomo_loco_experiment 接口 ===
    print()
    print("[3/5] 验证 lomo_loco_experiment 接口...")
    try:
        from lomo_loco_experiment import (
            MATERIALS_CONFIG,
            CONDITIONS_CONFIG,
            LomoLocoDataset,
        )
        print(f"  [OK] MATERIALS_CONFIG keys: {list(MATERIALS_CONFIG.keys())}")
        print(f"  [OK] CONDITIONS_CONFIG keys: {list(CONDITIONS_CONFIG.keys())}")
        sig = inspect.signature(LomoLocoDataset.__init__)
        print(f"  [OK] LomoLocoDataset.__init__ signature: {sig}")
        # 确认 ID/OOD 划分中的材料都存在
        for m in ["45_Steel", "304_SS", "6061-T6", "TC4", "HRC52"]:
            assert m in MATERIALS_CONFIG, f"材料 {m} 不在 MATERIALS_CONFIG 中"
        print("  [OK] ID/OOD 材料划分所需材料均存在")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False

    # === 4. 贝叶斯包装器 ===
    print()
    print("[4/5] 验证 bayesian_dllnn_wrapper 接口...")
    try:
        from bayesian_dllnn_wrapper import BayesianDLLNNWrapper, load_bayesian_dllnn
        sig1 = inspect.signature(BayesianDLLNNWrapper.__init__)
        sig2 = inspect.signature(load_bayesian_dllnn)
        sig3 = inspect.signature(BayesianDLLNNWrapper.predict_with_uncertainty)
        sig4 = inspect.signature(BayesianDLLNNWrapper.predict_batch)
        print(f"  [OK] BayesianDLLNNWrapper.__init__: {sig1}")
        print(f"  [OK] load_bayesian_dllnn: {sig2}")
        print(f"  [OK] predict_with_uncertainty: {sig3}")
        print(f"  [OK] predict_batch: {sig4}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False

    # === 5. trainer 关键属性 ===
    print()
    print("[5/5] 验证 trainer 关键属性（不实例化）...")
    try:
        from experiments.trainer import DLLNNTrainer
        # 检查类源码中是否定义了所需属性
        src = inspect.getsource(DLLNNTrainer)
        for attr in ["target_mean", "target_std", "best_val_loss",
                     "def denormalize", "def _compute_target_stats",
                     "def train_stage1", "def train_stage2"]:
            assert attr in src, f"trainer.py 缺少: {attr}"
            print(f"  [OK] DLLNNTrainer 含: {attr}")
    except Exception as e:
        print(f"  [FAIL] {e}")
        return False

    print()
    print("=" * 70)
    print("所有 import 与接口对接验证通过！")
    print("=" * 70)
    print()
    print("待运行（需等待 v4 消融实验结束、GPU 空闲后）:")
    print("  1. python research/papers/论文相关/脚本/bayesian_uq/rerun_full_save_weights.py")
    print("     → 生成 results/full_weights.pt")
    print("  2. python research/papers/论文相关/脚本/bayesian_uq/bayesian_uq_experiment.py")
    print("     → 生成 results/bayesian_uq_results.json + 图表 + 报告")
    return True


if __name__ == "__main__":
    ok = verify()
    sys.exit(0 if ok else 1)
