import json
import os
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class TraceNode:
    node_id: str
    task_id: str
    parent_ids: list[str] = field(default_factory=list)
    hypothesis: str = ""
    reason: str = ""
    result: dict = field(default_factory=dict)
    validation_result: dict = field(default_factory=dict)
    metrics: dict = field(default_factory=dict)
    feedback: str = ""
    is_sota: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ProcessTrace:
    def __init__(self, storage_dir: str = "traces"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self.nodes: dict[str, TraceNode] = {}

    def add_node(self, node: TraceNode, parent_ids: list[str] | None = None):
        if parent_ids is not None:
            node.parent_ids = parent_ids
        self.nodes[node.node_id] = node

    def get_node(self, node_id: str) -> Optional[TraceNode]:
        return self.nodes.get(node_id)

    def update_node(
        self,
        node_id: str,
        result: dict | None = None,
        validation_result: dict | None = None,
        metrics: dict | None = None,
        feedback: str | None = None,
        is_sota: bool | None = None,
    ):
        node = self.nodes.get(node_id)
        if not node:
            return
        if result is not None:
            node.result = result
        if validation_result is not None:
            node.validation_result = validation_result
        if metrics is not None:
            node.metrics = metrics
        if feedback is not None:
            node.feedback = feedback
        if is_sota is not None:
            if is_sota:
                for n in self.nodes.values():
                    n.is_sota = False
            node.is_sota = is_sota

    def get_evolution_chain(self, node_id: str) -> list[TraceNode]:
        chain = []
        current = self.nodes.get(node_id)
        while current:
            chain.insert(0, current)
            if not current.parent_ids:
                break
            current = self.nodes.get(current.parent_ids[0])
        return chain

    def get_branches(self, parent_id: str) -> list[list[TraceNode]]:
        branches = []
        for node in self.nodes.values():
            if parent_id in node.parent_ids:
                branch = self.get_evolution_chain(node.node_id)
                branches.append(branch)
        return branches

    def get_sota_node(self) -> Optional[TraceNode]:
        for node in self.nodes.values():
            if node.is_sota:
                return node
        return None

    def to_mermaid(self) -> str:
        lines = ["graph TD"]
        for node_id, node in self.nodes.items():
            short_id = node_id[:8]
            label = node.hypothesis[:40].replace('"', "'") if node.hypothesis else short_id
            marker = "🏆" if node.is_sota else ""
            lines.append(f'    {short_id}["{marker}{label}"]')
            for parent_id in node.parent_ids:
                lines.append(f"    {parent_id[:8]} --> {short_id}")
        return "\n".join(lines)

    def export_json(self, file_path: str) -> str:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "nodes": {nid: asdict(n) for nid, n in self.nodes.items()},
            "exported_at": datetime.now().isoformat(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return str(path)

    def import_json(self, file_path: str):
        path = Path(file_path)
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        for nid, node_data in data.get("nodes", {}).items():
            node = TraceNode(**node_data)
            self.nodes[nid] = node
