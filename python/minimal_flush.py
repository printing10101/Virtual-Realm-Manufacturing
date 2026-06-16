"""Minimal test - just flush."""
import os
import sys

print("Step 1: imports", flush=True)
from sqlalchemy import create_engine
from app.knowledge_graph.models import Base
from app.knowledge_graph.graph_store import GraphStore

print("Step 2: engine", flush=True)
DB_URL = "sqlite:///./e2e_test2.db"
if os.path.exists("./e2e_test2.db"):
    os.remove("./e2e_test2.db")
engine = create_engine(DB_URL, future=True)
Base.metadata.create_all(engine)
engine.dispose()
print("Step 3: schema created", flush=True)

print("Step 4: GraphStore", flush=True)
g = GraphStore()
g.add_node("material", "M-45steel", {"name": "45 steel"})
g.add_node("tool", "T-endmill-10", {"name": "Endmill D10"})
g.add_edge("T-endmill-10", "M-45steel", "SUITABLE_FOR", {"confidence": 0.9})
print("Step 5: in-memory OK, count =", g.node_count(), flush=True)

print("Step 6: calling flush_to_repository", flush=True)
sys.stdout.flush()
result = g.flush_to_repository()
print("Step 7: flush result =", result, flush=True)

# Cleanup
os.remove("./e2e_test2.db")
print("Step 8: done", flush=True)
