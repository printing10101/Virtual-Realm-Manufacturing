"""
最小化消融 smoke test（AR-05 修复验证）

目标：快速验证 A2（λ₃=0, PINN 模式）在 AR-05 修复后不再反常优于 Full。

设计：
    - 使用 300 样本（而非默认 10,000）大幅缩短运行时间
    - stage1=3, stage2=5 极少轮数
    - 仅对比 Full vs A2
    - 验证标准：A2 的 MAE 不应显著低于 Full（反常优势应消失）

运行：
    python python/experiments/_test_ablation_smoke.py
"""

import sys
import os
import types
from pathlib import Path

# === WinSock 损坏绕过补丁（必须在 import torch 之前执行）===
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

# 添加项目路径
PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = PROJECT_ROOT / "python"
EXPERIMENTS_DIR = PYTHON_DIR / "experiments"
SCRIPTS_DIR = PROJECT_ROOT / "论文相关" / "脚本"
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(EXPERIMENTS_DIR))
sys.path.insert(0, str(SCRIPTS_DIR))

from research.training.reproducibility import set_global_seed
from experiments.config import get_config
from experiments.data_generator import SyntheticChatterDataset
from experiments.metrics import ChatterMetrics
from ablation_experiment import (
    get_ablation_specs,
    train_and_evaluate_ablation,
    load_ablation_dataset,
)


def run_smoke_test():
    """运行最小化 smoke test：Full vs A2。"""
    print("\n" + "=" * 70)
    print("AR-05 修复验证 — 最小化消融 smoke test (Full vs A2)")
    print("=" * 70)

    seed = 42
    n_samples = 300  # 极小数据集
    stage1_epochs = 3
    stage2_epochs = 5

    # === 1. 构造小数据集 ===
    print(f"\n[1/3] 构造合成数据集 (n_samples={n_samples})...")
    set_global_seed(seed)
    full_dataset = SyntheticChatterDataset(num_samples=n_samples)

    # 70/15/15 划分
    n_total = len(full_dataset)
    train_size = int(0.7 * n_total)
    val_size = int(0.15 * n_total)
    test_size = n_total - train_size - val_size

    split_generator = torch.Generator().manual_seed(seed)
    train_subset, val_subset, test_subset = torch.utils.data.random_split(
        full_dataset, [train_size, val_size, test_size], generator=split_generator
    )

    # 提取 numpy 数组
    def subset_to_arrays(subset):
        loader = DataLoader(subset, batch_size=128, shuffle=False)
        X_list, y_list, yphys_list = [], [], []
        for batch in loader:
            if len(batch) == 3:
                x, y, yp = batch
                yphys_list.append(yp.numpy())
            else:
                x, y = batch
                yphys_list.append(y.numpy())
            X_list.append(x.numpy())
            y_list.append(y.numpy())
        X = np.concatenate(X_list, axis=0).astype(np.float32)
        y = np.concatenate(y_list, axis=0).astype(np.float32).reshape(-1, 1)
        yp = np.concatenate(yphys_list, axis=0).astype(np.float32).reshape(-1, 1)
        return X, y, yp

    # 一次性提取
    X_train, y_train, yp_train = subset_to_arrays(train_subset)
    X_val, y_val, yp_val = subset_to_arrays(val_subset)
    X_test, y_test, yp_test = subset_to_arrays(test_subset)
    data = {
        "X_train": X_train, "y_train": y_train, "y_phys_train": yp_train,
        "X_val": X_val, "y_val": y_val, "y_phys_val": yp_val,
        "X_test": X_test, "y_test": y_test, "y_phys_test": yp_test,
    }
    print(f"  训练集: {len(X_train)}, 验证集: {len(X_val)}, 测试集: {len(X_test)}")

    # === 2. 运行 Full 和 A2 ===
    base_config = get_config()
    specs = get_ablation_specs()

    results = {}
    for spec_name in ["Full", "A2"]:
        print(f"\n[2/3] 运行消融配置: {spec_name} ({specs[spec_name].description})...")
        result = train_and_evaluate_ablation(
            spec=specs[spec_name],
            data=data,
            base_config=base_config,
            seed=seed,
            stage1_epochs=stage1_epochs,
            stage2_epochs=stage2_epochs,
        )
        results[spec_name] = result
        m = result.get("metrics", {})
        print(f"  MAE={m.get('mae', 'N/A'):.4f}, R²={m.get('r2', 'N/A'):.4f}, "
              f"PCC={m.get('pcc', 'N/A'):.4f}, 耗时={result.get('elapsed_sec', 'N/A')}s")

    # === 3. 验证 A2 不再反常 ===
    print("\n" + "=" * 70)
    print("[3/3] 验证结果分析")
    print("=" * 70)

    full_m = results["Full"].get("metrics", {})
    a2_m = results["A2"].get("metrics", {})

    full_mae = full_m.get("mae", float("inf"))
    a2_mae = a2_m.get("mae", float("inf"))
    full_r2 = full_m.get("r2", 0)
    a2_r2 = a2_m.get("r2", 0)
    full_pcc = full_m.get("pcc", 0)
    a2_pcc = a2_m.get("pcc", 0)

    print(f"\n  {'指标':<10} {'Full':<15} {'A2 (PINN)':<15} {'差异':<15}")
    print(f"  {'-'*55}")
    print(f"  {'MAE':<10} {full_mae:<15.4f} {a2_mae:<15.4f} {a2_mae - full_mae:+.4f}")
    print(f"  {'R²':<10} {full_r2:<15.4f} {a2_r2:<15.4f} {a2_r2 - full_r2:+.4f}")
    print(f"  {'PCC':<10} {full_pcc:<15.4f} {a2_pcc:<15.4f} {a2_pcc - full_pcc:+.4f}")

    # 验证标准：A2 不应显著优于 Full
    # "反常" 定义：A2 的 MAE 比 Full 低 20% 以上（即 A2_mae < 0.8 * Full_mae）
    # 修复后，A2 应该与 Full 相当或略差（因为缺少 L_pcc 约束）
    abnormal_threshold = 0.20
    if full_mae > 0:
        relative_diff = (full_mae - a2_mae) / full_mae
    else:
        relative_diff = 0

    print(f"\n  A2 相对 Full 的 MAE 优势: {relative_diff:+.2%}")
    print(f"  反常阈值: A2 MAE 优势 > {abnormal_threshold:.0%}")

    all_pass = True
    if relative_diff > abnormal_threshold:
        print(f"  ✗ 警告：A2 仍显著优于 Full（{relative_diff:.2%} > {abnormal_threshold:.0%}），AR-05 修复可能未完全生效")
        all_pass = False
    else:
        print(f"  ✓ 通过：A2 不再反常优于 Full，AR-05 修复验证成功")

    # 额外检查：无 NaN
    for name, m in [("Full", full_m), ("A2", a2_m)]:
        for k, v in m.items():
            if np.isnan(v) or np.isinf(v):
                print(f"  ✗ 警告：{name} 的 {k} 包含 NaN/Inf: {v}")
                all_pass = False

    print("\n" + "=" * 70)
    if all_pass:
        print("✓ Smoke test 全部通过：A2 不再反常，AR-05 修复验证成功")
    else:
        print("✗ Smoke test 存在问题，需进一步排查")
    print("=" * 70)

    return all_pass


if __name__ == "__main__":
    success = run_smoke_test()
    sys.exit(0 if success else 1)
