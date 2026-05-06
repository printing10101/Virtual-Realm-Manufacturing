import logging
import math
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from app.data.bosch_cnc_loader import BoschCNCDataLoader

logger = logging.getLogger(__name__)


@dataclass
class GroundTruthRecord:
    record_id: str
    machine: str
    process: str
    timeframe: str
    label: str
    vibration_features: dict
    feature_summary: str
    metadata: dict
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class BoschGroundTruthAdapter:
    def __init__(self, data_dir: str = "python/app/data/datasets/bosch_cnc"):
        self.loader = BoschCNCDataLoader(data_dir=data_dir)
        self._records: list[GroundTruthRecord] = []
        self._loaded = False

    def load_ground_truth(
        self,
        machines: list[str] | None = None,
        processes: list[str] | None = None,
        labels: list[str] | None = None,
    ) -> list[GroundTruthRecord]:
        if self._loaded:
            return self._records

        samples = self.loader.load_dataset(
            machines=machines,
            processes=processes,
            labels=labels,
        )

        self._records = []
        for sample in samples:
            metadata = sample["metadata"]
            vibration_data = sample["data"]
            features = self.loader.extract_features(vibration_data)
            feature_summary = self._generate_feature_summary(features)

            record = GroundTruthRecord(
                record_id=f"gt-{uuid.uuid4().hex[:12]}",
                machine=metadata.get("machine", "unknown"),
                process=metadata.get("process", "unknown"),
                timeframe=metadata.get("timeframe", "unknown"),
                label=sample["label"],
                vibration_features=features,
                feature_summary=feature_summary,
                metadata=metadata,
            )
            self._records.append(record)

        self._loaded = True
        logger.info("Loaded %d ground truth records", len(self._records))
        return self._records

    def find_similar_cases(
        self,
        query_features: dict,
        top_k: int = 5,
    ) -> list[dict]:
        if not self._loaded:
            self.load_ground_truth()

        query_vector = self._features_to_vector(query_features)
        results = []

        for record in self._records:
            record_vector = self._features_to_vector(record.vibration_features)
            similarity = self._cosine_similarity(query_vector, record_vector)

            feature_comparison = self._compare_features(
                query_features, record.vibration_features
            )

            results.append({
                "record": asdict(record),
                "similarity_score": round(float(similarity), 4),
                "is_normal": record.label == "good",
                "feature_comparison": feature_comparison,
            })

        results.sort(key=lambda x: x["similarity_score"], reverse=True)
        return results[:top_k]

    def get_process_success_rate(
        self,
        process: str,
        machine: str | None = None,
        timeframe: str | None = None,
    ) -> dict:
        if not self._loaded:
            self.load_ground_truth()

        filtered = [r for r in self._records if r.process == process]

        if machine:
            filtered = [r for r in filtered if r.machine == machine]
        if timeframe:
            filtered = [r for r in filtered if r.timeframe == timeframe]

        total = len(filtered)
        good_count = sum(1 for r in filtered if r.label == "good")
        bad_count = total - good_count
        success_rate = good_count / total if total > 0 else 0.0

        time_trend = self.get_time_trend(process, machine or "M01")

        return {
            "process": process,
            "machine": machine,
            "timeframe": timeframe,
            "total_samples": total,
            "good_count": good_count,
            "bad_count": bad_count,
            "success_rate": round(success_rate, 4),
            "time_trend": time_trend,
        }

    def get_time_trend(
        self,
        process: str,
        machine: str = "M01",
    ) -> dict:
        if not self._loaded:
            self.load_ground_truth()

        filtered = [
            r for r in self._records
            if r.process == process and r.machine == machine
        ]

        timeframes_dict: dict[str, list[GroundTruthRecord]] = {}
        for r in filtered:
            if r.timeframe not in timeframes_dict:
                timeframes_dict[r.timeframe] = []
            timeframes_dict[r.timeframe].append(r)

        timeframe_order = [
            "Oct_2018", "Apr_2019", "Aug_2019",
            "Feb_2020", "Aug_2020", "Feb_2021"
        ]

        trend_data = []
        for tf in timeframe_order:
            if tf not in timeframes_dict:
                continue

            records = timeframes_dict[tf]
            total = len(records)
            good = sum(1 for r in records if r.label == "good")
            good_ratio = good / total if total > 0 else 0.0

            rms_values = []
            for r in records:
                for key, val in r.vibration_features.items():
                    if "rms" in key:
                        rms_values.append(val)
            avg_vibration = float(np.mean(rms_values)) if rms_values else 0.0

            trend_data.append({
                "period": tf,
                "good_ratio": round(good_ratio, 4),
                "avg_vibration": round(avg_vibration, 4),
                "sample_count": total,
            })

        trend_direction = self._calculate_trend_direction(trend_data)

        return {
            "process": process,
            "machine": machine,
            "timeframes": trend_data,
            "trend": trend_direction,
        }

    def validate_experience(
        self,
        experience: dict,
        process: str,
    ) -> dict:
        if not self._loaded:
            self.load_ground_truth()

        process_records = [r for r in self._records if r.process == process]

        if not process_records:
            return {
                "is_consistent": True,
                "confidence": 0.0,
                "discrepancies": [],
                "supporting_evidence": [
                    f"No ground truth data found for process {process}"
                ],
            }

        discrepancies = []
        supporting_evidence = []

        exp_metrics = experience.get("metrics", {})
        exp_params = experience.get("parameters", {})

        good_records = [r for r in process_records if r.label == "good"]
        if good_records:
            avg_vibration = self._compute_avg_vibration(good_records)
            exp_vibration = exp_metrics.get("vibration")

            if exp_vibration is not None:
                deviation = abs(exp_vibration - avg_vibration) / avg_vibration if avg_vibration > 0 else 0
                if deviation > 0.3:
                    discrepancies.append({
                        "metric": "vibration",
                        "expected_range": f"~{avg_vibration:.2f}",
                        "actual": exp_vibration,
                        "deviation": round(deviation, 4),
                    })
                else:
                    supporting_evidence.append(
                        f"Vibration within normal range (deviation: {deviation:.1%})"
                    )

        good_count = sum(1 for r in process_records if r.label == "good")
        success_rate = good_count / len(process_records)

        if success_rate < 0.5:
            supporting_evidence.append(
                f"Process {process} has low success rate ({success_rate:.1%}) in ground truth"
            )

        is_consistent = len(discrepancies) == 0
        confidence = 1.0 - (len(discrepancies) * 0.2) if process_records else 0.0

        return {
            "is_consistent": is_consistent,
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
            "discrepancies": discrepancies,
            "supporting_evidence": supporting_evidence,
            "ground_truth_sample_count": len(process_records),
            "ground_truth_success_rate": round(success_rate, 4),
        }

    def get_statistics(self) -> dict:
        if not self._loaded:
            self.load_ground_truth()

        machines = {}
        processes = {}
        labels = {}

        for record in self._records:
            machines[record.machine] = machines.get(record.machine, 0) + 1
            processes[record.process] = processes.get(record.process, 0) + 1
            labels[record.label] = labels.get(record.label, 0) + 1

        return {
            "total_records": len(self._records),
            "machines": machines,
            "processes": processes,
            "labels": labels,
            "timeframes": list(set(r.timeframe for r in self._records)),
        }

    def _generate_feature_summary(self, features: dict) -> str:
        parts = []

        rms_keys = [k for k in features if "rms" in k]
        if rms_keys:
            avg_rms = float(np.mean([features[k] for k in rms_keys]))
            parts.append(f"avg_rms={avg_rms:.2f}")

        peak_keys = [k for k in features if "peak" in k and "to" not in k]
        if peak_keys:
            avg_peak = float(np.mean([features[k] for k in peak_keys]))
            parts.append(f"avg_peak={avg_peak:.2f}")

        freq_keys = [k for k in features if "dominant_freq" in k]
        if freq_keys:
            avg_freq = float(np.mean([features[k] for k in freq_keys]))
            parts.append(f"avg_dominant_freq={avg_freq:.2f}")

        return "; ".join(parts) if parts else "no features"

    def _features_to_vector(self, features: dict) -> np.ndarray:
        sorted_keys = sorted(features.keys())
        values = [features.get(k, 0.0) for k in sorted_keys]
        return np.array(values, dtype=np.float64)

    @staticmethod
    def _cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return float(np.dot(vec1, vec2) / (norm1 * norm2))

    def _compare_features(self, query: dict, record: dict) -> dict:
        comparison = {}
        all_keys = set(query.keys()) | set(record.keys())

        for key in all_keys:
            q_val = query.get(key, 0.0)
            r_val = record.get(key, 0.0)
            diff = abs(q_val - r_val)
            rel_diff = diff / max(abs(q_val), 1e-10)
            comparison[key] = {
                "query": round(q_val, 6),
                "record": round(r_val, 6),
                "absolute_diff": round(diff, 6),
                "relative_diff": round(rel_diff, 4),
            }

        return comparison

    @staticmethod
    def _compute_avg_vibration(records: list[GroundTruthRecord]) -> float:
        rms_values = []
        for r in records:
            for key, val in r.vibration_features.items():
                if "rms" in key:
                    rms_values.append(val)
        return float(np.mean(rms_values)) if rms_values else 0.0

    @staticmethod
    def _calculate_trend_direction(trend_data: list[dict]) -> str:
        if len(trend_data) < 2:
            return "insufficient_data"

        ratios = [td["good_ratio"] for td in trend_data]
        n = len(ratios)

        x_mean = (n - 1) / 2
        y_mean = sum(ratios) / n

        numerator = sum((i - x_mean) * (ratios[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return "stable"

        slope = numerator / denominator

        if slope > 0.01:
            return "improving"
        elif slope < -0.01:
            return "degrading"
        else:
            return "stable"
