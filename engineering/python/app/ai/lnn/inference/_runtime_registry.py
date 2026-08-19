"""ModelRegistry 运行时注册表（从 registry 拆出）。"""

from __future__ import annotations

import os
import json
import time
from typing import Any, Dict, List, Optional, Type

try:
    from app.ai.lnn.models.base_lnn import BaseLNNModel
    from app.ai.lnn.models.cfc_model import CFCModel
    from app.ai.lnn.models.ltc_model import LTCModel
    from app.ai.lnn.models.hybrid_lnn import HybridLNNModel

    _HAS_TORCH_MODELS = True
except ImportError:
    BaseLNNModel = None
    CFCModel = None
    LTCModel = None
    HybridLNNModel = None
    _HAS_TORCH_MODELS = False

from app.ai.lnn.core import ModelConfig, ModelType
from app.ai.lnn.inference._base_registry import BaseModelRegistry, get_quantized_model_name
from app.ai.lnn.inference._registry_models import ModelEntry

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
                f"模型获取失败：模型 '{model_name}' 未在注册表中找到。可能原因：1) 模型尚未注册；2) 模型名称拼写错误。请调用 GET /api/v1/lnn/models 查看所有已注册的模型列表，确认模型名称后重试。"
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
            f"模型获取失败：模型 '{model_name}' 尚未加载到内存中。可能原因：1) 模型尚未从磁盘加载；2) 模型已卸载。解决方案：1) 设置 load_if_needed=True 以自动加载模型；2) 调用 POST /api/v1/lnn/models/{{name}}/load 手动加载模型。"
        )

    def load_model(self, model_name: str) -> None:
        self._load_model(model_name)

    def _require_config(self, entry) -> "ModelConfig":
        """返回非空 ModelConfig，配置缺失时抛 ValueError。"""
        config = entry.config
        if config is None:
            raise ValueError(f"模型注册数据缺少配置: {entry}")
        return config

    def _load_model(self, model_name: str) -> None:
        entry = self.registry[model_name]
        config = self._require_config(entry)

        model_class = self.MODEL_CLASS_MAP.get(config.model_type)
        if model_class is None:
            raise ValueError(
                f"模型加载失败：未知的模型类型 '{config.model_type}'。支持的模型类型可通过 registry.MODEL_CLASS_MAP.keys() 查看。请检查 ModelConfig 中的 model_type 配置，或调用 GET /api/v1/lnn/models 查看支持的模型类型。"
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

        loaded_models = [(name, entry) for name, entry in self.registry.items() if entry.is_loaded]

        if len(loaded_models) > self.cache_size:
            loaded_models.sort(key=lambda x: x[1].last_accessed)
            for name, _ in loaded_models[: len(loaded_models) - self.cache_size]:
                self.registry[name].model = None
                self.registry[name].is_loaded = False

    def list_models(self) -> List[Dict[str, Any]]:
        models = []
        for name, entry in self.registry.items():
            config = self._require_config(entry)
            models.append(
                {
                    "name": name,
                    "type": config.model_type.value,
                    "is_loaded": entry.is_loaded,
                    "access_count": entry.access_count,
                    "version": config.version,
                }
            )
        return models

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        if model_name not in self.registry:
            raise KeyError(
                f"模型信息获取失败：模型 '{model_name}' 未找到。可能原因：1) 模型尚未注册；2) 模型名称拼写错误。请调用 GET /api/v1/lnn/models 查看所有已注册的模型列表。"
            )

        entry = self.registry[model_name]
        config = self._require_config(entry)
        info = {
            "name": config.model_name,
            "type": config.model_type.value,
            "path": config.model_path,
            "is_loaded": entry.is_loaded,
            "device": config.device,
            "version": config.version,
            "hyperparameters": config.hyperparameters,
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
        export_data = {}
        for name, entry in self.registry.items():
            config = self._require_config(entry)
            export_data[name] = {
                "config": {
                    "model_type": config.model_type.value,
                    "model_name": config.model_name,
                    "model_path": config.model_path,
                    "device": config.device,
                    "version": config.version,
                    "hyperparameters": config.hyperparameters,
                },
                "access_count": entry.access_count,
                "metadata": entry.metadata,
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

