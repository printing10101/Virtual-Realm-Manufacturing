import asyncio
import time
from enum import Enum
from typing import Optional, Dict, Any, List, AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime


class SolverPhase(Enum):
    FEASIBILITY = "feasibility"
    CUTTING_FORCE = "cutting_force"
    SURFACE_ROUGHNESS = "surface_roughness"
    TOOL_LIFE = "tool_life"


class SolverState(Enum):
    WAITING = "waiting"
    SOLVING = "solving"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"
    TERMINATED = "terminated"


@dataclass
class PhaseResult:
    phase: SolverPhase
    state: SolverState
    parameters: Dict[str, Any]
    constraints: Dict[str, Any]
    metrics: Dict[str, float]
    duration_ms: float = 0.0
    validation_feedback: Optional[Dict[str, Any]] = None
    error_message: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "phase": self.phase.value,
            "state": self.state.value,
            "parameters": self.parameters,
            "constraints": self.constraints,
            "metrics": self.metrics,
            "duration_ms": self.duration_ms,
            "validation_feedback": self.validation_feedback,
            "error_message": self.error_message,
            "timestamp": self.timestamp
        }


@dataclass
class SolverStateInfo:
    current_phase: Optional[SolverPhase] = None
    state: SolverState = SolverState.WAITING
    phase_results: List[PhaseResult] = field(default_factory=list)
    current_parameters: Dict[str, Any] = field(default_factory=dict)
    rollback_count: int = 0
    total_duration_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_phase": self.current_phase.value if self.current_phase else None,
            "state": self.state.value,
            "phase_results": [r.to_dict() for r in self.phase_results],
            "current_parameters": self.current_parameters,
            "rollback_count": self.rollback_count,
            "total_duration_ms": self.total_duration_ms
        }


class IncrementalSCIPSolver:
    DEFAULT_PHASE_ORDER = [
        SolverPhase.FEASIBILITY,
        SolverPhase.CUTTING_FORCE,
        SolverPhase.SURFACE_ROUGHNESS,
        SolverPhase.TOOL_LIFE
    ]

    def __init__(
        self,
        phase_order: Optional[List[SolverPhase]] = None,
        max_rollbacks: int = 3,
        config: Optional[Dict[str, Any]] = None
    ):
        self.phase_order = phase_order or self.DEFAULT_PHASE_ORDER
        self.max_rollbacks = max_rollbacks
        self.config = config or {}

        self.state = SolverStateInfo()
        self._feedback_event: asyncio.Event = asyncio.Event()
        self._feedback_data: Optional[Dict[str, Any]] = None
        self._current_phase_index = 0
        self._is_terminated = False

        self._phase_solvers = {
            SolverPhase.FEASIBILITY: self._solve_feasibility,
            SolverPhase.CUTTING_FORCE: self._optimize_cutting_force,
            SolverPhase.SURFACE_ROUGHNESS: self._optimize_surface_roughness,
            SolverPhase.TOOL_LIFE: self._optimize_tool_life
        }

    def send_feedback(self, feedback: Dict[str, Any]) -> None:
        self._feedback_data = feedback
        self._feedback_event.set()

    async def _wait_for_feedback(self) -> Optional[Dict[str, Any]]:
        try:
            await asyncio.wait_for(self._feedback_event.wait(), timeout=30.0)
        except asyncio.TimeoutError:
            pass
        self._feedback_event.clear()
        data = self._feedback_data
        self._feedback_data = None
        return data

    async def solve(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]] = None,
        tool_info: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[PhaseResult, None]:
        self._feedback_event = asyncio.Event()
        self._feedback_data = None
        self.state = SolverStateInfo()
        self._current_phase_index = 0
        self._is_terminated = False

        constraints_snapshot = dict(constraints)
        requirements_snapshot = dict(requirements)

        for phase_idx, phase in enumerate(self.phase_order):
            if self._is_terminated:
                break

            self.state.current_phase = phase
            self.state.state = SolverState.SOLVING

            phase_result = await self._execute_phase(
                phase, constraints_snapshot, requirements_snapshot,
                material_info, tool_info
            )

            self.state.phase_results.append(phase_result)
            self.state.total_duration_ms += phase_result.duration_ms

            if phase_result.state == SolverState.FAILED:
                rollback_success = await self._handle_phase_failure(
                    phase_result, constraints_snapshot, requirements_snapshot,
                    material_info, tool_info
                )
                if not rollback_success:
                    self.state.state = SolverState.FAILED
                    yield phase_result
                    return
                continue

            self.state.current_parameters = phase_result.parameters
            self._feedback_event.clear()

            yield phase_result

            validation_feedback = await self._wait_for_feedback()

            self.state.state = SolverState.WAITING

            if validation_feedback:
                self._process_validation_feedback(
                    validation_feedback, phase_result, constraints_snapshot
                )

                if validation_feedback.get("passed") is False and \
                   validation_feedback.get("strategy") == "strict":
                    self.state.state = SolverState.FAILED
                    failed_result = PhaseResult(
                        phase=phase,
                        state=SolverState.FAILED,
                        parameters=phase_result.parameters,
                        constraints=constraints_snapshot,
                        metrics=phase_result.metrics,
                        validation_feedback=validation_feedback,
                        error_message="严格模式：验证失败，终止优化流程"
                    )
                    self.state.phase_results[-1] = failed_result
                    yield failed_result
                    return

            if phase_idx < len(self.phase_order) - 1:
                constraints_snapshot = self._update_constraints_for_next_phase(
                    constraints_snapshot, phase_result
                )

        if not self._is_terminated:
            self.state.state = SolverState.COMPLETED
            final_result = PhaseResult(
                phase=self.phase_order[-1],
                state=SolverState.COMPLETED,
                parameters=self.state.current_parameters,
                constraints=constraints_snapshot,
                metrics=self._calculate_final_metrics(),
                duration_ms=self.state.total_duration_ms
            )
            yield final_result

    async def _execute_phase(
        self,
        phase: SolverPhase,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> PhaseResult:
        start_time = time.time()
        try:
            solver_fn = self._phase_solvers[phase]
            result = await solver_fn(constraints, requirements, material_info, tool_info)

            duration_ms = (time.time() - start_time) * 1000

            return PhaseResult(
                phase=phase,
                state=SolverState.COMPLETED,
                parameters=result.get("parameters", {}),
                constraints=result.get("constraints", constraints),
                metrics=result.get("metrics", {}),
                duration_ms=duration_ms
            )
        except Exception as e:
            duration_ms = (time.time() - start_time) * 1000
            return PhaseResult(
                phase=phase,
                state=SolverState.FAILED,
                parameters={},
                constraints=constraints,
                metrics={},
                duration_ms=duration_ms,
                error_message=str(e)
            )

    async def _solve_feasibility(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.05)

        cutting_speed = requirements.get("cutting_speed", 120.0)
        feed_rate = requirements.get("feed_rate", 0.15)
        depth_of_cut = requirements.get("depth_of_cut", 2.0)

        cutting_speed_min = constraints.get("cutting_speed_min", 50.0)
        cutting_speed_max = constraints.get("cutting_speed_max", 200.0)
        feed_rate_min = constraints.get("feed_rate_min", 0.05)
        feed_rate_max = constraints.get("feed_rate_max", 0.3)
        depth_min = constraints.get("depth_of_cut_min", 0.5)
        depth_max = constraints.get("depth_of_cut_max", 5.0)

        cutting_speed = max(cutting_speed_min, min(cutting_speed, cutting_speed_max))
        feed_rate = max(feed_rate_min, min(feed_rate, feed_rate_max))
        depth_of_cut = max(depth_min, min(depth_of_cut, depth_max))

        cutting_force = self._estimate_cutting_force(
            cutting_speed, feed_rate, depth_of_cut, material_info
        )
        surface_roughness = self._estimate_surface_roughness(
            cutting_speed, feed_rate, depth_of_cut, tool_info
        )
        tool_life = self._estimate_tool_life(
            cutting_speed, feed_rate, depth_of_cut, material_info, tool_info
        )

        return {
            "parameters": {
                "cutting_speed": cutting_speed,
                "feed_rate": feed_rate,
                "depth_of_cut": depth_of_cut
            },
            "metrics": {
                "cutting_force": cutting_force,
                "surface_roughness": surface_roughness,
                "tool_life": tool_life
            },
            "constraints": {
                **constraints,
                "feasibility_checked": True
            }
        }

    async def _optimize_cutting_force(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.05)

        prev_params = self.state.current_parameters or {
            "cutting_speed": requirements.get("cutting_speed", 120.0),
            "feed_rate": requirements.get("feed_rate", 0.15),
            "depth_of_cut": requirements.get("depth_of_cut", 2.0)
        }

        max_cutting_force = constraints.get("cutting_force_max", 1000.0)

        best_params = dict(prev_params)
        best_force = self._estimate_cutting_force(
            prev_params["cutting_speed"], prev_params["feed_rate"],
            prev_params["depth_of_cut"], material_info
        )

        for iteration in range(10):
            test_speed = prev_params["cutting_speed"] * (0.95 - iteration * 0.02)
            test_feed = prev_params["feed_rate"] * (0.95 - iteration * 0.015)
            test_depth = prev_params["depth_of_cut"] * (0.98 - iteration * 0.01)

            test_speed = max(constraints.get("cutting_speed_min", 50.0), test_speed)
            test_feed = max(constraints.get("feed_rate_min", 0.05), test_feed)
            test_depth = max(constraints.get("depth_of_cut_min", 0.5), test_depth)

            test_force = self._estimate_cutting_force(
                test_speed, test_feed, test_depth, material_info
            )

            if test_force <= max_cutting_force and test_force < best_force:
                best_params = {
                    "cutting_speed": test_speed,
                    "feed_rate": test_feed,
                    "depth_of_cut": test_depth
                }
                best_force = test_force
            elif test_force > max_cutting_force:
                continue

        test_roughness = self._estimate_surface_roughness(
            best_params["cutting_speed"], best_params["feed_rate"],
            best_params["depth_of_cut"], tool_info
        )
        test_tool_life = self._estimate_tool_life(
            best_params["cutting_speed"], best_params["feed_rate"],
            best_params["depth_of_cut"], material_info, tool_info
        )

        return {
            "parameters": best_params,
            "metrics": {
                "cutting_force": best_force,
                "surface_roughness": test_roughness,
                "tool_life": test_tool_life
            },
            "constraints": {
                **constraints,
                "cutting_force_optimized": True,
                "cutting_force_max": max_cutting_force
            }
        }

    async def _optimize_surface_roughness(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.05)

        prev_params = self.state.current_parameters or {
            "cutting_speed": requirements.get("cutting_speed", 120.0),
            "feed_rate": requirements.get("feed_rate", 0.15),
            "depth_of_cut": requirements.get("depth_of_cut", 2.0)
        }

        max_roughness = constraints.get("surface_roughness_max", 3.2)
        max_force = constraints.get("cutting_force_max", 1000.0)

        best_params = dict(prev_params)
        best_roughness = self._estimate_surface_roughness(
            prev_params["cutting_speed"], prev_params["feed_rate"],
            prev_params["depth_of_cut"], tool_info
        )

        for iteration in range(10):
            test_speed = prev_params["cutting_speed"] * (1.0 + iteration * 0.03)
            test_feed = prev_params["feed_rate"] * (0.92 - iteration * 0.01)
            test_depth = prev_params["depth_of_cut"] * (0.95 - iteration * 0.005)

            test_speed = min(constraints.get("cutting_speed_max", 200.0), test_speed)
            test_feed = max(constraints.get("feed_rate_min", 0.05), test_feed)
            test_depth = max(constraints.get("depth_of_cut_min", 0.5), test_depth)

            test_force = self._estimate_cutting_force(
                test_speed, test_feed, test_depth, material_info
            )
            if test_force > max_force:
                continue

            test_roughness = self._estimate_surface_roughness(
                test_speed, test_feed, test_depth, tool_info
            )

            if test_roughness <= max_roughness and test_roughness < best_roughness:
                best_params = {
                    "cutting_speed": test_speed,
                    "feed_rate": test_feed,
                    "depth_of_cut": test_depth
                }
                best_roughness = test_roughness

        test_force = self._estimate_cutting_force(
            best_params["cutting_speed"], best_params["feed_rate"],
            best_params["depth_of_cut"], material_info
        )
        test_tool_life = self._estimate_tool_life(
            best_params["cutting_speed"], best_params["feed_rate"],
            best_params["depth_of_cut"], material_info, tool_info
        )

        return {
            "parameters": best_params,
            "metrics": {
                "cutting_force": test_force,
                "surface_roughness": best_roughness,
                "tool_life": test_tool_life
            },
            "constraints": {
                **constraints,
                "surface_roughness_optimized": True,
                "surface_roughness_max": max_roughness
            }
        }

    async def _optimize_tool_life(
        self,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> Dict[str, Any]:
        await asyncio.sleep(0.05)

        prev_params = self.state.current_parameters or {
            "cutting_speed": requirements.get("cutting_speed", 120.0),
            "feed_rate": requirements.get("feed_rate", 0.15),
            "depth_of_cut": requirements.get("depth_of_cut", 2.0)
        }

        min_tool_life = constraints.get("tool_life_min", 30.0)
        max_force = constraints.get("cutting_force_max", 1000.0)
        max_roughness = constraints.get("surface_roughness_max", 3.2)

        best_params = dict(prev_params)
        best_life = self._estimate_tool_life(
            prev_params["cutting_speed"], prev_params["feed_rate"],
            prev_params["depth_of_cut"], material_info, tool_info
        )

        for iteration in range(10):
            test_speed = prev_params["cutting_speed"] * (0.95 - iteration * 0.02)
            test_feed = prev_params["feed_rate"] * (0.98 - iteration * 0.01)
            test_depth = prev_params["depth_of_cut"] * (0.98 - iteration * 0.005)

            test_speed = max(constraints.get("cutting_speed_min", 50.0), test_speed)
            test_feed = max(constraints.get("feed_rate_min", 0.05), test_feed)
            test_depth = max(constraints.get("depth_of_cut_min", 0.5), test_depth)

            test_force = self._estimate_cutting_force(
                test_speed, test_feed, test_depth, material_info
            )
            if test_force > max_force:
                continue

            test_roughness = self._estimate_surface_roughness(
                test_speed, test_feed, test_depth, tool_info
            )
            if test_roughness > max_roughness:
                continue

            test_life = self._estimate_tool_life(
                test_speed, test_feed, test_depth, material_info, tool_info
            )

            if test_life >= min_tool_life and test_life > best_life:
                best_params = {
                    "cutting_speed": test_speed,
                    "feed_rate": test_feed,
                    "depth_of_cut": test_depth
                }
                best_life = test_life

        final_force = self._estimate_cutting_force(
            best_params["cutting_speed"], best_params["feed_rate"],
            best_params["depth_of_cut"], material_info
        )
        final_roughness = self._estimate_surface_roughness(
            best_params["cutting_speed"], best_params["feed_rate"],
            best_params["depth_of_cut"], tool_info
        )

        return {
            "parameters": best_params,
            "metrics": {
                "cutting_force": final_force,
                "surface_roughness": final_roughness,
                "tool_life": best_life
            },
            "constraints": {
                **constraints,
                "tool_life_optimized": True,
                "tool_life_min": min_tool_life
            }
        }

    async def _handle_phase_failure(
        self,
        failed_result: PhaseResult,
        constraints: Dict[str, Any],
        requirements: Dict[str, Any],
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> bool:
        if self.state.rollback_count >= self.max_rollbacks:
            return False

        self.state.rollback_count += 1
        self.state.state = SolverState.ROLLBACK

        if self._current_phase_index > 0:
            self._current_phase_index -= 1

            previous_phase = self.phase_order[self._current_phase_index]
            previous_result = None
            for r in reversed(self.state.phase_results):
                if r.phase == previous_phase:
                    previous_result = r
                    break

            if previous_result:
                constraints["relaxed"] = True
                constraints[f"{previous_phase.value}_relaxed"] = True

                relaxed_result = await self._execute_phase(
                    previous_phase, constraints, requirements, material_info, tool_info
                )

                if relaxed_result.state == SolverState.COMPLETED:
                    self.state.phase_results.append(relaxed_result)
                    self.state.current_parameters = relaxed_result.parameters
                    return True

        return False

    def _process_validation_feedback(
        self,
        feedback: Dict[str, Any],
        phase_result: PhaseResult,
        constraints: Dict[str, Any]
    ) -> None:
        phase_result.validation_feedback = feedback

        if feedback.get("passed") is False:
            error_rate = feedback.get("error_rate", 1.0)
            tolerance = self.config.get("tolerance_threshold", 0.1)

            if feedback.get("strategy") == "tolerant" and error_rate < tolerance:
                return

            for constraint_name, constraint_value in feedback.get("violated_constraints", {}).items():
                if constraint_name in constraints:
                    if isinstance(constraints[constraint_name], (int, float)):
                        margin = abs(constraints[constraint_name]) * 0.15
                        constraints[constraint_name] = constraints[constraint_name] + margin

    def _update_constraints_for_next_phase(
        self,
        current_constraints: Dict[str, Any],
        phase_result: PhaseResult
    ) -> Dict[str, Any]:
        updated = dict(current_constraints)

        for metric_name, metric_value in phase_result.metrics.items():
            if metric_name == "cutting_force":
                updated["cutting_force_max"] = metric_value * 1.05
            elif metric_name == "surface_roughness":
                updated["surface_roughness_max"] = metric_value * 1.05
            elif metric_name == "tool_life":
                updated["tool_life_min"] = metric_value * 0.95

        updated["parameters"] = phase_result.parameters

        return updated

    def _calculate_final_metrics(self) -> Dict[str, float]:
        if not self.state.phase_results:
            return {}

        last_result = self.state.phase_results[-1]
        return dict(last_result.metrics)

    def terminate(self) -> None:
        self._is_terminated = True
        self.state.state = SolverState.TERMINATED

    def get_state(self) -> SolverStateInfo:
        return self.state

    def reset(self) -> None:
        self.state = SolverStateInfo()
        self._current_phase_index = 0
        self._is_terminated = False

    def _estimate_cutting_force(
        self,
        cutting_speed: float,
        feed_rate: float,
        depth_of_cut: float,
        material_info: Optional[Dict[str, Any]]
    ) -> float:
        material_factor = 1.0
        if material_info:
            hardness = material_info.get("hardness", 200)
            material_factor = 0.5 + (hardness / 400.0)

        base_force = 500.0
        speed_factor = 1.0 - (cutting_speed - 100.0) * 0.001
        feed_factor = feed_rate / 0.15
        depth_factor = depth_of_cut / 2.0

        force = base_force * speed_factor * feed_factor * depth_factor * material_factor
        return max(100.0, force)

    def _estimate_surface_roughness(
        self,
        cutting_speed: float,
        feed_rate: float,
        depth_of_cut: float,
        tool_info: Optional[Dict[str, Any]]
    ) -> float:
        tool_factor = 1.0
        if tool_info:
            nose_radius = tool_info.get("nose_radius", 0.8)
            tool_factor = 0.8 / nose_radius

        base_roughness = 1.6
        speed_factor = 1.0 - (cutting_speed - 100.0) * 0.0005
        feed_factor = (feed_rate / 0.15) ** 2
        depth_factor = 1.0 + (depth_of_cut - 2.0) * 0.02

        roughness = base_roughness * speed_factor * feed_factor * depth_factor * tool_factor
        return max(0.2, roughness)

    def _estimate_tool_life(
        self,
        cutting_speed: float,
        feed_rate: float,
        depth_of_cut: float,
        material_info: Optional[Dict[str, Any]],
        tool_info: Optional[Dict[str, Any]]
    ) -> float:
        material_factor = 1.0
        if material_info:
            hardness = material_info.get("hardness", 200)
            material_factor = 1.0 - (hardness - 200.0) * 0.001

        tool_factor = 1.0
        if tool_info:
            tool_material = tool_info.get("material", "HSS")
            if tool_material in ["carbide", "coated_carbide"]:
                tool_factor = 1.5
            elif tool_material == "ceramic":
                tool_factor = 2.0

        base_life = 60.0
        speed_factor = (100.0 / cutting_speed) ** 3.0
        feed_factor = (0.15 / feed_rate) ** 1.5
        depth_factor = (2.0 / depth_of_cut) ** 0.5

        life = base_life * speed_factor * feed_factor * depth_factor * material_factor * tool_factor
        return max(5.0, min(200.0, life))
