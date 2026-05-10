"""Input validation utilities for API endpoints."""
from __future__ import annotations

import os
import re
from typing import Any


def validate_cutting_parameters(
    cutting_speed: float,
    feed_rate: float,
    depth_of_cut: float,
) -> list[str]:
    errors = []
    if cutting_speed <= 0:
        errors.append("切削速度必须大于0")
    elif cutting_speed > 10000:
        errors.append("切削速度不能超过10000 m/min")
    if feed_rate <= 0:
        errors.append("进给量必须大于0")
    elif feed_rate > 50:
        errors.append("进给量不能超过50 mm/r")
    if depth_of_cut <= 0:
        errors.append("切削深度必须大于0")
    elif depth_of_cut > 100:
        errors.append("切削深度不能超过100 mm")
    return errors


def validate_prediction_horizon(horizon: float) -> list[str]:
    errors = []
    if horizon <= 0:
        errors.append("预测时长必须大于0")
    elif horizon > 86400:
        errors.append("预测时长不能超过24小时")
    return errors


def validate_training_params(
    model_name: str,
    dataset_path: str,
    epochs: int,
    batch_size: int,
    learning_rate: float,
    validation_split: float,
    model_type: str = "CFC",
) -> list[str]:
    errors = []
    if not model_name or not model_name.strip():
        errors.append("模型名称不能为空")
    elif not re.match(r'^[a-zA-Z0-9_\-]{1,64}$', model_name):
        errors.append("模型名称只能包含字母、数字、下划线和连字符，长度1-64")
    if not dataset_path:
        errors.append("数据集路径不能为空")
    elif not os.path.exists(dataset_path):
        errors.append(f"数据集路径不存在: {dataset_path}")
    if epochs <= 0 or epochs > 10000:
        errors.append("训练轮数必须在1-10000之间")
    if batch_size <= 0 or batch_size > 512:
        errors.append("批量大小必须在1-512之间")
    if learning_rate <= 0 or learning_rate > 1.0:
        errors.append("学习率必须在0-1之间")
    if not 0.0 <= validation_split <= 0.5:
        errors.append("验证集比例必须在0.0-0.5之间")
    valid_types = {"CFC", "LTC", "HYBRID", "cnn", "CNN"}
    if model_type.upper() not in valid_types:
        errors.append(f"不支持的模型类型: {model_type}")
    return errors


def sanitize_string(value: str, max_length: int = 256) -> str:
    return value.strip()[:max_length]


def validate_rag_query(query: str) -> list[str]:
    errors = []
    if not query or not query.strip():
        errors.append("查询文本不能为空")
    elif len(query) > 2000:
        errors.append("查询文本不能超过2000个字符")
    return errors


def validate_material_name(material: str) -> list[str]:
    errors = []
    if not material or not material.strip():
        errors.append("材料名称不能为空")
    elif len(material) > 100:
        errors.append("材料名称不能超过100个字符")
    return errors


def validate_file_path(path: str, must_exist: bool = True) -> list[str]:
    errors = []
    if not path:
        errors.append("文件路径不能为空")
        return errors
    normalized = os.path.normpath(path)
    if must_exist and not os.path.exists(normalized):
        errors.append(f"文件路径不存在: {path}")
    return errors


def coalesce(*values: Any) -> Any:
    """Return the first non-None value from the given arguments."""
    for v in values:
        if v is not None:
            return v
    return None