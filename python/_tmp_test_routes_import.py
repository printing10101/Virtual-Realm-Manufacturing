"""临时测试：注入 _overlapped 假模块绕过 asyncio 损坏（不创建事件循环）。"""
import sys
import types as _types

# 注入 _overlapped 假模块
if "_overlapped" not in sys.modules:
    _ov = _types.ModuleType("_overlapped")
    _ov.Overlapped = type("Overlapped", (), {"__init__": lambda self, *a, **kw: None})
    _ov.NULL = 0
    _ov.INVALID_HANDLE_VALUE = -1
    _ov.OVERLAPPED_VERSION = 1
    _ov.CreateEvent = lambda *a, **kw: 0
    _ov.SetEvent = lambda *a, **kw: True
    _ov.ResetEvent = lambda *a, **kw: True
    _ov.CloseHandle = lambda *a, **kw: True
    _ov.GetQueuedCompletionStatus = lambda *a, **kw: (0, 0, 0)
    _ov.PostQueuedCompletionStatus = lambda *a, **kw: True
    _ov.RegisterWaitWithQueue = lambda *a, **kw: 0
    _ov.UnregisterWaitEx = lambda *a, **kw: True
    _ov.BindIoCompletionCallback = lambda *a, **kw: None
    _ov.CreateIoCompletionPort = lambda *a, **kw: 0
    _ov.GetOverlappedResult = lambda *a, **kw: (0, 0)
    _ov.WSARecv = lambda *a, **kw: 0
    _ov.WSASend = lambda *a, **kw: 0
    _ov.AcceptEx = lambda *a, **kw: 0
    _ov.ConnectEx = lambda *a, **kw: 0
    sys.modules["_overlapped"] = _ov
    print("_overlapped mock OK")

import asyncio
print(f"asyncio import OK")

# 不创建事件循环（避免 _overlapped 属性缺失）

sys.path.insert(0, r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python")

if "matplotlib" not in sys.modules:
    _mpl = _types.ModuleType("matplotlib")
    _mpl.use = lambda *a, **kw: None
    _mpl.rcParams = {}
    _mpl.figure = lambda *a, **kw: None
    _mpl.pyplot = _types.ModuleType("matplotlib.pyplot")
    _mpl.pyplot.figure = lambda *a, **kw: None
    _mpl.pyplot.savefig = lambda *a, **kw: None
    _mpl.pyplot.close = lambda *a, **kw: None
    _mpl.pyplot.show = lambda *a, **kw: None
    sys.modules["matplotlib"] = _mpl
    sys.modules["matplotlib.pyplot"] = _mpl.pyplot

if "slowapi" not in sys.modules:
    _slowapi = _types.ModuleType("slowapi")
    _slowapi.Limiter = type("Limiter", (), {
        "__init__": lambda self, *a, **kw: None,
        "limit": lambda self, *a, **kw: (lambda f: f),
    })
    _slowapi.RateLimitExceeded = type("RateLimitExceeded", (Exception,), {})
    _slowapi.get_remote_address = lambda req: "127.0.0.1"
    _slowapi.errors = _types.ModuleType("slowapi.errors")
    _slowapi.errors.RateLimitExceeded = _slowapi.RateLimitExceeded
    sys.modules["slowapi"] = _slowapi
    sys.modules["slowapi.errors"] = _slowapi.errors

import os
os.environ["ENVIRONMENT"] = "testing"
os.environ["LNN_AUTH_ENABLED"] = "false"
os.environ["LNN_PERMISSION_ENFORCED"] = "false"

try:
    from app.api.v1.cam_validation.routes import router
    print(f"routes OK: {len(router.routes)} routes")
    for r in router.routes:
        methods = getattr(r, "methods", set())
        path = getattr(r, "path", "?")
        print(f"  {sorted(methods) if methods else 'SUB'} {path}")
except Exception as e:
    import traceback
    print(f"routes FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
