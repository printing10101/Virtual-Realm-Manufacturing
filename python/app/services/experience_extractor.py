import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from app.core.process_trace import ProcessTrace, TraceNode

logger = logging.getLogger(__name__)


@dataclass
class ExtractedExperience:
    experience_id: str
    trace_node_id: str
    task_id: str
    process: str
    parameters: dict
    metrics: dict
    hypothesis: str
    validation_result: dict
    warnings: list[str] = field(default_factory=list)
    ground_truth_context: dict = field(default_factory=dict)
    extracted_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ExperienceExtractor:
    def __init__(self):
        self._extraction_count = 0

    def extract_from_trace(
        self,
        trace: ProcessTrace,
        node_id: str | None = None,
    ) -> list[ExtractedExperience]:
        nodes_to_extract = []

        if node_id:
            node = trace.get_node(node_id)
            if node:
                nodes_to_extract.append(node)
        else:
            nodes_to_extract = list(trace.nodes.values())

        experiences = []
        for node in nodes_to_extract:
            exp = self._extract_single_experience(node)
            experiences.append(exp)

        self._extraction_count += len(experiences)
        logger.info("Extracted %d experiences from trace", len(experiences))
        return experiences

    def extract_from_trace_with_ground_truth(
        self,
        trace: ProcessTrace,
        ground_truth_adapter=None,
        node_id: str | None = None,
    ) -> list[ExtractedExperience]:
        nodes_to_extract = []

        if node_id:
            node = trace.get_node(node_id)
            if node:
                nodes_to_extract.append(node)
        else:
            nodes_to_extract = list(trace.nodes.values())

        experiences = []
        for node in nodes_to_extract:
            exp = self._extract_single_experience(node)

            if ground_truth_adapter and exp.process:
                gt_validation = ground_truth_adapter.validate_experience(
                    experience=asdict_experience(exp),
                    process=exp.process,
                )

                exp.ground_truth_context = {
                    "validation": gt_validation,
                    "is_consistent": gt_validation.get("is_consistent", False),
                    "confidence": gt_validation.get("confidence", 0.0),
                }

                if not gt_validation.get("is_consistent", True):
                    for discrepancy in gt_validation.get("discrepancies", []):
                        exp.warnings.append(
                            f"Ground truth discrepancy: {discrepancy.get('metric', 'unknown')} "
                            f"deviation={discrepancy.get('deviation', 0):.1%}"
                        )

            experiences.append(exp)

        self._extraction_count += len(experiences)
        logger.info(
            "Extracted %d experiences with ground truth validation",
            len(experiences)
        )
        return experiences

    def _extract_single_experience(self, node: TraceNode) -> ExtractedExperience:
        process = self._infer_process_from_node(node)
        parameters = self._extract_parameters(node)
        metrics = self._extract_metrics(node)

        exp = ExtractedExperience(
            experience_id=f"extracted-{node.node_id[:12]}",
            trace_node_id=node.node_id,
            task_id=node.task_id,
            process=process,
            parameters=parameters,
            metrics=metrics,
            hypothesis=node.hypothesis,
            validation_result=node.validation_result,
        )

        return exp

    @staticmethod
    def _infer_process_from_node(node: TraceNode) -> str:
        scenario_id = node.metrics.get("scenario_id", "")
        material = node.metrics.get("material", "")

        if scenario_id:
            return scenario_id

        if "cutting_speed" in node.metrics:
            return "machining"

        return "unknown"

    @staticmethod
    def _extract_parameters(node: TraceNode) -> dict:
        parameters = {}

        result = node.result or {}
        for stage_name, stage_data in result.items():
            if isinstance(stage_data, dict):
                if "optimized_params" in stage_data:
                    parameters.update(stage_data["optimized_params"])
                if "solver_result" in stage_data:
                    parameters["solver_optimal"] = stage_data["solver_result"].get("optimal", False)
                    parameters["objective_value"] = stage_data["solver_result"].get("objective_value", 0.0)

        metrics = node.metrics or {}
        for key in ["cutting_speed", "feed_rate", "depth_of_cut"]:
            if key in metrics:
                parameters[key] = metrics[key]

        return parameters

    @staticmethod
    def _extract_metrics(node: TraceNode) -> dict:
        metrics = dict(node.metrics or {})

        validation = node.validation_result or {}
        if "quality_metrics" in validation:
            metrics.update(validation["quality_metrics"])

        if "cutting_force" in validation:
            metrics["cutting_force"] = validation["cutting_force"]

        return metrics


def asdict_experience(exp: ExtractedExperience) -> dict:
    return {
        "experience_id": exp.experience_id,
        "trace_node_id": exp.trace_node_id,
        "task_id": exp.task_id,
        "process": exp.process,
        "parameters": exp.parameters,
        "metrics": exp.metrics,
        "hypothesis": exp.hypothesis,
        "validation_result": exp.validation_result,
        "warnings": exp.warnings,
        "ground_truth_context": exp.ground_truth_context,
        "extracted_at": exp.extracted_at,
    }
