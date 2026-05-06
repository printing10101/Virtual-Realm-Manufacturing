import asyncio
import time
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field
from datetime import datetime

from app.services.incremental_solver import IncrementalSCIPSolver, PhaseResult, SolverPhase, SolverState


class ValidationStrategy(Enum):
    STRICT = "strict"
    TOLERANT = "tolerant"
    BEST_EFFORT = "best_effort"


@dataclass
class PhaseValidationReport:
    phase: SolverPhase
    validation_passed: bool
    error_rate: float = 0.0
    violations: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    validation_duration_ms: float = 0.0
    solver_duration_ms: float = 0.0
    total_duration_ms: float = 0.0
    metrics: Dict[str, float] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "validation_passed": self.validation_passed,
            "error_rate": self.error_rate,
            "violations": self.violations,
            "warnings": self.warnings,
            "validation_duration_ms": self.validation_duration_ms,
            "solver_duration_ms": self.solver_duration_ms,
            "total_duration_ms": self.total_duration_ms,
            "metrics": self.metrics,
            "timestamp": self.timestamp
        }


@dataclass
class AlternatingValidationResult:
    success: bool
    final_parameters: Optional[Dict[str, Any]]
    phase_reports: List[PhaseValidationReport]
    strategy: ValidationStrategy
    terminated_early: bool = False
    termination_reason: str = ""
    total_duration_ms: float = 0.0
    rollback_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "final_parameters": self.final_parameters,
            "phase_reports": [r.to_dict() for r in self.phase_reports],
            "strategy": self.strategy.value,
            "terminated_early": self.terminated_early,
            "termination_reason": self.termination_reason,
            "total_duration_ms": self.total_duration_ms,
            "rollback_count": self.rollback_count
        }


class AlternatingValidator:
    def __init__(
        self,
        solver: IncrementalSCIPSolver,
        validation_fn: Optional[Callable] = None,
        strategy: ValidationStrategy = ValidationStrategy.TOLERANT,
        tolerance_threshold: float = 0.1,
        config: Optional[Dict[str, Any]] = None
    ):
        self.solver = solver
        self.validation_fn = validation_fn
        self.strategy = strategy
        self.tolerance_threshold = tolerance_threshold
        self.config = config or {}

        self._phase_reports: List[PhaseValidationReport] = []
        self._start_time: float = 0.0
        self._progress_callback: Optional[Callable] = None

    def set_progress_callback(self, callback: Callable) -> None:
        self._progress_callback = callback

    async def validate(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]] = None,
        tool_info: Optional[Dict[str, Any]] = None
    ) -> AlternatingValidationResult:
        self._start_time = time.time()
        self._phase_reports = []

        try:
            solver_gen = self.solver.solve(
                constraints=constraints,
                requirements=requirements,
                material_info=material_info,
                tool_info=tool_info
            )

            final_params = None
            terminated_early = False
            termination_reason = ""

            async for phase_result in solver_gen:
                if phase_result.state == SolverState.FAILED:
                    report = await self._handle_solver_failure(phase_result)
                    self._phase_reports.append(report)

                    if self.strategy == ValidationStrategy.STRICT:
                        terminated_early = True
                        termination_reason = f"严格模式：{phase_result.error_message}"
                        break
                    elif self.strategy == ValidationStrategy.TOLERANT:
                        if report.error_rate >= self.tolerance_threshold:
                            terminated_early = True
                            termination_reason = f"容忍模式：误差超过阈值 ({report.error_rate:.2%} >= {self.tolerance_threshold:.2%})"
                            break
                    continue

                validation_feedback = await self._validate_phase(phase_result, requirements)

                self._phase_reports.append(validation_feedback)

                final_params = phase_result.parameters

                if self._progress_callback:
                    await self._progress_callback({
                        "type": "phase_progress",
                        "phase": phase_result.phase.value,
                        "state": phase_result.state.value,
                        "parameters": phase_result.parameters,
                        "metrics": phase_result.metrics,
                        "validation": validation_feedback.to_dict(),
                        "solver_state": self.solver.get_state().to_dict()
                    })

                feedback_to_solver = {
                    "passed": validation_feedback.validation_passed,
                    "error_rate": validation_feedback.error_rate,
                    "violated_constraints": validation_feedback.violations,
                    "strategy": self.strategy.value,
                    "warnings": validation_feedback.warnings
                }

                self.solver.send_feedback(feedback_to_solver)

                if validation_feedback.validation_passed is False and \
                   self.strategy == ValidationStrategy.STRICT:
                    terminated_early = True
                    termination_reason = f"严格模式：阶段 {phase_result.phase.value} 验证失败"
                    break

            total_duration = (time.time() - self._start_time) * 1000

            success = not terminated_early and final_params is not None

            if terminated_early and self.strategy == ValidationStrategy.BEST_EFFORT:
                success = True
                terminated_early = False

            return AlternatingValidationResult(
                success=success,
                final_parameters=final_params,
                phase_reports=self._phase_reports,
                strategy=self.strategy,
                terminated_early=terminated_early,
                termination_reason=termination_reason,
                total_duration_ms=total_duration,
                rollback_count=self.solver.get_state().rollback_count
            )

        except Exception as e:
            total_duration = (time.time() - self._start_time) * 1000
            return AlternatingValidationResult(
                success=False,
                final_parameters=None,
                phase_reports=self._phase_reports,
                strategy=self.strategy,
                terminated_early=True,
                termination_reason=f"异常：{str(e)}",
                total_duration_ms=total_duration
            )

    async def _validate_phase(
        self,
        phase_result: PhaseResult,
        requirements: Dict[str, Any]
    ) -> PhaseValidationReport:
        validation_start = time.time()

        if self.validation_fn:
            if asyncio.iscoroutinefunction(self.validation_fn):
                validation_result = await self.validation_fn(
                    phase_result.parameters, requirements, phase_result.metrics
                )
            else:
                validation_result = self.validation_fn(
                    phase_result.parameters, requirements, phase_result.metrics
                )
        else:
            validation_result = await self._default_validation(
                phase_result.parameters, requirements, phase_result.metrics
            )

        validation_duration = (time.time() - validation_start) * 1000

        passed = validation_result.get("passed", True)
        error_rate = self._calculate_error_rate(validation_result, phase_result.metrics)
        violations = validation_result.get("unmet_constraints", {})
        warnings = validation_result.get("warnings", [])

        return PhaseValidationReport(
            phase=phase_result.phase,
            validation_passed=passed,
            error_rate=error_rate,
            violations=violations,
            warnings=warnings,
            validation_duration_ms=validation_duration,
            solver_duration_ms=phase_result.duration_ms,
            total_duration_ms=validation_duration + phase_result.duration_ms,
            metrics=phase_result.metrics
        )

    async def _handle_solver_failure(
        self,
        phase_result: PhaseResult
    ) -> PhaseValidationReport:
        return PhaseValidationReport(
            phase=phase_result.phase,
            validation_passed=False,
            error_rate=1.0,
            violations={"solver_error": phase_result.error_message},
            warnings=[],
            validation_duration_ms=0,
            solver_duration_ms=phase_result.duration_ms,
            total_duration_ms=phase_result.duration_ms,
            metrics=phase_result.metrics
        )

    async def _default_validation(
        self,
        parameters: Dict[str, Any],
        requirements: Dict[str, Any],
        metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        passed = True
        unmet_constraints = {}
        warnings = []

        cutting_force = metrics.get("cutting_force", 0)
        max_cutting_force = requirements.get("max_cutting_force", 1000)
        if cutting_force > max_cutting_force:
            passed = False
            unmet_constraints["cutting_force_max"] = {
                "actual": cutting_force,
                "required": max_cutting_force,
                "violation": cutting_force - max_cutting_force
            }

        surface_roughness = metrics.get("surface_roughness", 0)
        max_roughness = requirements.get("max_surface_roughness", 3.2)
        if surface_roughness > max_roughness:
            passed = False
            unmet_constraints["surface_roughness_max"] = {
                "actual": surface_roughness,
                "required": max_roughness,
                "violation": surface_roughness - max_roughness
            }

        tool_life = metrics.get("tool_life", 0)
        min_tool_life = requirements.get("min_tool_life", 30)
        if tool_life < min_tool_life:
            passed = False
            unmet_constraints["tool_life_min"] = {
                "actual": tool_life,
                "required": min_tool_life,
                "violation": min_tool_life - tool_life
            }

        if not passed:
            force_ratio = cutting_force / max_cutting_force if max_cutting_force > 0 else 1.0
            roughness_ratio = surface_roughness / max_roughness if max_roughness > 0 else 1.0
            life_ratio = min_tool_life / tool_life if tool_life > 0 else 1.0
            max_ratio = max(force_ratio, roughness_ratio, life_ratio)

            if max_ratio < 1.1:
                warnings.append(f"验证失败但误差较小 ({(max_ratio-1)*100:.1f}%)，可能可以接受")

        return {
            "passed": passed,
            "unmet_constraints": unmet_constraints,
            "warnings": warnings,
            "metrics": metrics
        }

    def _calculate_error_rate(
        self,
        validation_result: Dict[str, Any],
        metrics: Dict[str, float]
    ) -> float:
        if validation_result.get("passed", True):
            return 0.0

        violations = validation_result.get("unmet_constraints", {})
        if not violations:
            return 1.0

        max_error = 0.0
        for constraint_name, constraint_data in violations.items():
            if isinstance(constraint_data, dict):
                actual = constraint_data.get("actual", 0)
                required = constraint_data.get("required", 1)
                if required != 0:
                    error = abs(actual - required) / abs(required)
                    max_error = max(max_error, error)
                else:
                    max_error = 1.0
            else:
                max_error = 1.0

        return max_error

    def get_phase_reports(self) -> List[PhaseValidationReport]:
        return list(self._phase_reports)

    def generate_performance_report(self) -> Dict[str, Any]:
        if not self._phase_reports:
            return {"message": "No validation reports available"}

        total_solver_time = sum(r.solver_duration_ms for r in self._phase_reports)
        total_validation_time = sum(r.validation_duration_ms for r in self._phase_reports)
        total_time = sum(r.total_duration_ms for r in self._phase_reports)

        passed_phases = sum(1 for r in self._phase_reports if r.validation_passed)
        failed_phases = len(self._phase_reports) - passed_phases

        return {
            "total_phases": len(self._phase_reports),
            "passed_phases": passed_phases,
            "failed_phases": failed_phases,
            "success_rate": passed_phases / len(self._phase_reports),
            "total_solver_time_ms": total_solver_time,
            "total_validation_time_ms": total_validation_time,
            "total_time_ms": total_time,
            "average_phase_time_ms": total_time / len(self._phase_reports),
            "strategy": self.strategy.value,
            "phase_details": [r.to_dict() for r in self._phase_reports]
        }
