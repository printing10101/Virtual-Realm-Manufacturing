"""CNC 工艺验证引擎

支持两种验证模式：
1. 理论验证：基于物理模型（Kienzle 切削力、Taylor 刀具寿命等）
2. Bosch 数据驱动验证：基于 Bosch CNC 真实工业数据校准的阈值
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, TYPE_CHECKING

import numpy as np

if TYPE_CHECKING:
    from app.core.task_manager import TaskManager

from app.core.physical_models import KienzleModel, TaylorModel, SurfaceRoughnessModel
from app.models.validation import CuttingDataPoint, ValidationResult, ValidationReport, ValidationStatus

logger = logging.getLogger(__name__)


class ValidationEngine:
    """CNC 工艺验证引擎"""

    def __init__(
        self,
        rules_path: str = "python/app/core/validation_rules.json",
        task_manager: Optional["TaskManager"] = None,
        workflow_logger=None,
        config=None,
    ):
        self.rules_path = Path(rules_path)
        self.rules = self._load_rules()
        self._backup_path: Optional[Path] = None
        self.task_manager = task_manager
        self.workflow_logger = workflow_logger
        self.config = config

    def _load_rules(self) -> dict:
        if self.rules_path.exists():
            with open(self.rules_path, "r", encoding="utf-8") as f:
                return json.load(f)
        logger.warning("Validation rules not found at %s, using defaults", self.rules_path)
        return self._default_rules()

    @staticmethod
    def _default_rules() -> dict:
        return {
            "general_rules": {
                "anomaly_detection_confidence": 0.95,
                "minimum_samples_for_calibration": 20,
                "default_warning_k": 2.0,
                "default_critical_k": 3.0,
                "vibration_rms_warning_multiplier": 2.0,
                "vibration_rms_critical_multiplier": 3.0,
            },
            "theoretical_thresholds": {
                "vibration_rms_limits": {
                    "max_healthy_g": 0.15,
                    "warning_threshold_g": 0.30,
                    "critical_threshold_g": 0.45,
                },
                "frequency_analysis": {
                    "dominant_freq_range_hz": [50, 200],
                    "shift_warning_percent": 10,
                    "shift_critical_percent": 20,
                },
                "energy_distribution": {
                    "x_axis_ratio": 0.45,
                    "y_axis_ratio": 0.35,
                    "z_axis_ratio": 0.20,
                    "imbalance_warning_percent": 25,
                },
            },
        }

    def reload_rules(self) -> None:
        self.rules = self._load_rules()

    def save_rules(self, path: Optional[str] = None) -> None:
        target = Path(path) if path else self.rules_path
        with open(target, "w", encoding="utf-8") as f:
            json.dump(self.rules, f, indent=2, ensure_ascii=False)
        logger.info("Validation rules saved to %s", target)

    def backup_rules(self) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_name = f"validation_rules_backup_{timestamp}.json"
        self._backup_path = self.rules_path.parent / backup_name
        with open(self._backup_path, "w", encoding="utf-8") as f:
            json.dump(self.rules, f, indent=2, ensure_ascii=False)
        logger.info("Rules backed up to %s", self._backup_path)
        return self._backup_path

    def restore_from_backup(self, backup_path: Optional[Path] = None) -> None:
        target = backup_path or self._backup_path
        if target is None or not target.exists():
            raise FileNotFoundError("No backup found to restore")
        with open(target, "r", encoding="utf-8") as f:
            self.rules = json.load(f)
        self.save_rules()
        logger.info("Rules restored from %s", target)

    # ==================== 理论验证方法 ====================
    # 注意：物理公式已迁移到 app.core.physical_models 模块
    # 这些方法保留为向后兼容的包装器

    def calculate_kienzle_force(
        self, v_c: float, f: float, a_p: float,
        k_c: float = 2000.0, mc: float = 0.25,
    ) -> float:
        """向后兼容的Kienzle力计算方法（委托给统一模型）"""
        result = KienzleModel.calculate_cutting_force(v_c, f, a_p, kc_base=k_c, mc=mc)
        return result["cutting_force_N"]

    def calculate_taylor_life(
        self, v_c: float, n: float = 0.25, c: float = 350.0,
    ) -> float:
        """向后兼容的Taylor寿命计算方法（委托给统一模型）"""
        return TaylorModel.calculate_tool_life(v_c, n=n, c=c)

    def calculate_surface_roughness(self, f: float, re: float = 0.8) -> float:
        """向后兼容的表面粗糙度计算方法（委托给统一模型）"""
        return SurfaceRoughnessModel.calculate_ra(f, re)

    def calculate_mape(self, predicted: list, actual: list) -> float:
        if not actual or len(predicted) != len(actual):
            return 0.0
        errors = []
        for p, a in zip(predicted, actual):
            if a != 0:
                errors.append(abs((p - a) / a) * 100)
        return float(np.mean(errors)) if errors else 0.0

    def calculate_rmse(self, predicted: list, actual: list) -> float:
        if not actual or len(predicted) != len(actual):
            return 0.0
        errors = [(p - a) ** 2 for p, a in zip(predicted, actual)]
        return float(np.sqrt(np.mean(errors)))

    def calculate_r_squared(self, predicted: list, actual: list) -> float:
        if not actual or len(predicted) != len(actual):
            return 0.0
        actual_arr = np.array(actual)
        predicted_arr = np.array(predicted)
        ss_res = np.sum((actual_arr - predicted_arr) ** 2)
        ss_tot = np.sum((actual_arr - np.mean(actual_arr)) ** 2)
        if ss_tot == 0:
            return 0.0
        return float(1 - ss_res / ss_tot)

    async def run_online_validation(self, task_id: str, params: dict) -> list:
        results = []
        v_c = params.get("v_c", 150.0)
        f = params.get("f", 0.2)
        a_p = params.get("a_p", 2.0)

        fc_pred = self.calculate_kienzle_force(v_c, f, a_p)
        fc_actual = params.get("F_c_actual")
        if fc_actual is not None:
            error = fc_pred - fc_actual
            error_pct = abs(error / fc_actual) * 100 if fc_actual != 0 else 0
            threshold = fc_pred * 0.2
            status = ValidationStatus.PASS if abs(error_pct) < 20 else ValidationStatus.FAIL
            results.append(ValidationResult(
                metric_name="F_c",
                predicted_value=fc_pred,
                actual_value=fc_actual,
                error=error,
                error_percent=error_pct,
                status=status,
                threshold=threshold,
            ))

        t_pred = self.calculate_taylor_life(v_c)
        t_actual = params.get("T_actual")
        if t_actual is not None:
            error = t_pred - t_actual
            error_pct = abs(error / t_actual) * 100 if t_actual != 0 else 0
            threshold = t_pred * 0.3
            status = ValidationStatus.PASS if abs(error_pct) < 30 else ValidationStatus.FAIL
            results.append(ValidationResult(
                metric_name="T",
                predicted_value=t_pred,
                actual_value=t_actual,
                error=error,
                error_percent=error_pct,
                status=status,
                threshold=threshold,
            ))

        ra_pred = self.calculate_surface_roughness(f)
        ra_actual = params.get("R_a_actual")
        if ra_actual is not None:
            error = ra_pred - ra_actual
            error_pct = abs(error / ra_actual) * 100 if ra_actual != 0 else 0
            threshold = ra_pred * 0.25
            status = ValidationStatus.PASS if abs(error_pct) < 25 else ValidationStatus.FAIL
            results.append(ValidationResult(
                metric_name="R_a",
                predicted_value=ra_pred,
                actual_value=ra_actual,
                error=error,
                error_percent=error_pct,
                status=status,
                threshold=threshold,
            ))

        return results

    async def run_dataset_validation(
        self, task_id: str, dataset_name: str, params: dict,
    ) -> ValidationReport:
        if self.config and hasattr(self.config, "datasets"):
            ds = self.config.datasets.get(dataset_name, {})
            data_points = ds.get("data", [])
        else:
            data_points = []

        predicted_values = []
        actual_values = []
        details = []

        for dp in data_points:
            if isinstance(dp, CuttingDataPoint) and dp.F_c is not None:
                fc_pred = self.calculate_kienzle_force(
                    dp.v_c if dp.v_c else params.get("v_c", 150.0),
                    dp.f if dp.f else params.get("f", 0.2),
                    dp.a_p if dp.a_p else params.get("a_p", 2.0),
                )
                predicted_values.append(fc_pred)
                actual_values.append(dp.F_c)

                error = fc_pred - dp.F_c
                error_pct = abs(error / dp.F_c) * 100 if dp.F_c != 0 else 0
                threshold = fc_pred * 0.2
                status = ValidationStatus.PASS if abs(error_pct) < 20 else ValidationStatus.FAIL
                details.append(ValidationResult(
                    metric_name="F_c",
                    predicted_value=fc_pred,
                    actual_value=dp.F_c,
                    error=error,
                    error_percent=error_pct,
                    status=status,
                    threshold=threshold,
                ))

        mape = self.calculate_mape(predicted_values, actual_values)
        rmse = self.calculate_rmse(predicted_values, actual_values)
        r_squared = self.calculate_r_squared(predicted_values, actual_values)
        pass_count = sum(1 for d in details if d.status == ValidationStatus.PASS)
        fail_count = sum(1 for d in details if d.status == ValidationStatus.FAIL)

        return ValidationReport(
            dataset_name=dataset_name,
            total_samples=len(data_points),
            pass_count=pass_count,
            fail_count=fail_count,
            mape=mape,
            rmse=rmse,
            r_squared=r_squared,
            details=details,
        )

    async def run_comprehensive_validation(
        self, task_id: str, dataset_names: list, params: dict,
    ) -> dict:
        online_results = await self.run_online_validation(task_id, params)

        dataset_reports = []
        all_predicted = []
        all_actual = []

        for ds_name in dataset_names:
            report = await self.run_dataset_validation(task_id, ds_name, params)
            dataset_reports.append(report)
            for detail in report.details:
                all_predicted.append(detail.predicted_value)
                all_actual.append(detail.actual_value)

        combined_mape = self.calculate_mape(all_predicted, all_actual)
        combined_rmse = self.calculate_rmse(all_predicted, all_actual)
        combined_r_squared = self.calculate_r_squared(all_predicted, all_actual)

        return {
            "online_results": online_results,
            "dataset_reports": dataset_reports,
            "combined_metrics": {
                "mape": combined_mape,
                "rmse": combined_rmse,
                "r_squared": combined_r_squared,
            },
        }

    # ==================== Bosch 数据驱动验证方法 ====================

    def validate_with_theoretical(
        self,
        vibration_rms: float,
        frequency_shift_percent: float = 0.0,
    ) -> dict:
        limits = self.rules.get("theoretical_thresholds", {}).get("vibration_rms_limits", {})
        warning = limits.get("warning_threshold_g", 0.30)
        critical = limits.get("critical_threshold_g", 0.45)

        checks = []
        if vibration_rms > critical:
            vibration_status = "fail"
            vibration_msg = f"RMS {vibration_rms:.3f}g exceeds critical threshold {critical:.3f}g"
        elif vibration_rms > warning:
            vibration_status = "warning"
            vibration_msg = f"RMS {vibration_rms:.3f}g exceeds warning threshold {warning:.3f}g"
        else:
            vibration_status = "pass"
            vibration_msg = f"RMS {vibration_rms:.3f}g within normal range"

        checks.append({
            "name": "vibration_rms",
            "status": vibration_status,
            "value": round(vibration_rms, 4),
            "threshold": warning,
            "message": vibration_msg,
        })

        freq_config = self.rules.get("theoretical_thresholds", {}).get("frequency_analysis", {})
        freq_warn = freq_config.get("shift_warning_percent", 10)
        freq_crit = freq_config.get("shift_critical_percent", 20)

        if frequency_shift_percent > freq_crit:
            freq_status = "fail"
            freq_msg = f"Frequency shift {frequency_shift_percent:.1f}% exceeds critical {freq_crit}%"
        elif frequency_shift_percent > freq_warn:
            freq_status = "warning"
            freq_msg = f"Frequency shift {frequency_shift_percent:.1f}% exceeds warning {freq_warn}%"
        else:
            freq_status = "pass"
            freq_msg = f"Frequency shift {frequency_shift_percent:.1f}% within normal range"

        checks.append({
            "name": "frequency_shift",
            "status": freq_status,
            "value": round(frequency_shift_percent, 2),
            "threshold": freq_warn,
            "message": freq_msg,
        })

        is_valid = all(c["status"] == "pass" for c in checks)
        has_fail = any(c["status"] == "fail" for c in checks)

        if has_fail:
            overall_risk = "high"
        elif any(c["status"] == "warning" for c in checks):
            overall_risk = "medium"
        else:
            overall_risk = "low"

        recommendations = []
        if vibration_status != "pass":
            recommendations.append("Check tool condition and reduce cutting parameters")
        if freq_status != "pass":
            recommendations.append("Investigate spindle imbalance or resonance issues")
        if not recommendations:
            recommendations.append("Process parameters within normal operating range")

        return {
            "is_valid": is_valid,
            "checks": checks,
            "overall_risk": overall_risk,
            "recommendations": recommendations,
        }

    def validate_with_bosch_baseline(
        self,
        process: str,
        vibration_features: dict,
        machine: str = "M01",
    ) -> dict:
        calibrated = self.rules.get("bosch_calibrated", {})
        if calibrated.get("calibration_status") != "applied":
            return {
                "is_valid": True,
                "checks": [],
                "overall_risk": "unknown",
                "recommendations": ["Bosch calibration not yet applied. Using theoretical thresholds."],
            }

        process_thresholds = calibrated.get("process_thresholds", {})
        process_config = process_thresholds.get(process)
        if not process_config:
            return {
                "is_valid": True,
                "checks": [],
                "overall_risk": "unknown",
                "recommendations": [f"No calibrated thresholds for process {process}"],
            }

        checks = []
        recommendations = []

        vibration_cfg = process_config.get("vibration", {})
        for axis in ["x_axis", "y_axis", "z_axis"]:
            axis_cfg = vibration_cfg.get(axis, {})
            rms_value = vibration_features.get(f"vibration_rms_{axis.replace('_axis', '')}", 0.0)
            warning = axis_cfg.get("warning_threshold", 0.3)
            critical = axis_cfg.get("critical_threshold", 0.45)

            if rms_value > critical:
                status = "fail"
                msg = f"{axis} RMS {rms_value:.3f} exceeds critical {critical:.3f}"
                recommendations.append(f"Check {axis} vibration - possible tool wear or imbalance")
            elif rms_value > warning:
                status = "warning"
                msg = f"{axis} RMS {rms_value:.3f} exceeds warning {warning:.3f}"
                recommendations.append(f"Monitor {axis} vibration trend")
            else:
                status = "pass"
                msg = f"{axis} RMS {rms_value:.3f} within normal range"

            checks.append({
                "name": f"vibration_rms_{axis}",
                "status": status,
                "value": round(rms_value, 4),
                "threshold": warning,
                "message": msg,
            })

        freq_cfg = process_config.get("frequency", {})
        dominant_freq = vibration_features.get("dominant_frequency", 0.0)
        freq_range = freq_cfg.get("dominant_range", [50, 200])
        freq_warn_pct = freq_cfg.get("shift_warning_percent", 15)
        freq_crit_pct = freq_cfg.get("shift_critical_percent", 25)

        freq_center = (freq_range[0] + freq_range[1]) / 2
        if freq_center > 0:
            shift_pct = abs(dominant_freq - freq_center) / freq_center * 100
        else:
            shift_pct = 0.0

        if shift_pct > freq_crit_pct:
            freq_status = "fail"
            freq_msg = f"Frequency shift {shift_pct:.1f}% exceeds critical {freq_crit_pct}%"
            recommendations.append("Spindle frequency shift critical - inspect spindle bearings")
        elif shift_pct > freq_warn_pct:
            freq_status = "warning"
            freq_msg = f"Frequency shift {shift_pct:.1f}% exceeds warning {freq_warn_pct}%"
            recommendations.append("Monitor spindle frequency drift")
        else:
            freq_status = "pass"
            freq_msg = f"Frequency shift {shift_pct:.1f}% within normal range"

        checks.append({
            "name": "frequency_shift",
            "status": freq_status,
            "value": round(shift_pct, 2),
            "threshold": freq_warn_pct,
            "message": freq_msg,
        })

        energy_cfg = process_config.get("energy_ratio", {})
        normal_dist = energy_cfg.get("normal_distribution", {})
        imbalance_warn = energy_cfg.get("imbalance_warning_percent", 30)

        for axis_short in ["x", "y", "z"]:
            key = f"energy_ratio_{axis_short}"
            actual = vibration_features.get(key, 0.0)
            expected = normal_dist.get(axis_short, 0.0)
            if expected > 0:
                deviation_pct = abs(actual - expected) / expected * 100
            else:
                deviation_pct = 0.0

            if deviation_pct > imbalance_warn:
                e_status = "warning"
                e_msg = f"{axis_short}-axis energy ratio deviation {deviation_pct:.1f}%"
                recommendations.append(f"{axis_short}-axis energy distribution imbalanced")
            else:
                e_status = "pass"
                e_msg = f"{axis_short}-axis energy ratio within normal deviation"

            checks.append({
                "name": f"energy_ratio_{axis_short}",
                "status": e_status,
                "value": round(actual, 4),
                "threshold": imbalance_warn,
                "message": e_msg,
            })

        is_valid = all(c["status"] == "pass" for c in checks)
        has_fail = any(c["status"] == "fail" for c in checks)

        if has_fail:
            overall_risk = "high"
        elif any(c["status"] == "warning" for c in checks):
            overall_risk = "medium"
        else:
            overall_risk = "low"

        if not recommendations:
            recommendations.append("All calibrated thresholds within normal range")

        return {
            "is_valid": is_valid,
            "checks": checks,
            "overall_risk": overall_risk,
            "recommendations": recommendations,
        }

    def get_process_calibration_status(self, process: str) -> dict:
        calibrated = self.rules.get("bosch_calibrated", {})
        process_thresholds = calibrated.get("process_thresholds", {})
        process_config = process_thresholds.get(process)

        if not process_config:
            return {
                "process": process,
                "calibrated": False,
                "sample_count": 0,
                "confidence": 0.0,
                "message": f"No calibration data for process {process}",
            }

        return {
            "process": process,
            "calibrated": True,
            "sample_count": process_config.get("sample_count", 0),
            "confidence": process_config.get("confidence", 0.0),
            "last_calibrated": calibrated.get("last_calibrated", "unknown"),
            "message": f"Process {process} calibrated with {process_config.get('sample_count', 0)} samples",
        }

    def apply_calibrated_rules(self, calibrated_rules: dict) -> None:
        self.backup_rules()
        self.rules["bosch_calibrated"]["process_thresholds"].update(
            calibrated_rules.get("process_thresholds", {})
        )
        self.rules["bosch_calibrated"]["calibration_status"] = "applied"
        self.rules["bosch_calibrated"]["last_calibrated"] = calibrated_rules.get(
            "last_calibrated", datetime.now().strftime("%Y-%m-%d")
        )
        self.save_rules()
        logger.info("Applied calibrated rules for %d processes", len(calibrated_rules.get("process_thresholds", {})))

    def get_theoretical_threshold(self, rule_name: str, default: float = 0.0) -> float:
        theoretical = self.rules.get("theoretical_thresholds", {})
        return self._resolve_path(theoretical, rule_name, default)

    def get_general_rule(self, rule_name: str, default=None):
        general = self.rules.get("general_rules", {})
        return general.get(rule_name, default)

    @staticmethod
    def _resolve_path(d: dict, path: str, default=None):
        keys = path.split(".")
        current = d
        for k in keys:
            if isinstance(current, dict) and k in current:
                current = current[k]
            else:
                return default
        return current