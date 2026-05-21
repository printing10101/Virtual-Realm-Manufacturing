"""后处理器注册表与工厂模式实现。

提供后处理器的注册、查找、实例化机制，
支持基于配置文件动态选择和加载后处理器。
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Type

from app.postprocessor.base import BasePostProcessor
from app.postprocessor.config_loader import ConfigLoader
from app.postprocessor.fanuc import FanucPostProcessor
from app.postprocessor.siemens import SiemensPostProcessor
from app.postprocessor.heidenhain import HeidenhainPostProcessor

logger = logging.getLogger(__name__)


class PostProcessorRegistry:
    """后处理器注册表单例。

    管理所有已注册的CNC后处理器类型，
    支持动态注册新类型和基于配置文件的实例化。

    Attributes:
        _instance: 单例实例
        _processors: 已注册的后处理器类型映射
        _instances: 已创建的实例缓存
        _config_loader: 配置加载器实例
    """

    _instance: Optional[PostProcessorRegistry] = None

    def __new__(cls) -> PostProcessorRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._processors: dict[str, Type[BasePostProcessor]] = {}
            cls._instance._instances: dict[str, BasePostProcessor] = {}
            cls._instance._config_loader = ConfigLoader()
            cls._instance._register_builtin()
        return cls._instance

    def _register_builtin(self) -> None:
        """注册内置后处理器类型。"""
        self._processors["fanuc_0i"] = FanucPostProcessor
        self._processors["siemens_840d"] = SiemensPostProcessor
        self._processors["heidenhain_tnc"] = HeidenhainPostProcessor

    def register(
        self,
        controller_id: str,
        processor_cls: Type[BasePostProcessor],
    ) -> None:
        """注册新的后处理器类型。

        Args:
            controller_id: 控制器标识符
            processor_cls: 后处理器类（必须继承自BasePostProcessor）

        Raises:
            TypeError: 如果processor_cls不是BasePostProcessor的子类
        """
        if not issubclass(processor_cls, BasePostProcessor):
            raise TypeError(
                f"processor_cls must be a subclass of BasePostProcessor, "
                f"got {processor_cls.__name__}"
            )
        self._processors[controller_id] = processor_cls
        logger.info(
            "Registered post-processor: %s -> %s", controller_id, processor_cls.__name__
        )

    def get_processor(
        self,
        controller_id: str,
        **config: Any,
    ) -> BasePostProcessor:
        """获取或创建后处理器实例。

        Args:
            controller_id: 控制器标识符
            **config: 传递给后处理器构造函数的配置参数（支持旧版接口）

        Returns:
            后处理器实例

        Raises:
            KeyError: 如果指定的控制器类型未注册
        """
        config_key = f"{controller_id}:{sorted(config.items())}"
        if config_key in self._instances:
            return self._instances[config_key]

        processor_cls = self._processors.get(controller_id)
        if processor_cls is None:
            available = ", ".join(self._processors.keys())
            raise KeyError(
                f"Unknown controller type: '{controller_id}'. Available: {available}"
            )

        instance = processor_cls(**config)
        self._instances[config_key] = instance
        return instance

    def list_controllers(self) -> list[str]:
        """列出所有已注册的控制器类型。"""
        return list(self._processors.keys())

    def clear_instances(self) -> None:
        """清除所有已创建的实例缓存。"""
        self._instances.clear()

    def load_from_config(
        self,
        config_path: Optional[str] = None,
        use_cache: bool = True,
    ) -> BasePostProcessor:
        """从配置文件加载并实例化后处理器。

        使用ConfigLoader加载YAML配置，合并基础配置和控制器特定配置，
        验证配置完整性，并将完整配置传递给后处理器。

        Args:
            config_path: YAML配置文件路径，默认查找"config/postprocessor_config.yaml"
            use_cache: 是否使用配置缓存

        Returns:
            配置好的后处理器实例

        Raises:
            FileNotFoundError: 如果配置文件不存在
            ConfigLoadError: 配置加载失败
            ConfigValidationError: 配置验证失败
        """
        merged_config = self._config_loader.load(
            config_path=config_path,
            use_cache=use_cache,
        )

        controller_id = merged_config.get("_controller_id", "fanuc")

        controller_map = {
            "fanuc": "fanuc_0i",
            "siemens": "siemens_840d",
            "heidenhain": "heidenhain_tnc",
        }
        full_id = controller_map.get(controller_id, "fanuc_0i")

        decimal_places = merged_config.get("decimal_places", 3)
        safe_z_height = float(merged_config.get("safe_z_height", 50.0))
        rapid_feed = float(merged_config.get("rapid_feed", 10000))

        instance = self.get_processor(
            full_id,
            decimal_places=decimal_places,
            safe_z_height=safe_z_height,
            rapid_feed=rapid_feed,
            config=merged_config,
        )

        logger.info(
            "Loaded post-processor from config: %s (%s) with full configuration",
            full_id,
            controller_id,
        )
        return instance

    def reload_config(self, config_path: Optional[str] = None) -> BasePostProcessor:
        """强制重新加载配置并返回新实例。

        清除所有缓存后重新加载配置。

        Args:
            config_path: 配置文件路径

        Returns:
            新配置的后处理器实例
        """
        self.clear_instances()
        self._config_loader.clear_cache()
        return self.load_from_config(config_path=config_path, use_cache=False)
