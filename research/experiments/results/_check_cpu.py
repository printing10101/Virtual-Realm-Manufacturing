"""快速检查 v4 进程的 CPU 累计时间，判断是否在干活。"""
import ctypes
import time
import sys

PID = 5444

class FILETIME(ctypes.Structure):
    _fields_ = [("dwLowDateTime", ctypes.c_ulong),
                ("dwHighDateTime", ctypes.c_ulong)]

PROCESS_QUERY_INFORMATION = 0x1000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
kernel32 = ctypes.windll.kernel32

def get_cpu_time(pid):
    h = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION, False, pid)
    if not h:
        return None
    try:
        creation, exit_t, kernel, user = FILETIME(), FILETIME(), FILETIME(), FILETIME()
        ok = kernel32.GetProcessTimes(h, ctypes.byref(creation), ctypes.byref(exit_t),
                                      ctypes.byref(kernel), ctypes.byref(user))
        if not ok:
            return None
        # FILETIME 是 100-ns 单位
        total_100ns = (kernel.dwHighDateTime << 32) + kernel.dwLowDateTime + \
                      (user.dwHighDateTime << 32) + user.dwLowDateTime
        return total_100ns / 1e7  # 转秒
    finally:
        kernel32.CloseHandle(h)

t0 = get_cpu_time(PID)
if t0 is None:
    print("PID " + str(PID) + " not found / no access")
    sys.exit(0)

print("T0 CPU = " + str(round(t0, 2)) + "s")
print("sleep 5s ...")
time.sleep(5)
t1 = get_cpu_time(PID)
if t1 is None:
    print("PID exited during sleep")
else:
    delta = t1 - t0
    print("T1 CPU = " + str(round(t1, 2)) + "s")
    print("Delta CPU = " + str(round(delta, 3)) + "s over 5s wallclock")
    if delta > 0.5:
        print("VERDICT: ALIVE_AND_WORKING (CPU advancing)")
    elif delta > 0:
        print("VERDICT: ALIVE_BUT_IDLE (CPU barely advancing, may be waiting)")
    else:
        print("VERDICT: DEAD (no CPU advance)")
