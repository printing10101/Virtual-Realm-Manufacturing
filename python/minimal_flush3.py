"""Minimal test - using session_factory like existing tests."""
import os
import sys

print("Step 1: imports", flush=True)
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.knowledge_graph.models import Base
from app.knowledge_graph.graph_store import GraphStore
from app.knowledge_graph.persistence import GraphPersistence

print("Step 2: engine", flush=True)
DB_URL = "sqlite:///./e2e_test4.db"
if os.path.exists("./e2e_test4.db"):
    os.remove("./e2e_test4.db")
engine = create_engine(DB_URL, future=True)
Base.metadata.create_all(engine)
print("Step 3: schema created", flush=True)
factory = sessionmaker(bind=engine, expire_on_commit=False, future=True)

g = GraphStore()
g.add_node("material", "M-45steel", {"name": "45 steel"})
g.add_node("tool", "T-endmill-10", {"name": "Endmill D10"})
g.add_edge("T-endmill-10", "M-45steel", "SUITABLE_FOR", {"confidence": 0.9})
print("Step 4: in-memory OK, count =", g.node_count(), flush=True)

persistence = GraphPersistence(session_factory=factory)
print("Step 5: GraphPersistence created", flush=True)

print("Step 6: calling persistence.flush_to_repository", flush=True)
sys.stdout.flush()
result = persistence.flush_to_repository(g)
print("Step 7: flush result =", result, flush=True)

# Cleanup
engine.dispose()
os.remove("./e2e_test4.db")
print("Step 8: done", flush=True)
