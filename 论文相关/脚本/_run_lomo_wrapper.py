"""LOMO 实验启动包装器 —— 行缓冲日志写入，避免 shell 重定向缓冲问题。

使用方式：
    python _run_lomo_wrapper.py > nul 2>&1   (Windows)
    python _run_lomo_wrapper.py              (前台，可观察启动信息)

设计：
    1. 用 sys.stdout = TeeWriter 包装，同时写到文件和真实 stdout
    2. 文件用 line buffering（newline='\n', buffering=1）
    3. 子进程用 subprocess.Popen 继承 stdout/stderr
    4. 实时读取子进程输出并写入日志
"""
import sys
import os
import time
import subprocess
from pathlib import Path
from datetime import datetime

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PYTHON_DIR = PROJECT_ROOT / "python"
LOG_PATH = PYTHON_DIR / "experiments" / "results" / "lomo_run_20260713_v2.log"

SCRIPT = Path(__file__).resolve().parent / "lomo_loco_experiment.py"

# 命令参数：与之前一致，但样本数进一步缩减以确保能完成
CMD = [
    sys.executable, "-u", str(SCRIPT),
    "--protocol", "LOMO",
    "--models", "DL-LNN",
    "--samples_per_group", "150",
    "--stage1_epochs", "30",
    "--stage2_epochs", "50",
    "--output_dir", "论文相关/脚本/results/lomo_loco",
]


def main():
    # 打开日志文件（行缓冲）
    log_file = open(str(LOG_PATH), "w", encoding="utf-8", buffering=1, newline="\n")

    def log(msg):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{ts}] {msg}"
        print(line, flush=True)
        log_file.write(line + "\n")

    log(f"启动 LOMO 包装器")
    log(f"日志文件: {LOG_PATH}")
    log(f"命令: {' '.join(CMD)}")
    log(f"工作目录: {PROJECT_ROOT}")

    # 启动子进程，stdout/stderr 直接继承（PIPE 让我们控制读取）
    proc = subprocess.Popen(
        CMD,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,  # 合并 stderr 到 stdout
        bufsize=1,                # 行缓冲
        encoding="utf-8",
        errors="replace",
    )

    log(f"子进程 PID: {proc.pid}")
    log(f"开始读取子进程输出...")

    # 实时读取子进程输出并写入日志
    line_count = 0
    last_progress_time = time.time()
    try:
        for line in iter(proc.stdout.readline, ""):
            line = line.rstrip("\n")
            if line:
                log_file.write(line + "\n")
                line_count += 1
                last_progress_time = time.time()
                # 每 50 行输出一次心跳到包装器 stdout（不会进入日志文件）
                if line_count % 50 == 0:
                    print(f"[wrapper heartbeat] 已写入 {line_count} 行", flush=True)
            # 检查子进程是否已退出
            if proc.poll() is not None:
                # 读完剩余输出
                remaining = proc.stdout.read()
                if remaining:
                    log_file.write(remaining)
                    line_count += remaining.count("\n")
                break
    except KeyboardInterrupt:
        log("[wrapper] 收到 Ctrl+C，终止子进程")
        proc.terminate()
        proc.wait(timeout=10)
    finally:
        # 检查是否长时间无输出（卡死检测）
        idle_seconds = time.time() - last_progress_time
        if idle_seconds > 300:  # 5 分钟无输出
            log(f"[警告] 子进程 {idle_seconds:.0f}s 无输出，可能卡死")

        exit_code = proc.returncode if proc.poll() is not None else -1
        log(f"子进程退出，exit_code={exit_code}, 总输出行数={line_count}")
        log_file.close()

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
