"""Validation rule calibrator using Bosch CNC real-world data."""

import json
import logging
from datetime import datetime
from pathlib import Path

import numpy as np

from app.data.bosch_cnc_loader import BoschCNCDataLoader

logger = logging.getLogger(__name__)


class ValidationCalibrator:
    """Calibrate validation rule thresholds using real industrial data."""

    def __init__(
        self,
        data_dir: str = "python/data/datasets/bosch_cnc",
        rules_path: str = "python/app/core/validation_rules.json",
        warning_k: float = 2.0,
        critical_k: float = 3.0,
    ):
        self.loader = BoschCNCDataLoader(data_dir)
        self.rules_path = Path(rules_path)
        self.warning_k = warning_k
        self.critical_k = critical_k
        self._calibration_cache: dict = {}

    def calibrate_vibration_thresholds(
        self,
        process: str | None = None,
        machine: str | None = None,
    ) -> dict:
        """Calculate vibration threshold baselines from normal operation data."""
        cache_key = f"{process}_{machine}"
        if cache_key in self._calibration_cache:
            return self._calibration_cache[cache_key]

        samples = self.loader.load_dataset(
            machines=[machine] if machine else None,
            processes=[process] if process else None,
            labels=["good"],
        )

        if not samples:
            raise ValueError(
                f"No 'good' samples found for process={process}, machine={machine}"
            )

        rms_x, rms_y, rms_z = [], [], []
        freq_x, freq_y, freq_z = [], [], []
        energy_x, energy_y, energy_z = [], [], []

        for sample in samples:
            features = self.loader.extract_features(sample["data"])

            rms_x.append(features.get("time_x_rms", 0.0))
            rms_y.append(features.get("time_y_rms", 0.0))
            rms_z.append(features.get("time_z_rms", 0.0))

            freq_x.append(features.get("freq_x_dominant_freq", 0.0))
            freq_y.append(features.get("freq_y_dominant_freq", 0.0))
            freq_z.append(features.get("freq_z_dominant_freq", 0.0))

            energy_x.append(features.get("cross_x_energy_ratio", 0.0))
            energy_y.append(features.get("cross_y_energy_ratio", 0.0))
            energy_z.append(features.get("cross_z_energy_ratio", 0.0))

        n_samples = len(samples)

        result = {
            "process": process or "ALL",
            "machine": machine or "ALL",
            "vibration": {
                "x_axis": self._axis_thresholds(np.array(rms_x)),
                "y_axis": self._axis_thresholds(np.array(rms_y)),
                "z_axis": self._axis_thresholds(np.array(rms_z)),
            },
            "frequency": {
                "dominant_range": [
                    round(float(np.mean(freq_x + freq_y + freq_z)) * 0.8, 2),
                    round(float(np.mean(freq_x + freq_y + freq_z)) * 1.2, 2),
                ],
                "shift_warning_percent": 15.0,
                "shift_critical_percent": 25.0,
            },
            "energy_ratio": {
                "normal_distribution": {
                    "x": round(float(np.mean(energy_x)), 4),
                    "y": round(float(np.mean(energy_y)), 4),
                    "z": round(float(np.mean(energy_z)), 4),
                },
                "imbalance_warning_percent": 30.0,
            },
            "sample_count": n_samples,
            "confidence": self._calculate_confidence(n_samples),
        }

        if n_samples < 20:
            logger.warning(
                "Insufficient samples (%d < 20) for %s - thresholds may be unreliable",
                n_samples, cache_key,
            )

        self._calibration_cache[cache_key] = result
        return result

    def calibrate_all_processes(self) -> dict:
        """Generate calibrated thresholds for all processes."""
        summary = self.loader.get_dataset_summary()
        all_processes = summary.get("available_processes", [])
        all_machines = summary.get("available_machines", [])

        calibrated: dict = {}
        for process in all_processes:
            try:
                result = self.calibrate_vibration_thresholds(process=process)
                calibrated[process] = result
                logger.info(
                    "Calibrated process %s with %d samples (confidence=%.2f)",
                    process, result["sample_count"], result["confidence"],
                )
            except Exception as e:
                logger.warning("Failed to calibrate %s: %s", process, e)

        return calibrated

    def compare_with_current_rules(self) -> dict:
        """Compare calibrated results with current validation_rules.json."""
        calibrated = self._load_or_calibrate()
        if not calibrated:
            return {"error": "No calibrated data available"}

        current_rules = self._load_rules()
        theoretical = current_rules.get("theoretical_thresholds", {})
        bosch_section = current_rules.get("bosch_calibrated", {})
        existing_calibrated = bosch_section.get("process_thresholds", {})

        comparison: dict = {}
        for process, cal_data in calibrated.items():
            process_comparison: dict = {}

            vibration_limits = theoretical.get("vibration_rms_limits", {})
            current_warning = vibration_limits.get("warning_threshold_g", 0.30)
            current_critical = vibration_limits.get("critical_threshold_g", 0.45)

            for axis in ["x_axis", "y_axis", "z_axis"]:
                axis_data = cal_data["vibration"][axis]
                cal_warning = axis_data["warning_threshold"]
                cal_critical = axis_data["critical_threshold"]

                warning_dev = self._percent_deviation(current_warning, cal_warning)
                critical_dev = self._percent_deviation(current_critical, cal_critical)

                process_comparison[f"vibration_{axis}_warning"] = {
                    "current": current_warning,
                    "calibrated": round(cal_warning, 4),
                    "deviation": round(warning_dev, 2),
                }
                process_comparison[f"vibration_{axis}_critical"] = {
                    "current": current_critical,
                    "calibrated": round(cal_critical, 4),
                    "deviation": round(critical_dev, 2),
                }

            existing = existing_calibrated.get(process, {})
            if existing:
                process_comparison["_already_calibrated"] = True

            comparison[process] = process_comparison

        return comparison

    def generate_updated_rules(self) -> dict:
        """Generate complete calibrated validation rules in JSON format."""
        calibrated = self.calibrate_all_processes()

        rules = self._load_rules()
        rules["bosch_calibrated"]["last_calibrated"] = datetime.now().strftime("%Y-%m-%d")
        rules["bosch_calibrated"]["calibration_status"] = "pending"
        rules["bosch_calibrated"]["process_thresholds"] = {}

        for process, cal_data in calibrated.items():
            rules["bosch_calibrated"]["process_thresholds"][process] = {
                "vibration": cal_data["vibration"],
                "frequency": cal_data["frequency"],
                "energy_ratio": cal_data["energy_ratio"],
                "sample_count": cal_data["sample_count"],
                "confidence": cal_data["confidence"],
                "vibration_rms_warning_multiplier": round(
                    cal_data["vibration"]["x_axis"]["warning_threshold"]
                    / max(cal_data["vibration"]["x_axis"]["rms_normal_range"][0], 1e-10),
                    2,
                ),
                "vibration_rms_critical_multiplier": round(
                    cal_data["vibration"]["x_axis"]["critical_threshold"]
                    / max(cal_data["vibration"]["x_axis"]["rms_normal_range"][0], 1e-10),
                    2,
                ),
                "frequency_shift_warning_percent": cal_data["frequency"]["shift_warning_percent"],
                "frequency_shift_critical_percent": cal_data["frequency"]["shift_critical_percent"],
            }

        return rules

    def apply_calibration(self, confirmed: bool = True) -> dict:
        """Apply calibrated rules after user confirmation."""
        if not confirmed:
            return {"status": "cancelled", "message": "Calibration not confirmed"}

        updated_rules = self.generate_updated_rules()
        self._save_rules(updated_rules)
        logger.info(
            "Calibration applied: %d processes calibrated",
            len(updated_rules["bosch_calibrated"]["process_thresholds"]),
        )
        return {
            "status": "applied",
            "process_count": len(updated_rules["bosch_calibrated"]["process_thresholds"]),
            "last_calibrated": updated_rules["bosch_calibrated"]["last_calibrated"],
        }

    def _axis_thresholds(self, rms_values: np.ndarray) -> dict:
        """Calculate per-axis thresholds using mean + k*std."""
        mean_val = float(np.mean(rms_values))
        std_val = float(np.std(rms_values, ddof=1))

        normal_min = float(np.percentile(rms_values, 5))
        normal_max = float(np.percentile(rms_values, 95))

        return {
            "rms_normal_range": [round(normal_min, 4), round(normal_max, 4)],
            "warning_threshold": round(mean_val + self.warning_k * std_val, 4),
            "critical_threshold": round(mean_val + self.critical_k * std_val, 4),
            "mean": round(mean_val, 4),
            "std": round(std_val, 4),
        }

    def _calculate_confidence(self, n_samples: int) -> float:
        """Calculate confidence level based on sample count."""
        if n_samples < 5:
            return 0.5
        if n_samples < 20:
            return 0.7
        if n_samples < 50:
            return 0.85
        return 0.95

    def _load_rules(self) -> dict:
        if self.rules_path.exists():
            with open(self.rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_rules(self, rules: dict) -> None:
        with open(self.rules_path, "w", encoding="utf-8") as f:
            json.dump(rules, f, indent=2, ensure_ascii=False)

    def _load_or_calibrate(self) -> dict:
        if self._calibration_cache:
            return self._calibration_cache
        try:
            return self.calibrate_all_processes()
        except Exception as e:
            logger.error("Auto-calibration failed: %s", e)
            return {}

    @staticmethod
    def _percent_deviation(current: float, calibrated: float) -> float:
        if current == 0:
            return 0.0
        return (calibrated - current) / current * 100