"""
YAML Configuration Management Module

Provides YAML-based configuration loading, validation, access, and persistence
for the LNN workflow system with environment adaptation and runtime updates.
"""

import os
import copy
import json
import yaml
import logging
from typing import Any, Dict, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timezone

try:
    import torch

    HAS_TORCH = True
except ImportError:
    HAS_TORCH = False

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """单个LNN模型的配置"""

    type: str = "cfc"
    path: str = ""
    enabled: bool = True
    device: str = "cpu"
    input_dim: int = 128
    output_dim: int = 10
    hidden_dim: int = 256
    num_layers: int = 2
    dropout_rate: float = 0.1
    temporal_horizon: int = 1000
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class ThresholdConfig:
    """阈值配置"""

    quick: float = 0.85
    hybrid: float = 0.60
    complexity: int = 3
    fallback: float = 0.50
    confidence: float = 0.70


@dataclass
class LNNConfig:
    """LNN引擎配置"""

    enabled: bool = True
    models_dir: str = "models/lnn"
    default_device: str = "cpu"
    models: Dict[str, ModelConfig] = field(default_factory=dict)
    thresholds: ThresholdConfig = field(default_factory=ThresholdConfig)
    cache_size: int = 10
    enable_amp: bool = True
    max_retry_count: int = 3


@dataclass
class DatasetCacheConfig:
    """数据集缓存配置"""

    cache_directory: str = "~/.lingjing/cache/datasets/"
    max_cache_size: int = 5 * 1024 * 1024 * 1024
    memory_cache_size: int = 1024 * 1024 * 1024
    cache_eviction_policy: str = "lru"
    enabled: bool = True


@dataclass
class WorkflowConfig:
    """工作流配置"""

    enabled: bool = True
    max_steps: int = 10
    timeout_seconds: int = 300
    enable_fallback: bool = True
    fallback_engine: str = "Rule"
    log_enabled: bool = True
    log_dir: str = "logs/workflows"


@dataclass
class EnvironmentConfig:
    """环境配置"""

    name: str = "development"
    debug: bool = True
    device_override: Optional[str] = None
    models_path_override: Optional[str] = None


@dataclass
class AppConfig:
    """应用根配置"""

    lnn: LNNConfig = field(default_factory=LNNConfig)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    environment: EnvironmentConfig = field(default_factory=EnvironmentConfig)
    dataset_cache: DatasetCacheConfig = field(default_factory=DatasetCacheConfig)


class YAMLConfigManager:
    """
    YAML配置管理器

    功能：
    - 从YAML文件加载配置
    - 验证配置结构和参数合法性
    - 提供类型安全的配置访问接口
    - 支持运行时动态更新配置
    - 将修改的配置持久化到文件系统
    - 根据运行环境自动调整配置
    """

    DEFAULT_CONFIG = {
        "lnn": {
            "enabled": True,
            "models_dir": "models/lnn",
            "default_device": "cpu",
            "models": {
                "cfc_fast": {
                    "type": "cfc",
                    "path": "cfc_fast_v1.pt",
                    "enabled": True,
                    "input_dim": 128,
                    "output_dim": 10,
                    "hidden_dim": 256,
                    "num_layers": 2,
                    "dropout_rate": 0.1,
                },
                "ltc_timeseries": {
                    "type": "ltc",
                    "path": "ltc_timeseries_v1.pt",
                    "enabled": True,
                    "input_dim": 64,
                    "output_dim": 32,
                    "hidden_dim": 128,
                    "num_layers": 2,
                    "dropout_rate": 0.1,
                    "temporal_horizon": 1000,
                },
                "hybrid_multimodal": {
                    "type": "hybrid_lnn",
                    "path": "hybrid_multimodal_v1.pt",
                    "enabled": True,
                    "input_dim": 256,
                    "output_dim": 10,
                    "hidden_dim": 512,
                    "num_layers": 3,
                    "dropout_rate": 0.1,
                },
                "cutting_force": {
                    "type": "cfc",
                    "path": "cutting_force_v1.pt",
                    "enabled": True,
                },
                "wear_prediction": {
                    "type": "ltc",
                    "path": "wear_prediction_v1.pt",
                    "enabled": True,
                },
            },
            "thresholds": {
                "quick": 0.85,
                "hybrid": 0.60,
                "complexity": 3,
            },
        },
        "workflow": {
            "enabled": True,
            "max_steps": 10,
            "timeout_seconds": 300,
            "enable_fallback": True,
            "fallback_engine": "Rule",
        },
        "dataset_cache": {
            "cache_directory": "~/.lingjing/cache/datasets/",
            "max_cache_size": 5368709120,
            "memory_cache_size": 1073741824,
            "cache_eviction_policy": "lru",
            "enabled": True,
        },
        "environment": {
            "name": "development",
            "debug": True,
        },
    }

    REQUIRED_LNN_KEYS = ["enabled", "models_dir", "default_device"]
    REQUIRED_MODEL_KEYS = ["type", "path"]
    REQUIRED_THRESHOLD_KEYS = ["quick", "hybrid", "complexity"]

    VALID_MODEL_TYPES = ["cfc", "ltc", "hybrid_lnn"]
    VALID_ENVIRONMENTS = ["development", "staging", "production", "testing"]

    def __init__(self, config_path: Optional[str] = None, use_defaults: bool = True):
        """
        初始化配置管理器

        Args:
            config_path: YAML配置文件路径
            use_defaults: 是否使用默认配置作为基础
        """
        self.config_path = config_path
        self._raw_config: Dict[str, Any] = {}
        self._config: AppConfig = AppConfig()
        self._last_modified: Optional[datetime] = None
        self._cache_enabled = True
        self._is_dirty = False

        if use_defaults:
            self._raw_config = copy.deepcopy(self.DEFAULT_CONFIG)

        if config_path:
            self.load(config_path)

        self._apply_environment_adaptations()
        self._build_config_object()

    def load(self, config_path: Optional[str] = None) -> None:
        """
        从YAML文件加载配置

        Args:
            config_path: YAML配置文件路径（可选，使用初始化时设置的路径）

        Raises:
            FileNotFoundError: 配置文件不存在
            yaml.YAMLError: YAML解析错误
            ValueError: 配置验证失败
        """
        path = config_path or self.config_path
        if not path:
            raise ValueError(
                "配置加载失败：未指定配置文件路径。请通过 config_manager.set_path('/path/to/config.json') 设置配置文件路径，或在初始化时传入 config_path 参数。"
            )

        if not os.path.exists(path):
            raise FileNotFoundError(
                f"配置加载失败：找不到配置文件 '{path}'。可能原因：1) 文件路径错误；2) 配置文件尚未创建。请检查路径是否正确，或调用 config_manager.create_default_config() 创建默认配置文件。"
            )

        try:
            with open(path, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f) or {}

            self._merge_config(loaded_config)
            self._validate_config()
            self._apply_environment_adaptations()
            self._build_config_object()

            self._last_modified = datetime.fromtimestamp(os.path.getmtime(path))
            self.config_path = path
            self._is_dirty = False

            logger.info("Configuration loaded from %s", path)

        except yaml.YAMLError as e:
            raise yaml.YAMLError(f"Failed to parse YAML config: {e}")
        except (OSError, FileNotFoundError, json.JSONDecodeError, ValueError) as e:
            logger.error("配置加载失败: %s", e, exc_info=True)
            if isinstance(e, (ValueError, FileNotFoundError)):
                raise
            raise RuntimeError(
                f"配置加载失败：解析配置文件时出现异常。错误详情: {e}。可能原因：1) 配置文件格式不正确（非 JSON/YAML 格式）；2) 配置文件内容有误；3) 文件编码不匹配。请检查配置文件语法、内容格式和文件编码。"
            ) from e

    def validate(self, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        验证配置结构和参数合法性

        Args:
            config: 要验证的配置字典（可选，默认验证当前配置）

        Returns:
            验证结果字典，包含valid字段和详细的errors/warnings
        """
        target_config = config or self._raw_config
        errors = []
        warnings = []

        errors.extend(self._validate_lnn_section(target_config.get("lnn", {})))
        errors.extend(
            self._validate_workflow_section(target_config.get("workflow", {}))
        )
        errors.extend(
            self._validate_environment_section(target_config.get("environment", {}))
        )

        if "lnn" in target_config:
            warnings.extend(self._check_lnn_best_practices(target_config["lnn"]))

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def get(self, section: str, key: Optional[str] = None, default: Any = None) -> Any:
        """
        获取配置值（类型安全）

        Args:
            section: 配置节名称（如 "lnn", "workflow"）
            key: 配置键（可选，为None时返回整个节）
            default: 默认值（当配置不存在时返回）

        Returns:
            配置值

        Examples:
            >>> config.get("lnn", "enabled")
            True
            >>> config.get("lnn", "thresholds", {}).get("quick")
            0.85
        """
        section_data = self._raw_config.get(section)
        if section_data is None:
            return default

        if key is None:
            return section_data

        if isinstance(key, str):
            keys = key.split(".")
        else:
            keys = [key]

        current = section_data
        for k in keys:
            if isinstance(current, dict):
                current = current.get(k)
                if current is None:
                    return default
            else:
                return default

        return current

    def set(self, section: str, key: str, value: Any) -> None:
        """
        动态更新配置参数

        Args:
            section: 配置节名称
            key: 配置键（支持点分隔的嵌套键，如 "thresholds.quick"）
            value: 新值

        Raises:
            ValueError: 配置值验证失败

        Examples:
            >>> config.set("lnn", "enabled", False)
            >>> config.set("lnn", "thresholds.quick", 0.90)
        """
        if section not in self._raw_config:
            self._raw_config[section] = {}

        # 验证配置值
        self._validate_config_value(section, key, value)

        if "." in key:
            keys = key.split(".")
            current = self._raw_config[section]
            for k in keys[:-1]:
                if k not in current or not isinstance(current[k], dict):
                    current[k] = {}
                current = current[k]
            current[keys[-1]] = value
        else:
            self._raw_config[section][key] = value

        self._is_dirty = True
        self._build_config_object()
        logger.debug("Config updated: %s.%s = %s", section, key, value)

    def _validate_config_value(self, section: str, key: str, value: Any) -> None:
        """验证单个配置值的合法性"""
        # 验证阈值范围
        if key == "quick" or key.endswith(".quick"):
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise ValueError(f"阈值 'quick' 必须在 0.0-1.0 范围内，实际值: {value}")
        elif key == "hybrid" or key.endswith(".hybrid"):
            if not isinstance(value, (int, float)) or not (0.0 <= value <= 1.0):
                raise ValueError(f"阈值 'hybrid' 必须在 0.0-1.0 范围内，实际值: {value}")
        elif key == "complexity" or key.endswith(".complexity"):
            if not isinstance(value, int) or value < 1:
                raise ValueError(f"复杂度 'complexity' 必须是正整数，实际值: {value}")
        
        # 验证设备类型
        elif key == "default_device":
            valid_devices = ["cpu", "cuda", "mps"]
            if not isinstance(value, str) or value not in valid_devices:
                raise ValueError(f"设备类型必须是 {valid_devices} 之一，实际值: {value}")
        
        # 验证环境名称
        elif key == "name" and section == "environment":
            if not isinstance(value, str) or value not in self.VALID_ENVIRONMENTS:
                raise ValueError(f"环境名称必须是 {self.VALID_ENVIRONMENTS} 之一，实际值: {value}")
        
        # 验证模型类型
        elif key == "type" and "models" in section:
            if not isinstance(value, str) or value not in self.VALID_MODEL_TYPES:
                raise ValueError(f"模型类型必须是 {self.VALID_MODEL_TYPES} 之一，实际值: {value}")

    def save(self, output_path: Optional[str] = None) -> None:
        """
        将配置持久化到文件系统

        Args:
            output_path: 输出路径（可选，默认使用加载时的路径）

        Raises:
            ValueError: 没有指定输出路径
            IOError: 写入文件失败
        """
        target_path = output_path or self.config_path
        if not target_path:
            raise ValueError(
                "配置保存失败：未指定输出文件路径。请通过 config_manager.set_path('/path/to/config.json') 设置保存路径，或在调用 save() 时传入 output_path 参数。"
            )

        try:
            output_dir = os.path.dirname(target_path)
            if output_dir and not os.path.exists(output_dir):
                os.makedirs(output_dir, exist_ok=True)

            with open(target_path, "w", encoding="utf-8") as f:
                yaml.dump(
                    self._raw_config,
                    f,
                    default_flow_style=False,
                    allow_unicode=True,
                    sort_keys=False,
                )

            self._is_dirty = False
            self._last_modified = datetime.now(timezone.utc)
            logger.info("Configuration saved to %s", target_path)

        except IOError as e:
            raise IOError(
                f"配置保存失败：无法将配置写入文件。错误详情: {e}。可能原因：1) 磁盘空间不足；2) 目标目录无写入权限；3) 文件被其他进程占用。请检查磁盘状态和目录权限。"
            ) from e

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典格式"""
        return copy.deepcopy(self._raw_config)

    def to_dataclass(self) -> AppConfig:
        """获取类型安全的配置对象"""
        return self._config

    def is_dirty(self) -> bool:
        """检查配置是否有未保存的修改"""
        return self._is_dirty

    def reset_to_defaults(self) -> None:
        """重置配置为默认值"""
        self._raw_config = copy.deepcopy(self.DEFAULT_CONFIG)
        self._apply_environment_adaptations()
        self._build_config_object()
        self._is_dirty = True
        logger.info("Configuration reset to defaults")

    def get_model_config(self, model_name: str) -> Optional[ModelConfig]:
        """
        获取指定模型的配置

        Args:
            model_name: 模型名称

        Returns:
            ModelConfig对象或None
        """
        models = self._raw_config.get("lnn", {}).get("models", {})
        model_data = models.get(model_name)
        if model_data is None:
            return None

        return ModelConfig(
            type=model_data.get("type", "cfc"),
            path=model_data.get("path", ""),
            enabled=model_data.get("enabled", True),
            device=model_data.get("device", self._config.lnn.default_device),
            input_dim=model_data.get("input_dim", 128),
            output_dim=model_data.get("output_dim", 10),
            hidden_dim=model_data.get("hidden_dim", 256),
            num_layers=model_data.get("num_layers", 2),
            dropout_rate=model_data.get("dropout_rate", 0.1),
            temporal_horizon=model_data.get("temporal_horizon", 1000),
            metadata=model_data.get("metadata"),
        )

    def add_model(self, model_name: str, model_config: Dict[str, Any]) -> None:
        """
        添加新模型配置

        Args:
            model_name: 模型名称
            model_config: 模型配置字典
        """
        if "lnn" not in self._raw_config:
            self._raw_config["lnn"] = {"models": {}}
        if "models" not in self._raw_config["lnn"]:
            self._raw_config["lnn"]["models"] = {}

        self._raw_config["lnn"]["models"][model_name] = model_config
        self._is_dirty = True
        self._build_config_object()
        logger.info("Model config added: %s", model_name)

    def remove_model(self, model_name: str) -> bool:
        """
        移除模型配置

        Args:
            model_name: 模型名称

        Returns:
            是否成功移除
        """
        models = self._raw_config.get("lnn", {}).get("models", {})
        if model_name in models:
            del self._raw_config["lnn"]["models"][model_name]
            self._is_dirty = True
            self._build_config_object()
            logger.info("Model config removed: %s", model_name)
            return True
        return False

    def get_dataset_cache_config(self) -> DatasetCacheConfig:
        """
        获取数据集缓存配置

        Returns:
            DatasetCacheConfig对象
        """
        return self._config.dataset_cache

    def set_dataset_cache_config(self, config: DatasetCacheConfig) -> None:
        """
        设置数据集缓存配置

        Args:
            config: DatasetCacheConfig对象
        """
        self._raw_config["dataset_cache"] = {
            "cache_directory": config.cache_directory,
            "max_cache_size": config.max_cache_size,
            "memory_cache_size": config.memory_cache_size,
            "cache_eviction_policy": config.cache_eviction_policy,
            "enabled": config.enabled,
        }
        self._is_dirty = True
        self._build_config_object()
        logger.info("Dataset cache config updated")

    def _merge_config(self, loaded_config: Dict[str, Any]) -> None:
        """合并加载的配置到现有配置"""
        self._raw_config = self._deep_merge(self._raw_config, loaded_config)

    def _deep_merge(self, base: Dict, override: Dict) -> Dict:
        """深度合并两个字典"""
        result = base.copy()
        for key, value in override.items():
            if (
                key in result
                and isinstance(result[key], dict)
                and isinstance(value, dict)
            ):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _validate_config(self) -> None:
        """验证当前配置，失败时抛出异常"""
        result = self.validate()
        if not result["valid"]:
            error_msg = (
                "配置验证失败：以下配置项不符合要求:\n"
                + "\n".join(f"  - {e}" for e in result["errors"])
                + "\n\n请检查配置文件中的相关字段，或参考文档了解各配置项的合法取值范围。"
            )
            raise ValueError(error_msg)

    def _validate_lnn_section(self, lnn_config: Dict[str, Any]) -> List[str]:
        """验证LNN配置节"""
        errors = []

        for key in self.REQUIRED_LNN_KEYS:
            if key not in lnn_config:
                errors.append(f"Missing required LNN key: {key}")

        if "default_device" in lnn_config:
            device = lnn_config["default_device"]
            valid_devices = ["cpu", "cuda", "mps", "auto"]
            if device not in valid_devices:
                errors.append(
                    f"Invalid default_device: {device}. Must be one of {valid_devices}"
                )

        if "models" in lnn_config:
            models = lnn_config["models"]
            if not isinstance(models, dict):
                errors.append("LNN models must be a dictionary")
            else:
                for model_name, model_config in models.items():
                    if not isinstance(model_config, dict):
                        errors.append(
                            f"Model config for '{model_name}' must be a dictionary"
                        )
                        continue

                    for key in self.REQUIRED_MODEL_KEYS:
                        if key not in model_config:
                            errors.append(
                                f"Missing required key '{key}' for model '{model_name}'"
                            )

                    if "type" in model_config:
                        model_type = model_config["type"].lower()
                        if model_type not in self.VALID_MODEL_TYPES:
                            errors.append(
                                f"Invalid model type '{model_type}' for model '{model_name}'. "
                                f"Must be one of {self.VALID_MODEL_TYPES}"
                            )

        if "thresholds" in lnn_config:
            thresholds = lnn_config["thresholds"]
            if not isinstance(thresholds, dict):
                errors.append("LNN thresholds must be a dictionary")
            else:
                for key in self.REQUIRED_THRESHOLD_KEYS:
                    if key not in thresholds:
                        errors.append(f"Missing required threshold key: {key}")

                if "quick" in thresholds:
                    val = thresholds["quick"]
                    if not isinstance(val, (int, float)) or not (0 <= val <= 1):
                        errors.append(
                            "Threshold 'quick' must be a float between 0 and 1"
                        )

                if "hybrid" in thresholds:
                    val = thresholds["hybrid"]
                    if not isinstance(val, (int, float)) or not (0 <= val <= 1):
                        errors.append(
                            "Threshold 'hybrid' must be a float between 0 and 1"
                        )

        return errors

    def _validate_workflow_section(self, workflow_config: Dict[str, Any]) -> List[str]:
        """验证工作流配置节"""
        errors = []

        if "max_steps" in workflow_config:
            val = workflow_config["max_steps"]
            if not isinstance(val, int) or val < 1:
                errors.append("Workflow max_steps must be a positive integer")

        if "timeout_seconds" in workflow_config:
            val = workflow_config["timeout_seconds"]
            if not isinstance(val, int) or val < 1:
                errors.append("Workflow timeout_seconds must be a positive integer")

        return errors

    def _validate_environment_section(self, env_config: Dict[str, Any]) -> List[str]:
        """验证环境配置节"""
        errors = []

        if "name" in env_config:
            name = env_config["name"]
            if name not in self.VALID_ENVIRONMENTS:
                errors.append(
                    f"Invalid environment name: {name}. Must be one of {self.VALID_ENVIRONMENTS}"
                )

        return errors

    def _check_lnn_best_practices(self, lnn_config: Dict[str, Any]) -> List[str]:
        """检查LNN配置最佳实践"""
        warnings = []

        if lnn_config.get("default_device") == "cuda" and HAS_TORCH:
            if not torch.cuda.is_available():
                warnings.append("CUDA device specified but CUDA is not available")

        if lnn_config.get("enabled", True):
            models = lnn_config.get("models", {})
            if not models:
                warnings.append("LNN is enabled but no models are configured")

        return warnings

    def _apply_environment_adaptations(self) -> None:
        """根据运行环境自动调整配置"""
        env_name = self._raw_config.get("environment", {}).get("name", "development")
        env_config = self._raw_config.get("environment", {})

        if env_name == "production":
            self._raw_config.setdefault("lnn", {})["enabled"] = True
            self._raw_config.setdefault("environment", {})["debug"] = False
            if "default_device" not in self._raw_config.get("lnn", {}):
                self._raw_config["lnn"]["default_device"] = (
                    "cuda" if HAS_TORCH and torch.cuda.is_available() else "cpu"
                )

        elif env_name == "development":
            self._raw_config.setdefault("lnn", {})["enabled"] = True
            self._raw_config.setdefault("environment", {})["debug"] = True

        elif env_name == "testing":
            self._raw_config.setdefault("lnn", {})["enabled"] = True
            self._raw_config.setdefault("workflow", {})["timeout_seconds"] = 60

        device_override = env_config.get("device_override")
        if device_override:
            self._raw_config.setdefault("lnn", {})["default_device"] = device_override

        models_override = env_config.get("models_path_override")
        if models_override and "lnn" in self._raw_config:
            self._raw_config["lnn"]["models_dir"] = models_override

    def _build_config_object(self) -> None:
        """从原始配置字典构建类型安全的AppConfig对象"""
        lnn_data = self._raw_config.get("lnn", {})
        workflow_data = self._raw_config.get("workflow", {})
        env_data = self._raw_config.get("environment", {})

        models = {}
        for name, model_data in lnn_data.get("models", {}).items():
            models[name] = ModelConfig(
                type=model_data.get("type", "cfc"),
                path=model_data.get("path", ""),
                enabled=model_data.get("enabled", True),
                device=model_data.get("device", lnn_data.get("default_device", "cpu")),
                input_dim=model_data.get("input_dim", 128),
                output_dim=model_data.get("output_dim", 10),
                hidden_dim=model_data.get("hidden_dim", 256),
                num_layers=model_data.get("num_layers", 2),
                dropout_rate=model_data.get("dropout_rate", 0.1),
                metadata=model_data.get("metadata"),
            )

        threshold_data = lnn_data.get("thresholds", {})
        thresholds = ThresholdConfig(
            quick=threshold_data.get("quick", 0.85),
            hybrid=threshold_data.get("hybrid", 0.60),
            complexity=threshold_data.get("complexity", 3),
            fallback=threshold_data.get("fallback", 0.50),
            confidence=threshold_data.get("confidence", 0.70),
        )

        lnn_config = LNNConfig(
            enabled=lnn_data.get("enabled", True),
            models_dir=lnn_data.get("models_dir", "models/lnn"),
            default_device=lnn_data.get("default_device", "cpu"),
            models=models,
            thresholds=thresholds,
            cache_size=lnn_data.get("cache_size", 10),
            enable_amp=lnn_data.get("enable_amp", True),
            max_retry_count=lnn_data.get("max_retry_count", 3),
        )

        workflow_config = WorkflowConfig(
            enabled=workflow_data.get("enabled", True),
            max_steps=workflow_data.get("max_steps", 10),
            timeout_seconds=workflow_data.get("timeout_seconds", 300),
            enable_fallback=workflow_data.get("enable_fallback", True),
            fallback_engine=workflow_data.get("fallback_engine", "Rule"),
            log_enabled=workflow_data.get("log_enabled", True),
            log_dir=workflow_data.get("log_dir", "logs/workflows"),
        )

        env_config = EnvironmentConfig(
            name=env_data.get("name", "development"),
            debug=env_data.get("debug", True),
            device_override=env_data.get("device_override"),
            models_path_override=env_data.get("models_path_override"),
        )

        dataset_cache_data = self._raw_config.get("dataset_cache", {})
        dataset_cache_config = DatasetCacheConfig(
            cache_directory=dataset_cache_data.get(
                "cache_directory", "~/.lingjing/cache/datasets/"
            ),
            max_cache_size=dataset_cache_data.get(
                "max_cache_size", 5 * 1024 * 1024 * 1024
            ),
            memory_cache_size=dataset_cache_data.get(
                "memory_cache_size", 1024 * 1024 * 1024
            ),
            cache_eviction_policy=dataset_cache_data.get(
                "cache_eviction_policy", "lru"
            ),
            enabled=dataset_cache_data.get("enabled", True),
        )

        self._config = AppConfig(
            lnn=lnn_config,
            workflow=workflow_config,
            environment=env_config,
            dataset_cache=dataset_cache_config,
        )
