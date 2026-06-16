"""Sanity check: just import and count nodes/edges without running full import."""
import sys
sys.path.insert(0, r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python")

print("START", flush=True)

from app.knowledge_graph.graph_store import GraphStore
print("IMPORTED GraphStore", flush=True)

g = GraphStore(auto_load=False)
print(f"G created: nodes={g.node_count()}", flush=True)

g.add_node("material", "material-test", {"name": "test"})
print(f"After add: nodes={g.node_count()}", flush=True)

print("END", flush=True)
