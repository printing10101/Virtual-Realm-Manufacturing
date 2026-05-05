import asyncio
from typing import Any

from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType


class SimulationValidationService:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self.validation_stages = [
            "data_loading",
            "formula_calculation",
            "metric_evaluation",
            "result_analysis",
            "report_generation"
        ]

    async def validate_with_task(self, task_id: str | None = None,
                                  simulation_data: dict | None = None,
                                  validation_rules: list | None = None) -> dict:
        if not task_id:
            task_id = self.task_manager.create_task(
                task_type=self.task_manager.TaskType.SIMULATION_VALIDATION,
                params={
                    "simulation_data": simulation_data,
                    "validation_rules": validation_rules or []
                }
            )

        await self.task_manager.update_progress(task_id, 0, "正在初始化仿真验证...")

        with self.logger.log_step(task_id, "validation_service", StepType.WORKFLOW_START,
                                  input_data={"rules_count": len(validation_rules or [])}):
            pass

        async def _run_validation():
            stage_results = {}
            total_stages = len(self.validation_stages)

            params = simulation_data.get("params", {}) if simulation_data else {}
            params.get("v_c", 150.0)
            params.get("f", 0.20)
            params.get("a_p", 2.0)
            params.get("material", "45钢")

            calc_results = {}
            metrics_results = {}

            for idx, stage in enumerate(self.validation_stages):
                task = self.task_manager.get_task(task_id)
                if task and task.status.value == 'cancelled':
                    return {"cancelled": True, "stage_results": stage_results}

                progress = (idx / total_stages) * 100
                await self.task_manager.update_progress(
                    task_id, progress,
                    f"正在执行{self._get_stage_name(stage)}..."
                )

                with self.logger.log_step(
                    task_id, "validation_service", StepType.VALIDATION,
                    input_data={"stage": stage, "index": idx}
                ) as log_entry:
                    stage_result = await self._execute_stage(stage, params, calc_results, metrics_results)
                    stage_results[stage] = stage_result
                    log_entry.output = {"stage_status": stage_result["status"]}

                if stage == "formula_calculation":
                    calc_results = stage_result.get("calc_results", {})
                elif stage == "metric_evaluation":
                    metrics_results = stage_result.get("metrics", {})

                await self.task_manager.update_progress(
                    task_id, ((idx + 1) / total_stages) * 100,
                    f"完成{self._get_stage_name(stage)}"
                )

            validation_result = {
                "overall_status": "passed" if all(s["status"] == "passed" for s in stage_results.values()) else "failed",
                "stage_results": stage_results,
                "total_stages": total_stages,
                "passed_stages": len([s for s in stage_results.values() if s["status"] == "passed"]),
                "calc_results": calc_results,
                "metrics": metrics_results
            }

            return validation_result

        try:
            await self.task_manager.update_progress(task_id, 5, "开始执行验证...")
            result = await self.task_manager.run_with_timeout(task_id, _run_validation())

            if result.get("cancelled"):
                await self.task_manager.cancel_task(task_id)
                return result

            with self.logger.log_step(task_id, "validation_service", StepType.WORKFLOW_END,
                                      output_data=result):
                pass

            await self.task_manager.complete_task(task_id, result)
            return result
        except Exception as e:
            await self.task_manager.fail_task(task_id, str(e))
            raise

    async def _execute_stage(self, stage: str, params: dict, calc_results: dict, metrics_results: dict) -> dict:
        if stage == "data_loading":
            return await self._stage_data_loading(params)
        elif stage == "formula_calculation":
            return await self._stage_formula_calculation(params)
        elif stage == "metric_evaluation":
            return await self._stage_metric_evaluation(params, calc_results)
        elif stage == "result_analysis":
            return await self._stage_result_analysis(calc_results, metrics_results)
        elif stage == "report_generation":
            return await self._stage_report_generation(calc_results, metrics_results)
        return {"status": "skipped", "details": f"Unknown stage: {stage}"}

    async def _stage_data_loading(self, params: dict) -> dict:
        required_params = ["v_c", "f", "a_p"]
        missing = [p for p in required_params if p not in params]
        if missing:
            return {
                "status": "failed",
                "metrics": {"missing_params": missing},
                "details": f"缺少必需参数: {', '.join(missing)}"
            }
        return {
            "status": "passed",
            "metrics": {"loaded_params": list(params.keys())},
            "details": "数据加载成功"
        }

    async def _stage_formula_calculation(self, params: dict) -> dict:
        v_c = params.get("v_c", 150.0)
        f = params.get("f", 0.20)
        a_p = params.get("a_p", 2.0)
        params.get("material", "45钢")

        kc_base = 1800.0
        f_ref = 0.1
        exponent = -0.25
        kc = kc_base * ((f / f_ref) ** exponent)
        fc = kc * a_p * f

        n = 0.25
        c = 350.0
        t = (c / (v_c ** (1 - n))) ** (1 / n)

        re = params.get("nose_radius", 0.8)
        ra = (f ** 2) / (8 * re) * 1000

        calc_results = {
            "kienzle": {"cutting_force_N": fc, "specific_cutting_force_Nmm2": kc},
            "taylor": {"tool_life_min": t, "tool_life_hours": t / 60, "taylor_exponent": n},
            "surface_roughness": {"predicted_ra_um": ra}
        }

        return {
            "status": "passed",
            "metrics": {"fc": fc, "t": t, "ra": ra},
            "details": "公式计算完成",
            "calc_results": calc_results
        }

    async def _stage_metric_evaluation(self, params: dict, calc_results: dict) -> dict:

        metrics = {}
        all_passed = True

        if "kienzle" in calc_results:
            fc = calc_results["kienzle"]["cutting_force_N"]
            fc_limit = params.get("F_c_limit", 5000)
            fc_satisfied = fc <= fc_limit
            fc_margin = ((fc_limit - fc) / fc_limit * 100) if fc_limit > 0 else 0
            metrics["cutting_force"] = {
                "actual_value": fc,
                "limit": fc_limit,
                "unit": "N",
                "satisfied": fc_satisfied,
                "margin_percent": fc_margin
            }
            if not fc_satisfied:
                all_passed = False

        if "taylor" in calc_results:
            t = calc_results["taylor"]["tool_life_min"]
            t_limit = params.get("T_limit", 30)
            t_satisfied = t >= t_limit
            t_margin = ((t - t_limit) / t_limit * 100) if t_limit > 0 else 0
            metrics["tool_life"] = {
                "actual_value": t,
                "limit": t_limit,
                "unit": "min",
                "satisfied": t_satisfied,
                "margin_percent": t_margin
            }
            if not t_satisfied:
                all_passed = False

        if "surface_roughness" in calc_results:
            ra = calc_results["surface_roughness"]["predicted_ra_um"]
            ra_limit = params.get("Ra_limit", 1.6)
            ra_satisfied = ra <= ra_limit
            ra_margin = ((ra_limit - ra) / ra_limit * 100) if ra_limit > 0 else 0
            metrics["surface_roughness"] = {
                "actual_value": ra,
                "limit": ra_limit,
                "unit": "μm",
                "satisfied": ra_satisfied,
                "margin_percent": ra_margin
            }
            if not ra_satisfied:
                all_passed = False

        return {
            "status": "passed" if all_passed else "failed",
            "metrics": metrics,
            "details": "指标评估完成"
        }

    async def _stage_result_analysis(self, calc_results: dict, metrics_results: dict) -> dict:
        total_metrics = len(metrics_results)
        passed_metrics = sum(1 for m in metrics_results.values() if m.get("satisfied"))
        pass_rate = (passed_metrics / total_metrics * 100) if total_metrics > 0 else 0

        analysis = {
            "total_metrics": total_metrics,
            "passed_metrics": passed_metrics,
            "pass_rate": pass_rate,
            "overall_assessment": "良好" if pass_rate >= 80 else "需优化"
        }

        return {
            "status": "passed",
            "metrics": analysis,
            "details": f"结果分析完成，通过率 {pass_rate:.1f}%"
        }

    async def _stage_report_generation(self, calc_results: dict, metrics_results: dict) -> dict:
        report_summary = {
            "calculation_results": calc_results,
            "metric_evaluations": metrics_results,
            "timestamp": asyncio.get_event_loop().time()
        }

        return {
            "status": "passed",
            "metrics": {"report_generated": True},
            "details": "报告生成完成",
            "report_summary": report_summary
        }

    def _get_stage_name(self, stage_key: str) -> str:
        names = {
            "data_loading": "数据加载",
            "formula_calculation": "公式计算",
            "metric_evaluation": "指标评估",
            "result_analysis": "结果分析",
            "report_generation": "报告生成"
        }
        return names.get(stage_key, stage_key)


validation_service = SimulationValidationService
