"""
Predictor Module

Implements single-sample, batch, and streaming inference interfaces for LNN models.
Supports automatic device selection and AMP (Automatic Mixed Precision) acceleration.
"""
import numpy as np
import time
import logging
import psutil
from typing import Any, Dict, List, Optional, Union, Tuple
from dataclasses import dataclass, field

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
from app.ai.lnn.inference.registry import ModelRegistry, BaseModelRegistry
from app.ai.lnn.inference.model_cache import get_model_cache
from app.ai.lnn.inference.registry import is_quantized_model

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

        self.device = self._select_device()
        if HAS_TORCH and hasattr(self.model, "to"):
            self.model.to(self.device)

        self._stats = {
            "total_inferences": 0,
            "total_inference_time_ms": 0.0,
            "max_inference_time_ms": 0.0,
            "min_inference_time_ms": float("inf"),
            "peak_memory_mb": 0.0,
        }

    def _select_device(self) -> Any:
        """Automatically select best available device"""
        if not self.auto_device or not HAS_TORCH:
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
        if self.preprocessor.is_fitted:
            preprocessed = self.preprocessor.transform(input_array)
        else:
            preprocessed = self.preprocessor.fit_transform(input_array)
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

    def predict(
        self,
        input_data: Any,
        return_confidence: bool = False,
    ) -> Union[PredictionResult, Any]:
        """
        Single sample prediction
        
        Args:
            input_data: Input data (numpy array, Tensor, list, dict, etc.)
            return_confidence: Whether to return confidence score
            
        Returns:
            PredictionResult if return_confidence=True, else prediction value
        """
        start_time = time.perf_counter()

        try:
            features, hidden = self._preprocess(input_data)
            features_tensor = self._to_tensor(features)

            if self.use_amp and self.device.type == "cuda" and HAS_AMP:
                with autocast():
                    with torch.no_grad():
                        output = self.model(features_tensor)
            else:
                with torch.no_grad():
                    output = self.model(features_tensor)

            processed_output = self._postprocess(output, hidden)

            inference_time = (time.perf_counter() - start_time) * 1000
            mem_after = self._get_memory_usage_mb()
            self._update_stats(inference_time, mem_after)

            confidence = self._compute_confidence(output) if return_confidence else 0.0

            result = PredictionResult(
                value=processed_output,
                confidence=confidence,
                inference_time=inference_time,
                model_info={"name": self.model_name, "device": str(self.device)},
            )

            if return_confidence:
                return result
            return result.value

        except Exception as e:
            inference_time = (time.perf_counter() - start_time) * 1000
            self._update_stats(inference_time, self._get_memory_usage_mb())
            raise RuntimeError(f"Prediction failed: {str(e)}")

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
        """Process a single batch chunk"""
        features_list = []
        hidden_list = []
        for data in chunk:
            features, hidden = self._preprocess(data)
            features_list.append(features)
            hidden_list.append(hidden)

        batch_features = np.concatenate(features_list, axis=0)
        batch_tensor = self._to_tensor(batch_features)

        start_time = time.perf_counter()

        if self.use_amp and self.device.type == "cuda" and HAS_AMP:
            with autocast():
                with torch.no_grad():
                    outputs = self.model(batch_tensor)
        else:
            with torch.no_grad():
                outputs = self.model(batch_tensor)

        inference_time = (time.perf_counter() - start_time) * 1000
        mem_after = self._get_memory_usage_mb()

        if HAS_TORCH and isinstance(outputs, torch.Tensor):
            outputs = outputs.detach().cpu().numpy()

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

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get inference statistics
        
        Returns:
            Dictionary with inference statistics including:
            - total_inferences: Total number of inferences
            - average_inference_time_ms: Average inference time
            - max_inference_time_ms: Maximum inference time
            - min_inference_time_ms: Minimum inference time
            - peak_memory_mb: Peak memory usage
        """
        stats = self._stats.copy()
        total = stats["total_inferences"]
        stats["average_inference_time_ms"] = (
            stats["total_inference_time_ms"] / total if total > 0 else 0.0
        )
        if stats["min_inference_time_ms"] == float("inf"):
            stats["min_inference_time_ms"] = 0.0
        stats["current_memory_mb"] = self._get_memory_usage_mb()
        return stats

    def _compute_confidence(self, output) -> float:
        """Compute prediction confidence"""
        if HAS_TORCH and isinstance(output, torch.Tensor):
            if output.dim() == 0:
                return 0.9
            probs = torch.softmax(output, dim=-1) if output.dim() > 1 else output
            max_prob = probs.max().item() if hasattr(probs, "max") else 0.9
            return min(max(max_prob, 0.0), 1.0)
        return 0.9

    def _standardize_input(self, input_data: Any) -> np.ndarray:
        """Standardize various input types to numpy array"""
        if isinstance(input_data, np.ndarray):
            return input_data
        elif isinstance(input_data, dict):
            return DataPreprocessor.extract_numeric_features(input_data)
        elif isinstance(input_data, (list, tuple)):
            return np.array(input_data)
        elif HAS_TORCH and isinstance(input_data, torch.Tensor):
            return input_data.detach().cpu().numpy()
        elif isinstance(input_data, (int, float)):
            return np.array([input_data])
        else:
            raise ValueError(f"Unsupported input type: {type(input_data)}")

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
        """Update inference statistics"""
        self._stats["total_inferences"] += 1
        self._stats["total_inference_time_ms"] += inference_time_ms
        self._stats["max_inference_time_ms"] = max(
            self._stats["max_inference_time_ms"], inference_time_ms
        )
        self._stats["min_inference_time_ms"] = min(
            self._stats["min_inference_time_ms"], inference_time_ms
        )
        self._stats["peak_memory_mb"] = max(
            self._stats["peak_memory_mb"], memory_mb
        )

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
        model = cls._load_model_from_registry(registry, model_name)

        try:
            memory_bytes = cls._calculate_model_memory(model)
            cache.put(model_name, model, memory_bytes)
            logger.info(
                f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] model={model_name} "
                f"operation=cache status=CACHED memory={memory_bytes} bytes"
            )
        except Exception as e:
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
            # Support dict-like registries with get() method
            if not (hasattr(registry, 'get') and callable(getattr(registry, 'get'))):
                supported = [BaseModelRegistry.__name__, "dict", "dict-like with get()"]
                actual = type(registry).__name__
                raise RuntimeError(
                    f"Unsupported registry type: {actual}. "
                    f"Expected one of: {', '.join(supported)}. "
                    f"Consider wrapping your registry in a BaseModelRegistry adapter."
                )
        
        try:
            model = registry.get(model_name)
            if model is None:
                raise KeyError(f"Model '{model_name}' found but returned None")
            return model
        except KeyError:
            raise
        except Exception as e:
            raise RuntimeError(f"Failed to load model '{model_name}': {e}") from e

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
        except Exception:
            return 0
