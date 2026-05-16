"""加工特征依赖关系图。

建立加工特征间的几何与工艺关系，实现拓扑排序驱动的最优加工顺序。
遵循"先面后孔"、"先粗后精"、"先主后次"、"基准先行"的工艺原则。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class MachiningFeature:
    name: str
    type: str
    geometric_type: str = ""
    tolerance_grade: str = "IT8"
    surface_roughness_ra: float = 6.3
    is_datum_candidate: bool = False
    machining_method: str = ""
    priority: str = "medium"
    surface: str = "A"
    dimensions: dict[str, float] = field(default_factory=dict)
    parent_feature: str = ""
    tolerances: dict[str, float] = field(default_factory=dict)

    def is_rough(self) -> bool:
        return self.tolerance_grade in ("IT10", "IT11", "IT12", "IT13", "IT14")

    def is_finish(self) -> bool:
        return self.tolerance_grade in ("IT5", "IT6", "IT7")

    def is_hole(self) -> bool:
        return self.geometric_type in ("cylinder",) and self.type in (
            "through_hole",
            "inner_bore",
            "counterbore",
            "center_hole",
        )

    def is_face(self) -> bool:
        return self.geometric_type == "plane"

    def priority_score(self) -> int:
        score = 0
        if self.is_datum_candidate:
            score += 100
        if self.tolerance_grade in ("IT5", "IT6", "IT7"):
            score += 30
        if self.priority == "high":
            score += 20
        if self.geometric_type == "plane":
            score += 10
        if self.type == "end_face":
            score += 50
        if self.is_hole():
            score -= 20
        if self.type in ("groove", "chamfer", "slot"):
            score -= 30
        return score

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "type": self.type,
            "geometric_type": self.geometric_type,
            "tolerance_grade": self.tolerance_grade,
            "surface_roughness_ra": self.surface_roughness_ra,
            "is_datum_candidate": self.is_datum_candidate,
            "machining_method": self.machining_method,
            "priority": self.priority,
            "surface": self.surface,
            "dimensions": self.dimensions,
            "parent_feature": self.parent_feature,
            "tolerances": self.tolerances,
        }


@dataclass
class Setup:
    name: str
    surface: str = "A"
    datum_features: list[str] = field(default_factory=list)
    fixture_type: str = ""
    clamped_features: list[str] = field(default_factory=list)


@dataclass
class FeatureEdge:
    from_feature: str
    to_feature: str
    relation: str


class FeatureDependencyGraph:
    def __init__(self) -> None:
        self._features: dict[str, MachiningFeature] = {}
        self._edges: list[FeatureEdge] = []
        self._in_degree: dict[str, int] = {}
        self._adjacency: dict[str, list[str]] = {}

    def build_graph(self, features: list[MachiningFeature]) -> None:
        self._features = {f.name: f for f in features}
        self._edges = []
        self._adjacency = {f.name: [] for f in features}
        self._in_degree = {f.name: 0 for f in features}

        for fe in features:
            for other in features:
                if fe.name == other.name:
                    continue
                self._add_dependency_if_applicable(fe, other)

    def _add_dependency_if_applicable(
        self,
        pred: MachiningFeature,
        succ: MachiningFeature,
    ) -> None:
        # 基准面优先于其他特征
        if pred.is_datum_candidate and not succ.is_datum_candidate:
            self._add_edge(pred.name, succ.name, "datum_before_feature")
            return

        # 端面优先于孔——先面后孔
        if pred.type == "end_face" and succ.is_hole():
            self._add_edge(pred.name, succ.name, "face_before_hole")
            return

        # 平面优先于孔
        if pred.is_face() and succ.is_hole() and not pred.is_datum_candidate:
            self._add_edge(pred.name, succ.name, "face_before_hole")
            return

        # 粗加工优先于精加工
        if (
            pred.is_rough()
            and succ.is_finish()
            and pred.geometric_type == succ.geometric_type
        ):
            self._add_edge(pred.name, succ.name, "rough_before_finish")
            return

        # 高精度优先于低精度
        if pred.priority_score() > succ.priority_score() + 40:
            self._add_edge(pred.name, succ.name, "primary_before_secondary")
            return

        # 钻孔优先于镗孔
        if pred.type == "through_hole" and succ.type == "inner_bore":
            self._add_edge(pred.name, succ.name, "bore_after_drilling")
            return

        # 父特征优先于子特征
        if pred.name and succ.parent_feature and succ.parent_feature == pred.name:
            self._add_edge(pred.name, succ.name, "parent_child")

    def _add_edge(self, from_f: str, to_f: str, relation: str) -> None:
        if to_f not in self._adjacency.get(from_f, []):
            edge = FeatureEdge(from_feature=from_f, to_feature=to_f, relation=relation)
            self._edges.append(edge)
            self._adjacency.setdefault(from_f, []).append(to_f)
            self._in_degree[to_f] = self._in_degree.get(to_f, 0) + 1

    def get_machining_sequence(self) -> list[MachiningFeature]:
        in_deg = dict(self._in_degree)
        queue = [name for name, deg in in_deg.items() if deg == 0]

        queue.sort(key=lambda n: -self._features[n].priority_score())

        result: list[str] = []
        while queue:
            current = queue.pop(0)
            result.append(current)
            for neighbor in self._adjacency.get(current, []):
                in_deg[neighbor] -= 1
                if in_deg[neighbor] == 0:
                    queue.append(neighbor)
            queue.sort(key=lambda n: -self._features[n].priority_score())

        for fname in self._features:
            if fname not in result:
                result.append(fname)

        return [self._features[name] for name in result]

    def check_accessibility(
        self,
        feature: MachiningFeature,
        current_setup: Setup,
    ) -> bool:
        if feature.name in current_setup.clamped_features:
            return False

        if feature.surface != current_setup.surface:
            return False

        return True

    def get_dependencies(self, feature_name: str) -> list[str]:
        deps: list[str] = []
        for edge in self._edges:
            if edge.to_feature == feature_name:
                deps.append(edge.from_feature)
        return deps

    def get_dependents(self, feature_name: str) -> list[str]:
        return list(self._adjacency.get(feature_name, []))

    @classmethod
    def from_features_list(
        cls,
        features: list[dict[str, Any]],
    ) -> FeatureDependencyGraph:
        graph = cls()
        mf_list = []
        for f in features:
            mf = MachiningFeature(
                name=f.get("name", ""),
                type=f.get("type", ""),
                geometric_type=f.get("geometric_type", ""),
                tolerance_grade=f.get("tolerance_grade", "IT8"),
                surface_roughness_ra=f.get("surface_roughness_ra", 6.3),
                is_datum_candidate=f.get("is_datum_candidate", False),
                machining_method=f.get("machining_method", ""),
                priority=f.get("priority", "medium"),
                surface=f.get("surface", "A"),
                dimensions=f.get("dimensions", {}),
                parent_feature=f.get("parent_feature", ""),
                tolerances=f.get("tolerances", {}),
            )
            mf_list.append(mf)
        graph.build_graph(mf_list)
        return graph
