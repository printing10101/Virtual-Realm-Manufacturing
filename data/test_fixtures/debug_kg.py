"""直接测试 knowledge-graph/stats 不通过 TestClient，而是直接调用服务函数"""
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("LNN_JWT_SECRET", "eval_secret_2026_32chars_min_xxxxxxxxxx")
os.environ.setdefault("LNN_BANNED_TOKENS_FILE", ".lnn_banned_tokens.json")
os.environ.setdefault("APP_ENV", "development")

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "python"))
sys.path.insert(0, str(REPO))

print("Step 1: import", flush=True)
from app.knowledge_graph.graph_store import GraphStore
print("Step 2: GraphStore imported", flush=True)
t0 = time.perf_counter()
gs = GraphStore(auto_load=False)
dt = (time.perf_counter() - t0) * 1000
print(f"Step 3: GraphStore(auto_load=False) ok, {dt:.1f}ms", flush=True)

print("Step 4: add some test nodes", flush=True)
gs.add_node("material", "M-45steel", {"name": "45 steel"})
gs.add_node("tool", "T-endmill-10", {"name": "Endmill D10"})
gs.add_edge("T-endmill-10", "M-45steel", "SUITABLE_FOR", {"confidence": 0.9})
print(f"Step 5: graph has {gs._graph.number_of_nodes()} nodes, {gs._graph.number_of_edges()} edges", flush=True)

print("Step 6: call stats()", flush=True)
from app.knowledge_graph.query_api import KnowledgeGraphQueryAPI
api = KnowledgeGraphQueryAPI(gs)
t0 = time.perf_counter()
stats = api.stats()
dt = (time.perf_counter() - t0) * 1000
print(f"Step 7: stats ok, {dt:.1f}ms", flush=True)
print(f"   result: {stats}", flush=True)

print("Step 8: now try with auto_load=True", flush=True)
t0 = time.perf_counter()
gs2 = GraphStore()
dt = (time.perf_counter() - t0) * 1000
print(f"Step 9: GraphStore() with auto_load=True ok, {dt:.1f}ms", flush=True)
print(f"   graph has {gs2._graph.number_of_nodes()} nodes, {gs2._graph.number_of_edges()} edges", flush=True)
