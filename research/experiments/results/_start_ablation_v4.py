"""启动 ablation v4 实验子进程（独立进程，脱离 IDE，可跨夜运行）。

关键变更：
- 使用 DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW
  使子进程完全脱离父进程（IDE），IDE 关闭不会终止 v4
- 日志文件保持 line-buffered，便于实时监控
"""
import subprocess
import sys
import time
from pathlib import Path

WD = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")
PY = r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe"
SCRIPT = WD / "research" / "papers" / "论文相关" / "脚本" / "ablation_experiment.py"
RESULTS_DIR = WD / "research" / "experiments" / "results"

ts = time.strftime("%Y%m%d_%H%M%S")
log_path = RESULTS_DIR / f"ablation_v4_{ts}.log"
err_path = RESULTS_DIR / f"ablation_v4_{ts}.err.log"
pid_path = RESULTS_DIR / f"ablation_v4_{ts}.pid"

args = [
    PY, "-u", str(SCRIPT),
    "--dataset", "synthetic",
    "--ablations",
    "Full", "A1", "A2", "A3",
    "A4_lam0.01", "A4_lam0.05", "A4_lam0.1", "A4_lam0.5", "A4_lam1.0",
    "A6_fixed0.0", "A6_fixed0.25", "A6_fixed0.5", "A6_fixed0.75", "A6_fixed1.0",
    "A7_MLP", "A7_CNN",
    "--stage1_epochs", "30",
    "--stage2_epochs", "60",
    "--output_dir", r"research\papers\论文相关\脚本\results\ablation",
    "--resume",
]

log_f = open(log_path, "w", encoding="utf-8", buffering=1)
err_f = open(err_path, "w", encoding="utf-8", buffering=1)
# CREATE_NEW_CONSOLE (0x00000010) | CREATE_NEW_PROCESS_GROUP (0x00000200)
# 独立最小化窗口运行，比 DETACHED 更稳定（避免被系统资源回收）
# 不使用 CREATE_NO_WINDOW，让进程有窗口句柄（更稳定）
import ctypes
SW_MINIMIZE = 6
CREATE_NEW_CONSOLE_FLAGS = 0x00000010 | 0x00000200
proc = subprocess.Popen(
    args,
    cwd=str(WD),
    stdout=log_f,
    stderr=err_f,
    creationflags=CREATE_NEW_CONSOLE_FLAGS,
    stdin=subprocess.DEVNULL,
    close_fds=False,  # Windows 上 close_fds=True 与重定向冲突
    startupinfo=None,
)
# 最小化新窗口（不抢焦点）
import time
time.sleep(1)
# 通过 PowerShell 最小化（可选，简化起见略过）
pid_path.write_text(str(proc.pid), encoding="ascii")
print(f"PID={proc.pid}")
print(f"LOG={log_path}")
print(f"ERR={err_path}")
print(f"PID_FILE={pid_path}")
print(f"MODE=NEW_CONSOLE (独立窗口运行，IDE 关闭不影响)")
# 不等待，立即返回；父脚本退出后子进程继续运行
