"""Smoke test script to run the importer and check counts."""
import sys
import os
# Add the python directory to path
sys.path.insert(0, r"c:\Users\Lenovo\Desktop\灵境制造（上线版）\python")

from app.knowledge_graph.importer.json_importer import import_all

r = import_all(flush_to_db=False)
print("=" * 60)
print(f"Total nodes: {r.total_nodes}")
print(f"Total edges: {r.total_edges}")
print("=" * 60)
print("Materials:", r.materials.success, "dup:", r.materials.duplicate, "fail:", r.materials.failed)
print("Tools:", r.tools.success, "dup:", r.tools.duplicate, "fail:", r.tools.failed)
print("Machines:", r.machines.success, "dup:", r.machines.duplicate, "fail:", r.machines.failed)
print("Process rules:", r.process_rules.success, "dup:", r.process_rules.duplicate, "fail:", r.process_rules.failed)
print("=" * 60)
print("Overall success:", r.overall_success)
print("Message:", r.overall_message)
