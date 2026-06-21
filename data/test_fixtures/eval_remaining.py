"""3 个慢端点独立验证（每个端点写到单独文件）"""
import os
import sys
import time
import json
from pathlib import Path

os.environ.setdefault("LNN_JWT_SECRET", "eval_secret_2026_32chars_min_xxxxxxxxxx")
os.environ.setdefault("LNN_BANNED_TOKENS_FILE", ".lnn_banned_tokens.json")
os.environ.setdefault("APP_ENV", "development")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
token = (REPO / ".lnn_token").read_text(encoding="utf-8").strip()
AUTH = {"Authorization": f"Bearer {token}"}

results = {}

# 3. /knowledge-graph/stats
print("[3] GET /knowledge-graph/stats (may take 10-20s due to DB load)...", flush=True)
t0 = time.perf_counter()
try:
    r = c.get("/knowledge-graph/stats", headers=AUTH, timeout=30.0)
    dt = (time.perf_counter() - t0) * 1000
    results["3"] = {"status": r.status_code, "ms": round(dt, 1)}
    if r.status_code == 200:
        d = r.json()
        results["3"]["body"] = d
        print(f"  -> {r.status_code} ({dt:.1f}ms), keys={list(d.keys())[:6]}", flush=True)
    else:
        results["3"]["body"] = r.text[:200]
        print(f"  -> {r.status_code} ({dt:.1f}ms), body={r.text[:200]}", flush=True)
except Exception as e:
    dt = (time.perf_counter() - t0) * 1000
    results["3"] = {"status": "EXC", "ms": round(dt, 1), "err": str(e)}
    print(f"  -> EXC ({dt:.1f}ms): {e}", flush=True)

# 4. /status/postprocessors
print("\n[4] GET /status/postprocessors...", flush=True)
t0 = time.perf_counter()
try:
    r = c.get("/status/postprocessors", headers=AUTH, timeout=10.0)
    dt = (time.perf_counter() - t0) * 1000
    results["4"] = {"status": r.status_code, "ms": round(dt, 1)}
    if r.status_code == 200:
        results["4"]["body"] = r.json()
        print(f"  -> {r.status_code} ({dt:.1f}ms)", flush=True)
    else:
        results["4"]["body"] = r.text[:200]
        print(f"  -> {r.status_code} ({dt:.1f}ms)", flush=True)
except Exception as e:
    dt = (time.perf_counter() - t0) * 1000
    results["4"] = {"status": "EXC", "ms": round(dt, 1), "err": str(e)}
    print(f"  -> EXC ({dt:.1f}ms): {e}", flush=True)

# 5. /status/research-bridge
print("\n[5] GET /status/research-bridge...", flush=True)
t0 = time.perf_counter()
try:
    r = c.get("/status/research-bridge", headers=AUTH, timeout=10.0)
    dt = (time.perf_counter() - t0) * 1000
    results["5"] = {"status": r.status_code, "ms": round(dt, 1)}
    if r.status_code == 200:
        d = r.json()
        results["5"]["body"] = d
        print(f"  -> {r.status_code} ({dt:.1f}ms), keys={list(d.keys())[:6]}", flush=True)
    else:
        results["5"]["body"] = r.text[:200]
        print(f"  -> {r.status_code} ({dt:.1f}ms)", flush=True)
except Exception as e:
    dt = (time.perf_counter() - t0) * 1000
    results["5"] = {"status": "EXC", "ms": round(dt, 1), "err": str(e)}
    print(f"  -> EXC ({dt:.1f}ms): {e}", flush=True)

# 写入结果
out_path = REPO / "data" / "test_fixtures" / "eval_remaining_results.json"
out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
print(f"\n结果已写入: {out_path}", flush=True)
