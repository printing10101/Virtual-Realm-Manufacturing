import asyncio
import uuid
from typing import Optional, Dict, Any, List
from app.core.task_manager import TaskManager, TaskType
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.core.process_trace import ProcessTrace, TraceNode
from app.core.hypothesis_loop import HypothesisDrivenLoop, HypothesisLoopResult
from app.agents.hypothesis_generator import HypothesisGenerator
from app.services.ai_service import AIService
from app.core.scenario_manager import scenario_manager


class ProcessService:
    def __init__(self, task_manager: TaskManager, workflow_logger: AIWorkflowLogger, config: Any, ai_service: Optional[AIService] = None):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.config = config
        self.trace = ProcessTrace()
        self.ai_service = ai_service
        self.default_scenario = "base"
        self.process_stages = [
            "constraint_parsing",
            "parameter_optimization",
            "solver_execution",
            "result_validation"
        ]

        if ai_service:
            self.hypothesis_generator = HypothesisGenerator(ai_service, workflow_logger)
            self.hypothesis_loop = HypothesisDrivenLoop(
                task_manager=task_manager,
                workflow_logger=workflow_logger,
                hypothesis_generator=self.hypothesis_generator,
                max_iterations=5
            )
        else:
            self.hypothesis_generator = None
            self.hypothesis_loop = None

    async def generate_process_params_with_task(self, task_id: Optional[str] = None,
                                                  user_requirements: Dict = None,
                                                  material: str = "",
                                                  part_type: str = "",
                                                  scenario_id: Optional[str] = None,
                                                  parent_node_id: Optional[str] = None) -> Dict:
        scenario = scenario_id or self.default_scenario

        if not task_id:
            task_id = self.task_manager.create_task(
                task_type=TaskType.PROCESS_GENERATION,
                params={
                    "user_requirements": user_requirements,
                    "material": material,
                    "part_type": part_type,
                    "scenario_id": scenario
                }
            )

        await self.task_manager.update_progress(task_id, 0, "正在初始化工艺参数生成...")

        hypothesis = f"使用{material}材料，{part_type}零件类型，场景[{scenario}]生成工艺参数"
        reason = f"基于用户需求和材料特性进行参数优化"

        trace_node = TraceNode(
            node_id=str(uuid.uuid4()),
            task_id=task_id,
            parent_ids=[parent_node_id] if parent_node_id else [],
            hypothesis=hypothesis,
            reason=reason,
            metrics={
                "material_hardness": 0.0,
                "expected_surface_finish": 0.0,
                "scenario_id": scenario
            }
        )

        self.trace.add_node(trace_node, trace_node.parent_ids)

        with self.logger.log_step(task_id, "process_service", StepType.WORKFLOW_START,
                                  input_data={"material": material, "part_type": part_type,
                                             "trace_node_id": trace_node.node_id, "scenario_id": scenario}):
            pass

        try:
            await self.task_manager.update_progress(task_id, 5, "开始假设驱动循环...")

            if self.hypothesis_loop:
                result = await self._run_hypothesis_loop(
                    task_id, user_requirements, material, part_type, trace_node.node_id, scenario
                )
            else:
                result = await self._run_legacy_process(
                    task_id, user_requirements, material, part_type, trace_node.node_id, scenario
                )

            with self.logger.log_step(task_id, "process_service", StepType.WORKFLOW_END,
                                      output_data=result):
                pass

            await self.task_manager.complete_task(task_id, result)
            return result
        except Exception as e:
            self.trace.update_node(
                trace_node.node_id,
                validation_result={"passed": False, "error": str(e)},
                feedback=str(e)
            )
            await self.task_manager.fail_task(task_id, str(e))
            raise

    async def _run_hypothesis_loop(
        self,
        task_id: str,
        user_requirements: Dict,
        material: str,
        part_type: str,
        trace_node_id: str,
        scenario_id: str = "base"
    ) -> Dict:
        from app.services.solver_progress_service import get_solver_progress_service
        solver_progress = get_solver_progress_service()
        solver_progress.initialize_progress(task_id)

        requirements = {
            "user_input": user_requirements,
            "material": material,
            "part_type": part_type,
            "constraints": user_requirements.get("constraints", {}) if user_requirements else {}
        }

        material_info = {
            "material_name": material,
            "hardness": user_requirements.get("material_hardness", 200) if user_requirements else 200
        }

        tool_info = user_requirements.get("tool_info", {}) if user_requirements else {}

        loop_result: HypothesisLoopResult = await self.hypothesis_loop.run(
            task_id=task_id,
            requirements=requirements,
            material_info=material_info,
            tool_info=tool_info,
            scenario_id=scenario_id
        )

        result_dict = {
            "success": loop_result.success,
            "loop_result": loop_result.to_dict(),
            "stage_results": {
                "hypothesis_iterations": [i.to_dict() for i in loop_result.iterations],
                "final_hypothesis": loop_result.final_hypothesis.to_dict() if loop_result.final_hypothesis else None,
                "best_solution": loop_result.best_feasible_solution
            },
            "total_stages": len(loop_result.iterations),
            "completed_stages": len([i for i in loop_result.iterations if i.is_passed]),
            "trace_node_id": trace_node_id,
            "warning_message": loop_result.warning_message,
            "scenario_id": scenario_id
        }

        if loop_result.final_hypothesis:
            self.trace.update_node(
                trace_node_id,
                result=result_dict["stage_results"],
                validation_result={"passed": loop_result.success},
                metrics=self._extract_metrics_from_loop(loop_result)
            )

        return result_dict

    async def _run_legacy_process(
        self,
        task_id: str,
        user_requirements: Dict,
        material: str,
        part_type: str,
        trace_node_id: str,
        scenario_id: str = "base"
    ) -> Dict:
        async def _run_process_generation():
            stage_results = {}
            total_stages = len(self.process_stages)

            for idx, stage in enumerate(self.process_stages):
                task = self.task_manager.get_task(task_id)
                if task and task.status.value == 'cancelled':
                    return {"cancelled": True, "stage_results": stage_results}

                progress = (idx / total_stages) * 100
                stage_name = self._get_stage_name(stage)
                await self.task_manager.update_progress(
                    task_id, progress, f"正在执行{stage_name}..."
                )

                with self.logger.log_step(
                    task_id, "process_service", StepType.CONSTRAINT_PARSE,
                    input_data={"stage": stage, "index": idx, "scenario_id": scenario_id}
                ) as log_entry:
                    stage_result = await self._execute_stage(stage, user_requirements, material, part_type, scenario_id)
                    stage_results[stage] = stage_result
                    log_entry.output = {"stage_result": stage_result}

                self.trace.update_node(
                    trace_node_id,
                    result={**self.trace.get_node(trace_node_id).result if self.trace.get_node(trace_node_id) else {}, stage: stage_result}
                )

                await self.task_manager.update_progress(
                    task_id, ((idx + 1) / total_stages) * 100, f"完成{stage_name}"
                )

            return {
                "stage_results": stage_results,
                "total_stages": total_stages,
                "completed_stages": len([s for s in stage_results.values() if s.get("status") == "success"]),
                "trace_node_id": trace_node_id,
                "scenario_id": scenario_id
            }

        result = await self.task_manager.run_with_timeout(task_id, _run_process_generation())

        if result.get("cancelled"):
            return result

        validation_data = result.get("stage_results", {}).get("result_validation", {})
        self.trace.update_node(
            trace_node_id,
            validation_result=validation_data,
            metrics=self._extract_metrics(result.get("stage_results", {}))
        )

        return result

    def _extract_metrics_from_loop(self, loop_result: HypothesisLoopResult) -> Dict[str, float]:
        metrics = {}
        if loop_result.best_feasible_solution:
            solution = loop_result.best_feasible_solution
            for key in ["cutting_speed", "feed_rate", "depth_of_cut",
                       "cutting_force", "surface_roughness", "tool_life"]:
                if key in solution:
                    metrics[key] = float(solution[key])
        return metrics

    async def _execute_stage(self, stage: str, user_requirements: Dict, material: str, part_type: str, scenario_id: str = "base") -> Dict:
        if stage == "constraint_parsing":
            return await self._parse_constraints(user_requirements, scenario_id)
        elif stage == "parameter_optimization":
            return await self._optimize_parameters(material, part_type, scenario_id)
        elif stage == "solver_execution":
            return await self._run_solver(user_requirements, material, scenario_id)
        elif stage == "result_validation":
            return await self._validate_results(user_requirements, scenario_id)
        return {"status": "unknown"}

    async def _parse_constraints(self, user_requirements: Dict, scenario_id: str = "base") -> Dict:
        await asyncio.sleep(0.5)
        try:
            scenario_info = scenario_manager.get_scenario_info(scenario_id)
            constraints = scenario_manager.get_constraints(scenario_id)
        except Exception:
            scenario_info = {"id": scenario_id}
            constraints = {}

        return {
            "status": "success",
            "constraints": ["tolerance", "surface_finish", "material_hardness"],
            "parsed_params": user_requirements or {},
            "scenario_id": scenario_id,
            "scenario_info": scenario_info,
            "scenario_constraints": constraints
        }

    async def _optimize_parameters(self, material: str, part_type: str, scenario_id: str = "base") -> Dict:
        await asyncio.sleep(0.5)
        try:
            objective_weights = scenario_manager.get_objective_weights(scenario_id)
        except Exception:
            objective_weights = {}

        return {
            "status": "success",
            "optimized_params": {
                "cutting_speed": 150.0,
                "feed_rate": 0.2,
                "depth_of_cut": 2.0
            },
            "material": material,
            "part_type": part_type,
            "scenario_id": scenario_id,
            "objective_weights": objective_weights
        }

    async def _run_solver(self, user_requirements: Dict, material: str, scenario_id: str = "base") -> Dict:
        await asyncio.sleep(0.5)
        return {
            "status": "success",
            "solver_result": {
                "optimal": True,
                "objective_value": 0.85,
                "computation_time_ms": 1200
            },
            "material": material,
            "scenario_id": scenario_id
        }

    async def _validate_results(self, user_requirements: Dict, scenario_id: str = "base") -> Dict:
        await asyncio.sleep(0.5)
        try:
            validation_rules = scenario_manager.get_validation_rules(scenario_id)
        except Exception:
            validation_rules = {}

        return {
            "status": "success",
            "validation_passed": True,
            "quality_metrics": {
                "accuracy": 0.95,
                "efficiency": 0.88,
                "stability": 0.92
            },
            "scenario_id": scenario_id,
            "validation_rules": validation_rules
        }

    async def retry_with_correction(self, original_task_id: str,
                                     failed_node_id: str,
                                     correction_reason: str,
                                     user_requirements: Dict = None,
                                     material: str = "",
                                     part_type: str = "",
                                     scenario_id: str = "base") -> Dict:
        new_task_id = self.task_manager.create_task(
            task_type=TaskType.PROCESS_GENERATION,
            params={
                "user_requirements": user_requirements,
                "material": material,
                "part_type": part_type,
                "correction_reason": correction_reason,
                "original_node_id": failed_node_id,
                "scenario_id": scenario_id
            }
        )

        original_node = self.trace.get_node(failed_node_id)
        original_hypothesis = original_node.hypothesis if original_node else ""

        hypothesis = f"修正：{correction_reason}。原始假设：{original_hypothesis}"
        reason = f"基于失败节点{failed_node_id[:8]}的反馈进行修正"

        trace_node = TraceNode(
            node_id=str(uuid.uuid4()),
            task_id=new_task_id,
            parent_ids=[failed_node_id],
            hypothesis=hypothesis,
            reason=reason,
            feedback=correction_reason,
            metrics={
                "material_hardness": 0.0,
                "expected_surface_finish": 0.0,
                "scenario_id": scenario_id
            }
        )

        self.trace.add_node(trace_node, trace_node.parent_ids)

        await self.task_manager.update_progress(new_task_id, 0, "正在基于失败反馈修正工艺参数...")

        with self.logger.log_step(new_task_id, "process_service", StepType.WORKFLOW_START,
                                  input_data={
                                      "material": material,
                                      "part_type": part_type,
                                      "correction_reason": correction_reason,
                                      "parent_node_id": failed_node_id,
                                      "trace_node_id": trace_node.node_id,
                                      "scenario_id": scenario_id
                                  }):
            pass

        async def _run_correction():
            stage_results = {}
            total_stages = len(self.process_stages)

            for idx, stage in enumerate(self.process_stages):
                task = self.task_manager.get_task(new_task_id)
                if task and task.status.value == 'cancelled':
                    return {"cancelled": True, "stage_results": stage_results}

                progress = (idx / total_stages) * 100
                stage_name = self._get_stage_name(stage)
                await self.task_manager.update_progress(
                    new_task_id, progress, f"正在执行{stage_name}（修正）..."
                )

                with self.logger.log_step(
                    new_task_id, "process_service", StepType.CONSTRAINT_PARSE,
                    input_data={"stage": stage, "index": idx, "correction": True, "scenario_id": scenario_id}
                ) as log_entry:
                    stage_result = await self._execute_stage(stage, user_requirements, material, part_type, scenario_id)
                    stage_results[stage] = stage_result
                    log_entry.output = {"stage_result": stage_result}

                self.trace.update_node(
                    trace_node.node_id,
                    result={**trace_node.result, stage: stage_result}
                )

                await self.task_manager.update_progress(
                    new_task_id, ((idx + 1) / total_stages) * 100, f"完成{stage_name}（修正）"
                )

            return {
                "stage_results": stage_results,
                "total_stages": total_stages,
                "completed_stages": len([s for s in stage_results.values() if s.get("status") == "success"]),
                "trace_node_id": trace_node.node_id,
                "is_correction": True,
                "scenario_id": scenario_id
            }

        try:
            await self.task_manager.update_progress(new_task_id, 5, "开始修正工艺参数...")
            result = await self.task_manager.run_with_timeout(new_task_id, _run_correction())

            if result.get("cancelled"):
                await self.task_manager.cancel_task(new_task_id)
                return result

            validation_data = result.get("stage_results", {}).get("result_validation", {})
            self.trace.update_node(
                trace_node.node_id,
                validation_result=validation_data,
                metrics=self._extract_metrics(result.get("stage_results", {}))
            )

            with self.logger.log_step(new_task_id, "process_service", StepType.WORKFLOW_END,
                                      output_data=result):
                pass

            await self.task_manager.complete_task(new_task_id, result)
            return result
        except Exception as e:
            self.trace.update_node(
                trace_node.node_id,
                validation_result={"passed": False, "error": str(e)},
                feedback=str(e)
            )
            await self.task_manager.fail_task(new_task_id, str(e))
            raise

    def _get_stage_name(self, stage_key: str) -> str:
        names = {
            "constraint_parsing": "约束解析",
            "parameter_optimization": "参数优化",
            "solver_execution": "求解器执行",
            "result_validation": "结果验证"
        }
        return names.get(stage_key, stage_key)

    def _extract_metrics(self, stage_results: Dict) -> Dict[str, float]:
        metrics = {}

        opt_params = stage_results.get("parameter_optimization", {}).get("optimized_params", {})
        if opt_params:
            metrics["cutting_speed"] = float(opt_params.get("cutting_speed", 0.0))
            metrics["feed_rate"] = float(opt_params.get("feed_rate", 0.0))
            metrics["depth_of_cut"] = float(opt_params.get("depth_of_cut", 0.0))

        quality = stage_results.get("result_validation", {}).get("quality_metrics", {})
        if quality:
            metrics["accuracy"] = float(quality.get("accuracy", 0.0))
            metrics["efficiency"] = float(quality.get("efficiency", 0.0))
            metrics["stability"] = float(quality.get("stability", 0.0))

        solver = stage_results.get("solver_execution", {}).get("solver_result", {})
        if solver:
            metrics["objective_value"] = float(solver.get("objective_value", 0.0))

        return metrics


process_service = ProcessService
