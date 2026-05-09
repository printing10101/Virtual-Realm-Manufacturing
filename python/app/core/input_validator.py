"""
输入验证模块
提供材料、尺寸、公差等输入的验证和清理功能
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class ValidationErrorDetail:
    """验证错误详情"""
    field: str
    message: str
    value: Any = None

    def to_response(self) -> dict[str, Any]:
        """转换为响应格式"""
        return {
            "field": self.field,
            "message": self.message,
            "value": self.value,
        }


def validate_and_clean(
    content: str,
    field_name: str = "content",
    max_length: int = 10000
) -> tuple[str, Optional[ValidationErrorDetail]]:
    """
    验证并清理字符串输入

    Args:
        content: 输入内容
        field_name: 字段名称
        max_length: 最大长度

    Returns:
        tuple: (清理后的内容, 错误详情)
    """
    if not isinstance(content, str):
        return "", ValidationErrorDetail(
            field=field_name,
            message="输入必须为字符串",
            value=content,
        )

    cleaned = content.strip()
    if len(cleaned) > max_length:
        return cleaned[:max_length], ValidationErrorDetail(
            field=field_name,
            message=f"输入长度超过限制{max_length}",
            value=cleaned,
        )

    return cleaned, None


class MaterialValidator:
    """材料验证器"""

    VALID_MATERIALS = [
        "45钢",
        "6061铝合金",
        "304不锈钢",
        "HT200灰铸铁",
        "40Cr",
        "T8钢",
        "紫铜",
        "黄铜",
    ]

    @classmethod
    def validate(cls, material: str, strict: bool = False) -> Optional[ValidationErrorDetail]:
        if not material or not material.strip():
            return ValidationErrorDetail(
                field="material",
                message="材料不能为空",
                value=material,
            )

        if strict and material not in cls.VALID_MATERIALS:
            return ValidationErrorDetail(
                field="material",
                message=f"未知材料类型: {material}，有效材料: {', '.join(cls.VALID_MATERIALS)}",
                value=material,
            )

        if material not in cls.VALID_MATERIALS:
            logger.warning("未知材料类型: %s，允许通过但建议验证", material)

        return None


class SizeValidator:
    """尺寸验证器"""

    @classmethod
    def validate(
        cls,
        dimensions: dict[str, Any]
    ) -> tuple[dict[str, Any], Optional[ValidationErrorDetail]]:
        """
        验证尺寸参数

        Args:
            dimensions: 尺寸字典，包含length/width/height

        Returns:
            tuple: (清理后的尺寸, 错误详情)
        """
        if not isinstance(dimensions, dict):
            return {}, ValidationErrorDetail(
                field="dimensions",
                message="尺寸必须为字典",
                value=dimensions,
            )

        cleaned = {}
        for key in ["length", "width", "height"]:
            value = dimensions.get(key, 0)
            try:
                numeric_value = float(value)
                if numeric_value <= 0:
                    return {}, ValidationErrorDetail(
                        field=f"dimensions.{key}",
                        message=f"尺寸{key}必须大于0",
                        value=value,
                    )
                cleaned[key] = numeric_value
            except (ValueError, TypeError):
                return {}, ValidationErrorDetail(
                    field=f"dimensions.{key}",
                    message=f"尺寸{key}必须为数值",
                    value=value,
                )

        return cleaned, None


class ToleranceValidator:
    """公差验证器"""

    VALID_TOLERANCES = [
        "IT5",
        "IT6",
        "IT7",
        "IT8",
        "IT9",
        "IT10",
        "IT11",
        "IT12",
    ]

    @classmethod
    def validate(
        cls,
        tolerance: str
    ) -> Optional[ValidationErrorDetail]:
        """验证公差等级"""
        if not tolerance or not tolerance.strip():
            return ValidationErrorDetail(
                field="tolerance",
                message="公差不能为空",
                value=tolerance,
            )

        tolerance_upper = tolerance.upper().strip()
        if tolerance_upper not in cls.VALID_TOLERANCES:
            return ValidationErrorDetail(
                field="tolerance",
                message=f"无效公差等级: {tolerance}",
                value=tolerance,
            )

        return None
