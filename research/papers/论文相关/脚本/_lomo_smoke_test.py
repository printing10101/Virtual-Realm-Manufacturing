"""LOMO 快速烟雾测试 —— 验证 AR-05 修复后代码能否正常完成一个 fold。

参数极小：20 样本/组 × 5 材料 × 9 工况 = 900 样本，3+3 epoch。
预期耗时：< 2 分钟。
若能完成 Fold 1，说明代码可运行，可启动正式实验。
"""
import sys
import os
import time
import types
from pathlib import Path

# WinSock 绕过补丁
try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 模块加载失败，已注入空实现绕过 WinSock 损坏。")

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = PROJECT_ROOT / "python"
EXPERIMENTS_DIR = PYTHON_DIR / "experiments"
sys.path.insert(0, str(PYTHON_DIR))
sys.path.insert(0, str(EXPERIMENTS_DIR))

# 直接 import 内部函数，避免 argparse 等开销
sys.argv = [
    "lomo_smoke_test.py",
    "--protocol", "LOMO",
    "--models", "DL-LNN",
    "--samples_per_group", "20",
    "--stage1_epochs", "3",
    "--stage2_epochs", "3",
    "--baseline_epochs", "3",
    "--output_dir", "论文相关/脚本/results/lomo_smoke_test",
]

print(f"[smoke test] 开始: {time.strftime('%H:%M:%S')}")
print(f"[smoke test] 参数: 20 样本/组, 3+3 epoch")
print(f"[smoke test] 预期: < 2 分钟完成 Fold 1")
sys.stdout.flush()

t0 = time.time()
try:
    # 直接运行 lomo_loco_experiment.py 的 main
    script_path = Path(__file__).resolve().parent / "lomo_loco_experiment.py"
    import runpy
    runpy.run_path(str(script_path), run_name="__main__")
    print(f"\n[smoke test] ✓ 完成，耗时 {time.time()-t0:.1f}s")
except SystemExit as e:
    print(f"\n[smoke test] SystemExit: code={e.code}, 耗时 {time.time()-t0:.1f}s")
except Exception as e:
    import traceback
    print(f"\n[smoke test] ✗ 失败: {e}")
    traceback.print_exc()
    print(f"\n[smoke test] 耗时 {time.time()-t0:.1f}s")
