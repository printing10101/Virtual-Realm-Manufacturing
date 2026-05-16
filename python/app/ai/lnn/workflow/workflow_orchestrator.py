"""
Workflow LNN Orchestrator

Implements LNN-enhanced workflow orchestration with fallback mechanisms,
configuration management, and execution plan generation.
"""

import os
import time
import json
import logging
import numpy as np
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

from app.ai.lnn.config.config_manager import YAMLConfigManager
from app.ai.lnn.core import (
    EngineType,
    TaskInput,
    RoutingDecision,
    InferenceResult,
    FusionResult,
    TaskCategory,
    DataType,
)
from app.ai.lnn.engine import HybridInferenceEngine, EngineConfig
from app.ai.lnn.preprocessing import DataPreprocessor

logger = logging.getLogger(__name__)


class WorkflowStepStatus(str, Enum):
    """工作流步骤执行状态"""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    FALLBACK = "fallback"


class FallbackStrategy(str, Enum):
    """降级策略"""

    RULE_ENGINE = "rule_engine"
    DEFAULT_OUTPUT = "default_output"
    CACHED_RESULT = "cached_result"
    ERROR_RAISE = "error_raise"


@dataclass
class WorkflowStep:
    """工作流步骤定义"""

    name: str
    step_type: str = "lnn_inference"
    model_name: Optional[str] = None
    input_mapping: Optional[Dict[str, str]] = None
    output_key: str = "result"
    timeout_ms: int = 5000
    retry_count: int = 0
    on_failure: str = "fallback"
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    started_at: Optional[float] = None
    completed_at: Optional[float] = None


@dataclass
class WorkflowExecutionPlan:
    """工作流执行计划"""

    workflow_id: str
    steps: List[WorkflowStep]
    selected_model: str = ""
    routing_decision: Optional[RoutingDecision] = None
    created_at: float = 0.0
    status: WorkflowStepStatus = WorkflowStepStatus.PENDING
    total_steps: int = 0
    completed_steps: int = 0


@dataclass
class WorkflowResult:
    """工作流执行结果"""

    workflow_id: str
    success: bool
    output: Dict[str, Any] = field(default_factory=dict)
    execution_plan: Optional[WorkflowExecutionPlan] = None
    total_time_ms: float = 0.0
    steps_result: List[Dict[str, Any]] = field(default_factory=list)
    fallback_triggered: bool = False
    fallback_reason: str = ""
    metadata: Optional[Dict[str, Any]] = None
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "success": self.success,
            "output": self.output,
            "total_time_ms": self.total_time_ms,
            "steps_result": self.steps_result,
            "fallback_triggered": self.fallback_triggered,
            "fallback_reason": self.fallback_reason,
            "metadata": self.metadata or {},
            "timestamp": self.timestamp,
        }


class WorkflowLNNOrchestrator:
    """
    LNN增强的工作流编排器

    功能：
    - 接收用户输入并进行预处理
    - 根据输入动态选择合适的LNN模型
    - 处理模型推理结果并生成工作流执行计划
    - 执行工作流步骤并返回最终结果
    - 支持降级机制，当LNN不可用时切换至规则引擎
    """

    def __init__(
        self,
        config_path: Optional[str] = None,
        config: Optional[YAMLConfigManager] = None,
        engine: Optional[HybridInferenceEngine] = None,
    ):
        """
        初始化工作流编排器

        Args:
            config_path: YAML配置文件路径
            config: 已有的配置管理器实例
            engine: 已有的混合推理引擎实例
        """
        if config:
            self.config = config
        elif config_path:
            self.config = YAMLConfigManager(config_path=config_path)
        else:
            self.config = YAMLConfigManager()

        self.engine = engine or HybridInferenceEngine(
            EngineConfig(
                device=self.config.get("lnn", "default_device", "cpu"),
                cache_size=self.config.get("lnn", "cache_size", 10),
                config=self.config,
            ),
        )

        self._workflow_history: List[WorkflowResult] = []
        self._result_cache: Dict[str, Any] = {}
        self._fallback_threshold = self.config.get("lnn", "thresholds.fallback", 0.50)
        self._max_steps = self.config.get("workflow", "max_steps", 10)
        self._timeout_seconds = self.config.get("workflow", "timeout_seconds", 300)
        self._enable_fallback = self.config.get("workflow", "enable_fallback", True)
        self._fallback_strategy = FallbackStrategy.RULE_ENGINE
        self._log_dir = self.config.get("workflow", "log_dir", "logs/workflows")
        self._log_enabled = self.config.get("workflow", "log_enabled", True)

    def execute_workflow(self, user_input: Any) -> WorkflowResult:
        """
        执行LNN增强的工作流

        Args:
            user_input: 用户输入（可以是字符串描述、字典或numpy数组）

        Returns:
            WorkflowResult 工作流执行结果
        """
        workflow_id = (
            f"wf_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(user_input) % 10000}"
        )
        start_time = time.perf_counter()

        try:
            # 1. 预处理用户输入
            task_input = self._preprocess_input(user_input)

            # 2. 动态选择LNN模型
            routing_decision = self.engine.router.route(task_input)

            # 3. 生成工作流执行计划
            execution_plan = self._generate_execution_plan(
                workflow_id, task_input, routing_decision
            )

            # 4. 执行工作流步骤
            workflow_result = self._execute_plan(execution_plan, task_input)

            # 5. 记录结果
            processing_time = (time.perf_counter() - start_time) * 1000
            workflow_result.total_time_ms = processing_time
            workflow_result.timestamp = time.time()
            workflow_result.metadata = {
                "routing_decision": routing_decision.to_dict(),
                "engine_stats": self.engine.get_engine_stats(),
            }

            self._workflow_history.append(workflow_result)
            self._log_workflow(workflow_result)

            return workflow_result

        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            error_result = WorkflowResult(
                workflow_id=workflow_id,
                success=False,
                total_time_ms=processing_time,
                fallback_triggered=self._enable_fallback,
                fallback_reason=f"Workflow execution error: {str(e)}",
                timestamp=time.time(),
            )
            self._workflow_history.append(error_result)
            self._log_workflow(error_result)
            return error_result

    def execute_with_fallback(self, task_input: Any) -> WorkflowResult:
        """
        执行带有降级机制的工作流

        主路径：使用LNN模型进行任务处理
        降级路径：当LNN模型不可用或置信度低于阈值时，自动切换至传统规则引擎

        Args:
            task_input: 任务输入

        Returns:
            WorkflowResult 工作流执行结果
        """
        workflow_id = (
            f"wf_fb_{datetime.now().strftime('%Y%m%d%H%M%S')}_{id(task_input) % 10000}"
        )

        # 检查LNN是否可用
        if not self._is_lnn_available():
            return self._execute_fallback_path(
                workflow_id, task_input, "LNN not available"
            )

        try:
            # 尝试主路径：LNN推理
            result = self.execute_workflow(task_input)

            # 检查置信度
            confidence = self._extract_confidence(result)
            if confidence < self._fallback_threshold:
                reason = f"Low confidence ({confidence:.3f} < {self._fallback_threshold:.3f})"
                return self._execute_fallback_path(workflow_id, task_input, reason)

            return result

        except Exception as e:
            return self._execute_fallback_path(
                workflow_id, task_input, f"LNN execution failed: {str(e)}"
            )

    def _preprocess_input(self, user_input: Any) -> TaskInput:
        """
        预处理用户输入，转换为标准TaskInput格式

        Args:
            user_input: 用户原始输入

        Returns:
            TaskInput 标准化任务输入
        """
        if isinstance(user_input, TaskInput):
            return user_input

        if isinstance(user_input, str):
            return TaskInput(
                task_description=user_input,
                input_data=user_input,
                task_category=self._infer_task_category(user_input),
                data_type=DataType.UNSTRUCTURED,
            )

        if isinstance(user_input, dict):
            description = user_input.get(
                "task_description", user_input.get("description", "")
            )
            input_data = user_input.get("input_data", user_input)
            return TaskInput(
                task_description=description,
                input_data=input_data,
                context=user_input.get("context"),
                task_category=user_input.get("task_category"),
                data_type=user_input.get("data_type", DataType.STRUCTURED),
                precision_requirement=user_input.get("precision_requirement", 0.9),
                time_sensitivity=user_input.get("time_sensitivity", 0.5),
                max_latency_ms=user_input.get("max_latency_ms", 1000),
            )

        return TaskInput(
            task_description=f"Process input data of type {type(user_input).__name__}",
            input_data=user_input,
            data_type=DataType.STRUCTURED,
        )

    def _generate_execution_plan(
        self,
        workflow_id: str,
        task: TaskInput,
        routing_decision: RoutingDecision,
    ) -> WorkflowExecutionPlan:
        """
        根据输入内容和路由决策生成工作流执行计划

        Args:
            workflow_id: 工作流ID
            task: 任务输入
            routing_decision: 路由决策结果

        Returns:
            WorkflowExecutionPlan 执行计划
        """
        steps = []

        # 步骤1：数据预处理
        steps.append(
            WorkflowStep(
                name="preprocess",
                step_type="data_preprocessing",
                output_key="preprocessed_data",
                timeout_ms=1000,
            )
        )

        # 步骤2：模型推理（根据路由决策选择模型）
        model_name = routing_decision.selected_model or "CFC-Fast"
        steps.append(
            WorkflowStep(
                name="lnn_inference",
                step_type="lnn_inference",
                model_name=model_name,
                input_mapping={"data": "preprocessed_data"},
                output_key="inference_result",
                timeout_ms=self.config.get("workflow", "timeout_seconds", 300) * 1000,
                retry_count=self.config.get("lnn", "max_retry_count", 3),
            )
        )

        # 步骤3：后处理与结果验证
        steps.append(
            WorkflowStep(
                name="postprocess",
                step_type="result_postprocessing",
                input_mapping={"result": "inference_result"},
                output_key="final_result",
                timeout_ms=1000,
            )
        )

        # 检查步骤数限制
        if len(steps) > self._max_steps:
            steps = steps[: self._max_steps]

        return WorkflowExecutionPlan(
            workflow_id=workflow_id,
            steps=steps,
            selected_model=model_name,
            routing_decision=routing_decision,
            created_at=time.time(),
            total_steps=len(steps),
        )

    def _execute_plan(
        self,
        plan: WorkflowExecutionPlan,
        task: TaskInput,
    ) -> WorkflowResult:
        """
        执行工作流计划

        Args:
            plan: 执行计划
            task: 任务输入

        Returns:
            WorkflowResult 执行结果
        """
        plan.status = WorkflowStepStatus.RUNNING
        step_results = []
        context: Dict[str, Any] = {}
        all_success = True

        for step in plan.steps:
            step.status = WorkflowStepStatus.RUNNING
            step.started_at = time.perf_counter()

            try:
                if step.step_type == "data_preprocessing":
                    step.result = self._execute_preprocessing_step(task, context)

                elif step.step_type == "lnn_inference":
                    step.result = self._execute_inference_step(step, task, context)

                elif step.step_type == "result_postprocessing":
                    step.result = self._execute_postprocessing_step(step, task, context)

                step.status = WorkflowStepStatus.COMPLETED
                context[step.output_key] = step.result

            except Exception as e:
                step.status = WorkflowStepStatus.FAILED
                step.error = str(e)
                all_success = False

                if step.on_failure == "fallback" and self._enable_fallback:
                    step.status = WorkflowStepStatus.FALLBACK
                    step.result = self._execute_fallback_step(step, task, context)
                    context[step.output_key] = step.result
                    all_success = True
                else:
                    break

            finally:
                step.completed_at = time.perf_counter()
                step.execution_time_ms = (step.completed_at - step.started_at) * 1000
                step_results.append(
                    {
                        "name": step.name,
                        "status": step.status.value,
                        "execution_time_ms": step.execution_time_ms,
                        "error": step.error,
                    }
                )

            plan.completed_steps += 1

        plan.status = (
            WorkflowStepStatus.COMPLETED if all_success else WorkflowStepStatus.FAILED
        )

        final_output = context.get("final_result", context.get("inference_result"))

        return WorkflowResult(
            workflow_id=plan.workflow_id,
            success=all_success,
            output={"result": final_output, "context": context},
            execution_plan=plan,
            steps_result=step_results,
            fallback_triggered=any(s["status"] == "fallback" for s in step_results),
        )

    def _execute_preprocessing_step(
        self, task: TaskInput, context: Dict[str, Any]
    ) -> Any:
        """执行数据预处理步骤"""
        input_array = self._prepare_input_array(task.input_data)
        preprocessor = DataPreprocessor()
        return preprocessor.fit_transform(input_array)

    def _execute_inference_step(
        self, step: WorkflowStep, task: TaskInput, context: Dict[str, Any]
    ) -> Any:
        """执行LNN推理步骤"""
        max_retries = step.retry_count + 1
        last_error = None

        for attempt in range(max_retries):
            try:
                result = self.engine.infer(
                    task_description=task.task_description,
                    input_data=task.input_data,
                    context=task.context,
                    precision_requirement=task.precision_requirement,
                    time_sensitivity=task.time_sensitivity,
                    max_latency_ms=task.max_latency_ms,
                )
                return result

            except Exception as e:
                last_error = e
                if attempt < max_retries - 1:
                    logger.warning(
                        f"Inference attempt {attempt + 1}/{max_retries} failed: {e}"
                    )
                    time.sleep(0.1 * (attempt + 1))

        raise RuntimeError(
            f"工作流推理失败：已连续尝试 {max_retries} 次但全部失败。最后错误: {last_error}。可能原因：1) 模型推理服务不可用；2) 输入数据不符合模型要求；3) 系统资源不足。请检查推理日志，确认模型和输入数据状态后重试。"
        )

    def _execute_postprocessing_step(
        self, step: WorkflowStep, task: TaskInput, context: Dict[str, Any]
    ) -> Any:
        """执行后处理步骤"""
        inference_result = context.get("inference_result")
        if inference_result is None:
            return {"status": "no_inference_result"}

        if isinstance(inference_result, (InferenceResult, FusionResult)):
            return {
                "prediction": inference_result.prediction
                if hasattr(inference_result, "prediction")
                else inference_result.final_prediction,
                "confidence": inference_result.confidence,
                "metadata": inference_result.metadata
                if hasattr(inference_result, "metadata")
                else {},
            }

        return {"raw_result": inference_result}

    def _execute_fallback_step(
        self, step: WorkflowStep, task: TaskInput, context: Dict[str, Any]
    ) -> Any:
        """执行降级步骤"""
        if self._fallback_strategy == FallbackStrategy.RULE_ENGINE:
            return self.engine._rule_inference(
                task,
                RoutingDecision(
                    selected_engine=EngineType.RULE,
                    confidence=0.5,
                    reasoning="Fallback to rule engine",
                ),
            )

        elif self._fallback_strategy == FallbackStrategy.DEFAULT_OUTPUT:
            return {"fallback": True, "default_output": "No result available"}

        elif self._fallback_strategy == FallbackStrategy.CACHED_RESULT:
            cache_key = str(hash(task.task_description))
            return self._result_cache.get(
                cache_key, {"fallback": True, "cache_miss": True}
            )

        return {"fallback": True, "strategy": self._fallback_strategy.value}

    def _execute_fallback_path(
        self, workflow_id: str, task_input: Any, reason: str
    ) -> WorkflowResult:
        """执行降级路径"""
        start_time = time.perf_counter()

        try:
            task = self._preprocess_input(task_input)

            if self._fallback_strategy == FallbackStrategy.RULE_ENGINE:
                result = self.engine._rule_inference(
                    task,
                    RoutingDecision(
                        selected_engine=EngineType.RULE,
                        confidence=0.5,
                        reasoning=f"Fallback: {reason}",
                    ),
                )
                output = {
                    "prediction": result.prediction,
                    "confidence": result.confidence,
                }
            else:
                output = {"fallback_reason": reason, "status": "fallback_triggered"}

            processing_time = (time.perf_counter() - start_time) * 1000

            return WorkflowResult(
                workflow_id=workflow_id,
                success=True,
                output=output,
                total_time_ms=processing_time,
                fallback_triggered=True,
                fallback_reason=reason,
                timestamp=time.time(),
            )

        except Exception as e:
            processing_time = (time.perf_counter() - start_time) * 1000
            return WorkflowResult(
                workflow_id=workflow_id,
                success=False,
                total_time_ms=processing_time,
                fallback_triggered=True,
                fallback_reason=f"Fallback also failed: {str(e)}",
                timestamp=time.time(),
            )

    def _is_lnn_available(self) -> bool:
        """检查LNN是否可用"""
        if not self.config.get("lnn", "enabled", True):
            return False

        if not self.engine.lnn_models:
            try:
                self.engine.initialize_models()
            except Exception:
                return False

        return len(self.engine.lnn_models) > 0

    def _extract_confidence(self, result: WorkflowResult) -> float:
        """从工作流结果中提取置信度"""
        output = result.output
        if isinstance(output, dict):
            context = output.get("context", {})
            inference_result = context.get("inference_result")
            if inference_result and hasattr(inference_result, "confidence"):
                return inference_result.confidence

        return 1.0

    def _infer_task_category(self, description: str) -> TaskCategory:
        """根据描述推断任务类别"""
        desc_lower = description.lower()

        temporal_keywords = ["predict", "forecast", "trend", "时间序列", "预测"]
        rule_keywords = ["rule", "check", "validate", "规则", "验证", "检查"]
        nlp_keywords = ["explain", "summarize", "翻译", "解释", "分析"]

        if any(kw in desc_lower for kw in temporal_keywords):
            return TaskCategory.TIME_SERIES
        if any(kw in desc_lower for kw in rule_keywords):
            return TaskCategory.RULE_BASED
        if any(kw in desc_lower for kw in nlp_keywords):
            return TaskCategory.NLP

        return TaskCategory.REGRESSION

    def _prepare_input_array(self, input_data: Any) -> np.ndarray:
        """将输入数据转换为numpy数组"""
        if isinstance(input_data, np.ndarray):
            return input_data
        elif isinstance(input_data, dict):
            return DataPreprocessor.extract_numeric_features(input_data)
        elif isinstance(input_data, (list, tuple)):
            return np.array(input_data)
        elif HAS_TORCH and isinstance(input_data, torch.Tensor):
            return input_data.detach().cpu().numpy()
        else:
            return np.array([input_data])

    def _log_workflow(self, result: WorkflowResult) -> None:
        """记录工作流执行日志"""
        if not self._log_enabled:
            return

        try:
            os.makedirs(self._log_dir, exist_ok=True)
            log_file = os.path.join(
                self._log_dir, f"workflow_{datetime.now().strftime('%Y-%m-%d')}.jsonl"
            )

            log_entry = result.to_dict()
            with open(log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        except Exception as e:
            logger.error(f"Failed to log workflow: {e}")

    def get_workflow_history(self, limit: int = 100) -> List[WorkflowResult]:
        """获取工作流执行历史"""
        return self._workflow_history[-limit:]

    def get_statistics(self) -> Dict[str, Any]:
        """获取编排器统计信息"""
        total_workflows = len(self._workflow_history)
        successful = sum(1 for wf in self._workflow_history if wf.success)
        fallback_count = sum(
            1 for wf in self._workflow_history if wf.fallback_triggered
        )

        avg_time = (
            sum(wf.total_time_ms for wf in self._workflow_history) / total_workflows
            if total_workflows > 0
            else 0.0
        )

        return {
            "total_workflows": total_workflows,
            "successful_workflows": successful,
            "failed_workflows": total_workflows - successful,
            "fallback_count": fallback_count,
            "success_rate": successful / total_workflows
            if total_workflows > 0
            else 0.0,
            "avg_execution_time_ms": avg_time,
            "engine_stats": self.engine.get_engine_stats(),
        }

    def update_config(self, section: str, key: str, value: Any) -> None:
        """
        运行时更新配置

        Args:
            section: 配置节
            key: 配置键
            value: 新值
        """
        self.config.set(section, key, value)

        if section == "lnn" and key == "thresholds.fallback":
            self._fallback_threshold = value
        elif section == "workflow" and key == "max_steps":
            self._max_steps = value
        elif section == "workflow" and key == "timeout_seconds":
            self._timeout_seconds = value
        elif section == "workflow" and key == "enable_fallback":
            self._enable_fallback = value
        elif section == "workflow" and key == "fallback_strategy":
            self._fallback_strategy = FallbackStrategy(value)

    def save_config(self, output_path: Optional[str] = None) -> None:
        """保存配置到文件"""
        self.config.save(output_path)

    def set_fallback_strategy(self, strategy: FallbackStrategy) -> None:
        """设置降级策略"""
        self._fallback_strategy = strategy
