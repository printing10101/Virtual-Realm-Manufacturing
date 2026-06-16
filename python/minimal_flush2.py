"""Minimal test - just GraphPersistence directly."""
import os
import sys

print("Step 1: imports", flush=True)
from sqlalchemy import create_engine
from app.knowledge_graph.models import Base
from app.knowledge_graph.graph_store import GraphStore
from app.knowledge_graph.persistence import GraphPersistence

print("Step 2: engine", flush=True)
DB_URL = "sqlite:///./e2e_test3.db"
if os.path.exists("./e2e_test3.db"):
    os.remove("./e2e_test3.db")
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

print("Step 6: creating GraphPersistence directly", flush=True)
os.environ["DB_URL"] = DB_URL
persistence = GraphPersistence()
print("Step 7: GraphPersistence created", flush=True)

print("Step 8: calling persistence.flush_to_repository", flush=True)
sys.stdout.flush()
result = persistence.flush_to_repository(g)
print("Step 9: flush result =", result, flush=True)

# Cleanup
os.remove("./e2e_test3.db")
print("Step 10: done", flush=True)
