"""诊断 AR-02 启动状态——检查文件、进程、checkpoint。"""
import os
import sys
import time
import psutil
from pathlib import Path
from datetime import datetime

RESULTS_DIR = Path(r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results")
AR02_DIR = RESULTS_DIR / "lomo_loco_ar02_full"
CKPT = AR02_DIR / "lomo_ckpt_DL-LNN_physics_aware.json"
AR02_LOG = AR02_DIR / "ar02_run_20260719_203451.log"
GUARD_LOG = RESULTS_DIR / "guard_wps_20260719_203451.log"

print(f"=== 当前时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===\n")

# === 1. 进程状态 ===
print("=== 1. 进程状态 ===")
AR02_PID = 29356
GUARD_PID = 27756
for name, pid in [("AR-02", AR02_PID), ("GUARD", GUARD_PID)]:
    try:
        p = psutil.Process(pid)
        cpu = p.cpu_times()
        mem = p.memory_info().rss / 1024 / 1024
        print(f"{name} PID={pid}: ALIVE")
        print(f"  名称: {p.name()}")
        print(f"  启动: {datetime.fromtimestamp(p.create_time()).strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  CPU: user={cpu.user:.1f}s, sys={cpu.system:.1f}s")
        print(f"  内存: {mem:.0f} MB")
        print(f"  线程数: {p.num_threads()}")
        try:
            cmd = p.cmdline()
            print(f"  命令: {' '.join(cmd[:3])}...")
        except (psutil.AccessDenied, psutil.NoSuchProcess):
            pass
    except psutil.NoSuchProcess:
        print(f"{name} PID={pid}: DEAD")
    print()

# === 2. AR-02 结果目录 ===
print("=== 2. AR-02 结果目录 ===")
if AR02_DIR.exists():
    files = list(AR02_DIR.iterdir())
    print(f"目录存在: {AR02_DIR}")
    print(f"文件数: {len(files)}")
    for f in sorted(files, key=lambda x: x.stat().st_mtime, reverse=True):
        s = f.stat()
        mtime = datetime.fromtimestamp(s.st_mtime).strftime('%Y-%m-%d %H:%M:%S')
        print(f"  {f.name}: {s.st_size} bytes, mtime={mtime}")
else:
    print(f"目录不存在: {AR02_DIR}")

# === 3. AR-02 日志 ===
print("\n=== 3. AR-02 日志 ===")
if AR02_LOG.exists():
    s = AR02_LOG.stat()
    print(f"日志存在: {AR02_LOG.name}, {s.st_size} bytes, mtime={datetime.fromtimestamp(s.st_mtime)}")
    if s.st_size > 0:
        print("日志内容（最后 30 行）:")
        with open(AR02_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in lines[-30:]:
                print(f"  {line.rstrip()}")
else:
    print(f"日志不存在: {AR02_LOG}")

# === 4. Checkpoint ===
print("\n=== 4. Checkpoint ===")
if CKPT.exists():
    s = CKPT.stat()
    print(f"Checkpoint 存在: {s.st_size} bytes, mtime={datetime.fromtimestamp(s.st_mtime)}")
    import json
    with open(CKPT, "r", encoding="utf-8") as f:
        data = json.load(f)
    print(f"已完成 fold 数: {len(data['completed_folds'])}/{data['total_folds']}")
    print(f"保存时间: {data['saved_at']}")
    for fold in data['completed_folds']:
        print(f"  - {fold['test_material']}: MAE={fold['mae']:.3f}, PCC={fold['pcc']:.3f}")
else:
    print(f"Checkpoint 不存在: {CKPT}")

# === 5. 守护脚本日志 ===
print("\n=== 5. 守护脚本日志 ===")
if GUARD_LOG.exists():
    s = GUARD_LOG.stat()
    print(f"守护日志存在: {s.st_size} bytes")
    if s.st_size > 0:
        print("内容（最后 10 行）:")
        with open(GUARD_LOG, "r", encoding="utf-8", errors="replace") as f:
            for line in f.readlines()[-10:]:
                print(f"  {line.rstrip()}")
else:
    print(f"守护日志不存在: {GUARD_LOG}")
    # 看看 results 目录有没有任何 guard 相关文件
    guard_files = list(RESULTS_DIR.glob("guard*"))
    print(f"results 目录下 guard* 文件: {[f.name for f in guard_files]}")

print(f"\n=== 诊断完成: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} ===")
