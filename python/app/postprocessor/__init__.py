"""CNC后处理器模块——提供多控制器G代码生成能力。

核心导出：
- BasePostProcessor: 抽象基类，定义统一后处理接口
- FanucPostProcessor: Fanuc 0i系列后处理器
- SiemensPostProcessor: Siemens 840D后处理器
- HeidenhainPostProcessor: Heidenhain TNC后处理器
- PostProcessorRegistry: 后处理器注册表（单例工厂）
"""

from __future__ import annotations

from app.postprocessor.base import BasePostProcessor
from app.postprocessor.fanuc import FanucPostProcessor
from app.postprocessor.heidenhain import HeidenhainPostProcessor
from app.postprocessor.registry import PostProcessorRegistry
from app.postprocessor.siemens import SiemensPostProcessor

__all__ = [
    "BasePostProcessor",
    "FanucPostProcessor",
    "SiemensPostProcessor",
    "HeidenhainPostProcessor",
    "PostProcessorRegistry",
]
