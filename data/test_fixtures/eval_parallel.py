"""分多次独立进程验证 3 个慢端点（每个用独立子进程跑）"""
import os
import sys
import time
import multiprocessing as mp
from pathlib import Path

os.environ.setdefault("LNN_JWT_SECRET", "eval_secret_2026_32chars_min_xxxxxxxxxx")
os.environ.setdefault("LNN_BANNED_TOKENS_FILE", ".lnn_banned_tokens.json")
os.environ.setdefault("APP_ENV", "development")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))


def call_endpoint(path: str, label: str) -> dict:
    """在子进程中调一个端点并返回结果。"""
    from fastapi.testclient import TestClient
    from app.main import app

    c = TestClient(app)
    token = (REPO / ".lnn_token").read_text(encoding="utf-8").strip()
    AUTH = {"Authorization": f"Bearer {token}"}

    t0 = time.perf_counter()
    try:
        r = c.get(path, headers=AUTH, timeout=20.0)
        dt = (time.perf_counter() - t0) * 1000
        out = {
            "label": label,
            "path": path,
            "status": r.status_code,
            "ms": round(dt, 1),
            "ok": r.status_code == 200,
        }
        if r.status_code == 200:
            try:
                out["body_keys"] = list(r.json().keys())[:8]
                if isinstance(r.json(), dict):
                    for k in ("count", "controllers", "service", "version", "components", "env", "health", "summary"):
                        if k in r.json():
                            v = r.json()[k]
                            if isinstance(v, dict):
                                out[f"_{k}"] = list(v.keys())[:6]
                            else:
                                out[f"_{k}"] = v
            except Exception as e:
                out["err"] = str(e)
        else:
            out["body"] = r.text[:200]
        return out
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        return {"label": label, "path": path, "ms": round(dt, 1), "ok": False, "err": str(e)}


if __name__ == "__main__":
    print("=" * 60)
    print("剩余 3 个端点独立子进程验证")
    print("=" * 60, flush=True)

    endpoints = [
        ("3", "/knowledge-graph/stats"),
        ("4", "/status/postprocessors"),
        ("5", "/status/research-bridge"),
    ]

    results = []
    for label, path in endpoints:
        print(f"\n[{label}] 启动子进程验证 {path} ...", flush=True)
        with mp.get_context("spawn").Pool(processes=1) as pool:
            async_result = pool.apply_async(call_endpoint, (path, label))
            try:
                result = async_result.get(timeout=25)
                results.append(result)
                print(f"  -> {result}", flush=True)
            except mp.TimeoutError:
                results.append({"label": label, "path": path, "ok": False, "err": "subprocess timeout"})
                print(f"  -> TIMEOUT (subprocess did not finish in 25s)", flush=True)
            except Exception as e:
                results.append({"label": label, "path": path, "ok": False, "err": str(e)})
                print(f"  -> EXC: {e}", flush=True)

    print("\n" + "=" * 60, flush=True)
    print("剩余端点验证结果", flush=True)
    print("=" * 60, flush=True)
    for r in results:
        print(f"  [{r['label']}] {r['path']} -> ok={r.get('ok', False)}, "
              f"status={r.get('status', '?')}, ms={r.get('ms', '?')}", flush=True)
