"""Input validation utilities for API endpoints."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any, Optional, Sequence

# 允许的根目录白名单（防止路径遍历攻击）
# 调用方可通过环境变量 LNN_ALLOWED_ROOTS（逗号分隔）扩展；
# 默认包含 LNN_DATA_DIR / LNN_OUTPUT_DIR / LNN_UPLOAD_DIR 对应的 data/output/uploads
# 目录。环境变量在每次调用时动态读取，方便测试时按需调整。
_DEFAULT_ROOT_NAMES: tuple[str, str] = ("LNN_DATA_DIR", "LNN_OUTPUT_DIR", "LNN_UPLOAD_DIR")
_DEFAULT_FALLBACK_DIRS: tuple[str, ...] = ("data", "output", "uploads")


def _resolve_allowed_roots(
    extra_roots: Optional[Sequence[str]] = None,
) -> list[Path]:
    """合并默认与调用方提供的允许根目录。

    注意：环境变量在每次调用时读取，避免模块级 import-time 副作用
    影响测试场景（pytest 通过 monkeypatch.setenv 注入临时目录）。
    """
    roots: list[Path] = []
    for env_name in _DEFAULT_ROOT_NAMES:
        env_value = os.environ.get(env_name)
        if env_value:
            roots.append(Path(env_value).resolve())
    # 如果 env 中未设置任何白名单目录，则退回到 CWD 下的默认子目录
    if not roots:
        cwd = Path(os.getcwd()).resolve()
        for sub in _DEFAULT_FALLBACK_DIRS:
            roots.append(cwd / sub)
    if extra_roots:
        roots.extend(Path(r).resolve() for r in extra_roots)
    return roots


def _is_within_allowed_roots(resolved: Path, allowed_roots: Sequence[Path]) -> bool:
    """检查解析后的路径是否落在白名单根目录内。"""
    if not allowed_roots:
        return False
    for root in allowed_roots:
        try:
            resolved.relative_to(root)
            return True
        except ValueError:
            continue
    return False


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
    elif not re.match(r"^[a-zA-Z0-9_\-]{1,64}$", model_name):
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


def validate_file_path(
    path: str,
    must_exist: bool = True,
    allowed_roots: Optional[Sequence[str]] = None,
) -> list[str]:
    """校验文件路径，阻止路径遍历攻击。

    解析为绝对路径后，必须落在允许的根目录白名单内（含默认 data/output/uploads
    及调用方提供的扩展目录）。空路径、不存在路径（当 must_exist=True）、
    指向白名单外的路径均会被拒绝。
    """
    errors: list[str] = []
    if not path:
        errors.append("文件路径不能为空")
        return errors
    if not isinstance(path, str):
        errors.append("文件路径类型不合法")
        return errors

    try:
        resolved = Path(path).expanduser().resolve(strict=False)
    except (OSError, RuntimeError) as exc:
        errors.append(f"文件路径无法解析: {exc}")
        return errors

    roots = _resolve_allowed_roots(allowed_roots)
    if not _is_within_allowed_roots(resolved, roots):
        errors.append("文件路径不在允许的访问范围内")
        return errors

    if must_exist and not resolved.exists():
        errors.append(f"文件路径不存在: {path}")
    return errors


def coalesce(*values: Any) -> Any:
    """Return the first non-None value from the given arguments."""
    for v in values:
        if v is not None:
            return v
    return None
