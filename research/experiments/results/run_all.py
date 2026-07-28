"""Unified launcher: runs ablation v4 then LOMO sequentially.

Both experiments share the same GPU, so they run one after another.
Each experiment uses --resume to skip completed work.

Double-click to run. DO NOT close the window.
"""
import os
import subprocess
import sys
import time
from pathlib import Path

WD = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）")
PY = r"C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe"
RESULTS_DIR = WD / "research" / "experiments" / "results"

# Force UTF-8 for all child processes
env = os.environ.copy()
env["PYTHONIOENCODING"] = "utf-8"


def run_experiment(name, args, log_suffix):
    """Run a single experiment, log to file, wait for completion."""
    ts = time.strftime("%Y%m%d_%H%M%S")
    log_path = RESULTS_DIR / f"{log_suffix}_{ts}.log"
    err_path = RESULTS_DIR / f"{log_suffix}_{ts}.err.log"

    print()
    print("=" * 60)
    print(f"  [{name}] Starting at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Log: {log_path}")
    print("=" * 60)
    print()

    log_f = open(log_path, "w", encoding="utf-8", buffering=1)
    err_f = open(err_path, "w", encoding="utf-8", buffering=1)

    proc = subprocess.Popen(
        [PY, "-u"] + args,
        cwd=str(WD),
        stdout=log_f,
        stderr=err_f,
        stdin=subprocess.DEVNULL,
        env=env,
    )

    print(f"  PID: {proc.pid}")
    print(f"  Waiting for {name} to finish...")
    print()

    try:
        proc.wait()
        rc = proc.returncode
        print()
        print(f"  [{name}] Finished at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"  Exit code: {rc}")
        if rc != 0:
            print(f"  WARNING: {name} exited with code {rc}!")
            # Show last 30 lines of err log
            if err_path.exists() and err_path.stat().st_size > 0:
                with open(err_path, "r", encoding="utf-8", errors="replace") as f:
                    lines = f.readlines()
                    print("  --- Last 30 lines of stderr ---")
                    for line in lines[-30:]:
                        print("  " + line.rstrip())
        return rc
    except KeyboardInterrupt:
        print(f"\n  Interrupted! Killing {name}...")
        proc.kill()
        return -1


def main():
    print("=" * 60)
    print("  Unified Experiment Launcher")
    print("  Order: ablation v4 -> LOMO")
    print("  Working dir: " + str(WD))
    print("  Python: " + PY)
    print("=" * 60)
    print()
    print("DO NOT CLOSE this window. You can minimize it.")
    print()

    # === Experiment 1: Ablation v4 ===
    ablation_args = [
        str(WD / "research" / "papers" / "论文相关" / "脚本" / "ablation_experiment.py"),
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

    rc1 = run_experiment("Ablation v4", ablation_args, "ablation_v4")

    if rc1 != 0:
        print()
        print("WARNING: Ablation v4 did not complete successfully (exit code {}).".format(rc1))
        print("LOMO will still run. Check the log for errors.")
        print()

    # === Experiment 2: LOMO ===
    lomo_args = [
        str(WD / "research" / "papers" / "论文相关" / "脚本" / "lomo_loco_experiment.py"),
        "--protocol", "LOMO",
        "--models", "DL-LNN",
        "--dataset", "synthetic_multi",
        "--output_dir", r"research\papers\论文相关\脚本\results\lomo_loco_ar02_full",
        "--stage1_epochs", "50",
        "--stage2_epochs", "100",
        "--physics_aware",
    ]

    rc2 = run_experiment("LOMO", lomo_args, "lomo_run")

    # === Summary ===
    print()
    print("=" * 60)
    print("  All experiments finished at " + time.strftime("%Y-%m-%d %H:%M:%S"))
    print("  Ablation v4 exit code: {}".format(rc1))
    print("  LOMO exit code: {}".format(rc2))
    print("=" * 60)

    input("\nPress Enter to close...")


if __name__ == "__main__":
    main()
