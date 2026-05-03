import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, List, Any


@dataclass
class TraceNode:
    node_id: str
    task_id: str
    parent_ids: List[str] = field(default_factory=list)
    hypothesis: str = ""
    reason: str = ""
    result: Dict[str, Any] = field(default_factory=dict)
    validation_result: Dict[str, Any] = field(default_factory=dict)
    feedback: str = ""
    metrics: Dict[str, float] = field(default_factory=dict)
    is_sota: bool = False
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ProcessTrace:
    def __init__(self, storage_dir: str = "data/traces"):
        self.nodes: Dict[str, TraceNode] = {}
        self.dag_children: Dict[str, List[str]] = {}
        self.sota_metrics: Dict[str, float] = {}
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)

    def add_node(self, node: TraceNode, parent_ids: Optional[List[str]] = None) -> str:
        if parent_ids is None:
            parent_ids = node.parent_ids

        self.nodes[node.node_id] = node

        for parent_id in parent_ids:
            if parent_id not in self.dag_children:
                self.dag_children[parent_id] = []
            if node.node_id not in self.dag_children[parent_id]:
                self.dag_children[parent_id].append(node.node_id)

        if node.node_id not in self.dag_children:
            self.dag_children[node.node_id] = []

        self.update_sota(node)
        self._persist_node(node)

        return node.node_id

    def update_node(self, node_id: str, **kwargs) -> Optional[TraceNode]:
        node = self.nodes.get(node_id)
        if not node:
            return None

        for key, value in kwargs.items():
            if hasattr(node, key):
                setattr(node, key, value)

        self._persist_node(node)
        return node

    def get_evolution_chain(self, node_id: str) -> List[TraceNode]:
        chain = []
        current_id = node_id

        visited = set()
        while current_id and current_id in self.nodes:
            if current_id in visited:
                break
            visited.add(current_id)

            node = self.nodes[current_id]
            chain.append(node)

            if not node.parent_ids:
                break
            current_id = node.parent_ids[0]

        chain.reverse()
        return chain

    def get_branches(self, node_id: str) -> List[List[TraceNode]]:
        branches = []
        self._collect_branches(node_id, [], branches)
        return branches

    def _collect_branches(self, node_id: str, current_path: List[TraceNode], branches: List[List[TraceNode]]):
        node = self.nodes.get(node_id)
        if not node:
            return

        current_path = current_path + [node]
        children = self.dag_children.get(node_id, [])

        if not children:
            branches.append(current_path)
        else:
            for child_id in children:
                self._collect_branches(child_id, current_path, branches)

    def update_sota(self, node: TraceNode) -> bool:
        if not node.metrics:
            return False

        new_sota = False
        for metric_name, metric_value in node.metrics.items():
            current_best = self.sota_metrics.get(metric_name)

            if current_best is None:
                self.sota_metrics[metric_name] = metric_value
                new_sota = True
            else:
                if self._is_better(metric_name, metric_value, current_best):
                    self.sota_metrics[metric_name] = metric_value
                    new_sota = True

        if new_sota:
            for existing_node in self.nodes.values():
                existing_node.is_sota = False
            node.is_sota = True

        return new_sota

    def _is_better(self, metric_name: str, new_value: float, current_value: float) -> bool:
        minimize_metrics = {"cutting_force", "surface_roughness", "tool_wear", "energy_consumption"}
        maximize_metrics = {"tool_life", "material_removal_rate", "efficiency", "accuracy"}

        metric_lower = metric_name.lower()

        if metric_lower in minimize_metrics:
            return new_value < current_value
        elif metric_lower in maximize_metrics:
            return new_value > current_value
        else:
            return abs(new_value - current_value) / (abs(current_value) + 1e-9) > 0.01

    def to_mermaid(self) -> str:
        lines = ["graph TD"]

        node_labels = {}
        for node_id, node in self.nodes.items():
            short_id = node_id[:8]
            status_color = self._get_node_color(node)
            label = f"{short_id}[{self._escape_mermaid(node.hypothesis[:30])}]"
            node_labels[node_id] = short_id
            lines.append(f"    {short_id}:::{status_color}")
            lines.append(f"    {label}")

        for node_id, children in self.dag_children.items():
            if node_id not in self.nodes:
                continue
            parent_short = node_id[:8]
            for child_id in children:
                if child_id in self.nodes:
                    child_short = child_id[:8]
                    lines.append(f"    {parent_short} --> {child_short}")

        lines.append("    classDef green fill:#b2f2b2,stroke:#333,stroke-width:2px")
        lines.append("    classDef red fill:#f2b2b2,stroke:#333,stroke-width:2px")
        lines.append("    classDef blue fill:#b2d4f2,stroke:#333,stroke-width:2px")
        lines.append("    classDef gray fill:#d3d3d3,stroke:#333,stroke-width:2px")

        return "\n".join(lines)

    def _get_node_color(self, node: TraceNode) -> str:
        if node.is_sota:
            return "blue"
        if node.validation_result:
            passed = node.validation_result.get("passed", False)
            return "green" if passed else "red"
        return "gray"

    def _escape_mermaid(self, text: str) -> str:
        return text.replace("(", "[").replace(")", "]").replace('"', "'")

    def export_json(self, file_path: Optional[str] = None) -> str:
        if file_path is None:
            file_path = str(self.storage_dir / "process_trace.json")

        data = {
            "nodes": {nid: asdict(node) for nid, node in self.nodes.items()},
            "dag_children": self.dag_children,
            "sota_metrics": self.sota_metrics,
            "exported_at": datetime.now().isoformat()
        }

        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return file_path

    def import_json(self, file_path: str) -> None:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.nodes = {}
        for nid, node_data in data.get("nodes", {}).items():
            self.nodes[nid] = TraceNode(**node_data)

        self.dag_children = data.get("dag_children", {})
        self.sota_metrics = data.get("sota_metrics", {})

    def _persist_node(self, node: TraceNode) -> None:
        log_file = self.storage_dir / "trace_log.jsonl"
        node_data = asdict(node)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(node_data, ensure_ascii=False, default=str) + "\n")

    def get_sota_node(self) -> Optional[TraceNode]:
        for node in self.nodes.values():
            if node.is_sota:
                return node
        return None

    def get_node(self, node_id: str) -> Optional[TraceNode]:
        return self.nodes.get(node_id)

    def get_task_traces(self, task_id: str) -> List[TraceNode]:
        return [node for node in self.nodes.values() if node.task_id == task_id]
