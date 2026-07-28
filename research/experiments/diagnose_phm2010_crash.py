"""诊断 PHM2010 崩溃：测试先导入 run_experiment.py 是否触发冲突。"""
import sys
import os
import types

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

try:
    import _overlapped  # noqa: F401
except OSError:
    _patch = types.ModuleType("_overlapped")
    _patch.Overlapped = type("Overlapped", (), {})
    sys.modules["_overlapped"] = _patch
    print("[warn] _overlapped 补丁已注入。", flush=True)

sys.path.insert(0, "python")
sys.path.insert(0, "python/experiments")

print("步骤1: 导入 run_experiment.py（触发重型导入）...", flush=True)
from experiments.run_experiment import run_single_dataset_experiment
print("  导入成功。", flush=True)

print("\n步骤2: 导入 PHM2010Dataset...", flush=True)
from experiments.data_generator import PHM2010Dataset
print("  导入成功。", flush=True)

print("\n步骤3: 实例化 PHM2010Dataset(num_samples=300)...", flush=True)
try:
    ds = PHM2010Dataset(num_samples=300, window_size=500, noise_level=0.05)
    print(f"  OK: {len(ds)} samples, shape: {ds.data['features'].shape}", flush=True)
    del ds
    import gc
    gc.collect()
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\n步骤4: 实例化 PHM2010Dataset + DataLoader 迭代...", flush=True)
try:
    from torch.utils.data import DataLoader
    ds = PHM2010Dataset(num_samples=300, window_size=500, noise_level=0.05)
    loader = DataLoader(ds, batch_size=32, shuffle=False)
    for i, batch in enumerate(loader):
        if i == 0:
            print(f"  batch {i}: types={[type(x).__name__ for x in batch]}, shapes={[x.shape if hasattr(x,'shape') else x for x in batch]}", flush=True)
        if i >= 2:
            break
    print("  DataLoader 迭代成功。", flush=True)
except Exception as e:
    print(f"  FAILED: {type(e).__name__}: {e}", flush=True)
    import traceback
    traceback.print_exc()

print("\n诊断完成。", flush=True)
