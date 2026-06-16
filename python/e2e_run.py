"""End-to-end acceptance script for M1.2."""
import os
import sys
from sqlalchemy import create_engine
from app.knowledge_graph.models import Base
from app.knowledge_graph.graph_store import GraphStore

DB_URL = os.environ.get("DB_URL", "sqlite:///./e2e_test.db")
print("DB_URL:", DB_URL, flush=True)

engine = create_engine(DB_URL, future=True)
Base.metadata.create_all(engine)
engine.dispose()
print("Schema initialized", flush=True)

g = GraphStore()
g.add_node("material", "M-45steel", {"name": "45 steel"})
g.add_node("tool", "T-endmill-10", {"name": "Endmill D10"})
g.add_edge("T-endmill-10", "M-45steel", "SUITABLE_FOR", {"confidence": 0.9})
print("In-memory nodes:", g.node_count(), flush=True)
print("flush stats:", g.flush_to_repository(), flush=True)

g2 = GraphStore()
print("g2 node_count (before load):", g2.node_count(), flush=True)
g2.load_from_repository()
print("Node count:", g2.node_count(), flush=True)

# 清理
try:
    if DB_URL.startswith("sqlite:///"):
        db_path = DB_URL.replace("sqlite:///", "", 1)
        if os.path.exists(db_path):
            os.remove(db_path)
            print("Cleaned up:", db_path, flush=True)
except Exception as e:
    print("Cleanup error:", e, flush=True)
