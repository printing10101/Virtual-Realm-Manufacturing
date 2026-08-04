"""Operation sequencing engine.

Generates optimized machining operation sequences based on feature
dependency relationships and manufacturing rules. Implements complete
operation planning, fixture suggestions, and time estimation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.process_planning.feature_dependency import (
    FeatureDependencyGraph,
    MachiningFeature,
    Setup,
)
from app.process_planning.datum_selector import DatumSelector
from app.process_planning.fixture_analyzer import (
    FixtureAnalyzer,
    FixtureRecommendation,
)


@dataclass
class Operation:
    """A single machining operation in the process plan.

    Attributes:
        seq: Operation sequence number.
        name: Operation name, e.g. 'OP01-Surface A'.
        feature_name: Name of the machining feature this operation processes.
        machining_method: Machining method, e.g. '钻孔', '精铣平面'.
        surface: Surface identifier this operation works on.
        tolerance_grade: Required tolerance grade.
        tool_type: Tool type description.
        cutting_params: Cutting parameters dictionary.
        estimated_time_min: Estimated operation time (minutes).
        notes: Additional operation notes.
    """

    seq: int
    name: str
    feature_name: str
    machining_method: str
    surface: str
    tolerance_grade: str
    tool_type: str = ""
    cutting_params: dict[str, Any] = field(default_factory=dict)
    estimated_time_min: float = 0.0
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Convert the operation to a dictionary representation.

        Returns:
            A dictionary containing all operation properties suitable
            for serialization.
        """
        return {
            "seq": self.seq,
            "name": self.name,
            "feature_name": self.feature_name,
            "machining_method": self.machining_method,
            "surface": self.surface,
            "tolerance_grade": self.tolerance_grade,
            "tool_type": self.tool_type,
            "cutting_params": self.cutting_params,
            "estimated_time_min": round(self.estimated_time_min, 2),
            "notes": self.notes,
        }


@dataclass
class OperationPlan:
    """Complete operation plan for a part.

    Attributes:
        operations: Ordered list of machining operations.
        setups: List of fixture setups (one per surface/group).
        estimated_time_min: Total estimated machining time (minutes).
        face_change_count: Number of face changes (setup transitions).
        fixture_recommendations: Recommended fixtures for each setup.
    """

    operations: list[Operation] = field(default_factory=list)
    setups: list[Setup] = field(default_factory=list)
    estimated_time_min: float = 0.0
    face_change_count: int = 0
    fixture_recommendations: list[FixtureRecommendation] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Convert the operation plan to a dictionary representation.

        Returns:
            A dictionary containing operations, setups, estimated time,
            face change count, and fixture recommendations.
        """
        return {
            "operations": [op.to_dict() for op in self.operations],
            "setups": [
                {
                    "name": s.name,
                    "surface": s.surface,
                    "fixture_type": s.fixture_type,
                    "datum_features": s.datum_features,
                }
                for s in self.setups
            ],
            "estimated_time_min": round(self.estimated_time_min, 2),
            "face_change_count": self.face_change_count,
            "fixture_recommendations": [fr.to_dict() for fr in self.fixture_recommendations],
        }


class OperationSequencer:
    """Operation sequencer that generates machining operation plans.

    Uses feature dependency graphs, datum selection, and fixture analysis
    to produce an optimized sequence of machining operations.
    """

    def __init__(self) -> None:
        self._dep_graph = FeatureDependencyGraph()
        self._datum_selector = DatumSelector()
        self._fixture_analyzer = FixtureAnalyzer()

    def plan_operations(
        self,
        features: list[MachiningFeature],
        material: str = "",
        blank_type: str = "",
        part_type: str = "general",
    ) -> OperationPlan:
        """Generate an optimized machining operation plan from a list of features.

        Args:
            features: List of machining features to plan operations for.
            material: Material name for feed rate adjustment.
            blank_type: Blank/stock type.
            part_type: Part type category (general/shaft/plate etc.).

        Returns:
            OperationPlan with ordered operations, setups, and time estimates.
        """
        self._dep_graph.build_graph(features)
        sequence = self._dep_graph.get_machining_sequence()

        operations: list[Operation] = []
        setups: dict[str, Setup] = {}
        seq = 0
        feed_rate_factor = self._get_feed_rate_factor(material)

        for fe in sequence:
            seq += 1
            surface = fe.surface
            if surface not in setups:
                setups[surface] = Setup(
                    name=f"装夹{len(setups) + 1}-面{surface}",
                    surface=surface,
                    fixture_type="",
                )

            method = self._select_machining_method(fe, blank_type)
            tool = self._select_tool(fe, method)

            estimated_time = self._estimate_operation_time(
                fe,
                method,
                feed_rate_factor,
            )

            op = Operation(
                seq=seq,
                name=f"OP{seq:02d}-{fe.name}",
                feature_name=fe.name,
                machining_method=method,
                surface=fe.surface,
                tolerance_grade=fe.tolerance_grade,
                tool_type=tool,
                cutting_params={
                    "feed_rate_factor": feed_rate_factor,
                    "recommended_feed": self._recommend_feed(fe, material),
                    "recommended_speed": self._recommend_speed(fe, material),
                },
                estimated_time_min=estimated_time,
                notes=self._generate_operation_notes(fe, method),
            )
            operations.append(op)

        setup_list = list(setups.values())
        fixture_recommendations = []
        for s in setup_list:
            fr = self._fixture_analyzer.suggest_fixture(s, part_type)
            s.fixture_type = fr.fixture_name
            fixture_recommendations.append(fr)

        total_time = sum(op.estimated_time_min for op in operations)

        return OperationPlan(
            operations=operations,
            setups=setup_list,
            estimated_time_min=total_time,
            face_change_count=len(setups) - 1 if len(setups) > 1 else 0,
            fixture_recommendations=fixture_recommendations,
        )

    def suggest_fixture(
        self,
        setup: Setup,
        part_type: str = "general",
    ) -> FixtureRecommendation:
        """Suggest a fixture for a given setup.

        Args:
            setup: Setup to suggest a fixture for.
            part_type: Part type category.

        Returns:
            FixtureRecommendation with fixture details and suitability score.
        """
        return self._fixture_analyzer.suggest_fixture(setup, part_type)

    def _select_machining_method(
        self,
        fe: MachiningFeature,
        blank_type: str,
    ) -> str:
        is_rough = fe.tolerance_grade in ("IT9", "IT10", "IT11", "IT12", "IT13", "IT14")

        if fe.type in ("end_face",):
            return "粗车端面" if is_rough else "精车端面"
        if fe.type in ("outer_cylinder",):
            return "粗车外圆" if is_rough else "精车外圆"
        if fe.type in ("inner_bore",):
            return "粗镗内孔" if is_rough else "精镗内孔"
        if fe.type in ("through_hole",):
            return "钻孔"
        if fe.type in ("center_hole",):
            return "钻中心孔"
        if fe.type in ("groove",):
            return "切槽"
        if fe.type in ("chamfer",):
            return "倒角"
        if fe.type in ("plane_surface",):
            return "粗铣平面" if is_rough else "精铣平面"
        if fe.type in ("keyway",):
            return "铣键槽"
        if fe.type in ("slot",):
            return "铣槽"
        if fe.type in ("step",):
            return "车台阶"
        if fe.type in ("counterbore",):
            return "钻沉头孔"

        if is_rough:
            return f"粗加工-{fe.type}"
        return f"精加工-{fe.type}"

    def _select_tool(self, fe: MachiningFeature, method: str) -> str:
        if "车" in method:
            if "粗" in method:
                return "外圆车刀(粗)"
            return "外圆车刀(精)"
        if "镗" in method:
            return "镗刀"
        if "钻" in method:
            if "中心" in method:
                return "中心钻"
            return "麻花钻"
        if "切槽" in method:
            return "切槽刀"
        if "倒角" in method:
            return "倒角刀"
        if "铣" in method:
            return "立铣刀"
        return "通用刀具"

    def _estimate_operation_time(
        self,
        fe: MachiningFeature,
        method: str,
        feed_factor: float = 1.0,
    ) -> float:
        base_time = 2.0
        if "粗" in method:
            base_time = 4.0
        elif "精" in method:
            base_time = 3.0
        if "车" in method:
            base_time *= 1.0
        elif "钻" in method:
            base_time *= 0.8
        elif "铣" in method:
            base_time *= 1.3

        dim_factor = 1.0
        dia = fe.dimensions.get("diameter", 50)
        if dia > 100:
            dim_factor = 1.5
        elif dia > 50:
            dim_factor = 1.2

        return round(base_time * dim_factor * feed_factor, 2)

    def _get_feed_rate_factor(self, material: str) -> float:
        if not material:
            return 1.0
        ml = material.lower()
        if "aluminum" in ml or "铝合金" in ml:
            return 0.7
        if "titanium" in ml or "钛合金" in ml:
            return 1.5
        if "stainless" in ml or "不锈钢" in ml:
            return 1.3
        if "cast_iron" in ml or "铸铁" in ml:
            return 0.8
        return 1.0

    def _recommend_feed(self, fe: MachiningFeature, material: str) -> str:
        if fe.type in ("outer_cylinder", "end_face"):
            if fe.is_finish():
                return "0.05-0.15 mm/rev"
            return "0.15-0.35 mm/rev"
        if fe.is_hole():
            return "0.05-0.15 mm/rev"
        if fe.is_face():
            return "0.05-0.20 mm/tooth"
        return "0.10-0.25 mm/rev"

    def _recommend_speed(self, fe: MachiningFeature, material: str) -> str:
        if not material:
            return "80-200 m/min"
        ml = material.lower()
        if "aluminum" in ml or "铝合金" in ml:
            return "300-800 m/min"
        if "titanium" in ml or "钛合金" in ml:
            return "30-60 m/min"
        if "stainless" in ml or "不锈钢" in ml:
            return "50-100 m/min"
        if "cast_iron" in ml or "铸铁" in ml:
            return "80-150 m/min"
        return "80-200 m/min"

    def _generate_operation_notes(
        self,
        fe: MachiningFeature,
        method: str,
    ) -> str:
        notes_parts = []
        if fe.is_datum_candidate:
            notes_parts.append("定位基准面，确保加工精度")
        if fe.tolerance_grade in ("IT5", "IT6", "IT7"):
            notes_parts.append(f"精密加工，公差等级{fe.tolerance_grade}")
        if "粗" in method:
            notes_parts.append("留余量0.5-1.0mm")
        if "精" in method:
            notes_parts.append("最终尺寸，使用切削液")
        if fe.is_hole():
            notes_parts.append("使用中心钻定位后钻孔")
        return "; ".join(notes_parts) if notes_parts else "标准加工"
