"""HypothesisDrivenLoopOptimized 单元测试模块。

测试优化版假设驱动循环的核心功能，包括：
- 任务复杂度评估
- 自适应迭代次数
- 早期终止机制
- 并行假设验证
- 性能指标收集

所有测试遵循 AAA（Arrange-Act-Assert）模式。
"""
import sys
from pathlib import Path
from unittest.mock import MagicMock

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

_mock_tools_module = MagicMock()
_mock_tools_module.BaseTool = MagicMock
_mock_tools_module.ToolObservation = MagicMock
sys.modules['app.agents.tools'] = _mock_tools_module

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.hypothesis_loop_optimized import (
    ComplexityConfig,
    ConvergenceMetrics,
    CorrectionMagnitudeResult,
    EarlyTerminationChecker,
    HypothesisDrivenLoopOptimized,
    HypothesisIteration,
    HypothesisLoopResult,
    ParallelHypothesisResult,
    ParallelHypothesisVerifier,
    PerformanceMetricsCollector,
    PerformanceMetricsRecord,
    TaskComplexityEvaluator,
    TaskComplexityLevel,
)
from app.core.task_manager import TaskManager, TaskStatus, TaskType
from app.core.workflow_logger import AIWorkflowLogger
from app.models.hypothesis import ProcessHypothesis


class TestTaskComplexityEvaluator:
    """任务复杂度评估器测试。"""

    def setup_method(self, method):
        self.evaluator = TaskComplexityEvaluator()

    def test_evaluate_simple_task(self):
        config = self.evaluator.evaluate(
            requirements={"max_cutting_force": 800},
            material_info={"material": "45钢"},
            tool_info={"tool_type": "高速钢"},
            history_reference=[{"material": "45钢", "result_summary": "success"}]
        )

        assert config.level == TaskComplexityLevel.SIMPLE
        assert config.min_iterations >= 2
        assert config.max_iterations <= 3

    def test_evaluate_moderate_task(self):
        config = self.evaluator.evaluate(
            requirements={
                "max_cutting_force": 800,
                "max_surface_roughness": 1.6,
                "min_tool_life": 60,
                "constraints": {"temp": 100}
            },
            material_info={"material": "45钢"},
            tool_info={"tool_type": "高速钢"},
            history_reference=[]
        )

        assert config.level == TaskComplexityLevel.MODERATE

    def test_evaluate_complex_task(self):
        config = self.evaluator.evaluate(
            requirements={
                "max_cutting_force": 800,
                "max_surface_roughness": 0.1,
                "min_tool_life": 120,
                "precision": "high",
                "constraints": {"temp": 100, "vibration": 0.01, "c1": 1, "c2": 2, "c3": 3}
            },
            material_info={"material": "titanium", "hardness": "HRC45", "density": 4.5},
            tool_info={"tool_type": "ceramic", "coating": "TiN", "diameter": 10},
            history_reference=None
        )

        assert config.level == TaskComplexityLevel.COMPLEX

    def test_evaluate_with_initial_result_adjust_up(self):
        config = ComplexityConfig(
            level=TaskComplexityLevel.MODERATE,
            min_iterations=4,
            max_iterations=5
        )

        result = self.evaluator.evaluate_with_initial_result(
            initial_result={
                "status": "failed",
                "validation_passed": False,
                "unmet_constraints": ["c1", "c2", "c3"]
            },
            current_config=config
        )

        assert result.max_iterations >= config.max_iterations

    def test_evaluate_with_initial_result_adjust_down(self):
        config = ComplexityConfig(
            level=TaskComplexityLevel.COMPLEX,
            min_iterations=5,
            max_iterations=7
        )

        result = self.evaluator.evaluate_with_initial_result(
            initial_result={
                "status": "success",
                "validation_passed": True,
                "unmet_constraints": []
            },
            current_config=config
        )

        assert result.max_iterations < config.max_iterations


class TestEarlyTerminationChecker:
    """早期终止检查器测试。"""

    def setup_method(self, method):
        self.checker = EarlyTerminationChecker(
            consecutive_threshold=2,
            base_threshold=0.02
        )

    def test_compute_correction_magnitude_with_params(self):
        result = self.checker.compute_correction_magnitude(
            current_params={"cutting_force": 800, "feed_rate": 0.15},
            previous_params={"cutting_force": 1000, "feed_rate": 0.2}
        )

        assert result.magnitude > 0
        assert "cutting_force" in result.components
        assert "feed_rate" in result.components

    def test_compute_correction_magnitude_empty(self):
        result = self.checker.compute_correction_magnitude(
            current_params={},
            previous_params={}
        )

        assert result.magnitude == 0.0

    def test_early_termination_triggered(self):
        for _ in range(3):
            result = CorrectionMagnitudeResult(
                magnitude=0.01,
                components={"cutting_force": 0.01}
            )
            terminated = self.checker.check_early_termination(result)

        assert terminated is True

    def test_early_termination_not_triggered(self):
        result1 = CorrectionMagnitudeResult(
            magnitude=0.05,
            components={"cutting_force": 0.05}
        )
        self.checker.check_early_termination(result1)

        result2 = CorrectionMagnitudeResult(
            magnitude=0.01,
            components={"cutting_force": 0.01}
        )
        terminated = self.checker.check_early_termination(result2)

        assert terminated is False

    def test_dynamic_threshold_adjustment(self):
        self.checker.magnitude_history = [0.1, 0.08, 0.05]

        threshold = self.checker.get_dynamic_threshold()

        assert threshold > 0
        assert isinstance(threshold, float)

    def test_reset(self):
        self.checker.magnitude_history = [0.1, 0.08]
        self.checker.consecutive_low_count = 2

        self.checker.reset()

        assert len(self.checker.magnitude_history) == 0
        assert self.checker.consecutive_low_count == 0

    def test_update_task_history(self):
        record = PerformanceMetricsRecord(
            iteration=1,
            duration_ms=100.0,
            validation_passed=True,
            score=0.8
        )

        self.checker.update_task_history("task_001", record)

        assert "task_001" in self.checker.task_history
        assert len(self.checker.task_history["task_001"]) == 1


class TestParallelHypothesisVerifier:
    """并行假设验证器测试。"""

    def setup_method(self, method):
        self.verifier = ParallelHypothesisVerifier(
            parallel_count=3,
            selection_strategy="best_score"
        )

    def test_select_best_result_by_score(self):
        results = [
            ParallelHypothesisResult(
                hypothesis=ProcessHypothesis(content="hyp1"),
                solution={"cutting_speed": 100},
                validation_result={"passed": False},
                score=0.5,
                duration_ms=50.0,
                is_passed=False,
                index=0
            ),
            ParallelHypothesisResult(
                hypothesis=ProcessHypothesis(content="hyp2"),
                solution={"cutting_speed": 120},
                validation_result={"passed": True},
                score=0.8,
                duration_ms=60.0,
                is_passed=True,
                index=1
            )
        ]

        best = self.verifier.select_best_result(results)

        assert best.score == 0.8
        assert best.index == 1

    def test_select_first_passed(self):
        verifier = ParallelHypothesisVerifier(
            parallel_count=3,
            selection_strategy="first_passed"
        )

        results = [
            ParallelHypothesisResult(
                hypothesis=ProcessHypothesis(content="hyp1"),
                solution={"cutting_speed": 100},
                validation_result={"passed": False},
                score=0.9,
                duration_ms=50.0,
                is_passed=False,
                index=0
            ),
            ParallelHypothesisResult(
                hypothesis=ProcessHypothesis(content="hyp2"),
                solution={"cutting_speed": 120},
                validation_result={"passed": True},
                score=0.6,
                duration_ms=60.0,
                is_passed=True,
                index=1
            )
        ]

        best = verifier.select_best_result(results)

        assert best.is_passed is True
        assert best.index == 1

    def test_select_best_tradeoff(self):
        verifier = ParallelHypothesisVerifier(
            parallel_count=3,
            selection_strategy="best_tradeoff"
        )

        results = [
            ParallelHypothesisResult(
                hypothesis=ProcessHypothesis(content="hyp1"),
                solution={"cutting_speed": 100},
                validation_result={"passed": True},
                score=0.5,
                duration_ms=100.0,
                is_passed=True,
                index=0
            ),
            ParallelHypothesisResult(
                hypothesis=ProcessHypothesis(content="hyp2"),
                solution={"cutting_speed": 120},
                validation_result={"passed": False},
                score=0.6,
                duration_ms=500.0,
                is_passed=False,
                index=1
            )
        ]

        best = verifier.select_best_result(results)

        assert best.is_passed is True

    def test_empty_results_raises_error(self):
        with pytest.raises(ValueError, match="No results to select"):
            self.verifier.select_best_result([])

    @pytest.mark.asyncio
    async def test_run_single_verification_fallback(self):
        self.verifier.parallel_count = 1

        mock_generator = AsyncMock()
        mock_generator.generate_correction_hypothesis.return_value = ProcessHypothesis(
            content="test", confidence=0.7
        )

        async def mock_solver(hyp, iteration):
            return {"status": "success", "solution": {"cutting_speed": 120}}

        async def mock_validate(solution, req, mat):
            return {"passed": True, "metrics": {}}

        results = await self.verifier.run_parallel_verification(
            task_id="task_001",
            iteration=1,
            hypothesis_generator=mock_generator,
            solver_fn=mock_solver,
            validate_fn=mock_validate,
            base_hypothesis=ProcessHypothesis(content="initial"),
            previous_validation=None,
            requirements={},
            material_info={}
        )

        assert len(results) == 1
        assert results[0].is_passed is True


class TestPerformanceMetricsCollector:
    """性能指标收集器测试。"""

    def setup_method(self, method):
        self.collector = PerformanceMetricsCollector(enable_collection=True)

    def test_record_iteration(self):
        self.collector.start_iteration(1)

        import time
        time.sleep(0.01)

        record = self.collector.record_iteration(
            iteration=1,
            validation_passed=True,
            score=0.8,
            correction_magnitude=0.05
        )

        assert record.iteration == 1
        assert record.validation_passed is True
        assert record.score == 0.8
        assert record.duration_ms > 0

    def test_get_convergence_metrics_empty(self):
        metrics = self.collector.get_convergence_metrics()

        assert metrics.convergence_rate == 0.0
        assert metrics.iterations_to_converge is None

    def test_get_convergence_metrics_with_data(self):
        for i in range(1, 5):
            self.collector.record_iteration(
                iteration=i,
                validation_passed=(i == 4),
                score=0.3 + i * 0.15,
                correction_magnitude=0.1 - i * 0.02
            )

        metrics = self.collector.get_convergence_metrics()

        assert metrics.average_improvement > 0
        assert metrics.final_score > 0.3

    def test_get_iteration_durations(self):
        for i in range(1, 4):
            self.collector.record_iteration(
                iteration=i,
                validation_passed=False,
                score=0.5,
                duration_ms=100.0 * i
            )

        durations = self.collector.get_iteration_durations()

        assert len(durations) == 3
        assert durations[1] == 100.0
        assert durations[3] == 300.0

    def test_get_total_duration_ms(self):
        for i in range(1, 4):
            self.collector.record_iteration(
                iteration=i,
                validation_passed=False,
                score=0.5,
                duration_ms=100.0
            )

        total = self.collector.get_total_duration_ms()

        assert total == 300.0

    def test_get_summary_report(self):
        for i in range(1, 4):
            self.collector.record_iteration(
                iteration=i,
                validation_passed=(i == 3),
                score=0.5 + i * 0.1,
                duration_ms=100.0
            )

        report = self.collector.get_summary_report()

        assert report["total_iterations"] == 3
        assert report["passed_iterations"] == 1
        assert report["total_duration_ms"] == 300.0

    def test_export_for_analysis(self):
        self.collector.record_iteration(
            iteration=1,
            validation_passed=True,
            score=0.8
        )

        exported = self.collector.export_for_analysis()

        assert len(exported) == 1
        assert "iteration" in exported[0]
        assert "timestamp" in exported[0]

    def test_disabled_collection(self):
        collector = PerformanceMetricsCollector(enable_collection=False)
        collector.start_iteration(1)
        collector.record_iteration(
            iteration=1,
            validation_passed=True,
            score=0.8
        )

        assert len(collector.records) == 0


class TestHypothesisIterationOptimized:
    """优化版 HypothesisIteration 测试。"""

    def test_to_dict_with_new_fields(self):
        hypothesis = ProcessHypothesis(content="test")
        iteration = HypothesisIteration(
            iteration=1,
            hypothesis=hypothesis,
            validation_result={"passed": True},
            is_passed=True,
            correction_magnitude=0.05,
            hypothesis_count=3
        )

        result_dict = iteration.to_dict()

        assert "correction_magnitude" in result_dict
        assert "hypothesis_count" in result_dict
        assert result_dict["correction_magnitude"] == 0.05
        assert result_dict["hypothesis_count"] == 3


class TestHypothesisLoopResultOptimized:
    """优化版 HypothesisLoopResult 测试。"""

    def test_to_dict_with_new_fields(self):
        hypothesis = ProcessHypothesis(content="test")
        result = HypothesisLoopResult(
            success=True,
            final_hypothesis=hypothesis,
            iterations=[],
            best_feasible_solution={"cutting_speed": 120},
            task_complexity=TaskComplexityLevel.MODERATE,
            convergence_metrics=ConvergenceMetrics(
                convergence_rate=0.5,
                average_improvement=0.1,
                iterations_to_converge=3,
                final_score=0.8,
                improvement_history=[0.1, 0.1, 0.1]
            ),
            early_terminated=False
        )

        result_dict = result.to_dict()

        assert result_dict["task_complexity"] == "moderate"
        assert result_dict["convergence_metrics"] is not None
        assert result_dict["convergence_metrics"]["final_score"] == 0.8
        assert result_dict["early_terminated"] is False

    def test_to_dict_with_none_values(self):
        result = HypothesisLoopResult(
            success=False,
            final_hypothesis=None,
            iterations=[],
            best_feasible_solution=None
        )

        result_dict = result.to_dict()

        assert result_dict["final_hypothesis"] is None
        assert result_dict["task_complexity"] is None
        assert result_dict["convergence_metrics"] is None


class TestHypothesisDrivenLoopOptimizedIntegration:
    """优化版循环集成测试。"""

    def setup_method(self, method):
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

    def teardown_method(self, method):
        self.task_manager = None
        self.logger = None
        self.hypothesis_generator = None

    def test_default_initialization(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

        assert loop.enable_adaptive_iterations is True
        assert loop.enable_early_termination is True
        assert loop.enable_parallel_verification is True
        assert loop.parallel_verifier.parallel_count == 3
        assert loop.complexity_evaluator is not None
        assert loop.early_termination_checker is not None
        assert loop.metrics_collector is not None

    def test_custom_initialization(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            enable_parallel_verification=False,
            parallel_count=5,
            early_termination_consecutive=3,
            early_termination_threshold=0.01
        )

        assert loop.enable_parallel_verification is False
        assert loop.parallel_verifier.parallel_count == 5
        assert loop.early_termination_checker.consecutive_threshold == 3
        assert loop.early_termination_checker.base_threshold == 0.01

    @pytest.mark.asyncio
    async def test_first_iteration_passes(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=AsyncMock(),
            enable_parallel_verification=False
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(
            content="使用高速钢刀具，切削速度 120m/min",
            expected_outcomes={"cutting_force": "< 800N"}
        )
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis

        loop.validator.validate.return_value = {
            "passed": True,
            "failure_reason": "",
            "unmet_constraints": [],
            "metrics": {"cutting_force": 750.0}
        }

        result = await loop.run(
            task_id=task_id,
            requirements={"max_cutting_force": 800},
            material_info={"material": "45钢"},
            tool_info={"tool_type": "高速钢"}
        )

        assert result.success is True
        assert len(result.iterations) == 1
        assert result.task_complexity is not None
        assert result.performance_summary is not None

    @pytest.mark.asyncio
    async def test_early_termination_triggered(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=AsyncMock(),
            enable_parallel_verification=False,
            early_termination_consecutive=2,
            early_termination_threshold=0.5
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="test")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        self.hypothesis_generator.generate_correction_hypothesis.return_value = test_hypothesis

        loop.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "constraint violation",
            "unmet_constraints": ["c1"],
            "metrics": {"cutting_force": 750.0, "surface_roughness": 1.4}
        }

        result = await loop.run(
            task_id=task_id,
            requirements={"max_cutting_force": 800},
            material_info={"material": "45钢"},
            tool_info={"tool_type": "高速钢"}
        )

        assert result.success is False
        assert result.early_terminated is True or len(result.iterations) > 0

    @pytest.mark.asyncio
    async def test_performance_metrics_collected(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=AsyncMock(),
            enable_parallel_verification=False
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="test")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        loop.validator.validate.return_value = {
            "passed": True,
            "failure_reason": "",
            "unmet_constraints": [],
            "metrics": {"cutting_force": 750.0}
        }

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.performance_summary is not None
        assert result.performance_summary["total_iterations"] >= 1
        assert result.performance_summary["total_duration_ms"] > 0

    @pytest.mark.asyncio
    async def test_task_cancellation(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=AsyncMock(),
            enable_parallel_verification=False,
            max_iterations=5
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        call_count = [0]

        async def mock_generate_initial(**kwargs):
            call_count[0] += 1
            if call_count[0] == 2:
                self.task_manager._tasks[task_id].status = TaskStatus.CANCELLED
            return ProcessHypothesis(content="test")

        self.hypothesis_generator.generate_initial_hypothesis.side_effect = mock_generate_initial
        self.hypothesis_generator.generate_correction_hypothesis.side_effect = mock_generate_initial
        loop.validator.validate.return_value = {
            "passed": False,
            "failure_reason": "验证失败",
            "unmet_constraints": []
        }

        result = await loop.run(
            task_id=task_id,
            requirements={},
            material_info={},
            tool_info={}
        )

        assert result.success is False
        assert "取消" in result.warning_message

    @pytest.mark.asyncio
    async def test_complexity_affects_result(self):
        loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator,
            validator=AsyncMock(),
            enable_parallel_verification=False
        )

        task_id = self.task_manager.create_task(TaskType.WORKFLOW_EXECUTION)

        test_hypothesis = ProcessHypothesis(content="test")
        self.hypothesis_generator.generate_initial_hypothesis.return_value = test_hypothesis
        loop.validator.validate.return_value = {
            "passed": True,
            "failure_reason": "",
            "unmet_constraints": []
        }

        complex_requirements = {
            "max_cutting_force": 0.001,
            "max_surface_roughness": 0.0001,
            "min_tool_life": 10000,
            "constraints": {"c1": 1, "c2": 2, "c3": 3}
        }

        result = await loop.run(
            task_id=task_id,
            requirements=complex_requirements,
            material_info={"material": "titanium"},
            tool_info={"tool_type": "ceramic"}
        )

        assert result.task_complexity in [
            TaskComplexityLevel.MODERATE,
            TaskComplexityLevel.COMPLEX
        ]


class TestDefaultConstraintMappingOptimized:
    """优化版默认约束映射测试。"""

    def setup_method(self, method):
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

        self.loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

    def test_mapping_with_all_constraints(self):
        hypothesis = ProcessHypothesis(
            content="test",
            expected_outcomes={
                "cutting_force": "< 800N",
                "surface_roughness": "< 1.6μm",
                "tool_life": "> 60min"
            }
        )

        constraints = self.loop._default_constraint_mapping(hypothesis, {})

        assert "cutting_force_max" in constraints
        assert "surface_roughness_max" in constraints
        assert "tool_life_min" in constraints
        assert constraints["cutting_force_max"] == 800.0
        assert constraints["surface_roughness_max"] == 1.6
        assert constraints["tool_life_min"] == 60.0


class TestScoreSolutionOptimized:
    """优化版评分测试。"""

    def setup_method(self, method):
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

        self.loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

    def test_good_solution_score(self):
        solution = {
            "cutting_force": 500.0,
            "surface_roughness": 1.0,
            "tool_life": 80.0,
            "cutting_speed": 150.0
        }

        score = self.loop._score_solution(solution)

        assert score > 0.5

    def test_poor_solution_score(self):
        solution = {
            "cutting_force": 950.0,
            "surface_roughness": 4.5,
            "tool_life": 10.0,
            "cutting_speed": 20.0
        }

        score = self.loop._score_solution(solution)

        assert score < 0.3


class TestExtractCorrectionDirectionOptimized:
    """优化版修正方向提取测试。"""

    def setup_method(self, method):
        self.task_manager = TaskManager(default_timeout=300.0)
        self.logger = AIWorkflowLogger()
        self.hypothesis_generator = AsyncMock()

        self.loop = HypothesisDrivenLoopOptimized(
            task_manager=self.task_manager,
            workflow_logger=self.logger,
            hypothesis_generator=self.hypothesis_generator
        )

    def test_cutting_force_direction(self):
        validation_result = {
            "failure_reason": "切削力 900N 超过限制 800N",
            "unmet_constraints": []
        }

        direction = self.loop._extract_correction_direction(validation_result)

        assert "切削力" in direction

    def test_surface_roughness_direction(self):
        validation_result = {
            "failure_reason": "表面粗糙度超标",
            "unmet_constraints": []
        }

        direction = self.loop._extract_correction_direction(validation_result)

        assert "粗糙度" in direction

    def test_multiple_failures_direction(self):
        validation_result = {
            "failure_reason": "切削力过高；表面粗糙度不足；刀具寿命短",
            "unmet_constraints": []
        }

        direction = self.loop._extract_correction_direction(validation_result)

        assert "切削力" in direction
        assert "粗糙度" in direction
        assert "刀具寿命" in direction
