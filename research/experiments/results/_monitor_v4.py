"""监控 ablation v4 实验进程状态和日志进度。"""
import os
import sys
import time
import ctypes
from pathlib import Path

PID = 5444
LOG = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\ablation_v4_20260718_153922.log")
ERR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\ablation_v4_20260718_153922.err.log")
CKPT_DIR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\ablation")

now = time.strftime("%Y-%m-%d %H:%M:%S")
print("=== ablation v4 monitor @ " + now + " ===")
print("PID=" + str(PID))

# 1. 进程状态
PROCESS_QUERY_INFORMATION = 0x1000
STILL_ACTIVE = 259
kernel32 = ctypes.windll.kernel32
h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, PID)
if h:
    exit_code = ctypes.c_ulong()
    kernel32.GetExitCodeProcess(h, ctypes.byref(exit_code))
    kernel32.CloseHandle(h)
    if exit_code.value == STILL_ACTIVE:
        print("STATUS=ALIVE")
    else:
        print("STATUS=EXITED  exit_code=" + str(exit_code.value))
else:
    print("STATUS=NOT_FOUND  (process does not exist or no access)")

# 2. 错误日志
if ERR.exists():
    err_size = ERR.stat().st_size
    print("")
    print("--- ERR LOG (" + str(err_size) + " bytes) ---")
    if err_size > 0:
        for enc in ["utf-8", "gbk"]:
            try:
                with open(ERR, "r", encoding=enc) as f:
                    content = f.read()
                if content.strip():
                    print(content[-2000:])
                break
            except UnicodeDecodeError:
                continue
    else:
        print("(empty)")
else:
    print("")
    print("ERR log not found: " + str(ERR))

# 3. 主日志末尾
if LOG.exists():
    log_size = LOG.stat().st_size
    print("")
    print("--- LOG TAIL (" + str(log_size) + " bytes) ---")
    with open(LOG, "rb") as f:
        f.seek(max(0, log_size - 4000))
        data = f.read()
    for enc in ["utf-8", "gbk"]:
        try:
            text = data.decode(enc)
            print(text)
            break
        except UnicodeDecodeError:
            continue
else:
    print("LOG not found: " + str(LOG))

# 4. checkpoint 文件
print("")
print("--- CHECKPOINT FILES in " + str(CKPT_DIR) + " ---")
if CKPT_DIR.exists():
    files = sorted(CKPT_DIR.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True)
    if not files:
        print("(no checkpoint files yet)")
    else:
        for f in files[:10]:
            mtime = time.strftime("%m-%d %H:%M:%S", time.localtime(f.stat().st_mtime))
            size = f.stat().st_size
            print("  " + mtime + "  " + str(size).rjust(8) + " B  " + f.name)
else:
    print("(checkpoint dir does not exist yet)")
