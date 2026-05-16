"""后处理器注册表与工厂模式实现。

提供后处理器的注册、查找、实例化机制，
支持基于配置文件动态选择和加载后处理器。
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Type

from app.postprocessor.base import BasePostProcessor
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
    """

    _instance: Optional[PostProcessorRegistry] = None

    def __new__(cls) -> PostProcessorRegistry:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._processors: dict[str, Type[BasePostProcessor]] = {}
            cls._instance._instances: dict[str, BasePostProcessor] = {}
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
            **config: 传递给后处理器构造函数的配置参数

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
    ) -> BasePostProcessor:
        """从配置文件加载并实例化后处理器。

        Args:
            config_path: YAML配置文件路径，默认查找"config/postprocessor_config.yaml"

        Returns:
            配置好的后处理器实例

        Raises:
            FileNotFoundError: 如果配置文件不存在
        """
        import os

        import yaml

        if config_path is None:
            project_root = os.path.dirname(
                os.path.dirname(
                    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                )
            )
            config_path = os.path.join(
                project_root, "config", "postprocessor_config.yaml"
            )

        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, "r", encoding="utf-8") as f:
            cfg = yaml.safe_load(f)

        controller_id = cfg.get("target_controller", "fanuc_0i")
        processor_config = {
            "decimal_places": cfg.get("decimal_places", 3),
            "safe_z_height": float(cfg.get("safe_z_height", 50.0)),
            "rapid_feed": float(cfg.get("rapid_feed", 10000)),
        }

        logger.info(
            "Loaded post-processor from config: %s with %s",
            controller_id,
            processor_config,
        )
        return self.get_processor(controller_id, **processor_config)
