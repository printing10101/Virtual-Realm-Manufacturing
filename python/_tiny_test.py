"""Tiny test - just check if GraphStore works at all."""
import sys
sys.path.insert(0, r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python")

print("Step 1: import GraphStore...")
from app.knowledge_graph.graph_store import GraphStore
print("Step 2: create GraphStore...")
g = GraphStore()
print(f"Step 3: nodes={g.node_count()}, edges={g.edge_count()}")
print("Step 4: add a node...")
g.add_node("material", "material-test-1", {"name": "Test"})
print(f"Step 5: nodes={g.node_count()}")
print("DONE")
