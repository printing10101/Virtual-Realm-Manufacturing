"""Launch ablation v4 experiment. Double-click to run."""
import os
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

print("=" * 60)
print("  ablation v4 launcher")
print(f"  Working dir: {WD}")
print(f"  Python: {PY}")
print(f"  Log: {log_path}")
print(f"  Resume mode: skipping Full + A1")
print(f"  Estimated time: ~80 hours")
print("=" * 60)
print()
print("DO NOT CLOSE this window. You can minimize it.")
print()

log_f = open(log_path, "w", encoding="utf-8", buffering=1)
err_f = open(err_path, "w", encoding="utf-8", buffering=1)

env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"

proc = subprocess.Popen(
    args,
    cwd=str(WD),
    stdout=log_f,
    stderr=err_f,
    stdin=subprocess.DEVNULL,
    env=env,
)

pid_path.write_text(str(proc.pid), encoding="ascii")
print(f"  PID: {proc.pid}")
print(f"  Started at: {time.strftime('%Y-%m-%d %H:%M:%S')}")
print()

# Wait for process to finish
try:
    proc.wait()
    print()
    print("=" * 60)
    print(f"  Experiment finished at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Exit code: {proc.returncode}")
    print(f"  Log: {log_path}")
    print("=" * 60)
except KeyboardInterrupt:
    print("\nInterrupted. Killing process...")
    proc.kill()

input("\nPress Enter to close...")
