"""启动 FastAPI TestClient 验证关键端点（用线程超时）"""
import os
import sys
import json
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout

os.environ.setdefault("LNN_JWT_SECRET", "eval_secret_2026_32chars_min_xxxxxxxxxx")
os.environ.setdefault("LNN_BANNED_TOKENS_FILE", ".lnn_banned_tokens.json")
os.environ.setdefault("APP_ENV", "development")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))

from fastapi.testclient import TestClient
from app.main import app

c = TestClient(app)
print("=" * 60)
print("整体软件可用性评估")
print("=" * 60, flush=True)

# 0. 读取 .lnn_token
token_file = REPO / ".lnn_token"
if token_file.exists():
    token = token_file.read_text(encoding="utf-8").strip()
    print(f"\n[0] 读取 .lnn_token        -> token={token[:30]}...", flush=True)
else:
    print("! .lnn_token 不存在", flush=True)
    sys.exit(1)
AUTH = {"Authorization": f"Bearer {token}"}

executor = ThreadPoolExecutor(max_workers=1)


def hit(label, method, path, timeout=8, **kwargs):
    def _do():
        return c.request(method, path, headers=AUTH, **kwargs)

    t0 = time.perf_counter()
    fut = executor.submit(_do)
    try:
        r = fut.result(timeout=timeout)
        dt = (time.perf_counter() - t0) * 1000
        print(f"\n[{label}] {method} {path} -> {r.status_code} ({dt:.1f}ms)", flush=True)
        try:
            body = r.json()
            if isinstance(body, dict):
                keys = list(body.keys())[:8]
                print(f"    keys: {keys}", flush=True)
                for k in ("service", "version", "count", "app", "components", "env", "registered", "stats", "feature_flags", "postprocessors", "research_bridge", "knowledge_graph"):
                    if k in body:
                        v = body[k]
                        if isinstance(v, dict):
                            print(f"    {k}: {list(v.keys())[:6]}", flush=True)
                            for k2 in ("total_count", "registered", "count", "node_count", "edge_count", "status", "shadow_mode_master", "rollout", "log_files", "healthy"):
                                if k2 in v:
                                    print(f"      .{k2} = {v[k2]}", flush=True)
                        else:
                            print(f"    {k}: {v}", flush=True)
            else:
                print(f"    body type: {type(body).__name__}", flush=True)
        except Exception as e:
            print(f"    parse err: {e}", flush=True)
        return r.status_code
    except FuturesTimeout:
        dt = (time.perf_counter() - t0) * 1000
        print(f"\n[{label}] {method} {path} -> TIMEOUT ({dt:.1f}ms)", flush=True)
        return None
    except Exception as e:
        dt = (time.perf_counter() - t0) * 1000
        print(f"\n[{label}] {method} {path} -> EXC ({dt:.1f}ms): {e}", flush=True)
        return None


print("\n--- 验证 5 个关键端点 ---", flush=True)
hit("1", "GET", "/status", timeout=10)
hit("2", "POST", "/dxf/process", timeout=10, json={
    "dxf_path": "data/test_fixtures/case1_simple_box.dxf",
    "postprocessor": "gsk_980_25i",
    "user_id": "eval_user",
})
hit("3", "GET", "/knowledge-graph/stats", timeout=10)
hit("4", "GET", "/status/postprocessors", timeout=6)
hit("5", "GET", "/status/research-bridge", timeout=6)

print("\n" + "=" * 60, flush=True)
print("评估结论", flush=True)
print("=" * 60, flush=True)
