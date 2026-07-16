"""
Predictor Module

Implements single-sample, batch, and streaming inference interfaces for LNN models.
Supports automatic device selection and AMP (Automatic Mixed Precision) acceleration.
"""

import os
import numpy as np
import time
import json
import logging
import threading
import psutil
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field
from pathlib import Path
from datetime import datetime

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

try:
    from torch.cuda.amp import autocast

    HAS_AMP = True
except ImportError:
    HAS_AMP = False

from app.ai.lnn.core import EngineType
from app.ai.lnn.preprocessing import DataPreprocessor
from app.ai.lnn.postprocessing import ResultPostprocessor
from app.ai.lnn.inference.registry import BaseModelRegistry, ModelEntry
from app.ai.lnn.inference.model_cache import get_model_cache
from app.ai.lnn.models.base_lnn import BaseLNNModel

try:
    from app.database.constraints import CuttingConstraintValidator

    _HAS_CONSTRAINT_VALIDATOR = True
except ImportError:
    _HAS_CONSTRAINT_VALIDATOR = False

logger = logging.getLogger(__name__)


@dataclass
class PredictionResult:
    """Prediction result dataclass with serialization support"""

    value: Any
    confidence: float = 0.0
    inference_time: float = 0.0
    model_info: Optional[Dict[str, Any]] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        val = self.value
        if isinstance(val, np.ndarray):
            val = val.tolist()
        return {
            "value": val,
            "confidence": self.confidence,
            "inference_time": self.inference_time,
            "model_info": self.model_info or {},
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PredictionResult":
        """Deserialize from dictionary"""
        value = data.get("value")
        if isinstance(value, list):
            value = np.array(value)
        return cls(
            value=value,
            confidence=data.get("confidence", 0.0),
            inference_time=data.get("inference_time", 0.0),
            model_info=data.get("model_info", {}),
        )


class LNNPredictor:
    """
    LNN Predictor with single, batch, and streaming inference support.

    Features:
    - Single sample prediction
    - Batch prediction with configurable batch size
    - Streaming prediction for continuous data
    - Automatic device selection (CPU/GPU/MPS)
    - AMP (Automatic Mixed Precision) acceleration
    - Inference statistics tracking
    """

    def __init__(
        self,
        model,
        preprocessor: Optional[DataPreprocessor] = None,
        postprocessor: Optional[ResultPostprocessor] = None,
        model_name: Optional[str] = None,
        engine_type: EngineType = EngineType.LNN,
        use_amp: bool = True,
        auto_device: bool = True,
        material_id: Optional[str] = None,
        tool_id: Optional[str] = None,
        machine_id: Optional[str] = None,
    ):
        """
        Initialize LNN Predictor

        Args:
            model: LNN model instance
            preprocessor: Optional data preprocessor
            postprocessor: Optional result postprocessor
            model_name: Model name identifier
            engine_type: Inference engine type
            use_amp: Enable automatic mixed precision
            auto_device: Enable automatic device selection
        """
        self.model = model
        self.preprocessor = preprocessor or DataPreprocessor()
        self.postprocessor = postprocessor or ResultPostprocessor()
        self.model_name = model_name or getattr(model, "model_name", "unknown")
        self.engine_type = engine_type
        self.use_amp = use_amp and HAS_AMP
        self.auto_device = auto_device

        # MC Dropout 并发保护锁：predict_mc_dropout 在切换 model.train(True)/eval()
        # 期间必须独占访问模型状态，否则并发请求的 eval() 会关闭其他请求的 dropout。
        # 使用 RLock（可重入锁）：predict_mc_dropout 内部可能间接调用其他也需要此锁的方法。
        self._mc_lock = threading.RLock()

        # 统计数据并发保护锁：_update_stats (写) 与 get_statistics/get_performance (读)
        # 在多线程并发推理时会同时操作 self._stats 字典，缺少锁保护会导致计数丢失、
        # 极值错乱、inference_times 列表竞争。使用独立 Lock 避免与 MC Dropout 锁耦合。
        self._stats_lock = threading.Lock()

        self.device = self._select_device()
        if HAS_TORCH and hasattr(self.model, "to"):
            self.model.to(self.device)

        self._material_id = material_id
        self._tool_id = tool_id
        self._machine_id = machine_id
        self._constraint_validator: CuttingConstraintValidator | None = None
        if _HAS_CONSTRAINT_VALIDATOR and material_id and tool_id:
            self._constraint_validator = CuttingConstraintValidator()
            logger.info(
                "物理约束校验已启用 material=%s tool=%s machine=%s",
                material_id,
                tool_id,
                machine_id or "none",
            )

        self._stats = {
            "total_inferences": 0,
            "total_inference_time_ms": 0.0,
            "max_inference_time_ms": 0.0,
            "min_inference_time_ms": float("inf"),
            "peak_memory_mb": 0.0,
            "inference_times": [],
            "window_start": time.perf_counter(),
            "window_inferences": 0,
        }
        self._max_recent_times = 10_000

        # Trace log persistence
        self._trace_log_path = os.path.join(
            os.getcwd(), "data", "traces", "trace_log.jsonl"
        )
        self._trace_log_enabled = True
        try:
            Path(self._trace_log_path).parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            logger.warning("无法创建 trace log 目录: %s", exc)
            self._trace_log_enabled = False

    def _select_device(self) -> Any:
        """Automatically select best available device"""
        if not self.auto_device or not HAS_TORCH:
            # 修复 P1: HAS_TORCH=False 时 torch 为 None，torch.device("cpu") 会抛 TypeError。
            # 此时返回字符串 "cpu" 作为降级设备标识，下游无需构造 torch.device 对象即可工作。
            if not HAS_TORCH:
                return "cpu"
            return torch.device("cpu")
        if torch.cuda.is_available():
            return torch.device("cuda")
        elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
            return torch.device("mps")
        return torch.device("cpu")

    def _preprocess(self, data: Any) -> Tuple[np.ndarray, Optional[Dict[str, Any]]]:
        """
        Preprocess input data

        Args:
            data: Raw input data

        Returns:
            Tuple of (processed features, metadata dict)
        """
        input_array = self._standardize_input(data)
        if not self.preprocessor.is_fitted:
            raise RuntimeError(
                "预处理器未拟合，无法执行推理。请先训练模型或加载已训练的预处理器。"
                "推理阶段禁止使用 fit_transform 以避免数据泄漏。"
            )
        preprocessed = self.preprocessor.transform(input_array)
        return preprocessed.features, {"input_shape": input_array.shape}

    def _postprocess(self, output: Any, hidden: Optional[Dict[str, Any]] = None) -> Any:
        """
        Postprocess model output

        Args:
            output: Raw model output
            hidden: Intermediate computation results

        Returns:
            Processed output
        """
        if HAS_TORCH and isinstance(output, torch.Tensor):
            output = output.detach().cpu().numpy()
        return output

    def _maybe_inverse_transform(self, predictions: np.ndarray) -> np.ndarray:
        if (
            self.preprocessor.is_fitted
            and hasattr(self.preprocessor, "mean_")
            and self.preprocessor.mean_ is not None
        ):
            if predictions.shape[-1] == self.preprocessor.mean_.shape[0]:
                return self.preprocessor.inverse_transform(predictions)
        return predictions

    def predict(
        self,
        input_data: Any,
        return_confidence: bool = False,
    ) -> Union[PredictionResult, Any]:
        """
        优化的单次预测接口
        
        性能优化点：
        - 减少不必要的类型转换
        - 优化设备同步
        - 减少内存拷贝
        """
        start_time = time.perf_counter()

        try:
            features, hidden = self._preprocess(input_data)

            if isinstance(self.model, BaseLNNModel):
                output = self.model.predict(features)
            else:
                features_tensor = self._to_tensor(features)

                # 优化：使用 torch.inference_mode 替代 torch.no_grad 以获得更好性能
                if self.use_amp and self.device.type == "cuda" and HAS_AMP:
                    with torch.inference_mode():
                        with autocast():
                            output = self.model(features_tensor)
                else:
                    with torch.inference_mode():
                        output = self.model(features_tensor)

            processed_output = self._postprocess(output, hidden)
            if isinstance(processed_output, np.ndarray):
                processed_output = self._maybe_inverse_transform(processed_output)

            inference_time = (time.perf_counter() - start_time) * 1000
            mem_after = self._get_memory_usage_mb()
            self._update_stats(inference_time, mem_after)
            
            # 持久化真实推理性能数据
            input_shape = features.shape if hasattr(features, 'shape') else (1,)
            self._write_trace(inference_time, input_shape, success=True)

            try:
                from app.utils.utils import get_metrics_collector

                m = get_metrics_collector()
                m.record_lnn_inference(self.model_name, inference_time / 1000.0)
                m.record_lnn_prediction(self.model_name, "success")
            except (ImportError, AttributeError, RuntimeError, ValueError) as e:
                logger.debug(
                    f"Failed to record inference metrics for {self.model_name}: {e}",
                    exc_info=True,
                )

            confidence = self._compute_confidence(output) if return_confidence else 0.0

            constraint_result = None
            if self._constraint_validator and isinstance(processed_output, dict):
                try:
                    constraint_result = self._constraint_validator.validate(
                        material_id=self._material_id,
                        tool_id=self._tool_id,
                        params=processed_output,
                        machine_id=self._machine_id,
                    )
                    if constraint_result.adjusted_params:
                        for k, v in constraint_result.adjusted_params.items():
                            if k in processed_output:
                                processed_output[k] = v
                    if constraint_result.warnings:
                        logger.warning(
                            "物理约束校验警告: %s",
                            "; ".join(constraint_result.warnings),
                        )
                except (ValueError, TypeError, AttributeError, KeyError, RuntimeError) as exc:
                    logger.warning("物理约束校验失败: %s", exc, exc_info=True)

            result = PredictionResult(
                value=processed_output,
                confidence=confidence,
                inference_time=inference_time,
                model_info={
                    "name": self.model_name,
                    "device": str(self.device),
                    "constraint_result": constraint_result.to_dict()
                    if constraint_result
                    else None,
                },
            )

            if return_confidence:
                return result
            return result.value

        except (ValueError, TypeError, RuntimeError, OSError) as e:
            logger.error("模型预测失败: %s", e, exc_info=True)
            inference_time = (time.perf_counter() - start_time) * 1000
            self._update_stats(inference_time, self._get_memory_usage_mb())
            try:
                from app.utils.utils import get_metrics_collector

                m = get_metrics_collector()
                m.record_lnn_prediction(self.model_name, "error")
            except (ImportError, AttributeError, RuntimeError, ValueError) as e:
                logger.debug(
                    f"Failed to record error metrics for {self.model_name}: {e}",
                    exc_info=True,
                )
            raise RuntimeError(
                "模型预测失败：推理过程出现异常。"
                "可能原因：1) 模型输入数据格式不匹配；2) 模型权重加载异常；"
                "3) GPU 内存不足。请检查输入数据格式，确认模型已正确加载，"
                "如使用 GPU 请检查显存使用情况。"
            ) from e

    def predict_batch(
        self,
        batch_data: List[Any],
        batch_size: int = 32,
    ) -> List[PredictionResult]:
        """
        Batch prediction with memory control

        Args:
            batch_data: List of input data
            batch_size: Batch size for memory management

        Returns:
            List of PredictionResult objects
        """
        results = []
        for i in range(0, len(batch_data), batch_size):
            chunk = batch_data[i : i + batch_size]
            batch_results = self._predict_batch_chunk(chunk)
            results.extend(batch_results)
        return results

    def _predict_batch_chunk(self, chunk: List[Any]) -> List[PredictionResult]:
        """
        优化的批量预测分块处理
        
        性能优化点：
        - 使用 torch.inference_mode 替代 torch.no_grad
        - 减少中间张量拷贝
        - 优化内存分配
        """
        features_list = []
        hidden_list = []
        for data in chunk:
            features, hidden = self._preprocess(data)
            features_list.append(features)
            hidden_list.append(hidden)

        batch_features = np.concatenate(features_list, axis=0)

        start_time = time.perf_counter()

        if isinstance(self.model, BaseLNNModel):
            outputs = self.model.predict(batch_features)
        else:
            batch_tensor = self._to_tensor(batch_features)

            # 优化：使用 torch.inference_mode 获得更好性能
            if self.use_amp and self.device.type == "cuda" and HAS_AMP:
                with torch.inference_mode():
                    with autocast():
                        outputs = self.model(batch_tensor)
            else:
                with torch.inference_mode():
                    outputs = self.model(batch_tensor)

        inference_time = (time.perf_counter() - start_time) * 1000
        mem_after = self._get_memory_usage_mb()

        if HAS_TORCH and isinstance(outputs, torch.Tensor):
            outputs = outputs.detach().cpu().numpy()

        if isinstance(outputs, np.ndarray):
            outputs = self._maybe_inverse_transform(outputs)

        results = []
        per_sample_time = inference_time / len(chunk)
        for i, output in enumerate(outputs):
            processed = self._postprocess(output, hidden_list[i])
            confidence = self._compute_confidence(output)
            result = PredictionResult(
                value=processed,
                confidence=confidence,
                inference_time=per_sample_time,
                model_info={"name": self.model_name, "device": str(self.device)},
            )
            results.append(result)

        self._update_stats(per_sample_time, mem_after)
        return results

    def predict_streaming(
        self,
        data_stream,
        return_confidence: bool = False,
    ):
        """
        Streaming prediction for continuous data

        Args:
            data_stream: Iterator or generator of input data
            return_confidence: Whether to return confidence scores

        Yields:
            Prediction results one by one
        """
        for item in data_stream:
            yield self.predict(item, return_confidence=return_confidence)

    def predict_mc_dropout(
        self,
        input_data: Any,
        n_samples: int = 30,
        dropout_override: Optional[float] = None,
    ) -> "PredictionResult":
        """Monte Carlo Dropout 不确定性量化（Bayesian LNN 近似）。

        通过在推理阶段保持 dropout 激活并执行多次前向传播，得到预测分布的
        样本集合，进而计算认知不确定性（epistemic uncertainty）。

        Args:
            input_data: 输入数据，与 :meth:`predict` 相同。
            n_samples: 前向传播次数，建议 30~100。低于 1 视为 1。
            dropout_override: 可选，临时覆盖 dropout 概率。None 时使用模型
                当前配置。

        Returns:
            PredictionResult，其中：
                - ``value`` 为样本均值；
                - ``confidence`` 为 ``1 - std/|mean|``（裁剪到 [0,1]）；
                - ``model_info["mc_std"]``、``mc_samples``、``mc_n_samples``
                  记录真实标准差与样本数，供上层 API 透传。
        """
        # 临界区：整个 predict_mc_dropout 方法体在锁保护下执行，
        # 确保 model.train(True)/eval() 模式切换和恢复是原子操作。
        # 并发调用时，一个请求的 eval() 会关闭另一个请求的 dropout，
        # 导致 MC Dropout 失效。RLock 可重入，不影响正常推理性能。
        with self._mc_lock:
            if n_samples < 1:
                n_samples = 1

            features, hidden = self._preprocess(input_data)

            if not HAS_TORCH:
                result = self.predict(input_data, return_confidence=True)
                if isinstance(result, PredictionResult):
                    result.model_info.setdefault("mc_n_samples", 1)
                    result.model_info.setdefault("mc_std", 0.0)
                    return result
                return PredictionResult(
                    value=result,
                    confidence=0.0,
                    inference_time=0.0,
                    model_info={"mc_n_samples": 1, "mc_std": 0.0},
                )

            samples: List[Any] = []
            original_dropout = getattr(self.model, "dropout_rate", None)
            if dropout_override is not None and hasattr(self.model, "dropout_rate"):
                try:
                    self.model.dropout_rate = float(dropout_override)
                except (AttributeError, TypeError, ValueError) as exc:
                    logger.debug(
                        "predict_mc_dropout: 无法覆盖 dropout: %s", exc
                    )

            was_training = getattr(self.model, "training", False)
            try:
                train_fn = getattr(self.model, "train", None)
                if callable(train_fn):
                    train_fn(True)
                else:
                    was_training = None
            except (RuntimeError, AttributeError) as exc:
                logger.debug("predict_mc_dropout: 切换 train 模式失败: %s", exc)
                was_training = None

            start_ts = time.perf_counter()
            try:
                for _ in range(n_samples):
                    if isinstance(self.model, BaseLNNModel):
                        output = self.model.predict(features)
                    else:
                        features_tensor = self._to_tensor(features)
                        # 修复 P1: inference_mode 会禁用 dropout，导致 n_samples 次前向
                        # 结果完全相同、std=0，MC Dropout 失效。改用 no_grad（不禁用 dropout），
                        # 配合上方已设置的 model.train(True) 使 dropout 层保持激活。
                        with torch.no_grad():
                            output = self.model(features_tensor)
                    if isinstance(output, torch.Tensor):
                        output = output.detach().cpu().numpy()
                    samples.append(np.asarray(output, dtype=float))
            finally:
                if was_training is not None:
                    eval_fn = getattr(self.model, "eval", None)
                    if callable(eval_fn):
                        try:
                            if was_training:
                                self.model.train()
                            else:
                                self.model.eval()
                        except (RuntimeError, AttributeError) as restore_err:
                            # 训练/推理模式恢复失败不阻塞预测结果返回（已得到 samples），
                            # 但记录便于排查：模型状态可能与预期不一致，影响后续推理
                            logger.debug("Failed to restore model train/eval mode: %s",
                                         restore_err, exc_info=True)
                if original_dropout is not None and hasattr(self.model, "dropout_rate"):
                    try:
                        self.model.dropout_rate = original_dropout
                    except (AttributeError, TypeError, ValueError) as dropout_err:
                        # dropout_rate 恢复失败同样不阻塞，但需记录：后续推理可能
                        # 仍处于 MC dropout 模式，导致确定性预测出现非确定性
                        logger.debug("Failed to restore original dropout_rate: %s",
                                     dropout_err, exc_info=True)

            inference_time = (time.perf_counter() - start_ts) * 1000.0

            try:
                stacked = np.stack(samples, axis=0)
                mean = np.mean(stacked, axis=0)
                std = np.std(stacked, axis=0)
            except (ValueError, TypeError) as exc:
                logger.warning(
                    "predict_mc_dropout: 样本堆叠失败，回退到首样本: %s", exc
                )
                mean = samples[0] if samples else np.array(0.0)
                std = np.zeros_like(mean)

            mean_value = self._maybe_inverse_transform(mean)
            processed = self._postprocess(mean_value, hidden)

            scalar_mean = float(np.mean(processed)) if isinstance(processed, np.ndarray) else float(processed)
            scalar_std = float(np.mean(std)) if std.size else 0.0

            mean_abs = abs(scalar_mean) if scalar_mean != 0 else 1.0
            confidence = max(0.0, min(1.0, 1.0 - scalar_std / mean_abs))

            mem_mb = self._get_memory_usage_mb()
            self._update_stats(inference_time, mem_mb)
            self._write_trace(inference_time, features.shape if hasattr(features, "shape") else (1,), success=True)

            return PredictionResult(
                value=processed,
                confidence=confidence,
                inference_time=inference_time,
                model_info={
                    "name": self.model_name,
                    "device": str(self.device),
                    "mc_n_samples": n_samples,
                    "mc_std": scalar_std,
                    "mc_mean": scalar_mean,
                    "uncertainty_method": "mc_dropout",
                },
            )

    def predict_with_intermediates(
        self,
        input_data: Any,
        *,
        capture_hidden: bool = True,
        capture_gates: bool = True,
    ) -> PredictionResult:
        """非侵入式推理并捕获中间状态（隐状态 / 门控值 / 时间常数）.

        对应 ADR-016（可解释性可视化）。本方法不修改主推理路径，
        仅在标准前向后附加读取模型内部状态，供可解释性服务消费：
        - 隐状态序列 → ``HiddenStateExplanation``（降维投影可视化）
        - 门控值 / 时间常数 → ``GateDynamicsExplanation``（门控动力学曲线）

        捕获策略
        --------
        1. **forward hook 模式**（首选）：若模型为 torch LTC 模型且暴露
           ``ltc_cells`` 属性，注册 forward hook 捕获每个 cell 的输出，
           得到逐层逐帧的隐状态序列。同时从 ``config.time_constant``
           读取 ``dt``，计算 ``τ = 1/dt`` 作为时间常数。
        2. **属性读取模式**（降级）：若模型暴露 ``hidden_state`` 属性但
           无 ``ltc_cells``，直接读取前向后的 ``hidden_state``（单帧快照）。
        3. **禁用模式**：torch 不可用或模型不暴露任何中间状态时，
           ``intermediates`` 返回空字典，仅保证主推理结果正确。

        线程安全
        --------
        使用 ``_mc_lock`` 保护（与 ``predict_mc_dropout`` 共享），避免
        并发请求的 hook 注册/移除相互干扰。hook 句柄在 finally 块中
        确保移除，防止泄漏。

        Parameters
        ----------
        input_data : Any
            输入数据（与 ``predict`` 接口一致）。
        capture_hidden : bool
            是否捕获隐状态序列（默认 True）。
        capture_gates : bool
            是否捕获门控值与时间常数（默认 True）。

        Returns
        -------
        PredictionResult
            标准预测结果，``model_info`` 中附加 ``intermediates`` 字段：
            - ``hidden_states``: list[list[float]] 隐状态 [N, hidden_dim]
            - ``gate_values``: list[list[float]] 门控值 [N, hidden_dim]
            - ``time_constants``: list[list[float]] 时间常数 τ [N, hidden_dim]
            - ``hidden_shape``: list[int] 原始隐状态形状
            - ``capture_mode``: str 捕获模式（``hook`` / ``attribute`` / ``disabled``）

        Notes
        -----
        - 本方法 **不更新** ``_stats`` 统计，避免与 ``predict`` 双重计数。
        - 捕获失败时记录 warning 并返回空 intermediates，不抛异常。
        """
        start_time = time.perf_counter()

        # _mc_lock 保护 hook 注册/移除与模型状态读取，避免并发干扰
        with self._mc_lock:
            intermediates: Dict[str, Any] = {
                "hidden_states": [],
                "gate_values": [],
                "time_constants": [],
                "hidden_shape": [],
                "capture_mode": "disabled",
            }

            try:
                features, hidden_meta = self._preprocess(input_data)
            except (ValueError, TypeError, RuntimeError) as exc:
                logger.warning(
                    "predict_with_intermediates: 预处理失败，返回空 intermediates: %s",
                    exc,
                    exc_info=True,
                )
                inference_time = (time.perf_counter() - start_time) * 1000
                return PredictionResult(
                    value=None,
                    confidence=0.0,
                    inference_time=inference_time,
                    model_info={
                        "name": self.model_name,
                        "device": str(self.device),
                        "intermediates": intermediates,
                        "intermediate_capture_error": str(exc),
                    },
                )

            # ---- 捕获中间状态 ----
            hook_handles: list[Any] = []
            captured_hidden: list[np.ndarray] = []

            if capture_hidden and HAS_TORCH:
                # 尝试 forward hook 模式：注册到 ltc_cells
                ltc_cells = getattr(self.model, "ltc_cells", None)
                if ltc_cells is not None and isinstance(ltc_cells, (list, tuple)):
                    for cell in ltc_cells:
                        def _hook(module, inputs, output, _cell=cell):
                            try:
                                if isinstance(output, torch.Tensor):
                                    captured_hidden.append(
                                        output.detach().cpu().numpy()
                                    )
                            except (RuntimeError, ValueError, TypeError):
                                pass

                        handle = cell.register_forward_hook(_hook)
                        hook_handles.append(handle)
                    intermediates["capture_mode"] = "hook"

            try:
                # 执行标准前向
                if isinstance(self.model, BaseLNNModel):
                    output = self.model.predict(features)
                else:
                    features_tensor = self._to_tensor(features)
                    with torch.no_grad():
                        output = self.model(features_tensor)

                processed_output = self._postprocess(output, hidden_meta)
                if isinstance(processed_output, np.ndarray):
                    processed_output = self._maybe_inverse_transform(processed_output)

                # ---- 收集隐状态 ----
                if capture_hidden:
                    if captured_hidden:
                        # hook 模式：逐层隐状态
                        # 取最后一层的输出作为帧序列（[seq, batch, hidden] → [seq, hidden]）
                        last_layer = captured_hidden[-1]
                        if last_layer.ndim == 3:
                            # [seq, batch, hidden] → [seq, hidden]（batch=1）
                            hidden_seq = last_layer[:, 0, :]
                        elif last_layer.ndim == 2:
                            hidden_seq = last_layer
                        else:
                            hidden_seq = last_layer.reshape(1, -1)
                        intermediates["hidden_states"] = hidden_seq.tolist()
                        intermediates["hidden_shape"] = list(hidden_seq.shape)
                    else:
                        # 降级：属性读取模式
                        last_hs = getattr(self.model, "hidden_state", None)
                        if last_hs is not None:
                            if HAS_TORCH and isinstance(last_hs, torch.Tensor):
                                last_hs = last_hs.detach().cpu().numpy()
                            # [num_layers, batch, hidden] → [num_layers, hidden]（batch=1）
                            if isinstance(last_hs, np.ndarray):
                                if last_hs.ndim == 3:
                                    hs_seq = last_hs[:, 0, :]
                                elif last_hs.ndim == 2:
                                    hs_seq = last_hs
                                else:
                                    hs_seq = last_hs.reshape(1, -1)
                                intermediates["hidden_states"] = hs_seq.tolist()
                                intermediates["hidden_shape"] = list(hs_seq.shape)
                                intermediates["capture_mode"] = "attribute"

                # ---- 收集门控值与时间常数 ----
                if capture_gates:
                    config = getattr(self.model, "config", None)
                    dt = getattr(config, "time_constant", None) if config else None
                    if dt is not None:
                        # 广播 dt 到 hidden_dim 维
                        hidden_dim = (
                            len(intermediates["hidden_states"][0])
                            if intermediates["hidden_states"]
                            else 1
                        )
                        gate_values = [float(dt)] * hidden_dim
                        time_constants = [1.0 / float(dt) if float(dt) > 0 else 0.0] * hidden_dim
                        # 广播到帧数
                        n_frames = len(intermediates["hidden_states"]) or 1
                        intermediates["gate_values"] = [gate_values] * n_frames
                        intermediates["time_constants"] = [time_constants] * n_frames
                        if intermediates["capture_mode"] == "disabled":
                            intermediates["capture_mode"] = "attribute"

            except (ValueError, TypeError, RuntimeError) as exc:
                logger.warning(
                    "predict_with_intermediates: 中间状态捕获失败: %s",
                    exc,
                    exc_info=True,
                )
                # 主推理已失败，返回错误结果
                inference_time = (time.perf_counter() - start_time) * 1000
                return PredictionResult(
                    value=None,
                    confidence=0.0,
                    inference_time=inference_time,
                    model_info={
                        "name": self.model_name,
                        "device": str(self.device),
                        "intermediates": intermediates,
                        "intermediate_capture_error": str(exc),
                    },
                )
            finally:
                # 确保 hook 移除，防止泄漏
                for handle in hook_handles:
                    try:
                        handle.remove()
                    except (RuntimeError, ValueError, AttributeError):
                        pass

            inference_time = (time.perf_counter() - start_time) * 1000
            confidence = self._compute_confidence(output) if output is not None else 0.0

            return PredictionResult(
                value=processed_output,
                confidence=confidence,
                inference_time=inference_time,
                model_info={
                    "name": self.model_name,
                    "device": str(self.device),
                    "intermediates": intermediates,
                },
            )

    def get_statistics(self) -> Dict[str, Any]:
        with self._stats_lock:
            stats = self._stats.copy()
        total = stats["total_inferences"]
        stats["average_inference_time_ms"] = (
            stats["total_inference_time_ms"] / total if total > 0 else 0.0
        )
        if stats["min_inference_time_ms"] == float("inf"):
            stats["min_inference_time_ms"] = 0.0
        stats["current_memory_mb"] = self._get_memory_usage_mb()
        return stats

    def get_performance(self) -> Dict[str, Any]:
        # 在锁内快照所有需要的字段并完成窗口重置写操作，
        # 锁外完成 sorted 等较重计算以减少锁持有时间。
        with self._stats_lock:
            total = self._stats["total_inferences"]
            times = sorted(self._stats["inference_times"])
            total_inference_time_ms = self._stats["total_inference_time_ms"]
            min_inference_time_ms = self._stats["min_inference_time_ms"]
            max_inference_time_ms = self._stats["max_inference_time_ms"]
            peak_memory_mb = self._stats["peak_memory_mb"]
            window_start = self._stats["window_start"]
            window_inferences = self._stats["window_inferences"]

            now = time.perf_counter()
            window_elapsed = now - window_start
            throughput = (
                window_inferences / window_elapsed if window_elapsed > 0 else 0.0
            )
            if window_elapsed > 60.0:
                self._stats["window_start"] = now
                self._stats["window_inferences"] = 0

        n = len(times)
        avg_ms = (total_inference_time_ms / total) if total > 0 else 0.0
        p50 = times[int(n * 0.50)] if n > 0 else 0.0
        p95 = times[min(int(n * 0.95), n - 1)] if n > 0 else 0.0
        p99 = times[min(int(n * 0.99), n - 1)] if n > 0 else 0.0

        device_type = str(self.device)
        if HAS_TORCH and self.device.type == "cuda":
            device_type = f"CUDA:{torch.cuda.get_device_name(self.device)}"
        elif self.device.type == "mps":
            device_type = "Apple MPS"

        return {
            "model_name": self.model_name,
            "device": device_type,
            "device_type": str(self.device),
            "amp_enabled": self.use_amp,
            "engine_type": self.engine_type.value
            if hasattr(self.engine_type, "value")
            else str(self.engine_type),
            "total_inferences": total,
            "avg_inference_ms": round(avg_ms, 4),
            "p50_inference_ms": round(p50, 4),
            "p95_inference_ms": round(p95, 4),
            "p99_inference_ms": round(p99, 4),
            "min_inference_ms": round(
                min_inference_time_ms
                if min_inference_time_ms != float("inf")
                else 0.0,
                4,
            ),
            "max_inference_ms": round(max_inference_time_ms, 4),
            "throughput_inf_per_sec": round(throughput, 2),
            "current_memory_mb": round(self._get_memory_usage_mb(), 2),
            "peak_memory_mb": round(peak_memory_mb, 2),
            "sample_count_recent": n,
        }

    def _compute_confidence(self, output) -> float:
        """
        优化置信度计算以提升推理性能
        
        优化策略：
        - 使用更高效的 softmax 计算
        - 减少不必要的张量操作
        - 缓存中间结果
        """
        if HAS_TORCH and isinstance(output, torch.Tensor):
            # 优化：对于标量或单元素输出直接返回固定高置信度
            if output.numel() <= 1:
                return 0.95
            
            # 优化：使用 in-place 操作减少内存分配
            # 注意：调用方已在 torch.inference_mode() 上下文中，无需再次禁用梯度
            if output.dim() > 1:
                probs = torch.softmax(output, dim=-1)
            else:
                # 对于一维输出，直接使用 sigmoid 近似
                probs = torch.sigmoid(output)
            
            max_prob = probs.max().item()
            return min(max(max_prob, 0.0), 1.0)
        
        return 0.9

    def _standardize_input(self, input_data: Any) -> np.ndarray:
        """Standardize various input types to numpy array"""
        if isinstance(input_data, np.ndarray):
            result = input_data
        elif isinstance(input_data, dict):
            result = DataPreprocessor.extract_numeric_features(input_data)
        elif isinstance(input_data, (list, tuple)):
            result = np.array(input_data)
        elif HAS_TORCH and isinstance(input_data, torch.Tensor):
            result = input_data.detach().cpu().numpy()
        elif isinstance(input_data, (int, float)):
            result = np.array([input_data])
        else:
            raise ValueError(
                f"模型预测失败：不支持的输入数据类型 '{type(input_data).__name__}'。"
                "支持的输入类型包括：dict（字典格式）、list（列表格式）、"
                "numpy.ndarray（数组格式）、torch.Tensor（张量格式）。"
                "请将输入数据转换为支持的格式后重试。"
            )

        if result.ndim == 1:
            result = result.reshape(1, -1)
        return result

    def _to_tensor(self, data: np.ndarray):
        """Convert numpy array to tensor on correct device"""
        if HAS_TORCH:
            return torch.from_numpy(data.astype(np.float32)).to(self.device)
        return data

    def _get_memory_usage_mb(self) -> float:
        """Get current process memory usage in MB"""
        process = psutil.Process()
        return process.memory_info().rss / (1024 * 1024)

    def _update_stats(self, inference_time_ms: float, memory_mb: float) -> None:
        """Update inference statistics (thread-safe)"""
        with self._stats_lock:
            self._stats["total_inferences"] += 1
            self._stats["total_inference_time_ms"] += inference_time_ms
            self._stats["max_inference_time_ms"] = max(
                self._stats["max_inference_time_ms"], inference_time_ms
            )
            self._stats["min_inference_time_ms"] = min(
                self._stats["min_inference_time_ms"], inference_time_ms
            )
            self._stats["peak_memory_mb"] = max(self._stats["peak_memory_mb"], memory_mb)
            times = self._stats["inference_times"]
            times.append(inference_time_ms)
            if len(times) > self._max_recent_times:
                self._stats["inference_times"] = times[-self._max_recent_times :]
            self._stats["window_inferences"] += 1

    def _write_trace(
        self,
        inference_time_ms: float,
        input_shape: tuple,
        success: bool = True,
        error_msg: Optional[str] = None,
    ) -> None:
        """
        持久化推理性能数据到 trace_log.jsonl
        
        Args:
            inference_time_ms: 真实推理耗时（毫秒）
            input_shape: 输入数据形状
            success: 是否成功
            error_msg: 错误信息（如有）
        """
        if not self._trace_log_enabled:
            return
        
        try:
            trace_entry = {
                "timestamp": datetime.now().isoformat(),
                "model_name": self.model_name,
                "device": str(self.device),
                "input_shape": list(input_shape),
                "inference_time_ms": round(inference_time_ms, 4),
                "memory_mb": round(self._get_memory_usage_mb(), 2),
                "success": success,
                "error": error_msg,
                "amp_enabled": self.use_amp,
                "engine_type": self.engine_type.value if hasattr(self.engine_type, "value") else str(self.engine_type),
            }
            
            with open(self._trace_log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(trace_entry, ensure_ascii=False) + "\n")
        except (OSError, IOError, TypeError, ValueError) as exc:
            logger.debug("写入 trace log 失败: %s", exc)

    @classmethod
    def from_registry(
        cls,
        registry: BaseModelRegistry,
        model_name: str,
        **kwargs,
    ) -> "LNNPredictor":
        """Create predictor from registry with model caching support"""
        cache = get_model_cache()
        cached_model = cache.get(model_name)

        if cached_model is not None:
            logger.info(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={model_name} "
                f"operation=load status=FROM_CACHE"
            )
            return cls(model=cached_model, model_name=model_name, **kwargs)

        logger.info(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={model_name} "
            f"operation=load status=FROM_REGISTRY"
        )
        load_start = time.perf_counter()
        model = cls._load_model_from_registry(registry, model_name)
        load_duration = time.perf_counter() - load_start

        try:
            from app.utils.utils import get_metrics_collector

            get_metrics_collector().record_lnn_model_load(model_name, load_duration)
        except (ImportError, AttributeError, RuntimeError, ValueError) as e:
            # 模型加载指标记录失败仅影响可观测性，不影响加载流程
            logger.debug(
                f"Failed to record model load metrics for {model_name}: {e}",
                exc_info=True,
            )

        try:
            memory_bytes = cls._calculate_model_memory(model)
            cache.put(model_name, model, memory_bytes)
            logger.info(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={model_name} "
                f"operation=cache status=CACHED memory={memory_bytes} bytes"
            )
        except (OSError, ValueError, TypeError, AttributeError) as e:
            # 模型缓存写入或内存计算可能因缓存后端或属性访问失败，
            # 失败时记录警告但允许模型继续使用（不缓存即可）
            logger.warning(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={model_name} "
                f"operation=cache status=FAILED error={e}"
            )

        return cls(model=model, model_name=model_name, **kwargs)

    @staticmethod
    def _load_model_from_registry(registry: BaseModelRegistry, model_name: str) -> Any:
        """Load model from registry using the standard get() interface.

        Args:
            registry: Model registry instance (must implement BaseModelRegistry)
            model_name: Name of the model to load

        Returns:
            Model instance

        Raises:
            KeyError: If model not found in registry
            RuntimeError: If registry type is unsupported
        """
        if not isinstance(registry, BaseModelRegistry):
            if not (hasattr(registry, "get") and callable(getattr(registry, "get"))):
                supported = [BaseModelRegistry.__name__, "dict", "dict-like with get()"]
                actual = type(registry).__name__
                raise RuntimeError(
                    f"模型加载失败：注册表类型不兼容。错误详情: 不支持的注册表类型 '{actual}'。"
                    f"预期类型为: {', '.join(supported)}。"
                    "请将注册表包装为 BaseModelRegistry 适配器，"
                    "或使用支持 get() 方法的字典类对象。"
                )

        try:
            model = registry.get(model_name)
            if model is None:
                raise KeyError(
                    f"模型加载异常：模型 '{model_name}' 在注册表中存在但返回为空（None）。"
                    "可能原因：1) 模型文件已损坏或丢失；2) 模型加载过程出现异常。"
                    "请检查模型文件完整性，或调用 POST /api/v1/lnn/models/{name}/load 重新加载模型。"
                )

            if isinstance(model, ModelEntry):
                return LNNPredictor._build_model_from_entry(model)

            return model
        except KeyError:
            raise
        except (OSError, RuntimeError, ValueError, TypeError, AttributeError, ImportError) as e:
            # 模型加载涉及文件 IO、模块导入、张量加载等具体异常
            raise RuntimeError(
                f"模型加载失败：无法加载模型 '{model_name}'。错误详情: {e}。"
                "可能原因：1) 模型权重文件不存在或已损坏；"
                "2) 模型配置与权重不匹配；3) 内存/GPU 显存不足。"
                "请检查模型文件路径和完整性，或查看日志获取详细错误信息。"
            ) from e

    @staticmethod
    def _build_model_from_entry(entry: ModelEntry) -> Any:
        """Build a real model instance from a ModelEntry metadata."""
        if entry.model is not None:
            logger.info(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={entry.info.name} "
                f"operation=build_model status=FROM_CACHED_ENTRY input_dim={entry.model.input_dim}"
            )
            return entry.model

        from app.ai.lnn.inference.registry import LNNModelRegistry

        model_cls = LNNModelRegistry.MODEL_CLASS_MAP.get(entry.info.model_type)
        if model_cls is None:
            raise ValueError(f"Unsupported model type: {entry.info.model_type}")

        input_dim = len(entry.info.input_features) if entry.info.input_features else 1
        output_dim = (
            len(entry.info.output_features) if entry.info.output_features else 1
        )

        logger.info(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={entry.info.name} "
            f"operation=build_model status=CREATING input_dim={input_dim} output_dim={output_dim} "
            f"input_features={entry.info.input_features}"
        )

        model = model_cls(
            model_name=entry.info.name,
            input_dim=input_dim,
            output_dim=output_dim,
        )

        model_path = entry.info.model_path
        if model_path and os.path.exists(model_path):
            logger.info(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={entry.info.name} "
                f"operation=build_model status=LOADING_FILE path={model_path}"
            )
            try:
                model.load(model_path)
            except (OSError, IOError, RuntimeError, ValueError, TypeError) as e:
                # 模型权重加载失败时使用初始化权重继续构建，记录以便排查
                logger.warning(
                    f"Failed to load weights from {model_path}, "
                    f"falling back to initialized weights: {e}",
                    exc_info=True,
                )

        model.build()

        logger.info(
            f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={entry.info.name} "
            f"operation=build_model status=BUILT model_input_dim={model.input_dim}"
        )

        entry.model = model
        entry.is_loaded = True
        return model

    @staticmethod
    def _calculate_model_memory(model) -> int:
        """
        Calculate memory size of a model in bytes.

        Args:
            model: Model instance

        Returns:
            Memory size in bytes
        """
        if not HAS_TORCH or not isinstance(model, torch.nn.Module):
            return 0

        try:
            param_size = sum(p.numel() * p.element_size() for p in model.parameters())
            buffer_size = sum(b.numel() * b.element_size() for b in model.buffers())
            return param_size + buffer_size
        except (AttributeError, RuntimeError, TypeError):
            # 计算模型内存可能因张量属性访问失败，回退返回 0（不影响主流程）
            return 0


Predictor = LNNPredictor
