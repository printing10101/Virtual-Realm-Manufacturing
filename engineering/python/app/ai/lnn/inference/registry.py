"""
Model Registry

Manages model metadata, version control, and validation.
Provides a centralized registry for all LNN models with predefined model support.
"""

import os
import json
import logging
import time
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Type
from dataclasses import dataclass

from app.ai.lnn.core import ModelConfig, ModelType

# 阶段2 解耦改造：models/ 已迁移到 research/models/。
# 工程侧推理路径应改为加载 ONNX（见 onnx_predictor.py）。
# 此处保留 try/except 兼容旧 torch 推理路径，torch 缺失时降级为 None。
try:
    from app.ai.lnn.models.base_lnn import BaseLNNModel  # type: ignore
    from app.ai.lnn.models.cfc_model import CFCModel  # type: ignore
    from app.ai.lnn.models.ltc_model import LTCModel  # type: ignore
    from app.ai.lnn.models.hybrid_lnn import HybridLNNModel  # type: ignore
    _HAS_TORCH_MODELS = True
except ImportError:
    BaseLNNModel = None  # type: ignore
    CFCModel = None  # type: ignore
    LTCModel = None  # type: ignore
    HybridLNNModel = None  # type: ignore
    _HAS_TORCH_MODELS = False

logger = logging.getLogger(__name__)


class BaseModelRegistry(ABC):
    """Abstract base class for model registries.

    Defines the minimal interface required for model loading.
    All registry implementations should inherit from this class.
    """

    @abstractmethod
    def get(self, model_name: str) -> Any:
        """Get a model instance by name.

        Args:
            model_name: Unique model identifier

        Returns:
            Model instance

        Raises:
            KeyError: If model not found
        """
        ...


def is_quantized_model(model_name: str) -> bool:
    """Check if a model name refers to a quantized model."""
    return model_name.endswith("_int8")


def get_base_model_name(model_name: str) -> str:
    """Get the base model name from a quantized model name."""
    if is_quantized_model(model_name):
        return model_name[:-5]
    return model_name


def get_quantized_model_name(model_name: str) -> str:
    """Get the quantized model name from a base model name."""
    if not is_quantized_model(model_name):
        return f"{model_name}_int8"
    return model_name


@dataclass
class ModelInfo:
    """Model information dataclass with validation"""

    name: str
    model_type: str
    model_path: str
    input_features: List[str]
    output_features: List[str]
    version: str = "1.0.0"

    def __post_init__(self):
        """Validate required fields"""
        if not self.name:
            raise ValueError(
                "Model registration failed: name cannot be empty. "
                "Use a meaningful name (e.g. 'cutting_force_45steel')."
            )
        if not self.model_type:
            raise ValueError(
                "Model registration failed: model_type cannot be empty. "
                "Supported types: LNN, CTC, CFC, LTC. "
                "Call GET /api/v1/lnn/models for the list."
            )
        if not self.model_path:
            raise ValueError(
                "Model registration failed: model_path cannot be empty. "
                "Path must point to a trained weight file (.pt or .pth), "
                "e.g. 'models/cutting_force_v1.pt'."
            )
        if not self.input_features:
            raise ValueError(
                "Model registration failed: Input features cannot be empty. "
                "Input features define model input variables "
                "(e.g. 'cutting_speed', 'feed_rate', 'depth_of_cut')."
            )
        if not self.output_features:
            raise ValueError(
                "Model registration failed: Output features cannot be empty. "
                "Output features define model prediction targets "
                "(e.g. 'cutting_force', 'tool_wear')."
            )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary"""
        return {
            "name": self.name,
            "model_type": self.model_type,
            "model_path": self.model_path,
            "input_features": self.input_features,
            "output_features": self.output_features,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ModelInfo":
        """Deserialize from dictionary"""
        return cls(
            name=data["name"],
            model_type=data["model_type"],
            model_path=data["model_path"],
            input_features=data.get("input_features", []),
            output_features=data.get("output_features", []),
            version=data.get("version", "1.0.0"),
        )


@dataclass
class ModelEntry:
    """Model registry entry"""

    config: Optional[ModelConfig] = None
    info: Optional[ModelInfo] = None
    model: Optional[BaseLNNModel] = None
    is_loaded: bool = False
    last_accessed: float = 0.0
    access_count: int = 0
    metadata: Optional[Dict[str, Any]] = None


class LNNModelRegistry(BaseModelRegistry):
    """
    LNN Model Registry with predefined models and validation support.

    Features:
    - Predefined models: cutting_force, wear_prediction, surface_roughness, temperature
    - Model registration with duplicate checking
    - Exact and fuzzy model lookup
    - Model file existence and structure validation
    """

    PREDEFINED_MODELS = {
        "cutting_force": ModelInfo(
            name="cutting_force",
            model_type="CFC",
            model_path="models/cutting_force.pt",
            input_features=[
                "force_x",
                "force_y",
                "force_z",
                "spindle_speed",
                "feed_rate",
            ],
            output_features=["predicted_cutting_force"],
            version="1.0.0",
        ),
        "wear_prediction": ModelInfo(
            name="wear_prediction",
            # 学术诚信说明 [S6]：model_type="LTC" 指向 LTCModel 类
            # （MODEL_CLASS_MAP["LTC"] = LTCModel）。LTCModel 同时提供：
            #   - NumPy 前向推理（forward / predict）：功能性实现，可独立运行
            #   - PyTorch 训练（_train_step / _train_step_torch）：真实梯度更新
            #   - NumPy 训练（_train_step_numpy）：非功能性占位（详见 S2 修复）
            # 当 models/wear_prediction.pt 不存在时，模型以 NumPy 权重初始化，
            # 仍可执行前向推理（用于演示/接口验证），但无法执行真实训练。
            # 论文报告训练结果时必须确认 .pt 文件已通过 PyTorch 后端生成。
            model_type="LTC",
            model_path="models/wear_prediction.pt",
            input_features=["vb", "time", "spindle_speed", "feed_rate", "depth_of_cut"],
            output_features=["predicted_wear"],
            version="1.0.0",
        ),
        "surface_roughness": ModelInfo(
            name="surface_roughness",
            model_type="HybridLNN",
            model_path="models/surface_roughness.pt",
            input_features=["roughness_ra", "cutting_speed", "feed_rate", "tool_wear"],
            output_features=["predicted_surface_roughness"],
            version="1.0.0",
        ),
        "temperature": ModelInfo(
            name="temperature",
            model_type="CFC",
            model_path="models/temperature.pt",
            input_features=["temp_zone1", "temp_zone2", "coolant_flow", "cutting_time"],
            output_features=["predicted_temperature"],
            version="1.0.0",
        ),
    }

    MODEL_CLASS_MAP: Dict[str, Type[BaseLNNModel]] = {
        "CFC": CFCModel,
        "LTC": LTCModel,
        "HybridLNN": HybridLNNModel,
    }

    def __init__(self, cache_size: int = 10, model_dir: Optional[str] = None):
        self.cache_size = cache_size
        self.model_dir = model_dir
        self.registry: Dict[str, ModelEntry] = {}
        self.cache_hits = 0
        self.cache_misses = 0
        self._lock = threading.Lock()  # 保护 registry 字典的线程安全
        self._register_predefined_models()

    def _register_predefined_models(self) -> None:
        """Register all predefined models"""
        for name, info in self.PREDEFINED_MODELS.items():
            if self.model_dir:
                model_path = os.path.join(
                    self.model_dir, os.path.basename(info.model_path)
                )
                info.model_path = model_path
            entry = ModelEntry(info=info)
            self.registry[name] = entry

    def get_model_info(
        self,
        model_name: str,
        fuzzy_match: bool = False,
    ) -> Optional[ModelInfo]:
        with self._lock:
            if not fuzzy_match:
                entry = self.registry.get(model_name)
                return entry.info if entry else None

            matches = [
                name for name in self.registry.keys() if model_name.lower() in name.lower()
            ]
            if matches:
                return self.registry[matches[0]].info
            return None

    def list_models(self, return_objects: bool = False) -> List[Any]:
        with self._lock:
            if return_objects:
                return [entry.info for entry in self.registry.values()]
            return list(self.registry.keys())

    def register_model(self, model_info: ModelInfo) -> bool:
        with self._lock:
            if model_info.name in self.registry:
                return False
            entry = ModelEntry(info=model_info)
            self.registry[model_info.name] = entry
            return True

    def register_quantized_model(
        self,
        base_model_name: str,
        quantized_model_path: str,
        quantization_type: str = "dynamic",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        with self._lock:
            quantized_name = (
                f"{base_model_name}_int8"
                if not base_model_name.endswith("_int8")
                else base_model_name
            )

            if quantized_name in self.registry:
                return False

            base_entry = self.registry.get(base_model_name)
            if base_entry:
                model_type = base_entry.info.model_type
                input_features = base_entry.info.input_features
                output_features = base_entry.info.output_features
            else:
                model_type = "CFC"
                input_features = []
                output_features = []

            quantized_info = ModelInfo(
                name=quantized_name,
                model_type=model_type,
                model_path=quantized_model_path,
                input_features=input_features,
                output_features=output_features,
                version="1.0.0-int8",
            )

            quant_meta = metadata or {}
            quant_meta.update(
                {
                    "is_quantized": True,
                    "quantization_type": quantization_type,
                    "quantization_date": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "base_model": base_model_name,
                }
            )

            entry = ModelEntry(info=quantized_info, metadata=quant_meta)
            self.registry[quantized_name] = entry
            return True

    def get(self, model_name: str) -> ModelEntry:
        """Get a model entry by name."""
        with self._lock:
            entry = self.registry.get(model_name)
            if entry is None:
                raise KeyError(f"Model '{model_name}' not found in registry")
            return entry

    def validate_model(
        self, model_name: str, model_path: Optional[str] = None
    ) -> Dict[str, Any]:
        with self._lock:
            entry = self.registry.get(model_name)
            if not entry:
                return {
                    "valid": False,
                    "reason": f"Model '{model_name}' not found in registry",
                    "details": {},
                }

            path = model_path or entry.info.model_path
            file_exists = os.path.exists(path)
            structure_valid = True
            load_test_passed = False

            if file_exists:
                try:
                    model_class = self.MODEL_CLASS_MAP.get(entry.info.model_type)
                    if model_class:
                        model = model_class(
                            model_name=entry.info.name,
                            input_dim=len(entry.info.input_features),
                            output_dim=len(entry.info.output_features),
                        )
                        model.load(path)
                        model.build()
                        load_test_passed = True
                except (ImportError, AttributeError, RuntimeError, ValueError, TypeError, OSError):
                    # 模型加载测试可能因模块导入、属性访问、文件 IO 等环节失败，
                    # 此处无需详细错误信息（仅作有效性标记）
                    structure_valid = False
                    load_test_passed = False

            return {
                "valid": file_exists and structure_valid and load_test_passed,
                "file_exists": file_exists,
                "structure_valid": structure_valid,
                "load_test_passed": load_test_passed,
                "model_name": model_name,
                "model_path": path,
            }


class ModelRegistry(BaseModelRegistry):
    """
    模型注册表

    管理：
    - 模型加载
    - 版本控制
    - 缓存管理
    - 模型查询
    """

    # PyTorch版本模型类映射 (lazy-initialized)
    _torch_model_class_map: Dict[str, Any] = {}

    # 模型类型到类的映射
    MODEL_CLASS_MAP: Dict[ModelType, Type[BaseLNNModel]] = {
        ModelType.CFC: CFCModel,
        ModelType.LTC: LTCModel,
        ModelType.HYBRID_LNN: HybridLNNModel,
    }

    def __init__(
        self,
        cache_size: int = 10,
        model_dir: Optional[str] = None,
        enable_auto_cache: bool = True,
    ):
        self.cache_size = cache_size
        self.model_dir = model_dir
        self.enable_auto_cache = enable_auto_cache
        self.registry: Dict[str, ModelEntry] = {}
        self.cache_hits = 0
        self.cache_misses = 0

    def register(
        self,
        model_name: str,
        model_type: ModelType,
        model_path: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if model_name in self.registry:
            raise ValueError(
                f"模型注册失败：模型名称 '{model_name}' 已被注册。已注册的模型名称必须唯一。请调用 GET /api/v1/lnn/models 查看当前已注册的模型列表，或使用其他名称注册。"
            )

        model_config = ModelConfig(
            model_type=model_type,
            model_name=model_name,
            model_path=model_path,
            hyperparameters=config,
            metadata=metadata,
        )

        entry = ModelEntry(
            config=model_config,
            metadata=metadata,
        )

        self.registry[model_name] = entry
        return model_name

    def get(self, model_name: str, load_if_needed: bool = True) -> BaseLNNModel:
        if model_name not in self.registry:
            raise KeyError(
                f"模型获取失败：模型 '{model_name}' 未在注册表中找到。可能原因：1) 模型尚未注册；2) 模型名称拼写错误。请调用 GET /api/v1/lnn/models 查看所有已注册的模型列表，确认模型名称后重试。"  # noqa: E501
            )

        entry = self.registry[model_name]
        entry.last_accessed = time.time()
        entry.access_count += 1

        if entry.model is not None:
            self.cache_hits += 1
            return entry.model

        self.cache_misses += 1

        if load_if_needed:
            self._load_model(model_name)
            return entry.model

        raise RuntimeError(
            f"模型获取失败：模型 '{model_name}' 尚未加载到内存中。可能原因：1) 模型尚未从磁盘加载；2) 模型已卸载。解决方案：1) 设置 load_if_needed=True 以自动加载模型；2) 调用 POST /api/v1/lnn/models/{{name}}/load 手动加载模型。"  # noqa: E501
        )

    def load_model(self, model_name: str) -> None:
        self._load_model(model_name)

    def _load_model(self, model_name: str) -> None:
        entry = self.registry[model_name]
        config = entry.config

        model_class = self.MODEL_CLASS_MAP.get(config.model_type)
        if model_class is None:
            raise ValueError(
                f"模型加载失败：未知的模型类型 '{config.model_type}'。支持的模型类型可通过 registry.MODEL_CLASS_MAP.keys() 查看。请检查 ModelConfig 中的 model_type 配置，或调用 GET /api/v1/lnn/models 查看支持的模型类型。"  # noqa: E501
            )

        hyperparams = config.hyperparameters or {}
        model = model_class(
            model_name=config.model_name,
            input_dim=hyperparams.get("input_dim", 128),
            output_dim=hyperparams.get("output_dim", 10),
            device=config.device,
            **hyperparams,
        )

        if config.model_path and os.path.exists(config.model_path):
            model.load(config.model_path)

        model.build()

        entry.model = model
        entry.is_loaded = True
        self._evict_cache()

    def _evict_cache(self) -> None:
        if len(self.registry) <= self.cache_size:
            return

        loaded_models = [
            (name, entry) for name, entry in self.registry.items() if entry.is_loaded
        ]

        if len(loaded_models) > self.cache_size:
            loaded_models.sort(key=lambda x: x[1].last_accessed)
            for name, _ in loaded_models[: len(loaded_models) - self.cache_size]:
                self.registry[name].model = None
                self.registry[name].is_loaded = False

    def list_models(self) -> List[Dict[str, Any]]:
        models = []
        for name, entry in self.registry.items():
            models.append(
                {
                    "name": name,
                    "type": entry.config.model_type.value,
                    "is_loaded": entry.is_loaded,
                    "access_count": entry.access_count,
                    "version": entry.config.version,
                }
            )
        return models

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        if model_name not in self.registry:
            raise KeyError(
                f"模型信息获取失败：模型 '{model_name}' 未找到。可能原因：1) 模型尚未注册；2) 模型名称拼写错误。请调用 GET /api/v1/lnn/models 查看所有已注册的模型列表。"
            )

        entry = self.registry[model_name]
        info = {
            "name": entry.config.model_name,
            "type": entry.config.model_type.value,
            "path": entry.config.model_path,
            "is_loaded": entry.is_loaded,
            "device": entry.config.device,
            "version": entry.config.version,
            "hyperparameters": entry.config.hyperparameters,
            "access_count": entry.access_count,
            "last_accessed": entry.last_accessed,
        }

        if entry.model is not None:
            info["model_info"] = entry.model.get_model_info()

        return info

    def unload(self, model_name: str) -> None:
        if model_name in self.registry:
            self.registry[model_name].model = None
            self.registry[model_name].is_loaded = False

    def unload_all(self) -> None:
        for name in list(self.registry.keys()):
            self.unload(name)

    def get_cache_stats(self) -> Dict[str, Any]:
        total_requests = self.cache_hits + self.cache_misses
        hit_rate = self.cache_hits / total_requests if total_requests > 0 else 0.0
        loaded_count = sum(1 for entry in self.registry.values() if entry.is_loaded)

        return {
            "total_models": len(self.registry),
            "loaded_models": loaded_count,
            "cache_size": self.cache_size,
            "cache_hits": self.cache_hits,
            "cache_misses": self.cache_misses,
            "hit_rate": hit_rate,
        }

    def export_registry(self, path: str) -> None:
        export_data = {
            name: {
                "config": {
                    "model_type": entry.config.model_type.value,
                    "model_name": entry.config.model_name,
                    "model_path": entry.config.model_path,
                    "device": entry.config.device,
                    "version": entry.config.version,
                    "hyperparameters": entry.config.hyperparameters,
                },
                "access_count": entry.access_count,
                "metadata": entry.metadata,
            }
            for name, entry in self.registry.items()
        }

        with open(path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, indent=2)

    def import_registry(self, path: str) -> None:
        with open(path, "r") as f:
            import_data = json.load(f)

        for name, data in import_data.items():
            config_data = data["config"]
            self.register(
                model_name=name,
                model_type=ModelType(config_data["model_type"]),
                model_path=config_data.get("model_path"),
                config=config_data.get("hyperparameters"),
                metadata=data.get("metadata"),
            )

    def register_custom_model(
        self,
        model_name: str,
        model_class: Type[BaseLNNModel],
        model_type: Optional[ModelType] = None,
        **kwargs,
    ) -> str:
        if model_name in self.registry:
            raise ValueError(
                f"模型注册失败：模型名称 '{model_name}' 已被注册。已注册的模型名称必须唯一。请调用 GET /api/v1/lnn/models 查看当前已注册的模型列表，或使用其他名称注册。"
            )

        mtype = model_type or ModelType.CFC
        self.MODEL_CLASS_MAP[mtype] = model_class

        config = ModelConfig(
            model_type=mtype,
            model_name=model_name,
            hyperparameters=kwargs,
        )

        entry = ModelEntry(config=config, metadata=kwargs)
        self.registry[model_name] = entry

        return model_name

    def register_quantized_model(
        self,
        model_name: str,
        model_type: ModelType,
        model_path: str,
        config: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        if model_name in self.registry:
            raise ValueError(
                f"模型注册失败：模型名称 '{model_name}' 已被注册。已注册的模型名称必须唯一。请调用 GET /api/v1/lnn/models 查看当前已注册的模型列表，或使用其他名称注册。"
            )

        quant_meta = metadata or {}
        quant_meta.update(
            {
                "is_quantized": True,
                "quantization_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            }
        )

        model_config = ModelConfig(
            model_type=model_type,
            model_name=model_name,
            model_path=model_path,
            hyperparameters=config,
            metadata=quant_meta,
        )

        entry = ModelEntry(
            config=model_config,
            metadata=quant_meta,
        )

        self.registry[model_name] = entry
        return model_name

    def has_quantized_version(self, base_model_name: str) -> bool:
        quantized_name = get_quantized_model_name(base_model_name)
        return quantized_name in self.registry

    def get_quantized_model_path(self, base_model_name: str) -> Optional[str]:
        quantized_name = get_quantized_model_name(base_model_name)
        entry = self.registry.get(quantized_name)
        if entry and entry.config:
            return entry.config.model_path
        return None


def get_torch_model_class(model_type_str: str) -> Optional[Type]:
    """Get PyTorch model class by type string.

    Args:
        model_type_str: Model type string (e.g. "CFC", "LTC", "HybridLNN")

    Returns:
        PyTorch model class or None if not supported
    """
    if not ModelRegistry._torch_model_class_map:
        _init_torch_model_map()
    return ModelRegistry._torch_model_class_map.get(model_type_str)


def _init_torch_model_map() -> None:
    """Initialize the PyTorch model class map lazily."""
    try:
        from app.ai.lnn.models.torch_cfc_model import CFCModel as TorchCFCModel
        from app.ai.lnn.models.torch_ltc_model import LTCModel as TorchLTCModel
        from app.ai.lnn.models.torch_hybrid_lnn import HybridLNN as TorchHybridLNNModel

        ModelRegistry._torch_model_class_map.update(
            {
                "CFC": TorchCFCModel,
                "LTC": TorchLTCModel,
                "HybridLNN": TorchHybridLNNModel,
            }
        )
    except ImportError as e:
        # PyTorch 可选依赖未安装时静默跳过（仅影响 PyTorch 后端注册）
        logger.debug(
            f"PyTorch backend not available, skipping model class registration: {e}",
            exc_info=True,
        )
