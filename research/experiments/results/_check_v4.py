"""Check unified launcher status."""
import ctypes
import time
from pathlib import Path

PID = 8776
LOG = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\ablation_v4_20260719_202211.log")
ERR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\ablation_v4_20260719_202211.err.log")
CKPT_DIR = Path(r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\ablation")

print("=== status @ " + time.strftime("%Y-%m-%d %H:%M:%S") + " ===")
print("PID=" + str(PID))

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
    print("STATUS=NOT_FOUND")

if ERR.exists() and ERR.stat().st_size > 0:
    print("\n--- ERR ---")
    with open(ERR, "r", encoding="utf-8", errors="replace") as f:
        print(f.read()[-2000:])

if LOG.exists():
    size = LOG.stat().st_size
    print("\n--- LOG (" + str(size) + " bytes) ---")
    with open(LOG, "rb") as f:
        f.seek(max(0, size - 5000))
        data = f.read()
    print(data.decode("utf-8", errors="replace"))

if CKPT_DIR.exists():
    import json
    ckpt = CKPT_DIR / "ablation_checkpoint_synthetic.json"
    if ckpt.exists():
        with open(ckpt, "r", encoding="utf-8") as f:
            d = json.load(f)
        completed = list(d.get("completed", {}).keys())
        print("\n--- CHECKPOINT: " + str(len(completed)) + "/16 ---")
        print("  " + ", ".join(completed))
