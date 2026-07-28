"""诊断 R² 全负的根因：分析 a_lim target 的方差与分布。"""

import sys
import os
import types

# WinSock 绕过
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from data_generator import SyntheticChatterDataset, TlustyAnalyticalModel


def diagnose():
    print("=" * 60)
    print("R² 全负根因诊断")
    print("=" * 60)

    # 1. 生成 Synthetic 数据集
    ds = SyntheticChatterDataset(num_samples=1000, noise_level=0.02, seed=42)
    a_lim = ds.data['a_lim']
    a_lim_clean = ds.data['a_lim_clean']
    spindle_speed = ds.data['spindle_speed']

    print(f"\n[Synthetic 数据集] N={len(a_lim)}")
    print(f"  a_lim (带噪声): mean={a_lim.mean():.4f}, std={a_lim.std():.4f}, "
          f"min={a_lim.min():.4f}, max={a_lim.max():.4f}")
    print(f"  a_lim (无噪声): mean={a_lim_clean.mean():.4f}, std={a_lim_clean.std():.4f}, "
          f"min={a_lim_clean.min():.4f}, max={a_lim_clean.max():.4f}")
    print(f"  a_lim 动态范围 (max-min): {a_lim.max()-a_lim.min():.4f} mm")
    print(f"  a_lim 变异系数 CV: {a_lim.std()/a_lim.mean()*100:.2f}%")

    print(f"\n  主轴转速范围: {spindle_speed.min():.0f} - {spindle_speed.max():.0f} rpm")

    # 2. 分析 Tlusty 模型的 a_lim 计算
    print("\n[Tlusty 模型分析]")
    model = TlustyAnalyticalModel()
    omega_n = np.sqrt(model.stiffness / model.modal_mass)
    f_n = omega_n / (2 * np.pi)
    print(f"  固有频率 f_n = {f_n:.2f} Hz")

    # 检查 a_lim 随转速的变化
    speeds = np.linspace(1000, 10000, 100)
    a_lims = model.compute_limiting_depth(speeds)
    print(f"  a_lim 随转速变化: min={a_lims.min():.4f}, max={a_lims.max():.4f}, "
          f"范围={a_lims.max()-a_lims.min():.4f}")
    print(f"  a_lim 变异系数 CV: {a_lims.std()/a_lims.mean()*100:.2f}%")

    # 3. 关键诊断：target 方差 vs MAE
    print("\n[关键诊断]")
    target_std = a_lim.std()
    # 假设 MAE=0.374 (DL-LNN 当前结果)
    mae = 0.374
    # R² ≈ 1 - (MAE^2 * N) / (target_std^2 * N) = 1 - (MAE/target_std)^2
    # (近似，假设 MSE ≈ MAE^2)
    r2_approx = 1 - (mae / target_std) ** 2
    print(f"  target std = {target_std:.4f}")
    print(f"  模型 MAE = {mae:.4f}")
    print(f"  MAE / target_std = {mae/target_std:.2f}x  (应 < 1 才有正 R²)")
    print(f"  近似 R² ≈ {r2_approx:.4f}")
    print(f"\n  结论: {'target 方差过小，R² 必然为负' if target_std < mae else 'target 方差正常'}")

    # 4. 检查特征与 target 的相关性
    print("\n[特征-target 相关性]")
    features = ds.data['features']
    feat_names = ['n (转速)', 'f (进给)', 'ap (切深)', 'ae (切宽)',
                  'H (硬度)', 'D (直径)', 'z (齿数)']
    for i, name in enumerate(feat_names):
        corr = np.corrcoef(features[:, i], a_lim)[0, 1]
        print(f"  {name}: r = {corr:+.4f}")

    print("\n" + "=" * 60)
    print("诊断完成")
    print("=" * 60)


if __name__ == "__main__":
    diagnose()
