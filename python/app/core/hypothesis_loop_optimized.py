import asyncio
import math
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from app.agents.hypothesis_generator import HypothesisGenerator
from app.core.alternating_validator import (
    AlternatingValidationResult,
    AlternatingValidator,
    ValidationStrategy,
)
from app.core.process_trace import ProcessTrace, TraceNode
from app.core.task_manager import TaskManager
from app.core.workflow_logger import AIWorkflowLogger, StepType
from app.models.hypothesis import ProcessHypothesis
from app.services.incremental_solver import (
    IncrementalSCIPSolver,
)


class TaskComplexityLevel(Enum):
    """任务复杂度等级枚举。"""
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"


@dataclass
class ComplexityConfig:
    """复杂度配置数据类，定义各等级的迭代范围。"""
    level: TaskComplexityLevel
    min_iterations: int
    max_iterations: int
    description: str = ""


@dataclass
class TaskComplexityFeatures:
    """任务复杂度评估特征。"""
    constraint_count: int = 0
    parameter_count: int = 0
    has_material_info: bool = False
    has_tool_info: bool = False
    has_history: bool = False
    requirement_count: int = 0
    special_operations: int = 0


@dataclass
class CorrectionMagnitudeResult:
    """修正幅度计算结果。"""
    magnitude: float
    components: dict[str, float]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class PerformanceMetricsRecord:
    """性能指标记录。"""
    iteration: int
    duration_ms: float
    correction_magnitude: float = 0.0
    hypothesis_count: int = 1
    validation_passed: bool = False
    score: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ParallelHypothesisResult:
    """并行假设验证结果。"""
    hypothesis: ProcessHypothesis
    solution: dict[str, Any] | None
    validation_result: dict[str, Any]
    score: float
    duration_ms: float
    is_passed: bool
    index: int


@dataclass
class IterationSummary:
    """迭代总结信息。"""
    iteration: int
    best_hypothesis: ProcessHypothesis | None
    best_solution: dict[str, Any] | None
    best_score: float
    hypothesis_count: int
    duration_ms: float
    early_terminated: bool = False


@dataclass
class ConvergenceMetrics:
    """收敛度量指标。"""
    convergence_rate: float
    average_improvement: float
    iterations_to_converge: int | None
    final_score: float
    improvement_history: list[float]


class TaskComplexityEvaluator:
    """任务复杂度评估器。

    根据输入特征自动评估任务复杂度等级，
    并返回对应的迭代次数配置。
    """

    DEFAULT_CONFIGS = {
        TaskComplexityLevel.SIMPLE: ComplexityConfig(
            level=TaskComplexityLevel.SIMPLE,
            min_iterations=2,
            max_iterations=3,
            description="简单任务：约束少，参数明确"
        ),
        TaskComplexityLevel.MODERATE: ComplexityConfig(
            level=TaskComplexityLevel.MODERATE,
            min_iterations=4,
            max_iterations=5,
            description="中等任务：常规约束组合"
        ),
        TaskComplexityLevel.COMPLEX: ComplexityConfig(
            level=TaskComplexityLevel.COMPLEX,
            min_iterations=5,
            max_iterations=7,
            description="复杂任务：多约束、特殊工艺"
        ),
    }

    def evaluate(
        self,
        requirements: dict[str, Any],
        material_info: dict[str, Any],
        tool_info: dict[str, Any],
        history_reference: list[dict[str, Any]] | None = None
    ) -> ComplexityConfig:
        features = self._extract_features(
            requirements, material_info, tool_info, history_reference
        )
        level = self._classify_complexity(features)
        return self.DEFAULT_CONFIGS[level]

    def evaluate_with_initial_result(
        self,
        initial_result: dict[str, Any],
        current_config: ComplexityConfig
    ) -> ComplexityConfig:
        success = initial_result.get("status") == "success"
        validation_passed = initial_result.get("validation_passed", False)
        constraint_violations = len(initial_result.get("unmet_constraints", []))

        if success and validation_passed:
            return self._adjust_down(current_config)
        elif constraint_violations >= 3:
            return self._adjust_up(current_config)

        return current_config

    def _extract_features(
        self,
        requirements: dict[str, Any],
        material_info: dict[str, Any],
        tool_info: dict[str, Any],
        history_reference: list[dict[str, Any]] | None
    ) -> TaskComplexityFeatures:
        features = TaskComplexityFeatures()

        constraints = requirements.get("constraints", {})
        features.constraint_count = len(constraints)

        features.parameter_count = sum(
            1 for k, v in requirements.items()
            if k not in ("constraints", "metadata") and isinstance(v, (int, float, str))
        )

        features.has_material_info = bool(material_info) and len(material_info) > 0
        features.has_tool_info = bool(tool_info) and len(tool_info) > 0
        features.has_history = bool(history_reference) and len(history_reference) > 0

        features.requirement_count = len(requirements)

        special_keywords = [
            "precision", "tolerance", "hard", "exotic", "multi_step",
            "heat_treatment", "surface_treatment", "coating"
        ]
        for kw in special_keywords:
            if kw in str(requirements).lower() or kw in str(material_info).lower():
                features.special_operations += 1

        return features

    def _classify_complexity(self, features: TaskComplexityFeatures) -> TaskComplexityLevel:
        score = 0

        score += features.constraint_count * 1.5
        score += features.parameter_count * 0.8
        score += features.requirement_count * 0.5

        if not features.has_material_info or not features.has_tool_info:
            score += 2

        if features.has_history:
            score -= 1

        score += features.special_operations * 2

        if score <= 5:
            return TaskComplexityLevel.SIMPLE
        elif score <= 12:
            return TaskComplexityLevel.MODERATE
        else:
            return TaskComplexityLevel.COMPLEX

    def _adjust_down(self, config: ComplexityConfig) -> ComplexityConfig:
        new_min = max(2, config.min_iterations - 1)
        new_max = max(config.min_iterations, config.max_iterations - 1)
        return ComplexityConfig(
            level=config.level,
            min_iterations=new_min,
            max_iterations=new_max,
            description=f"基于初始结果下调: {config.description}"
        )

    def _adjust_up(self, config: ComplexityConfig) -> ComplexityConfig:
        new_min = min(config.min_iterations + 1, config.max_iterations)
        new_max = min(config.max_iterations + 1, 7)
        return ComplexityConfig(
            level=config.level,
            min_iterations=new_min,
            max_iterations=new_max,
            description=f"基于初始结果上调: {config.description}"
        )


class EarlyTerminationChecker:
    """早期终止检查器。

    监控迭代修正幅度，当连续N轮修正幅度低于阈值时，
    触发提前终止以避免无效迭代。
    """

    DEFAULT_CONSECUTIVE_THRESHOLD = 2
    DEFAULT_BASE_THRESHOLD = 0.02
    HISTORY_WINDOW_SIZE = 10

    def __init__(
        self,
        consecutive_threshold: int = DEFAULT_CONSECUTIVE_THRESHOLD,
        base_threshold: float = DEFAULT_BASE_THRESHOLD,
        history_window_size: int = HISTORY_WINDOW_SIZE
    ):
        self.consecutive_threshold = consecutive_threshold
        self.base_threshold = base_threshold
        self.history_window_size = history_window_size
        self.magnitude_history: list[float] = []
        self.consecutive_low_count = 0
        self.task_history: dict[str, list[PerformanceMetricsRecord]] = {}

    def compute_correction_magnitude(
        self,
        current_params: dict[str, Any],
        previous_params: dict[str, Any]
    ) -> CorrectionMagnitudeResult:
        components = {}
        total_magnitude = 0.0
        param_count = 0

        all_keys = set(current_params.keys()) | set(previous_params.keys())

        for key in all_keys:
            current_val = self._extract_numeric(current_params.get(key))
            previous_val = self._extract_numeric(previous_params.get(key))

            if current_val is not None and previous_val is not None:
                if previous_val != 0:
                    relative_change = abs(current_val - previous_val) / abs(previous_val)
                else:
                    relative_change = abs(current_val) if current_val != 0 else 0.0

                components[key] = relative_change
                total_magnitude += relative_change
                param_count += 1

        avg_magnitude = total_magnitude / param_count if param_count > 0 else 0.0

        return CorrectionMagnitudeResult(
            magnitude=avg_magnitude,
            components=components
        )

    def compute_validation_magnitude(
        self,
        current_validation: dict[str, Any],
        previous_validation: dict[str, Any]
    ) -> CorrectionMagnitudeResult:
        current_metrics = current_validation.get("metrics", {})
        previous_metrics = previous_validation.get("metrics", {})

        return self.compute_correction_magnitude(current_metrics, previous_metrics)

    def check_early_termination(
        self,
        magnitude_result: CorrectionMagnitudeResult
    ) -> bool:
        current_threshold = self._compute_dynamic_threshold()

        self.magnitude_history.append(magnitude_result.magnitude)

        if len(self.magnitude_history) > self.history_window_size:
            self.magnitude_history.pop(0)

        if magnitude_result.magnitude < current_threshold:
            self.consecutive_low_count += 1
        else:
            self.consecutive_low_count = 0

        return self.consecutive_low_count >= self.consecutive_threshold

    def update_task_history(
        self,
        task_id: str,
        metrics_record: PerformanceMetricsRecord
    ) -> None:
        if task_id not in self.task_history:
            self.task_history[task_id] = []
        self.task_history[task_id].append(metrics_record)

        if len(self.task_history[task_id]) > self.history_window_size:
            self.task_history[task_id] = self.task_history[task_id][-self.history_window_size:]

    def get_dynamic_threshold(self) -> float:
        return self._compute_dynamic_threshold()

    def reset(self) -> None:
        self.magnitude_history.clear()
        self.consecutive_low_count = 0

    def _compute_dynamic_threshold(self) -> float:
        if len(self.magnitude_history) < 3:
            return self.base_threshold

        recent = self.magnitude_history[-self.history_window_size:]
        avg_magnitude = sum(recent) / len(recent)

        adaptive_factor = 0.5
        dynamic_threshold = self.base_threshold * (1 + adaptive_factor * math.exp(-avg_magnitude * 10))

        return max(dynamic_threshold, self.base_threshold * 0.5)

    def _extract_numeric(self, value: Any) -> float | None:
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            import re
            match = re.search(r'([\d.]+)', value)
            if match:
                try:
                    return float(match.group(1))
                except ValueError:
                    pass
        return None


class ParallelHypothesisVerifier:
    """并行假设验证器。

    支持多假设并行生成、求解与验证，
    并从多个验证结果中选择最优方案。
    """

    DEFAULT_PARALLEL_COUNT = 3

    def __init__(
        self,
        parallel_count: int = DEFAULT_PARALLEL_COUNT,
        max_parallel_workers: int = 3,
        selection_strategy: str = "best_score"
    ):
        self.parallel_count = parallel_count
        self.max_parallel_workers = max_parallel_workers
        self.selection_strategy = selection_strategy

    async def run_parallel_verification(
        self,
        task_id: str,
        iteration: int,
        hypothesis_generator: HypothesisGenerator,
        solver_fn: Callable,
        validate_fn: Callable,
        base_hypothesis: ProcessHypothesis | None = None,
        previous_validation: dict[str, Any] | None = None,
        requirements: dict[str, Any] | None = None,
        material_info: dict[str, Any] | None = None,
        trace_chain: list[dict[str, Any]] | None = None
    ) -> list[ParallelHypothesisResult]:
        if self.parallel_count <= 1 or iteration == 1:
            return await self._run_single_verification(
                task_id, iteration, hypothesis_generator,
                solver_fn, validate_fn, base_hypothesis,
                previous_validation, requirements, material_info, trace_chain
            )

        hypotheses = await self._generate_diverse_hypotheses(
            task_id, iteration, hypothesis_generator,
            base_hypothesis, previous_validation, trace_chain
        )

        tasks = [
            self._verify_single_hypothesis(
                task_id, iteration, hyp_idx, hyp,
                solver_fn, validate_fn, requirements, material_info
            )
            for hyp_idx, hyp in enumerate(hypotheses)
        ]

        semaphore = asyncio.Semaphore(self.max_parallel_workers)

        async def limited_task(task):
            async with semaphore:
                return await task

        results = await asyncio.gather(
            *[limited_task(t) for t in tasks],
            return_exceptions=True
        )

        valid_results = []
        for result in results:
            if isinstance(result, Exception):
                continue
            if isinstance(result, ParallelHypothesisResult):
                valid_results.append(result)

        if not valid_results:
            return await self._run_single_verification(
                task_id, iteration, hypothesis_generator,
                solver_fn, validate_fn, base_hypothesis,
                previous_validation, requirements, material_info, trace_chain
            )

        return valid_results

    def select_best_result(
        self, results: list[ParallelHypothesisResult]
    ) -> ParallelHypothesisResult:
        if not results:
            raise ValueError("No results to select from")

        if self.selection_strategy == "best_score":
            return max(results, key=lambda r: r.score)
        elif self.selection_strategy == "first_passed":
            for r in results:
                if r.is_passed:
                    return r
            return max(results, key=lambda r: r.score)
        elif self.selection_strategy == "best_tradeoff":
            return max(results, key=lambda r: self._compute_tradeoff_score(r))
        else:
            return max(results, key=lambda r: r.score)

    def _compute_tradeoff_score(self, result: ParallelHypothesisResult) -> float:
        base_score = result.score
        pass_bonus = 1.0 if result.is_passed else 0.0
        speed_bonus = max(0, 1 - result.duration_ms / 10000) * 0.1
        return base_score + pass_bonus + speed_bonus

    async def _generate_diverse_hypotheses(
        self,
        task_id: str,
        iteration: int,
        hypothesis_generator: HypothesisGenerator,
        base_hypothesis: ProcessHypothesis | None,
        previous_validation: dict[str, Any] | None,
        trace_chain: list[dict[str, Any]] | None
    ) -> list[ProcessHypothesis]:
        hypotheses = []

        if iteration == 1 and base_hypothesis:
            hypotheses.append(base_hypothesis)

        for i in range(self.parallel_count):
            modified_validation = self._perturb_validation_feedback(
                previous_validation, i
            ) if previous_validation else {}

            try:
                hyp = await hypothesis_generator.generate_correction_hypothesis(
                    task_id=task_id,
                    failed_hypothesis=base_hypothesis or ProcessHypothesis(),
                    validation_feedback=modified_validation,
                    trace_chain=trace_chain
                )
                hyp.confidence = hyp.confidence * (0.9 + 0.1 * (i + 1) / self.parallel_count)
                hypotheses.append(hyp)
            except Exception:
                continue

        if not hypotheses:
            hypotheses.append(base_hypothesis or ProcessHypothesis())

        return hypotheses[:self.parallel_count]

    def _perturb_validation_feedback(
        self,
        validation: dict[str, Any] | None,
        perturbation_index: int
    ) -> dict[str, Any]:
        if not validation:
            return {}

        perturbed = dict(validation)
        metrics = dict(perturbed.get("metrics", {}))

        perturb_factors = [
            {"cutting_force": 0.9, "surface_roughness": 1.1},
            {"cutting_force": 1.1, "tool_life": 0.9},
            {"surface_roughness": 0.9, "cutting_force": 1.05},
        ]

        factor = perturb_factors[perturbation_index % len(perturb_factors)]
        for key, multiplier in factor.items():
            if key in metrics:
                metrics[key] = metrics[key] * multiplier

        perturbed["metrics"] = metrics
        perturbed["perturbation_index"] = perturbation_index
        return perturbed

    async def _verify_single_hypothesis(
        self,
        task_id: str,
        iteration: int,
        hyp_idx: int,
        hypothesis: ProcessHypothesis,
        solver_fn: Callable,
        validate_fn: Callable,
        requirements: dict[str, Any] | None,
        material_info: dict[str, Any] | None
    ) -> ParallelHypothesisResult:
        iter_start = time.time()

        try:
            solver_result = await solver_fn(hypothesis, iteration)
            solution = solver_result.get("solution", {}) if solver_result.get("status") == "success" else {}

            if solution:
                validation_result = await validate_fn(solution, requirements or {}, material_info or {})
                is_passed = validation_result.get("passed", False)
                score = self._score_solution(solution, validation_result)
            else:
                validation_result = {"passed": False, "failure_reason": "求解失败"}
                is_passed = False
                score = 0.0

            duration_ms = (time.time() - iter_start) * 1000

            return ParallelHypothesisResult(
                hypothesis=hypothesis,
                solution=solution if solution else None,
                validation_result=validation_result,
                score=score,
                duration_ms=duration_ms,
                is_passed=is_passed,
                index=hyp_idx
            )
        except Exception as e:
            duration_ms = (time.time() - iter_start) * 1000
            return ParallelHypothesisResult(
                hypothesis=hypothesis,
                solution=None,
                validation_result={"passed": False, "failure_reason": str(e)},
                score=0.0,
                duration_ms=duration_ms,
                is_passed=False,
                index=hyp_idx
            )

    async def _run_single_verification(
        self,
        task_id: str,
        iteration: int,
        hypothesis_generator: HypothesisGenerator,
        solver_fn: Callable,
        validate_fn: Callable,
        base_hypothesis: ProcessHypothesis | None,
        previous_validation: dict[str, Any] | None,
        requirements: dict[str, Any] | None,
        material_info: dict[str, Any] | None,
        trace_chain: list[dict[str, Any]] | None
    ) -> list[ParallelHypothesisResult]:
        if iteration == 1 and base_hypothesis:
            hypothesis = base_hypothesis
        elif base_hypothesis:
            hypothesis = await hypothesis_generator.generate_correction_hypothesis(
                task_id=task_id,
                failed_hypothesis=base_hypothesis,
                validation_feedback=previous_validation or {},
                trace_chain=trace_chain
            )
        else:
            hypothesis = ProcessHypothesis()

        result = await self._verify_single_hypothesis(
            task_id, iteration, 0, hypothesis,
            solver_fn, validate_fn, requirements, material_info
        )
        return [result]

    def _score_solution(
        self,
        solution: dict[str, Any],
        validation_result: dict[str, Any]
    ) -> float:
        score = 0.0

        cutting_force = solution.get("cutting_force", 1000)
        score += max(0, 1 - cutting_force / 1000) * 0.3

        surface_roughness = solution.get("surface_roughness", 5)
        score += max(0, 1 - surface_roughness / 5) * 0.3

        tool_life = solution.get("tool_life", 0)
        score += min(1, tool_life / 100) * 0.2

        cutting_speed = solution.get("cutting_speed", 0)
        score += min(1, cutting_speed / 200) * 0.2

        if validation_result.get("passed", False):
            score += 0.5

        return score


class PerformanceMetricsCollector:
    """性能指标收集器。

    收集和分析每轮迭代的性能数据，
    为优化提供数据支持，同时最小化对主循环的影响。
    """

    def __init__(self, enable_collection: bool = True):
        self.enable_collection = enable_collection
        self.records: list[PerformanceMetricsRecord] = []
        self._current_iteration_start: float | None = None

    def start_iteration(self, iteration: int) -> None:
        if self.enable_collection:
            self._current_iteration_start = time.time()

    def record_iteration(
        self,
        iteration: int,
        validation_passed: bool,
        score: float = 0.0,
        correction_magnitude: float = 0.0,
        hypothesis_count: int = 1,
        duration_ms: float | None = None
    ) -> PerformanceMetricsRecord:
        if duration_ms is None and self._current_iteration_start:
            duration_ms = (time.time() - self._current_iteration_start) * 1000
        elif duration_ms is None:
            duration_ms = 0.0

        record = PerformanceMetricsRecord(
            iteration=iteration,
            duration_ms=duration_ms,
            correction_magnitude=correction_magnitude,
            hypothesis_count=hypothesis_count,
            validation_passed=validation_passed,
            score=score
        )

        if self.enable_collection:
            self.records.append(record)

        return record

    def get_convergence_metrics(self) -> ConvergenceMetrics:
        if len(self.records) < 2:
            return ConvergenceMetrics(
                convergence_rate=0.0,
                average_improvement=0.0,
                iterations_to_converge=None,
                final_score=self.records[-1].score if self.records else 0.0,
                improvement_history=[]
            )

        scores = [r.score for r in self.records]
        improvements = []
        for i in range(1, len(scores)):
            improvements.append(scores[i] - scores[i - 1])

        avg_improvement = sum(improvements) / len(improvements) if improvements else 0.0

        convergence_iteration = None
        for i, improvement in enumerate(improvements):
            if abs(improvement) < 0.01:
                convergence_iteration = i + 2
                break

        total_duration = sum(r.duration_ms for r in self.records)
        convergence_rate = len(self.records) / total_duration * 1000 if total_duration > 0 else 0.0

        return ConvergenceMetrics(
            convergence_rate=convergence_rate,
            average_improvement=avg_improvement,
            iterations_to_converge=convergence_iteration,
            final_score=scores[-1],
            improvement_history=improvements
        )

    def get_iteration_durations(self) -> dict[int, float]:
        return {r.iteration: r.duration_ms for r in self.records}

    def get_total_duration_ms(self) -> float:
        return sum(r.duration_ms for r in self.records)

    def get_summary_report(self) -> dict[str, Any]:
        convergence = self.get_convergence_metrics()

        return {
            "total_iterations": len(self.records),
            "total_duration_ms": self.get_total_duration_ms(),
            "average_iteration_ms": (
                self.get_total_duration_ms() / len(self.records)
                if self.records else 0.0
            ),
            "convergence_rate": convergence.convergence_rate,
            "average_improvement": convergence.average_improvement,
            "iterations_to_converge": convergence.iterations_to_converge,
            "final_score": convergence.final_score,
            "passed_iterations": sum(1 for r in self.records if r.validation_passed),
            "improvement_history": convergence.improvement_history
        }

    def export_for_analysis(self) -> list[dict[str, Any]]:
        return [
            {
                "iteration": r.iteration,
                "duration_ms": r.duration_ms,
                "correction_magnitude": r.correction_magnitude,
                "hypothesis_count": r.hypothesis_count,
                "validation_passed": r.validation_passed,
                "score": r.score,
                "timestamp": r.timestamp
            }
            for r in self.records
        ]


@dataclass
class HypothesisIteration:
    """单次迭代结果数据类。"""
    iteration: int
    hypothesis: ProcessHypothesis
    validation_result: dict[str, Any]
    is_passed: bool
    correction_direction: str = ""
    duration_ms: float = 0.0
    correction_magnitude: float = 0.0
    hypothesis_count: int = 1
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "iteration": self.iteration,
            "hypothesis": self.hypothesis.to_dict(),
            "validation_result": self.validation_result,
            "is_passed": self.is_passed,
            "correction_direction": self.correction_direction,
            "duration_ms": self.duration_ms,
            "correction_magnitude": self.correction_magnitude,
            "hypothesis_count": self.hypothesis_count,
            "created_at": self.created_at
        }


@dataclass
class HypothesisLoopResult:
    """假设驱动循环结果数据类。"""
    success: bool
    final_hypothesis: ProcessHypothesis | None
    iterations: list[HypothesisIteration]
    best_feasible_solution: dict[str, Any] | None
    warning_message: str = ""
    total_duration_ms: float = 0.0
    task_complexity: TaskComplexityLevel | None = None
    convergence_metrics: ConvergenceMetrics | None = None
    performance_summary: dict[str, Any] | None = None
    early_terminated: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "final_hypothesis": self.final_hypothesis.to_dict() if self.final_hypothesis else None,
            "iterations": [i.to_dict() for i in self.iterations],
            "best_feasible_solution": self.best_feasible_solution,
            "warning_message": self.warning_message,
            "total_duration_ms": self.total_duration_ms,
            "task_complexity": self.task_complexity.value if self.task_complexity else None,
            "convergence_metrics": self._convergence_to_dict() if self.convergence_metrics else None,
            "performance_summary": self.performance_summary,
            "early_terminated": self.early_terminated
        }

    def _convergence_to_dict(self) -> dict[str, Any]:
        return {
            "convergence_rate": self.convergence_metrics.convergence_rate,
            "average_improvement": self.convergence_metrics.average_improvement,
            "iterations_to_converge": self.convergence_metrics.iterations_to_converge,
            "final_score": self.convergence_metrics.final_score,
            "improvement_history": self.convergence_metrics.improvement_history
        }


class HypothesisDrivenLoopOptimized:
    """优化版假设驱动循环。

    集成自适应迭代、早期终止、并行验证和性能收集功能，
    提升任务处理效率与资源利用率。

    使用示例:
        loop = HypothesisDrivenLoopOptimized(
            task_manager=task_manager,
            workflow_logger=logger,
            hypothesis_generator=generator,
            enable_parallel_verification=True,
            parallel_count=3,
            enable_early_termination=True
        )

        result = await loop.run(
            task_id="task_001",
            requirements={"max_cutting_force": 800},
            material_info={"material": "45钢"},
            tool_info={"tool_type": "高速钢"}
        )

        print(f"任务复杂度: {result.task_complexity}")
        print(f"收敛指标: {result.convergence_metrics}")
        print(f"性能总结: {result.performance_summary}")
    """

    def __init__(
        self,
        task_manager: TaskManager,
        workflow_logger: AIWorkflowLogger,
        hypothesis_generator: HypothesisGenerator,
        max_iterations: int | None = None,
        constraint_mapper: Any | None = None,
        solver: Any | None = None,
        validator: Any | None = None,
        incremental_solver: IncrementalSCIPSolver | None = None,
        alternating_validator: AlternatingValidator | None = None,
        validation_strategy: str = "tolerant",
        tolerance_threshold: float = 0.1,
        progress_callback: Callable | None = None,
        enable_adaptive_iterations: bool = True,
        enable_early_termination: bool = True,
        enable_parallel_verification: bool = True,
        parallel_count: int = 3,
        max_parallel_workers: int = 3,
        parallel_selection_strategy: str = "best_score",
        early_termination_consecutive: int = 2,
        early_termination_threshold: float = 0.02,
        performance_collection: bool = True
    ):
        self.task_manager = task_manager
        self.logger = workflow_logger
        self.hypothesis_generator = hypothesis_generator
        self.max_iterations_override = max_iterations
        self.constraint_mapper = constraint_mapper
        self.solver = solver
        self.validator = validator
        self.process_trace = ProcessTrace()

        self.incremental_solver = incremental_solver
        self.alternating_validator = alternating_validator
        self.validation_strategy = validation_strategy
        self.tolerance_threshold = tolerance_threshold
        self.progress_callback = progress_callback

        self.enable_adaptive_iterations = enable_adaptive_iterations
        self.enable_early_termination = enable_early_termination
        self.enable_parallel_verification = enable_parallel_verification

        self.complexity_evaluator = TaskComplexityEvaluator()

        self.early_termination_checker = EarlyTerminationChecker(
            consecutive_threshold=early_termination_consecutive,
            base_threshold=early_termination_threshold
        )

        self.parallel_verifier = ParallelHypothesisVerifier(
            parallel_count=parallel_count,
            max_parallel_workers=max_parallel_workers,
            selection_strategy=parallel_selection_strategy
        )

        self.metrics_collector = PerformanceMetricsCollector(
            enable_collection=performance_collection
        )

    async def run(
        self,
        task_id: str,
        requirements: dict[str, Any],
        material_info: dict[str, Any],
        tool_info: dict[str, Any],
        history_reference: list[dict[str, Any]] | None = None
    ) -> HypothesisLoopResult:
        start_time = time.time()

        self._current_task_id = task_id

        complexity_config = self.complexity_evaluator.evaluate(
            requirements, material_info, tool_info, history_reference
        )
        task_complexity = complexity_config.level

        effective_max_iterations = self._determine_max_iterations(complexity_config)

        with self.logger.log_step(
            task_id, "hypothesis_loop_optimized", StepType.WORKFLOW_START,
            input_data={
                "task_complexity": task_complexity.value,
                "complexity_config": {
                    "min_iterations": complexity_config.min_iterations,
                    "max_iterations": complexity_config.max_iterations
                },
                "effective_max_iterations": effective_max_iterations,
                "adaptive_enabled": self.enable_adaptive_iterations,
                "early_termination_enabled": self.enable_early_termination,
                "parallel_enabled": self.enable_parallel_verification,
                "parallel_count": self.parallel_verifier.parallel_count,
                "requirements": requirements
            }
        ) as log_entry:
            pass

        await self.task_manager.update_progress(task_id, 5, "开始优化假设驱动循环...")

        iterations: list[HypothesisIteration] = []
        current_hypothesis: ProcessHypothesis | None = None
        best_solution: dict[str, Any] | None = None
        best_score = -1.0
        early_terminated = False

        for iteration in range(1, effective_max_iterations + 1):
            self.metrics_collector.start_iteration(iteration)

            task = self.task_manager.get_task(task_id)
            if task and task.status.value == 'cancelled':
                return HypothesisLoopResult(
                    success=False,
                    final_hypothesis=current_hypothesis,
                    iterations=iterations,
                    best_feasible_solution=best_solution,
                    warning_message="任务已取消",
                    task_complexity=task_complexity,
                    performance_summary=self.metrics_collector.get_summary_report()
                )

            progress = 5 + (iteration / effective_max_iterations) * 85
            await self.task_manager.update_progress(
                task_id, progress, f"执行第 {iteration}/{effective_max_iterations} 轮优化假设验证..."
            )

            try:
                iter_start = time.time()

                if iteration == 1:
                    current_hypothesis = await self.hypothesis_generator.generate_initial_hypothesis(
                        task_id=task_id,
                        requirements=requirements,
                        material_info=material_info,
                        tool_info=tool_info,
                        history_reference=history_reference
                    )
                else:
                    if self.enable_parallel_verification:
                        parallel_results = await self.parallel_verifier.run_parallel_verification(
                            task_id=task_id,
                            iteration=iteration,
                            hypothesis_generator=self.hypothesis_generator,
                            solver_fn=self._solver_wrapper,
                            validate_fn=self._validate_solution,
                            base_hypothesis=current_hypothesis,
                            previous_validation=iterations[-1].validation_result if iterations else None,
                            requirements=requirements,
                            material_info=material_info,
                            trace_chain=[i.to_dict() for i in iterations[:-1]]
                        )

                        best_parallel = self.parallel_verifier.select_best_result(parallel_results)

                        current_hypothesis = best_parallel.hypothesis
                        solution = best_parallel.solution
                        validation_result = best_parallel.validation_result
                        is_passed = best_parallel.is_passed
                        iter_score = best_parallel.score
                        hypothesis_count = len(parallel_results)
                        iteration_duration = (time.time() - iter_start) * 1000

                        if solution:
                            if best_solution is None or iter_score > best_score:
                                best_solution = solution
                                best_score = iter_score

                            correction_direction = (
                                self._extract_correction_direction(validation_result)
                                if not is_passed else ""
                            )

                            correction_magnitude = 0.0
                            if len(iterations) > 0 and iterations[-1].validation_result.get("metrics"):
                                magnitude_result = self.early_termination_checker.compute_validation_magnitude(
                                    validation_result, iterations[-1].validation_result
                                )
                                correction_magnitude = magnitude_result.magnitude

                                if self.enable_early_termination:
                                    should_terminate = self.early_termination_checker.check_early_termination(
                                        magnitude_result
                                    )
                                    if should_terminate and iteration > complexity_config.min_iterations:
                                        early_terminated = True
                                        self.metrics_collector.record_iteration(
                                            iteration=iteration,
                                            validation_passed=False,
                                            score=iter_score,
                                            correction_magnitude=correction_magnitude,
                                            hypothesis_count=hypothesis_count
                                        )
                                        break

                            self.early_termination_checker.update_task_history(
                                task_id,
                                PerformanceMetricsRecord(
                                    iteration=iteration,
                                    duration_ms=iteration_duration,
                                    correction_magnitude=correction_magnitude,
                                    hypothesis_count=hypothesis_count,
                                    validation_passed=is_passed,
                                    score=iter_score
                                )
                            )

                            self.metrics_collector.record_iteration(
                                iteration=iteration,
                                validation_passed=is_passed,
                                score=iter_score,
                                correction_magnitude=correction_magnitude,
                                hypothesis_count=hypothesis_count
                            )

                            iteration_result = HypothesisIteration(
                                iteration=iteration,
                                hypothesis=current_hypothesis,
                                validation_result=validation_result,
                                is_passed=is_passed,
                                correction_direction=correction_direction,
                                duration_ms=iteration_duration,
                                correction_magnitude=correction_magnitude,
                                hypothesis_count=hypothesis_count
                            )
                            iterations.append(iteration_result)

                            trace_node = TraceNode(
                                node_id=str(uuid.uuid4()),
                                task_id=task_id,
                                parent_ids=[iterations[-2].hypothesis.hypothesis_id] if len(iterations) > 1 else [],
                                hypothesis=current_hypothesis.content,
                                reason=current_hypothesis.reason,
                                result={"solution": solution, "solver_result": "parallel_verified"},
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
                                    total_duration_ms=total_duration,
                                    task_complexity=task_complexity,
                                    convergence_metrics=self.metrics_collector.get_convergence_metrics(),
                                    performance_summary=self.metrics_collector.get_summary_report()
                                )

                                with self.logger.log_step(
                                    task_id, "hypothesis_loop_optimized", StepType.WORKFLOW_END,
                                    output_data={
                                        "success": True,
                                        "iterations": iteration,
                                        "early_terminated": early_terminated,
                                        "parallel_used": self.enable_parallel_verification
                                    }
                                ):
                                    pass

                                return result

                        continue
                    else:
                        previous_hypothesis = iterations[-1].hypothesis
                        validation_feedback = iterations[-1].validation_result

                        current_hypothesis = await self.hypothesis_generator.generate_correction_hypothesis(
                            task_id=task_id,
                            failed_hypothesis=previous_hypothesis,
                            validation_feedback=validation_feedback,
                            trace_chain=[i.hypothesis.to_dict() for i in iterations[:-1]]
                        )

                if not self.enable_parallel_verification or iteration == 1:
                    with self.logger.log_step(
                        task_id, "hypothesis_loop_optimized", StepType.CONSTRAINT_PARSE,
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
                        task_id, "hypothesis_loop_optimized", StepType.SOLVER_RUN,
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
                            task_id, "hypothesis_loop_optimized", StepType.VALIDATION,
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

                        correction_magnitude = 0.0
                        if len(iterations) > 0 and iterations[-1].validation_result.get("metrics"):
                            magnitude_result = self.early_termination_checker.compute_validation_magnitude(
                                validation_result, iterations[-1].validation_result
                            )
                            correction_magnitude = magnitude_result.magnitude

                            if self.enable_early_termination:
                                should_terminate = self.early_termination_checker.check_early_termination(
                                    magnitude_result
                                )
                                if should_terminate and iteration > complexity_config.min_iterations:
                                    early_terminated = True
                                    self.metrics_collector.record_iteration(
                                        iteration=iteration,
                                        validation_passed=False,
                                        score=self._score_solution(solution),
                                        correction_magnitude=correction_magnitude
                                    )
                                    break

                        self.early_termination_checker.update_task_history(
                            task_id,
                            PerformanceMetricsRecord(
                                iteration=iteration,
                                duration_ms=iter_duration,
                                correction_magnitude=correction_magnitude,
                                validation_passed=is_passed,
                                score=self._score_solution(solution)
                            )
                        )

                        self.metrics_collector.record_iteration(
                            iteration=iteration,
                            validation_passed=is_passed,
                            score=self._score_solution(solution),
                            correction_magnitude=correction_magnitude
                        )

                        iteration_result = HypothesisIteration(
                            iteration=iteration,
                            hypothesis=current_hypothesis,
                            validation_result=validation_result,
                            is_passed=is_passed,
                            correction_direction=correction_direction,
                            duration_ms=iter_duration,
                            correction_magnitude=correction_magnitude
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
                                total_duration_ms=total_duration,
                                task_complexity=task_complexity,
                                convergence_metrics=self.metrics_collector.get_convergence_metrics(),
                                performance_summary=self.metrics_collector.get_summary_report()
                            )

                            with self.logger.log_step(
                                task_id, "hypothesis_loop_optimized", StepType.WORKFLOW_END,
                                output_data={
                                    "success": True,
                                    "iterations": iteration,
                                    "early_terminated": early_terminated
                                }
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

                        self.metrics_collector.record_iteration(
                            iteration=iteration,
                            validation_passed=False,
                            score=0.0
                        )

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

                self.metrics_collector.record_iteration(
                    iteration=iteration,
                    validation_passed=False,
                    score=0.0
                )

                iteration_result = HypothesisIteration(
                    iteration=iteration,
                    hypothesis=current_hypothesis or ProcessHypothesis(),
                    validation_result=validation_result,
                    is_passed=False,
                    correction_direction=f"系统异常：{e!s}",
                    duration_ms=iter_duration
                )
                iterations.append(iteration_result)

        total_duration = (time.time() - start_time) * 1000

        termination_reason = f"达到最大迭代次数 {effective_max_iterations}"
        if early_terminated:
            termination_reason = "早期终止：修正幅度连续低于阈值"

        warning_message = (
            f"{termination_reason}，未找到完全满足约束的解。"
            f"返回最佳可行解（得分：{best_score:.2f}）。"
        )

        with self.logger.log_step(
            task_id, "hypothesis_loop_optimized", StepType.WORKFLOW_END,
            output_data={
                "success": False,
                "warning": warning_message,
                "iterations": len(iterations),
                "early_terminated": early_terminated,
                "task_complexity": task_complexity.value
            }
        ):
            pass

        return HypothesisLoopResult(
            success=False,
            final_hypothesis=current_hypothesis,
            iterations=iterations,
            best_feasible_solution=best_solution,
            warning_message=warning_message,
            total_duration_ms=total_duration,
            task_complexity=task_complexity,
            convergence_metrics=self.metrics_collector.get_convergence_metrics(),
            performance_summary=self.metrics_collector.get_summary_report(),
            early_terminated=early_terminated
        )

    def _determine_max_iterations(self, config: ComplexityConfig) -> int:
        if self.max_iterations_override is not None:
            return self.max_iterations_override

        if not self.enable_adaptive_iterations:
            return config.max_iterations

        return config.max_iterations

    async def _solver_wrapper(
        self,
        hypothesis: ProcessHypothesis,
        iteration: int
    ) -> dict[str, Any]:
        constraints = await self._map_hypothesis_to_constraints(
            hypothesis, {}
        )

        if self.incremental_solver and self.alternating_validator:
            return await self._run_alternating_solver(
                constraints, {}, {}, iteration
            )
        else:
            return await self._run_solver(constraints, {})

    async def _map_hypothesis_to_constraints(
        self, hypothesis: ProcessHypothesis, requirements: dict[str, Any]
    ) -> dict[str, Any]:
        if self.constraint_mapper:
            return await self.constraint_mapper.map_hypothesis(hypothesis, requirements)

        return self._default_constraint_mapping(hypothesis, requirements)

    def _default_constraint_mapping(
        self, hypothesis: ProcessHypothesis, requirements: dict[str, Any]
    ) -> dict[str, Any]:
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

    def _extract_numeric_bound(self, constraint_str: str) -> float | None:
        import re
        match = re.search(r'([\d.]+)', constraint_str)
        if match:
            return float(match.group(1))
        return None

    async def _run_solver(
        self, constraints: dict[str, Any], requirements: dict[str, Any]
    ) -> dict[str, Any]:
        if self.solver:
            return await self.solver.solve(constraints, requirements)

        return self._default_solver(constraints, requirements)

    async def _run_alternating_solver(
        self,
        constraints: dict[str, Any],
        requirements: dict[str, Any],
        material_info: dict[str, Any],
        iteration: int
    ) -> dict[str, Any]:
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

        async def progress_handler(progress_data: dict[str, Any]):
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

    def _extract_final_metrics(self, result: AlternatingValidationResult) -> dict[str, float]:
        if not result.phase_reports:
            return {}

        final_report = result.phase_reports[-1]
        return {
            "cutting_force": final_report.metrics.get("cutting_force", 0),
            "surface_roughness": final_report.metrics.get("surface_roughness", 0),
            "tool_life": final_report.metrics.get("tool_life", 0)
        }

    def _default_solver(
        self, constraints: dict[str, Any], requirements: dict[str, Any]
    ) -> dict[str, Any]:
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
        solution: dict[str, Any],
        requirements: dict[str, Any],
        material_info: dict[str, Any]
    ) -> dict[str, Any]:
        if self.validator:
            return await self.validator.validate(solution, requirements, material_info)

        return self._default_validation(solution, requirements)

    def _default_validation(
        self, solution: dict[str, Any], requirements: dict[str, Any]
    ) -> dict[str, Any]:
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

    def _score_solution(self, solution: dict[str, Any]) -> float:
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
        self, solution: dict[str, Any], validation_result: dict[str, Any]
    ) -> dict[str, float]:
        metrics = {}

        for key in ["cutting_speed", "feed_rate", "depth_of_cut",
                    "cutting_force", "surface_roughness", "tool_life"]:
            if key in solution:
                metrics[key] = float(solution[key])

        return metrics

    def _extract_correction_direction(self, validation_result: dict[str, Any]) -> str:
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
