"""AR-02 实验稳健启动器（Python 版，避免 ps1/bat 编码与重定向陷阱）。

启动两个后台子进程：
1. AR-02 LOMO 实验（lomo_loco_experiment.py）
2. WPS 更新守护脚本（guard_wps_update.py）

PID 写入 .pid 文件，stdout/stderr 正确重定向到 .log 文件。
使用 subprocess.Popen + CREATE_NO_WINDOW 确保进程脱离当前会话。
"""
import os
import sys
import time
import subprocess
from pathlib import Path
from datetime import datetime

# === 路径配置 ===
SCRIPT_DIR = Path(r"C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本")
AR02_SCRIPT = SCRIPT_DIR / "lomo_loco_experiment.py"
GUARD_SCRIPT = SCRIPT_DIR / "guard_wps_update.py"
RESULTS_DIR = SCRIPT_DIR / "results"
AR02_RESULTS_DIR = RESULTS_DIR / "lomo_loco_ar02_full"

# Python 解释器（py -3.11 启动器）
PYTHON_EXE = sys.executable  # 当前 python.exe
if "pythonw" in PYTHON_EXE.lower():
    # 如果当前是 pythonw，切到 python.exe（用于诊断启动错误）
    PYTHON_EXE = PYTHON_EXE.replace("pythonw.exe", "python.exe")

# === 时间戳 ===
TS = datetime.now().strftime("%Y%m%d_%H%M%S")

# === 确保目录存在 ===
AR02_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# === AR-02 实验启动 ===
ar02_log = AR02_RESULTS_DIR / f"ar02_run_{TS}.log"
ar02_cmd = [
    PYTHON_EXE,
    str(AR02_SCRIPT),
    "--protocol", "LOMO",
    "--models", "DL-LNN",
    "--dataset", "synthetic_multi",
    "--output_dir", str(AR02_RESULTS_DIR),
    "--physics_aware",
]
print(f"[AR-02] 启动命令: {' '.join(ar02_cmd)}")
print(f"[AR-02] 日志文件: {ar02_log}")

ar02_log_f = open(ar02_log, "w", encoding="utf-8", buffering=1)
ar02_proc = subprocess.Popen(
    ar02_cmd,
    cwd=str(SCRIPT_DIR),
    stdout=ar02_log_f,
    stderr=subprocess.STDOUT,  # stderr 合并到 stdout
    creationflags=subprocess.CREATE_NO_WINDOW,
    close_fds=False,
)
print(f"[AR-02] PID={ar02_proc.pid}, 启动时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# 写 PID 文件
ar02_pid_file = RESULTS_DIR / "lomo_loco_ar02.pid"
ar02_pid_file.write_text(str(ar02_proc.pid), encoding="utf-8")

# === 守护脚本启动 ===
guard_log = RESULTS_DIR / f"guard_wps_{TS}.log"
guard_cmd = [
    PYTHON_EXE,
    str(GUARD_SCRIPT),
    "--duration", "36000",  # 10 小时
    "--log", str(guard_log),
]
print(f"\n[GUARD] 启动命令: {' '.join(guard_cmd)}")
print(f"[GUARD] 日志文件: {guard_log}")

guard_log_f = open(guard_log, "w", encoding="utf-8", buffering=1)
guard_proc = subprocess.Popen(
    guard_cmd,
    cwd=str(SCRIPT_DIR),
    stdout=guard_log_f,
    stderr=subprocess.STDOUT,
    creationflags=subprocess.CREATE_NO_WINDOW,
    close_fds=False,
)
print(f"[GUARD] PID={guard_proc.pid}, 启动时间={datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

guard_pid_file = RESULTS_DIR / "guard.pid"
guard_pid_file.write_text(str(guard_proc.pid), encoding="utf-8")

# === 等待 10 秒，确认进程没立即崩溃 ===
print("\n=== 等待 10 秒确认进程稳定... ===")
time.sleep(10)

ar02_alive = ar02_proc.poll() is None
guard_alive = guard_proc.poll() is None

print(f"\n[AR-02] PID={ar02_proc.pid}, alive={ar02_alive}, exit_code={ar02_proc.poll()}")
print(f"[GUARD] PID={guard_proc.pid}, alive={guard_alive}, exit_code={guard_proc.poll()}")

if ar02_alive and guard_alive:
    print("\n=== 启动成功！两个进程都在运行 ===")
    print(f"AR-02 日志: {ar02_log}")
    print(f"守护日志: {guard_log}")
    print(f"\nPID 文件:")
    print(f"  AR-02: {ar02_pid_file}")
    print(f"  GUARD: {guard_pid_file}")
else:
    print("\n=== 警告：进程启动后立即崩溃！ ===")
    if not ar02_alive:
        print(f"AR-02 退出码: {ar02_proc.returncode}")
        print(f"AR-02 日志内容:")
        ar02_log_f.close()
        with open(ar02_log, "r", encoding="utf-8", errors="replace") as f:
            print(f.read()[:2000])
    if not guard_alive:
        print(f"GUARD 退出码: {guard_proc.returncode}")

# 不关闭 log 文件句柄，否则子进程写入会失败
# 但本启动器进程退出后，文件句柄会自动关闭——子进程持有自己的句柄副本
ar02_log_f.close()
guard_log_f.close()
print("\n启动器退出。")
