"""Test using GraphStore with explicit session_factory."""
import os
import sys
import tempfile

print("Step 1: imports", flush=True)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.knowledge_graph.models import Base
from app.knowledge_graph.graph_store import GraphStore

print("Step 2: setup temp DB", flush=True)
tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "test.db")
DB_URL = f"sqlite:///{db_path}"
engine = create_engine(DB_URL, future=True)
Base.metadata.create_all(engine)
factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)
print(f"Step 3: schema created at {db_path}", flush=True)

g = GraphStore()
g.add_node("material", "M-45steel", {"name": "45 steel"})
g.add_node("tool", "T-endmill-10", {"name": "Endmill D10"})
g.add_edge("T-endmill-10", "M-45steel", "SUITABLE_FOR", {"confidence": 0.9})
print("Step 4: in-memory OK, count =", g.node_count(), flush=True)

# Use session_factory explicitly
print("Step 5: calling flush_to_repository with session_factory", flush=True)
sys.stdout.flush()
result = g.flush_to_repository(session_factory=factory)
print("Step 6: flush result =", result, flush=True)

g2 = GraphStore()
print("Step 7: g2 before load =", g2.node_count(), flush=True)
g2.load_from_repository(session_factory=factory)
print("Step 8: Node count =", g2.node_count(), flush=True)

# Cleanup
engine.dispose()
os.remove(db_path)
os.rmdir(tmpdir)
print("Step 9: done", flush=True)
