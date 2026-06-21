"""CNC后处理器模块——提供多控制器G代码生成能力。

核心导出：
- BasePostProcessor: 抽象基类，定义统一后处理接口
- FanucPostProcessor: Fanuc 0i系列后处理器
- SiemensPostProcessor: Siemens 840D后处理器
- HeidenhainPostProcessor: Heidenhain TNC后处理器
- GSKPostProcessor: 广数 GSK 980/25i 后处理器
- HNCPostProcessor: 华中 HNC 848/22 后处理器
- KNDPostProcessor: 凯恩帝 KND 1000/2000/3000 后处理器
- MitsubishiPostProcessor: 三菱 M70/M80 后处理器
- FagorPostProcessor: 法格 Fagor 8055 后处理器
- PostProcessorRegistry: 后处理器注册表（单例工厂）
"""

from __future__ import annotations

from app.postprocessor.base import BasePostProcessor
from app.postprocessor.fagor import FagorPostProcessor
from app.postprocessor.fanuc import FanucPostProcessor
from app.postprocessor.gsk import GSKPostProcessor
from app.postprocessor.heidenhain import HeidenhainPostProcessor
from app.postprocessor.hnc import HNCPostProcessor
from app.postprocessor.knd import KNDPostProcessor
from app.postprocessor.mitsubishi import MitsubishiPostProcessor
from app.postprocessor.registry import PostProcessorRegistry
from app.postprocessor.siemens import SiemensPostProcessor

__all__ = [
    "BasePostProcessor",
    "FanucPostProcessor",
    "SiemensPostProcessor",
    "HeidenhainPostProcessor",
    "GSKPostProcessor",
    "HNCPostProcessor",
    "KNDPostProcessor",
    "MitsubishiPostProcessor",
    "FagorPostProcessor",
    "PostProcessorRegistry",
]
