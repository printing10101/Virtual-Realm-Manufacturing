"""Test load via GraphPersistence directly."""
import os
import sys
import tempfile

print("Step 1: imports", flush=True)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.knowledge_graph.models import Base
from app.knowledge_graph.graph_store import GraphStore
from app.knowledge_graph.persistence import GraphPersistence

tmpdir = tempfile.mkdtemp()
db_path = os.path.join(tmpdir, "test.db")
DB_URL = f"sqlite:///{db_path}"
engine = create_engine(DB_URL, future=True)
Base.metadata.create_all(engine)
factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

g = GraphStore()
g.add_node("material", "M-45steel", {"name": "45 steel"})
g.add_node("tool", "T-endmill-10", {"name": "Endmill D10"})
g.add_edge("T-endmill-10", "M-45steel", "SUITABLE_FOR", {"confidence": 0.9})
print("Step 2: in-memory OK, count =", g.node_count(), flush=True)

persistence = GraphPersistence(session_factory=factory)
print("Step 3: flush", flush=True)
sys.stdout.flush()
result = persistence.flush_to_repository(g)
print("Step 4: flush result =", result, flush=True)

g2 = GraphStore()
print("Step 5: g2 before load =", g2.node_count(), flush=True)
sys.stdout.flush()
print("Step 6: calling load_from_repository", flush=True)
sys.stdout.flush()
result2 = persistence.load_from_repository(g2)
print("Step 7: load result =", result2, flush=True)
print("Step 8: Node count =", g2.node_count(), flush=True)

engine.dispose()
os.remove(db_path)
os.rmdir(tmpdir)
print("Step 9: done", flush=True)
