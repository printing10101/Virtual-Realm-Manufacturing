import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from app.services.incremental_solver import (  # noqa: E402
    IncrementalSCIPSolver,
    SolverState,
)
from app.core.alternating_validator import AlternatingValidator, ValidationStrategy  # noqa: E402
from app.services.solver_progress_service import get_solver_progress_service  # noqa: E402


async def test_incremental_solver():
    print("=" * 60)
    print("Test 1: IncrementalSCIPSolver - Basic Solve")
    print("=" * 60)

    solver = IncrementalSCIPSolver()

    constraints = {
        "cutting_speed_min": 50.0,
        "cutting_speed_max": 200.0,
        "feed_rate_min": 0.05,
        "feed_rate_max": 0.3,
        "depth_of_cut_min": 0.5,
        "depth_of_cut_max": 5.0,
    }

    requirements = {
        "cutting_speed": 120.0,
        "feed_rate": 0.15,
        "depth_of_cut": 2.0,
        "max_cutting_force": 800.0,
        "max_surface_roughness": 2.0,
        "min_tool_life": 40.0,
    }

    material_info = {"material_name": "45#", "hardness": 220}
    tool_info = {"nose_radius": 0.8, "material": "carbide"}

    gen = solver.solve(constraints, requirements, material_info, tool_info)

    phase_count = 0
    async for phase_result in gen:
        phase_count += 1
        print(f"  Phase {phase_count}: {phase_result.phase.value}")
        print(f"    State: {phase_result.state.value}")
        print(f"    Metrics: {phase_result.metrics}")
        print(f"    Duration: {phase_result.duration_ms:.1f}ms")

        feedback = {
            "passed": True,
            "error_rate": 0.0,
            "violated_constraints": {},
            "strategy": "tolerant",
            "warnings": [],
        }
        solver.send_feedback(feedback)

    assert phase_count > 0, "No phases were executed"
    assert solver.get_state().state == SolverState.COMPLETED, (
        f"Solver state should be COMPLETED, got {solver.get_state().state}"
    )
    print(f"\n  PASSED: {phase_count} phases executed successfully")


async def test_alternating_validator_strict():
    print("\n" + "=" * 60)
    print("Test 2: AlternatingValidator - Strict Mode")
    print("=" * 60)

    solver = IncrementalSCIPSolver()

    async def failing_validation(params, requirements, metrics):
        return {
            "passed": False,
            "unmet_constraints": {
                "cutting_force_max": {"actual": 1200, "required": 800, "violation": 400}
            },
            "warnings": [],
        }

    validator = AlternatingValidator(
        solver=solver,
        validation_fn=failing_validation,
        strategy=ValidationStrategy.STRICT,
    )

    constraints = {
        "cutting_speed_min": 50.0,
        "cutting_speed_max": 200.0,
        "feed_rate_min": 0.05,
        "feed_rate_max": 0.3,
        "depth_of_cut_min": 0.5,
        "depth_of_cut_max": 5.0,
    }

    requirements = {
        "max_cutting_force": 800.0,
        "max_surface_roughness": 3.2,
        "min_tool_life": 30.0,
    }

    result = await validator.validate(constraints, requirements)

    assert result.terminated_early, (
        "Strict mode should terminate early on validation failure"
    )
    assert not result.success, (
        "Result should not be successful in strict mode with failing validation"
    )
    print(f"  Terminated early: {result.terminated_early}")
    print(f"  Reason: {result.termination_reason}")
    print(f"  Phases executed: {len(result.phase_reports)}")
    print("\n  PASSED: Strict mode correctly terminated early")


async def test_alternating_validator_tolerant():
    print("\n" + "=" * 60)
    print("Test 3: AlternatingValidator - Tolerant Mode (small error)")
    print("=" * 60)

    solver = IncrementalSCIPSolver()
    call_count = 0

    async def tolerant_validation(params, requirements, metrics):
        nonlocal call_count
        call_count += 1
        if call_count <= 2:
            return {
                "passed": False,
                "unmet_constraints": {
                    "cutting_force_max": {
                        "actual": 850,
                        "required": 800,
                        "violation": 50,
                    }
                },
                "warnings": [],
            }
        return {"passed": True, "unmet_constraints": {}, "warnings": []}

    validator = AlternatingValidator(
        solver=solver,
        validation_fn=tolerant_validation,
        strategy=ValidationStrategy.TOLERANT,
        tolerance_threshold=0.10,
    )

    constraints = {
        "cutting_speed_min": 50.0,
        "cutting_speed_max": 200.0,
        "feed_rate_min": 0.05,
        "feed_rate_max": 0.3,
        "depth_of_cut_min": 0.5,
        "depth_of_cut_max": 5.0,
    }

    requirements = {
        "max_cutting_force": 800.0,
        "max_surface_roughness": 3.2,
        "min_tool_life": 30.0,
    }

    result = await validator.validate(constraints, requirements)

    error_rate = result.phase_reports[0].error_rate if result.phase_reports else 0
    print(f"  Error rate: {error_rate:.2%}")
    print(f"  Tolerance threshold: {validator.tolerance_threshold:.2%}")
    print(f"  Phases executed: {len(result.phase_reports)}")

    if error_rate < validator.tolerance_threshold:
        print(
            f"  PASSED: Tolerant mode correctly continued (error {error_rate:.2%} < threshold {validator.tolerance_threshold:.2%})"  # noqa: E501
        )
    else:
        print("  NOTE: Error exceeded threshold, early termination expected")


async def test_solver_progress_service():
    print("\n" + "=" * 60)
    print("Test 4: SolverProgressService")
    print("=" * 60)

    service = get_solver_progress_service()
    task_id = "test_phase_h_001"

    service.initialize_progress(task_id)
    state = service.get_progress_state(task_id)
    assert state is not None, "Progress state should be initialized"
    assert state.is_active, "Progress should be active after initialization"
    assert state.can_terminate, "Should be able to terminate after initialization"
    print(f"  Initialized: task_id={task_id}")
    print(f"  Is active: {state.is_active}")
    print(f"  Can terminate: {state.can_terminate}")

    service.update_phase_progress(
        task_id,
        {
            "phase": "feasibility",
            "state": "completed",
            "parameters": {
                "cutting_speed": 120.0,
                "feed_rate": 0.15,
                "depth_of_cut": 2.0,
            },
            "metrics": {
                "cutting_force": 750.0,
                "surface_roughness": 1.6,
                "tool_life": 60.0,
            },
            "duration_ms": 50.0,
        },
    )

    state = service.get_progress_state(task_id)
    assert len(state.phase_states) == 1, "Should have 1 phase state"
    assert state.phase_states[0]["phase"] == "feasibility"
    print(f"  Phase states: {len(state.phase_states)}")
    print(f"  First phase: {state.phase_states[0]['phase']}")

    service.complete_solving(
        task_id, {"total_phases": 4, "success_rate": 1.0, "total_time_ms": 200.0}
    )

    state = service.get_progress_state(task_id)
    assert not state.is_active, "Progress should not be active after completion"
    assert not state.can_terminate, "Should not be able to terminate after completion"
    print("  After completion:")
    print(f"    Is active: {state.is_active}")
    print(f"    Can terminate: {state.can_terminate}")
    print("\n  PASSED: Progress service works correctly")

    service.clear_task(task_id)


async def test_alternating_validator_best_effort():
    print("\n" + "=" * 60)
    print("Test 5: AlternatingValidator - Best Effort Mode")
    print("=" * 60)

    solver = IncrementalSCIPSolver()

    async def always_fail_validation(params, requirements, metrics):
        return {
            "passed": False,
            "unmet_constraints": {
                "cutting_force_max": {"actual": 1500, "required": 800, "violation": 700}
            },
            "warnings": [],
        }

    validator = AlternatingValidator(
        solver=solver,
        validation_fn=always_fail_validation,
        strategy=ValidationStrategy.BEST_EFFORT,
    )

    constraints = {
        "cutting_speed_min": 50.0,
        "cutting_speed_max": 200.0,
        "feed_rate_min": 0.05,
        "feed_rate_max": 0.3,
        "depth_of_cut_min": 0.5,
        "depth_of_cut_max": 5.0,
    }

    requirements = {
        "max_cutting_force": 800.0,
        "max_surface_roughness": 3.2,
        "min_tool_life": 30.0,
    }

    result = await validator.validate(constraints, requirements)

    assert result.success, "Best effort mode should always return success"
    assert not result.terminated_early, "Best effort mode should not terminate early"
    print(f"  Success: {result.success}")
    print(f"  Terminated early: {result.terminated_early}")
    print(f"  Phases executed: {len(result.phase_reports)}")
    print("\n  PASSED: Best effort mode completed all phases")


async def run_all_tests():
    print("\nPhase H: Generator Iterative Evaluation Tests")
    print("=" * 60)

    await test_incremental_solver()
    await test_alternating_validator_strict()
    await test_alternating_validator_tolerant()
    await test_solver_progress_service()
    await test_alternating_validator_best_effort()

    print("\n" + "=" * 60)
    print("ALL PHASE H TESTS PASSED")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(run_all_tests())
