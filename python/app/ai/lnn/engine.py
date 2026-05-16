"""
Hybrid Inference Engine

Main orchestrator that integrates TaskRouter, LNN engines, LLM engine, Rule engine,
and the Result Fusion Layer to provide a unified inference interface.
"""

import logging
import numpy as np
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Union

from .core import (
    EngineType,
    ModelType,
    TaskInput,
    RoutingDecision,
    InferenceResult,
    FusionResult,
)
from .models.cfc_model import CFCModel
from .models.ltc_model import LTCModel
from .models.hybrid_lnn import HybridLNNModel
from .router.task_router import TaskRouter
from .fusion import DempsterShaferFusion
from .preprocessing import DataPreprocessor
from .postprocessing import ResultPostprocessor
from .inference.registry import ModelRegistry
from .config.config_manager import YAMLConfigManager

logger = logging.getLogger(__name__)


@dataclass
class EngineConfig:
    """推理引擎配置类

    用于组织 HybridInferenceEngine 的配置参数，减少构造函数参数数量。

    Args:
        rule_weight: 规则决策权重 (默认 0.4)
        ml_weight: ML决策权重 (默认 0.6)
        enable_fusion: 是否启用结果融合 (默认 True)
        enable_parallel_execution: 是否启用并行执行 (默认 False)
        cache_size: 模型缓存大小 (默认 10)
        device: 计算设备 (默认 "cpu")
        max_retry: 最大重试次数 (默认 2)
        config_path: YAML配置文件路径 (可选)
        config: 已有的配置管理器实例 (可选)
    """

    rule_weight: float = 0.4
    ml_weight: float = 0.6
    enable_fusion: bool = True
    enable_parallel_execution: bool = False
    cache_size: int = 10
    device: str = "cpu"
    max_retry: int = 2
    config_path: Optional[str] = None
    config: Optional[YAMLConfigManager] = None

    @classmethod
    def from_dict(cls, config_dict: Dict[str, Any]) -> "EngineConfig":
        """从字典创建配置实例"""
        valid_fields = {f.name for f in cls.__dataclass_fields__.values()}
        filtered = {k: v for k, v in config_dict.items() if k in valid_fields}
        return cls(**filtered)

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        from dataclasses import asdict

        return asdict(self)


class HybridInferenceEngine:
    """
    混合推理引擎

    整合所有核心组件，提供统一的推理接口

    数据流：
    用户输入 -> 任务解析 -> 路由器决策 -> 引擎选择 -> 并行/串行执行 ->
    结果收集 -> 融合层处理 -> 最终输出
    """

    def __init__(self, config: Optional[EngineConfig] = None):
        """
        初始化混合推理引擎

        Args:
            config: 引擎配置对象，为 None 时使用默认配置
        """
        if config is None:
            config = EngineConfig()

        self.enable_fusion = config.enable_fusion
        self.enable_parallel_execution = config.enable_parallel_execution
        self.device = config.device
        self.max_retry = config.max_retry

        # 配置管理
        if config.config:
            self.config = config.config
        elif config.config_path:
            self.config = YAMLConfigManager(config_path=config.config_path)
        else:
            self.config = YAMLConfigManager()

        # 核心组件
        self.router = TaskRouter(
            rule_weight=config.rule_weight, ml_weight=config.ml_weight
        )
        self.fusion = DempsterShaferFusion()
        self.registry = ModelRegistry(cache_size=config.cache_size)
        self.preprocessor = DataPreprocessor()
        self.postprocessor = ResultPostprocessor()

        # 引擎实例
        self.lnn_models: Dict[str, Any] = {}
        self.rule_engine: Optional[Any] = None
        self._initialized = False
        self._degraded_mode = False

        # 统计
        self.inference_count = 0
        self.total_processing_time = 0.0

    def initialize_models(self) -> None:
        """初始化所有LNN模型并注册"""
        # 防止重复初始化
        if self._initialized:
            logger.warning("引擎已初始化，跳过重复初始化")
            return

        # 注册CFC模型
        try:
            cfc_cfg = self.config.get_model_config("cfc_fast")
            if cfc_cfg and cfc_cfg.enabled:
                cfc = CFCModel(
                    model_name="CFC-Fast",
                    input_dim=cfc_cfg.input_dim,
                    output_dim=cfc_cfg.output_dim,
                    hidden_dim=cfc_cfg.hidden_dim,
                    device=cfc_cfg.device,
                )
                cfc.build()
                self.lnn_models["CFC-Fast"] = cfc
                self.registry.register("CFC-Fast", ModelType.CFC)
        except Exception as e:
            logger.error(f"CFC模型初始化失败: {e}")

        # 注册LTC模型
        try:
            ltc_cfg = self.config.get_model_config("ltc_timeseries")
            if ltc_cfg and ltc_cfg.enabled:
                ltc = LTCModel(
                    model_name="LTC-TimeSeries",
                    input_dim=ltc_cfg.input_dim,
                    output_dim=ltc_cfg.output_dim,
                    hidden_dim=ltc_cfg.hidden_dim,
                    temporal_horizon=ltc_cfg.temporal_horizon,
                    device=ltc_cfg.device,
                )
                ltc.build()
                self.lnn_models["LTC-TimeSeries"] = ltc
                self.registry.register("LTC-TimeSeries", ModelType.LTC)
        except Exception as e:
            logger.error(f"LTC模型初始化失败: {e}")

        # 注册Hybrid模型
        try:
            hybrid_cfg = self.config.get_model_config("hybrid_multimodal")
            if hybrid_cfg and hybrid_cfg.enabled:
                hybrid = HybridLNNModel(
                    model_name="Hybrid-Multimodal",
                    input_dim=hybrid_cfg.input_dim,
                    output_dim=hybrid_cfg.output_dim,
                    device=hybrid_cfg.device,
                )
                hybrid.build()
                self.lnn_models["Hybrid-Multimodal"] = hybrid
                self.registry.register("Hybrid-Multimodal", ModelType.HYBRID_LNN)
        except Exception as e:
            logger.error(f"Hybrid模型初始化失败: {e}")

        # 验证初始化结果并提供降级策略
        if not self.lnn_models:
            logger.warning("无可用LNN模型，启用规则引擎降级模式")
            self._degraded_mode = True
        else:
            self._degraded_mode = False
            logger.info(f"引擎初始化完成，已注册 {len(self.lnn_models)} 个模型")

        self._initialized = True

    def infer(
        self,
        task_description: str,
        input_data: Any,
        context: Optional[Dict[str, Any]] = None,
        precision_requirement: float = 0.9,
        time_sensitivity: float = 0.5,
        max_latency_ms: int = 1000,
    ) -> Union[FusionResult, InferenceResult]:
        """
        主推理接口

        Args:
            task_description: 任务描述文本
            input_data: 输入数据
            context: 上下文信息
            precision_requirement: 精度要求
            time_sensitivity: 时间敏感性
            max_latency_ms: 最大延迟要求

        Returns:
            FusionResult 或 InferenceResult
        """
        start_time = time.perf_counter()

        # 1. 任务解析与标准化
        task_input = TaskInput(
            task_description=task_description,
            input_data=input_data,
            context=context,
            precision_requirement=precision_requirement,
            time_sensitivity=time_sensitivity,
            max_latency_ms=max_latency_ms,
        )

        # 2. 路由器决策
        routing_decision = self.router.route(task_input)

        # 3. 推理引擎选择与调用
        results = self._execute_inference(task_input, routing_decision)

        # 4. 结果处理
        if len(results) > 1 and self.enable_fusion:
            # 多引擎结果融合
            final_result = self.fusion.fuse(results)
        else:
            # 单引擎结果
            if not results:
                final_result = InferenceResult(
                    prediction=None,
                    confidence=0.0,
                    metadata={"error": "No engine available"},
                )
            else:
                final_result = results[0]

        # 5. 更新统计
        processing_time = (time.perf_counter() - start_time) * 1000
        self.inference_count += 1
        self.total_processing_time += processing_time

        return final_result

    def infer_batch(
        self,
        tasks: List[Dict[str, Any]],
        batch_size: int = 32,
    ) -> List[Union[FusionResult, InferenceResult]]:
        """
        批量推理

        Args:
            tasks: 任务列表，每个任务包含task_description和input_data
            batch_size: 批次大小

        Returns:
            推理结果列表
        """
        # 按批次分组
        batches = [tasks[i : i + batch_size] for i in range(0, len(tasks), batch_size)]
        results = []

        for batch in batches:
            # 批量预处理
            batch_inputs = [self._prepare_input(t["input_data"]) for t in batch]
            batch_descriptions = [t["task_description"] for t in batch]

            # 批量推理
            batch_results = self._batch_inference(
                batch_inputs, batch_descriptions, batch
            )
            results.extend(batch_results)

        return results

    def _batch_inference(
        self,
        batch_inputs: List[np.ndarray],
        batch_descriptions: List[str],
        batch_tasks: List[Dict[str, Any]],
    ) -> List[Union[FusionResult, InferenceResult]]:
        """
        批量推理执行

        Args:
            batch_inputs: 批量输入数据
            batch_descriptions: 批量任务描述
            batch_tasks: 原始任务列表

        Returns:
            批量推理结果
        """
        results = []
        for inputs, description, task in zip(
            batch_inputs, batch_descriptions, batch_tasks
        ):
            task_input = TaskInput(
                task_description=description,
                input_data=inputs,
                context=task.get("context"),
            )
            routing_decision = self.router.route(task_input)
            inference_results = self._execute_inference(task_input, routing_decision)

            if len(inference_results) > 1 and self.enable_fusion:
                final_result = self.fusion.fuse(inference_results)
            elif inference_results:
                final_result = inference_results[0]
            else:
                final_result = InferenceResult(
                    prediction=None,
                    confidence=0.0,
                    metadata={"error": "No engine available"},
                )

            results.append(final_result)

        return results

    def _execute_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
    ) -> List[InferenceResult]:
        """
        执行推理

        Args:
            task: 任务输入
            decision: 路由决策

        Returns:
            推理结果列表
        """
        results = []

        if (
            self.enable_parallel_execution
            and decision.selected_engine == EngineType.HYBRID
        ):
            # 并行执行多个引擎
            results = self._parallel_inference(task, decision)
        else:
            # 串行执行
            result = self._single_inference(task, decision)
            if result:
                results.append(result)

        return results

    def _single_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
    ) -> Optional[InferenceResult]:
        """单引擎推理"""
        engine = decision.selected_engine

        if engine == EngineType.LNN:
            return self._lnn_inference(task, decision)
        elif engine == EngineType.LLM:
            return self._llm_inference(task, decision)
        elif engine == EngineType.RULE:
            return self._rule_inference(task, decision)
        elif engine == EngineType.HYBRID:
            return self._hybrid_inference(task, decision)

        return None

    def _parallel_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
    ) -> List[InferenceResult]:
        """并行推理 - 使用ThreadPoolExecutor实现多线程并行执行"""
        import concurrent.futures

        results = []

        # 根据决策类型构建并行任务列表
        parallel_engines = []
        if decision.selected_engine == EngineType.HYBRID:
            # 混合模式：并行执行LNN和规则引擎
            parallel_engines = [
                (EngineType.LNN, self._lnn_inference),
                (EngineType.RULE, self._rule_inference),
            ]
        else:
            # 其他引擎类型也可并行多个备选方案
            parallel_engines = [
                (decision.selected_engine, self._single_inference),
            ]

        with concurrent.futures.ThreadPoolExecutor(
            max_workers=len(parallel_engines)
        ) as executor:
            future_to_engine = {
                executor.submit(engine_func, task, decision): engine_type
                for engine_type, engine_func in parallel_engines
            }

            for future in concurrent.futures.as_completed(future_to_engine):
                try:
                    result = future.result(timeout=30)
                    if result:
                        results.append(result)
                except Exception as e:
                    engine_type = future_to_engine[future]
                    logger.error(f"并行推理失败 ({engine_type}): {e}")

        return results

    def _lnn_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
        retry_count: int = 0,
    ) -> Optional[InferenceResult]:
        return self._model_inference(task, decision, EngineType.LNN, retry_count)

    def _hybrid_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
    ) -> Optional[InferenceResult]:
        return self._model_inference(task, decision, EngineType.HYBRID)

    def _model_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
        engine_type: EngineType,
        retry_count: int = 0,
    ) -> Optional[InferenceResult]:
        start_time = time.perf_counter()
        default_models = {
            EngineType.LNN: "CFC-Fast",
            EngineType.HYBRID: "Hybrid-Multimodal",
        }
        default_model = default_models.get(engine_type, "CFC-Fast")
        model_name = decision.selected_model or default_model
        model = self.lnn_models.get(model_name) or self.lnn_models.get(default_model)

        if model is None:
            logger.error("%s推理失败: 无可用模型", engine_type.value)
            return None

        def _build_error_result(
            error: Exception, extra_meta: dict | None = None
        ) -> InferenceResult:
            pt = (time.perf_counter() - start_time) * 1000
            meta: dict = {"error": str(error), "error_type": type(error).__name__}
            if extra_meta:
                meta.update(extra_meta)
            return InferenceResult(
                prediction=None,
                confidence=0.0,
                engine_used=engine_type,
                processing_time_ms=pt,
                metadata=meta,
            )

        try:
            input_array = self._prepare_input(task.input_data)
            preprocessed = (
                self.preprocessor.fit_transform(input_array)
                if not self.preprocessor.is_fitted
                else self.preprocessor.transform(input_array)
            )
            predictions = model.predict(preprocessed.features)
            processing_time = (time.perf_counter() - start_time) * 1000
            return self.postprocessor.process_result(
                predictions=predictions,
                engine=engine_type,
                model_name=model_name,
                processing_time_ms=processing_time,
            )
        except (ValueError, TypeError) as e:
            logger.error("%s推理失败（数据错误）: %s", engine_type.value, e)
            return _build_error_result(e)
        except (RuntimeError, MemoryError) as e:
            logger.error("%s推理失败（运行时错误）: %s", engine_type.value, e)
            if retry_count < self.max_retry:
                logger.info(
                    "%s推理重试: %s/%s",
                    engine_type.value,
                    retry_count + 1,
                    self.max_retry,
                )
                return self._model_inference(
                    task, decision, engine_type, retry_count + 1
                )
            return _build_error_result(
                e, {"retry_count": retry_count, "max_retry": self.max_retry}
            )
        except Exception as e:
            logger.error(
                "%s推理失败（未知错误）: %s", engine_type.value, e, exc_info=True
            )
            return _build_error_result(e)

    def _llm_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
    ) -> Optional[InferenceResult]:
        """LLM引擎推理（模拟实现）"""
        start_time = time.perf_counter()

        try:
            # 模拟LLM推理结果
            # 实际应用中应调用真实LLM API
            mock_prediction = np.array([0.8, 0.15, 0.05])

            processing_time = (time.perf_counter() - start_time) * 1000
            result = self.postprocessor.process_result(
                predictions=mock_prediction,
                engine=EngineType.LLM,
                model_name="LLM-GPT",
                processing_time_ms=processing_time,
            )

            return result

        except Exception as e:
            return InferenceResult(
                prediction=None,
                confidence=0.0,
                engine_used=EngineType.LLM,
                metadata={"error": str(e)},
            )

    def _rule_inference(
        self,
        task: TaskInput,
        decision: RoutingDecision,
    ) -> Optional[InferenceResult]:
        """规则引擎推理（简化实现）"""
        start_time = time.perf_counter()

        try:
            # 简单规则匹配（实际应用应使用规则引擎框架）
            description = task.task_description.lower()

            if "urgent" in description or "紧急" in description:
                mock_prediction = np.array([0.9, 0.1])
            else:
                mock_prediction = np.array([0.5, 0.5])

            processing_time = (time.perf_counter() - start_time) * 1000
            result = self.postprocessor.process_result(
                predictions=mock_prediction,
                engine=EngineType.RULE,
                model_name="RuleEngine-v1",
                processing_time_ms=processing_time,
            )

            return result

        except Exception as e:
            return InferenceResult(
                prediction=None,
                confidence=0.0,
                engine_used=EngineType.RULE,
                metadata={"error": str(e)},
            )

    def _prepare_input(self, input_data: Any) -> np.ndarray:
        """准备输入数据"""
        if isinstance(input_data, np.ndarray):
            return input_data
        elif isinstance(input_data, dict):
            return DataPreprocessor.extract_numeric_features(input_data)
        elif isinstance(input_data, (list, tuple)):
            return np.array(input_data)
        else:
            return np.array([input_data])

    def get_engine_stats(self) -> Dict[str, Any]:
        """获取引擎统计信息"""
        return {
            "inference_count": self.inference_count,
            "avg_processing_time_ms": (
                self.total_processing_time / self.inference_count
                if self.inference_count > 0
                else 0
            ),
            "registered_models": self.registry.list_models(),
            "router_stats": self.router.get_decision_stats(),
            "fusion_stats": self.fusion.get_fusion_stats(),
            "cache_stats": self.registry.get_cache_stats(),
        }

    def register_custom_model(
        self,
        model_name: str,
        model_instance: Any,
        model_type: ModelType = ModelType.CFC,
    ) -> None:
        """
        注册自定义模型

        Args:
            model_name: 模型名称
            model_instance: 模型实例
            model_type: 模型类型
        """
        self.lnn_models[model_name] = model_instance
        self.registry.register(model_name, model_type)
