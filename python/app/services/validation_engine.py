import math
from typing import List, Dict, Optional, Any
from dataclasses import asdict
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.models.validation import CuttingDataPoint, ValidationResult, ValidationReport, ValidationStatus
from app.services.dataset_manager import DatasetManager
from app.core.scenario_manager import scenario_manager


class ValidationEngine:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self.dataset_manager = DatasetManager()
        self.thresholds = {
            "F_c": 0.15,
            "T": 0.20,
            "R_a": 0.25
        }
        self._scenario_id = "base"

    def set_scenario(self, scenario_id: str):
        self._scenario_id = scenario_id
        try:
            validation_rules = scenario_manager.get_validation_rules(scenario_id)
            tolerance_thresholds = validation_rules.get("tolerance_thresholds", {})
            if tolerance_thresholds:
                self.thresholds.update(tolerance_thresholds)
        except Exception:
            pass

    def set_thresholds(self, thresholds: Dict[str, float]):
        if "cutting_force" in thresholds:
            self.thresholds["F_c"] = thresholds["cutting_force"] / 100
        if "tool_life" in thresholds:
            self.thresholds["T"] = thresholds["tool_life"] / 100
        if "surface_roughness" in thresholds:
            self.thresholds["R_a"] = thresholds["surface_roughness"] / 100

    def calculate_kienzle_force(self, v_c: float, f: float, a_p: float, material: str = "45钢") -> float:
        kc_base = 1800.0
        f_ref = 0.1
        exponent = -0.25
        kc = kc_base * ((f / f_ref) ** exponent)
        fc = kc * a_p * f
        return fc

    def calculate_taylor_life(self, v_c: float, n: float = 0.25, c: float = 350.0) -> float:
        t = (c / (v_c ** (1 - n))) ** (1 / n)
        return t

    def calculate_surface_roughness(self, f: float, re: float = 0.8) -> float:
        ra = (f ** 2) / (8 * re) * 1000
        return ra

    def calculate_mape(self, predicted: List[float], actual: List[float]) -> float:
        if not actual:
            return 0.0
        errors = []
        for p, a in zip(predicted, actual):
            if a != 0:
                errors.append(abs((p - a) / a) * 100)
        return sum(errors) / len(errors) if errors else 0.0

    def calculate_rmse(self, predicted: List[float], actual: List[float]) -> float:
        if not predicted:
            return 0.0
        squared_errors = [(p - a) ** 2 for p, a in zip(predicted, actual)]
        return math.sqrt(sum(squared_errors) / len(squared_errors))

    def calculate_r_squared(self, predicted: List[float], actual: List[float]) -> float:
        if len(actual) < 2:
            return 0.0
        mean_actual = sum(actual) / len(actual)
        ss_tot = sum((a - mean_actual) ** 2 for a in actual)
        ss_res = sum((a - p) ** 2 for p, a in zip(predicted, actual))
        if ss_tot == 0:
            return 0.0
        return 1 - (ss_res / ss_tot)

    async def run_online_validation(self, task_id: str, params: Dict[str, Any]) -> List[ValidationResult]:
        results = []

        with self.logger.log_step(task_id, "validation_engine", StepType.VALIDATION,
                                  input_data={"type": "online", "params": params}):
            pass

        v_c = params.get("v_c", 150.0)
        f = params.get("f", 0.20)
        a_p = params.get("a_p", 2.0)
        material = params.get("material", "45钢")

        fc_pred = self.calculate_kienzle_force(v_c, f, a_p, material)
        if params.get("F_c_actual"):
            fc_actual = params["F_c_actual"]
            fc_error = fc_pred - fc_actual
            fc_error_pct = abs(fc_error / fc_actual) * 100 if fc_actual != 0 else 0
            results.append(ValidationResult(
                metric_name="F_c",
                predicted_value=fc_pred,
                actual_value=fc_actual,
                error=fc_error,
                error_percent=fc_error_pct,
                status=ValidationStatus.PASS if fc_error_pct < self.thresholds["F_c"] * 100 else ValidationStatus.FAIL,
                threshold=self.thresholds["F_c"]
            ))

        t_pred = self.calculate_taylor_life(v_c)
        if params.get("T_actual"):
            t_actual = params["T_actual"]
            t_error = t_pred - t_actual
            t_error_pct = abs(t_error / t_actual) * 100 if t_actual != 0 else 0
            results.append(ValidationResult(
                metric_name="T",
                predicted_value=t_pred,
                actual_value=t_actual,
                error=t_error,
                error_percent=t_error_pct,
                status=ValidationStatus.PASS if t_error_pct < self.thresholds["T"] * 100 else ValidationStatus.FAIL,
                threshold=self.thresholds["T"]
            ))

        ra_pred = self.calculate_surface_roughness(f)
        if params.get("R_a_actual"):
            ra_actual = params["R_a_actual"]
            ra_error = ra_pred - ra_actual
            ra_error_pct = abs(ra_error / ra_actual) * 100 if ra_actual != 0 else 0
            results.append(ValidationResult(
                metric_name="R_a",
                predicted_value=ra_pred,
                actual_value=ra_actual,
                error=ra_error,
                error_percent=ra_error_pct,
                status=ValidationStatus.PASS if ra_error_pct < self.thresholds["R_a"] * 100 else ValidationStatus.FAIL,
                threshold=self.thresholds["R_a"]
            ))

        return results

    async def run_dataset_validation(self, task_id: str, dataset_name: str,
                                      generated_params: Dict[str, Any]) -> ValidationReport:
        with self.logger.log_step(task_id, "validation_engine", StepType.VALIDATION,
                                  input_data={"type": "offline", "dataset": dataset_name}):
            pass

        data = self.dataset_manager.filter_dataset(dataset_name)
        if not data:
            return ValidationReport(
                dataset_name=dataset_name,
                total_samples=0,
                pass_count=0,
                fail_count=0,
                mape=0.0,
                rmse=0.0,
                r_squared=0.0,
                details=[]
            )

        details = []
        fc_predicted = []
        fc_actual = []
        t_predicted = []
        t_actual = []
        ra_predicted = []
        ra_actual = []

        for point in data:
            fc_pred = self.calculate_kienzle_force(point.v_c, point.f, point.a_p, point.material)
            if point.F_c is not None:
                fc_predicted.append(fc_pred)
                fc_actual.append(point.F_c)
                fc_error = fc_pred - point.F_c
                fc_error_pct = abs(fc_error / point.F_c) * 100 if point.F_c != 0 else 0
                details.append(ValidationResult(
                    metric_name="F_c",
                    predicted_value=fc_pred,
                    actual_value=point.F_c,
                    error=fc_error,
                    error_percent=fc_error_pct,
                    status=ValidationStatus.PASS if fc_error_pct < self.thresholds["F_c"] * 100 else ValidationStatus.FAIL,
                    threshold=self.thresholds["F_c"]
                ))

            t_pred = self.calculate_taylor_life(point.v_c)
            if point.T is not None:
                t_predicted.append(t_pred)
                t_actual.append(point.T)
                t_error = t_pred - point.T
                t_error_pct = abs(t_error / point.T) * 100 if point.T != 0 else 0
                details.append(ValidationResult(
                    metric_name="T",
                    predicted_value=t_pred,
                    actual_value=point.T,
                    error=t_error,
                    error_percent=t_error_pct,
                    status=ValidationStatus.PASS if t_error_pct < self.thresholds["T"] * 100 else ValidationStatus.FAIL,
                    threshold=self.thresholds["T"]
                ))

            ra_pred = self.calculate_surface_roughness(point.f)
            if point.R_a is not None:
                ra_predicted.append(ra_pred)
                ra_actual.append(point.R_a)
                ra_error = ra_pred - point.R_a
                ra_error_pct = abs(ra_error / point.R_a) * 100 if point.R_a != 0 else 0
                details.append(ValidationResult(
                    metric_name="R_a",
                    predicted_value=ra_pred,
                    actual_value=point.R_a,
                    error=ra_error,
                    error_percent=ra_error_pct,
                    status=ValidationStatus.PASS if ra_error_pct < self.thresholds["R_a"] * 100 else ValidationStatus.FAIL,
                    threshold=self.thresholds["R_a"]
                ))

        total = len(details)
        pass_count = sum(1 for d in details if d.status == ValidationStatus.PASS)
        fail_count = total - pass_count

        combined_mape = 0.0
        if fc_predicted:
            combined_mape = self.calculate_mape(fc_predicted, fc_actual)
        elif t_predicted:
            combined_mape = self.calculate_mape(t_predicted, t_actual)
        elif ra_predicted:
            combined_mape = self.calculate_mape(ra_predicted, ra_actual)

        combined_rmse = 0.0
        if fc_predicted:
            combined_rmse = self.calculate_rmse(fc_predicted, fc_actual)
        elif t_predicted:
            combined_rmse = self.calculate_rmse(t_predicted, t_actual)
        elif ra_predicted:
            combined_rmse = self.calculate_rmse(ra_predicted, ra_actual)

        combined_r2 = 0.0
        if fc_predicted:
            combined_r2 = self.calculate_r_squared(fc_predicted, fc_actual)
        elif t_predicted:
            combined_r2 = self.calculate_r_squared(t_predicted, t_actual)
        elif ra_predicted:
            combined_r2 = self.calculate_r_squared(ra_predicted, ra_actual)

        report = ValidationReport(
            dataset_name=dataset_name,
            total_samples=total,
            pass_count=pass_count,
            fail_count=fail_count,
            mape=combined_mape,
            rmse=combined_rmse,
            r_squared=combined_r2,
            details=details
        )

        with self.logger.log_step(task_id, "validation_engine", StepType.VALIDATION,
                                  input_data={"type": "offline_summary", "dataset": dataset_name},
                                  output_data={"mape": combined_mape, "rmse": combined_rmse, "r2": combined_r2}):
            pass

        return report

    async def run_comprehensive_validation(self, task_id: str, datasets: List[str],
                                            params: Dict[str, Any]) -> Dict[str, Any]:
        online_results = await self.run_online_validation(task_id, params)

        dataset_reports = []
        for ds_name in datasets:
            report = await self.run_dataset_validation(task_id, ds_name, params)
            dataset_reports.append(report)

        combined_mape = 0.0
        combined_rmse = 0.0
        combined_r2 = 0.0

        if dataset_reports:
            combined_mape = sum(r.mape for r in dataset_reports) / len(dataset_reports)
            combined_rmse = sum(r.rmse for r in dataset_reports) / len(dataset_reports)
            combined_r2 = sum(r.r_squared for r in dataset_reports) / len(dataset_reports)

        return {
            "online_results": [asdict(r) for r in online_results],
            "dataset_reports": [asdict(r) for r in dataset_reports],
            "combined_metrics": {
                "mape": combined_mape,
                "rmse": combined_rmse,
                "r_squared": combined_r2
            }
        }


validation_engine = ValidationEngine
