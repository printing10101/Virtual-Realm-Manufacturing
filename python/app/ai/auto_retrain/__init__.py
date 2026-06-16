"""模型自动微调流水线模块

提供自动化模型微调功能，包括：
- 定时调度触发机制
- 数据量阈值触发机制
- 训练数据准备与预处理
- 模型评估与版本管理

设计原则：
- 复用现有LNNTrainer，不修改训练算法
- 新模型必须评估达标才能注册
- 老模型不删除，保留N个历史版本
- 数据量不足时不触发微调
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.ai.auto_retrain.scheduler import AutoRetrainScheduler, get_scheduler
from app.ai.auto_retrain.data_prep import DataPreparator, get_data_preparator
from app.ai.auto_retrain.evaluator import ModelEvaluator, get_model_evaluator

logger = logging.getLogger(__name__)

__version__ = "1.0.0"

__all__ = [
    "AutoRetrainScheduler",
    "DataPreparator",
    "ModelEvaluator",
    "get_scheduler",
    "get_data_preparator",
    "get_model_evaluator",
]
