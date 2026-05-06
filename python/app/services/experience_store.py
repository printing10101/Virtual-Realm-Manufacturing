import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class Experience:
    experience_id: str
    task_id: str
    process: str
    parameters: dict
    metrics: dict
    validation_result: dict
    ground_truth_validation: dict = field(default_factory=dict)
    metadata: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ExperienceStore:
    def __init__(self, storage_dir: str = "experiences"):
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(parents=True, exist_ok=True)
        self._experiences: dict[str, Experience] = {}
        self._validation_history: dict[str, list[dict]] = {}
        self._load_experiences()

    def save_experience(
        self,
        task_id: str,
        experience: dict,
        process: str | None = None,
    ) -> dict:
        exp_id = f"exp-{datetime.now().strftime('%Y%m%d%H%M%S')}-{task_id[:8]}"

        exp = Experience(
            experience_id=exp_id,
            task_id=task_id,
            process=process or "unknown",
            parameters=experience.get("parameters", {}),
            metrics=experience.get("metrics", {}),
            validation_result=experience.get("validation_result", {}),
            metadata=experience.get("metadata", {}),
        )

        self._experiences[exp_id] = exp
        self._save_to_disk()

        return {
            "experience_id": exp_id,
            "status": "saved",
        }

    def save_experience_with_validation(
        self,
        task_id: str,
        experience: dict,
        ground_truth_adapter=None,
        process: str | None = None,
    ) -> dict:
        exp_id = f"exp-{datetime.now().strftime('%Y%m%d%H%M%S')}-{task_id[:8]}"

        validation_result = {}
        if ground_truth_adapter and process:
            validation_result = ground_truth_adapter.validate_experience(
                experience=experience,
                process=process,
            )

        exp = Experience(
            experience_id=exp_id,
            task_id=task_id,
            process=process or "unknown",
            parameters=experience.get("parameters", {}),
            metrics=experience.get("metrics", {}),
            validation_result=experience.get("validation_result", {}),
            ground_truth_validation=validation_result,
            metadata=experience.get("metadata", {}),
        )

        self._experiences[exp_id] = exp

        if exp_id not in self._validation_history:
            self._validation_history[exp_id] = []
        self._validation_history[exp_id].append({
            "timestamp": datetime.now().isoformat(),
            "validation_result": validation_result,
        })

        self._save_to_disk()

        return {
            "experience_id": exp_id,
            "validation_result": validation_result,
        }

    def get_experience(self, experience_id: str) -> Optional[Experience]:
        return self._experiences.get(experience_id)

    def list_experiences(
        self,
        filters: dict | None = None,
        limit: int = 100,
    ) -> list[dict]:
        results = []
        for exp in self._experiences.values():
            if filters:
                match = all(
                    getattr(exp, k, None) == v
                    for k, v in filters.items()
                )
                if not match:
                    continue
            results.append(asdict(exp))
            if len(results) >= limit:
                break
        return results

    def search_with_ground_truth(
        self,
        query: dict,
        top_k: int = 5,
        include_ground_truth: bool = True,
    ) -> dict:
        experiences = self.list_experiences(filters=query, limit=top_k * 2)

        experience_scores = []
        for exp_dict in experiences:
            score = self._calculate_relevance_score(exp_dict, query)
            experience_scores.append((exp_dict, score))

        experience_scores.sort(key=lambda x: x[1], reverse=True)
        top_experiences = [exp for exp, _ in experience_scores[:top_k]]

        ground_truth_context = {}
        if include_ground_truth and query.get("process"):
            from app.services.ground_truth_adapter import BoschGroundTruthAdapter
            gt_adapter = BoschGroundTruthAdapter()
            gt_adapter.load_ground_truth()

            success_rate = gt_adapter.get_process_success_rate(
                process=query["process"],
                machine=query.get("machine"),
            )

            similar_cases = []
            if query.get("vibration_features"):
                similar_cases = gt_adapter.find_similar_cases(
                    query_features=query["vibration_features"],
                    top_k=3,
                )

            ground_truth_context = {
                "process_success_rate": success_rate,
                "similar_ground_truth_cases": similar_cases,
            }

        return {
            "experiences": top_experiences,
            "ground_truth_context": ground_truth_context,
        }

    def get_experience_reliability(self, experience_id: str) -> dict:
        exp = self._experiences.get(experience_id)
        if not exp:
            return {
                "reliability_score": 0.0,
                "validation_count": 0,
                "consistency_rate": 0.0,
                "last_validated": None,
            }

        history = self._validation_history.get(experience_id, [])
        validation_count = len(history)

        if validation_count == 0:
            gt_validation = exp.ground_truth_validation
            if gt_validation:
                consistency_rate = 1.0 if gt_validation.get("is_consistent") else 0.0
                last_validated = exp.created_at
            else:
                consistency_rate = 0.0
                last_validated = None
        else:
            consistent_count = sum(
                1 for h in history
                if h.get("validation_result", {}).get("is_consistent", False)
            )
            consistency_rate = consistent_count / validation_count
            last_validated = history[-1]["timestamp"]

        reliability_score = self._calculate_reliability_score(
            validation_count, consistency_rate
        )

        return {
            "reliability_score": round(reliability_score, 4),
            "validation_count": validation_count,
            "consistency_rate": round(consistency_rate, 4),
            "last_validated": last_validated,
        }

    def _calculate_relevance_score(self, exp_dict: dict, query: dict) -> float:
        score = 0.0

        if query.get("process") and exp_dict.get("process") == query["process"]:
            score += 1.0

        query_params = query.get("parameters", {})
        exp_params = exp_dict.get("parameters", {})
        if query_params and exp_params:
            common_keys = set(query_params.keys()) & set(exp_params.keys())
            if common_keys:
                param_similarity = sum(
                    1.0 - min(abs(query_params[k] - exp_params[k]) / max(abs(query_params[k]), 1e-10), 1.0)
                    for k in common_keys
                ) / len(common_keys)
                score += param_similarity * 0.5

        query_metrics = query.get("metrics", {})
        exp_metrics = exp_dict.get("metrics", {})
        if query_metrics and exp_metrics:
            common_keys = set(query_metrics.keys()) & set(exp_metrics.keys())
            if common_keys:
                metric_similarity = sum(
                    1.0 - min(abs(query_metrics[k] - exp_metrics[k]) / max(abs(query_metrics[k]), 1e-10), 1.0)
                    for k in common_keys
                ) / len(common_keys)
                score += metric_similarity * 0.3

        return score

    @staticmethod
    def _calculate_reliability_score(validation_count: int, consistency_rate: float) -> float:
        if validation_count == 0:
            return 0.5

        confidence_weight = min(validation_count / 10.0, 1.0)
        reliability = consistency_rate * 0.7 + confidence_weight * 0.3
        return max(0.0, min(1.0, reliability))

    def _save_to_disk(self):
        file_path = self.storage_dir / "experiences.json"
        data = {
            "experiences": {
                eid: asdict(exp)
                for eid, exp in self._experiences.items()
            },
            "validation_history": self._validation_history,
            "updated_at": datetime.now().isoformat(),
        }
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def _load_experiences(self):
        file_path = self.storage_dir / "experiences.json"
        if not file_path.exists():
            return

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            for eid, exp_data in data.get("experiences", {}).items():
                exp = Experience(**exp_data)
                self._experiences[eid] = exp

            self._validation_history = data.get("validation_history", {})
            logger.info("Loaded %d experiences from disk", len(self._experiences))
        except Exception as e:
            logger.warning("Failed to load experiences: %s", e)
