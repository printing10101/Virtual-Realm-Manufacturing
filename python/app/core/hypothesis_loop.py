import uuid
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

from app.models.hypothesis import ProcessHypothesis
from app.agents.hypothesis_generator import HypothesisGenerator
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.core.process_trace import ProcessTrace, TraceNode
from app.services.incremental_solver import IncrementalSCIPSolver, SolverPhase, SolverState, PhaseResult
from app.core.alternating_validator import AlternatingValidator, ValidationStrategy, PhaseValidationReport, AlternatingValidationResult


@dataclass
class HypothesisIteration:
    iteration: int
    hypothesis: ProcessHypothesis
    validation_result: Dict[str, Any]
    is_passed: bool
    correction_direction: str = ""
    duration_ms: float = 0.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "iteration": self.iteration,
            "hypothesis": self.hypothesis.to_dict(),
            "validation_result": self.validation_result,
            "is_passed": self.is_passed,
            "correction_direction": self.correction_direction,
            "duration_ms": self.duration_ms,
            "created_at": self.created_at
        }


@dataclass
class HypothesisLoopResult:
    success: bool
    final_hypothesis: Optional[ProcessHypothesis]
    iterations: List[HypothesisIteration]
    best_feasible_solution: Optional[Dict[str, Any]]
    warning_message: str = ""
    total_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_hypothesis": self.final_hypothesis.to_dict() if self.final_hypothesis else None,
            "iterations": [i.to_dict() for i in self.iterations],
            "best_feasible_solution": self.best_feasible_solution,
            "warning_message": self.warning_message,
            "total_duration_ms": self.total_duration_ms
        }


class HypothesisDrivenLoop:
    def __init__(
        self,
        task_manager: TaskManager,
        workflow_logger: AIWorkflowLogger,
        hypothesis_generator: HypothesisGenerator,
        max_iterations: int = 5,
        constraint_mapper: Optional[Any] = None,
        solver: Optional[Any] = None,
        validator: Optional[Any] = None,
        incremental_solver: Optional[IncrementalSCIPSolver] = None,
        alternating_validator: Optional[AlternatingValidator] = None,
        validation_strategy: str = "tolerant",
        tolerance_threshold: float = 0.1,
        progress_callback: Optional[Callable] = None
    ):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.hypothesis_generator = hypothesis_generator
        self.max_iterations = max_iterations
        self.constraint_mapper = constraint_mapper
        self.solver = solver
        self.validator = validator
        self.process_trace = ProcessTrace()

        self.incremental_solver = incremental_solver
        self.alternating_validator = alternating_validator
        self.validation_strategy = validation_strategy
        self.tolerance_threshold = tolerance_threshold
        self.progress_callback = progress_callback

    async def run(
        self,
        task_id: str,
        requirements: Dict[str, Any],
        material_info: Dict[str, Any],
        tool_info: Dict[str, Any],
        history_reference: Optional[List[Dict[str, Any]]] = None
    ) -> HypothesisLoopResult:
        import time
        start_time = time.time()

        self._current_task_id = task_id

        iterations: List[HypothesisIteration] = []
        current_hypothesis: Optional[ProcessHypothesis] = None
        best_solution: Optional[Dict[str, Any]] = None
        best_score = -1.0

        with self.logger.log_step(
            task_id, "hypothesis_loop", StepType.WORKFLOW_START,
            input_data={
                "max_iterations": self.max_iterations,
                "requirements": requirements
            }
        ) as log_entry:
            pass

        await self.task_manager.update_progress(task_id, 5, "开始假设驱动循环...")

        for iteration in range(1, self.max_iterations + 1):
            iter_start = time.time()

            task = self.task_manager.get_task(task_id)
            if task and task.status.value == 'cancelled':
                return HypothesisLoopResult(
                    success=False,
                    final_hypothesis=current_hypothesis,
                    iterations=iterations,
                    best_feasible_solution=best_solution,
                    warning_message="任务已取消"
                )

            progress = 5 + (iteration / self.max_iterations) * 85
            await self.task_manager.update_progress(
                task_id, progress, f"执行第 {iteration}/{self.max_iterations} 轮假设验证..."
            )

            try:
                if iteration == 1:
                    current_hypothesis = await self.hypothesis_generator.generate_initial_hypothesis(
                        task_id=task_id,
                        requirements=requirements,
                        material_info=material_info,
                        tool_info=tool_info,
                        history_reference=history_reference
                    )
                else:
                    previous_hypothesis = iterations[-1].hypothesis
                    validation_feedback = iterations[-1].validation_result

                    current_hypothesis = await self.hypothesis_generator.generate_correction_hypothesis(
                        task_id=task_id,
                        failed_hypothesis=previous_hypothesis,
                        validation_feedback=validation_feedback,
                        trace_chain=[i.hypothesis.to_dict() for i in iterations[:-1]]
                    )

                with self.logger.log_step(
                    task_id, "hypothesis_loop", StepType.CONSTRAINT_PARSE,
                    input_data={
                        "iteration": iteration,
                        "hypothesis_id": current_hypothesis.hypothesis_id,
                        "hypothesis_content": current_hypothesis.content
                    }
                ) as log_entry:
                    constraints = await self._map_hypothesis_to_constraints(
                        current_hypothesis, requirements
                    )
                    log_entry.output = {"constraints": constraints}

                with self.logger.log_step(
                    task_id, "hypothesis_loop", StepType.SOLVER_RUN,
                    input_data={"iteration": iteration, "constraints": constraints}
                ) as log_entry:
                    if self.incremental_solver and self.alternating_validator:
                        solver_result = await self._run_alternating_solver(
                            constraints, requirements, material_info, iteration
                        )
                    else:
                        solver_result = await self._run_solver(constraints, requirements)
                    log_entry.output = {"solver_result": solver_result}

                if solver_result.get("status") == "success":
                    solution = solver_result.get("solution", {})

                    if best_solution is None or self._score_solution(solution) > best_score:
                        best_solution = solution
                        best_score = self._score_solution(solution)

                    with self.logger.log_step(
                        task_id, "hypothesis_loop", StepType.VALIDATION,
                        input_data={"iteration": iteration, "solution": solution}
                    ) as log_entry:
                        validation_result = await self._validate_solution(
                            solution, requirements, material_info
                        )
                        log_entry.output = {"validation_result": validation_result}

                    is_passed = validation_result.get("passed", False)
                    correction_direction = ""

                    if not is_passed:
                        correction_direction = self._extract_correction_direction(
                            validation_result
                        )

                    iter_duration = (time.time() - iter_start) * 1000

                    iteration_result = HypothesisIteration(
                        iteration=iteration,
                        hypothesis=current_hypothesis,
                        validation_result=validation_result,
                        is_passed=is_passed,
                        correction_direction=correction_direction,
                        duration_ms=iter_duration
                    )
                    iterations.append(iteration_result)

                    trace_node = TraceNode(
                        node_id=str(uuid.uuid4()),
                        task_id=task_id,
                        parent_ids=[iterations[-2].hypothesis.hypothesis_id] if len(iterations) > 1 else [],
                        hypothesis=current_hypothesis.content,
                        reason=current_hypothesis.reason,
                        result={"solution": solution, "solver_result": solver_result},
                        validation_result=validation_result,
                        feedback=correction_direction if not is_passed else "",
                        metrics=self._extract_metrics(solution, validation_result)
                    )
                    self.process_trace.add_node(trace_node, trace_node.parent_ids)

                    if is_passed:
                        total_duration = (time.time() - start_time) * 1000
                        result = HypothesisLoopResult(
                            success=True,
                            final_hypothesis=current_hypothesis,
                            iterations=iterations,
                            best_feasible_solution=solution,
                            total_duration_ms=total_duration
                        )

                        with self.logger.log_step(
                            task_id, "hypothesis_loop", StepType.WORKFLOW_END,
                            output_data={"success": True, "iterations": iteration}
                        ):
                            pass

                        return result

                else:
                    iter_duration = (time.time() - iter_start) * 1000
                    validation_result = {
                        "passed": False,
                        "failure_reason": "求解器未能找到可行解",
                        "unmet_constraints": ["solver_infeasible"]
                    }

                    iteration_result = HypothesisIteration(
                        iteration=iteration,
                        hypothesis=current_hypothesis,
                        validation_result=validation_result,
                        is_passed=False,
                        correction_direction="尝试放宽约束或调整参数范围",
                        duration_ms=iter_duration
                    )
                    iterations.append(iteration_result)

            except Exception as e:
                iter_duration = (time.time() - iter_start) * 1000
                validation_result = {
                    "passed": False,
                    "failure_reason": str(e),
                    "unmet_constraints": []
                }

                iteration_result = HypothesisIteration(
                    iteration=iteration,
                    hypothesis=current_hypothesis or ProcessHypothesis(),
                    validation_result=validation_result,
                    is_passed=False,
                    correction_direction=f"系统异常：{str(e)}",
                    duration_ms=iter_duration
                )
                iterations.append(iteration_result)

        total_duration = (time.time() - start_time) * 1000
        warning_message = (
            f"达到最大迭代次数 {self.max_iterations}，未找到完全满足约束的解。"
            f"返回最佳可行解（得分：{best_score:.2f}）。"
        )

        with self.logger.log_step(
            task_id, "hypothesis_loop", StepType.WORKFLOW_END,
            output_data={"success": False, "warning": warning_message, "iterations": len(iterations)}
        ):
            pass

        return HypothesisLoopResult(
            success=False,
            final_hypothesis=current_hypothesis,
            iterations=iterations,
            best_feasible_solution=best_solution,
            warning_message=warning_message,
            total_duration_ms=total_duration
        )

    async def _map_hypothesis_to_constraints(
        self, hypothesis: ProcessHypothesis, requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self.constraint_mapper:
            return await self.constraint_mapper.map_hypothesis(hypothesis, requirements)

        return self._default_constraint_mapping(hypothesis, requirements)

    def _default_constraint_mapping(
        self, hypothesis: ProcessHypothesis, requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        constraints = {}

        expected = hypothesis.expected_outcomes
        if "cutting_force" in expected:
            value = self._extract_numeric_bound(expected["cutting_force"])
            if value:
                constraints["cutting_force_max"] = value

        if "surface_roughness" in expected:
            value = self._extract_numeric_bound(expected["surface_roughness"])
            if value:
                constraints["surface_roughness_max"] = value

        if "tool_life" in expected:
            value = self._extract_numeric_bound(expected["tool_life"])
            if value:
                constraints["tool_life_min"] = value

        constraints.update(requirements.get("constraints", {}))

        return constraints

    def _extract_numeric_bound(self, constraint_str: str) -> Optional[float]:
        import re
        match = re.search(r'([\d.]+)', constraint_str)
        if match:
            return float(match.group(1))
        return None

    async def _run_solver(
        self, constraints: Dict[str, Any], requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self.solver:
            return await self.solver.solve(constraints, requirements)

        return self._default_solver(constraints, requirements)

    async def _run_alternating_solver(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Dict[str, Any],
        iteration: int
    ) -> Dict[str, Any]:
        from app.services.solver_progress_service import get_solver_progress_service
        solver_progress = get_solver_progress_service()

        strategy = ValidationStrategy(self.validation_strategy)

        solver_config = {
            "tolerance_threshold": self.tolerance_threshold,
            "max_rollbacks": 3
        }

        incremental_solver = IncrementalSCIPSolver(
            phase_order=IncrementalSCIPSolver.DEFAULT_PHASE_ORDER,
            max_rollbacks=solver_config["max_rollbacks"],
            config=solver_config
        )

        task_id = getattr(self, "_current_task_id", "")

        async def progress_handler(progress_data: Dict[str, Any]):
            solver_progress.update_phase_progress(task_id, progress_data)

            if self.progress_callback:
                await self.progress_callback({
                    **progress_data,
                    "iteration": iteration,
                    "task_id": task_id
                })

            trace_node = TraceNode(
                node_id=str(uuid.uuid4()),
                task_id=task_id,
                parent_ids=[],
                hypothesis=f"Phase {progress_data.get('phase', 'unknown')} - Iteration {iteration}",
                reason="",
                result={
                    "parameters": progress_data.get("parameters", {}),
                    "metrics": progress_data.get("metrics", {}),
                    "solver_state": progress_data.get("solver_state", {})
                },
                validation_result=progress_data.get("validation", {}),
                feedback="",
                metrics=progress_data.get("metrics", {})
            )
            self.process_trace.add_node(trace_node, [])

        validator = AlternatingValidator(
            solver=incremental_solver,
            validation_fn=None,
            strategy=strategy,
            tolerance_threshold=self.tolerance_threshold
        )
        validator.set_progress_callback(progress_handler)

        result = await validator.validate(
            constraints=constraints,
            requirements=requirements,
            material_info=material_info
        )

        performance_report = validator.generate_performance_report()
        solver_progress.complete_solving(task_id, performance_report)

        if result.success:
            solution = {
                **result.final_parameters,
                **self._extract_final_metrics(result)
            }
            return {
                "status": "success",
                "solution": solution,
                "alternating_result": result.to_dict(),
                "performance_report": performance_report
            }
        else:
            solver_progress.terminate_solving(task_id, result.termination_reason)
            return {
                "status": "failed",
                "alternating_result": result.to_dict(),
                "performance_report": performance_report,
                "termination_reason": result.termination_reason
            }

    def _extract_final_metrics(self, result: AlternatingValidationResult) -> Dict[str, float]:
        if not result.phase_reports:
            return {}

        final_report = result.phase_reports[-1]
        return {
            "cutting_force": final_report.metrics.get("cutting_force", 0),
            "surface_roughness": final_report.metrics.get("surface_roughness", 0),
            "tool_life": final_report.metrics.get("tool_life", 0)
        }

    def _default_solver(
        self, constraints: Dict[str, Any], requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        return {
            "status": "success",
            "solution": {
                "cutting_speed": 120.0,
                "feed_rate": 0.15,
                "depth_of_cut": 2.0,
                "cutting_force": 750.0,
                "surface_roughness": 1.4,
                "tool_life": 65.0
            }
        }

    async def _validate_solution(
        self,
        solution: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        if self.validator:
            return await self.validator.validate(solution, requirements, material_info)

        return self._default_validation(solution, requirements)

    def _default_validation(
        self, solution: Dict[str, Any], requirements: Dict[str, Any]
    ) -> Dict[str, Any]:
        passed = True
        unmet_constraints = []
        failure_reasons = []

        cutting_force = solution.get("cutting_force", 0)
        max_cutting_force = requirements.get("max_cutting_force", 1000)
        if cutting_force > max_cutting_force:
            passed = False
            unmet_constraints.append(f"cutting_force: {cutting_force}N > {max_cutting_force}N")
            failure_reasons.append(f"切削力 {cutting_force}N 超过限制 {max_cutting_force}N")

        surface_roughness = solution.get("surface_roughness", 0)
        max_roughness = requirements.get("max_surface_roughness", 3.2)
        if surface_roughness > max_roughness:
            passed = False
            unmet_constraints.append(f"surface_roughness: {surface_roughness}μm > {max_roughness}μm")
            failure_reasons.append(f"表面粗糙度 {surface_roughness}μm 超过限制 {max_roughness}μm")

        tool_life = solution.get("tool_life", 0)
        min_tool_life = requirements.get("min_tool_life", 30)
        if tool_life < min_tool_life:
            passed = False
            unmet_constraints.append(f"tool_life: {tool_life}min < {min_tool_life}min")
            failure_reasons.append(f"刀具寿命 {tool_life}min 低于要求 {min_tool_life}min")

        return {
            "passed": passed,
            "failure_reason": "; ".join(failure_reasons) if failure_reasons else "",
            "unmet_constraints": unmet_constraints,
            "metrics": {
                "cutting_force": cutting_force,
                "surface_roughness": surface_roughness,
                "tool_life": tool_life
            }
        }

    def _score_solution(self, solution: Dict[str, Any]) -> float:
        score = 0.0

        cutting_force = solution.get("cutting_force", 1000)
        score += max(0, 1 - cutting_force / 1000) * 0.3

        surface_roughness = solution.get("surface_roughness", 5)
        score += max(0, 1 - surface_roughness / 5) * 0.3

        tool_life = solution.get("tool_life", 0)
        score += min(1, tool_life / 100) * 0.2

        cutting_speed = solution.get("cutting_speed", 0)
        score += min(1, cutting_speed / 200) * 0.2

        return score

    def _extract_metrics(
        self, solution: Dict[str, Any], validation_result: Dict[str, Any]
    ) -> Dict[str, float]:
        metrics = {}

        for key in ["cutting_speed", "feed_rate", "depth_of_cut",
                    "cutting_force", "surface_roughness", "tool_life"]:
            if key in solution:
                metrics[key] = float(solution[key])

        return metrics

    def _extract_correction_direction(self, validation_result: Dict[str, Any]) -> str:
        failure_reason = validation_result.get("failure_reason", "")
        unmet = validation_result.get("unmet_constraints", [])

        if not failure_reason and not unmet:
            return "未知原因，需综合调整参数"

        direction_parts = []

        if "cutting_force" in failure_reason.lower():
            direction_parts.append("降低切削力：减小切削速度或进给量")

        if "surface_roughness" in failure_reason.lower():
            direction_parts.append("改善表面粗糙度：降低进给量或增加刀尖圆弧半径")

        if "tool_life" in failure_reason.lower():
            direction_parts.append("提高刀具寿命：降低切削速度或更换刀具材料")

        if not direction_parts:
            direction_parts.append(f"根据失败原因调整：{failure_reason}")

        return "; ".join(direction_parts)
