"""参数化零件生成器。

提供基于参数的零件几何生成和编辑功能。
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class ParametricGenerator:
    """参数化零件生成器。"""

    def __init__(self) -> None:
        """初始化参数化生成器。"""
        self._parameters: dict[str, Any] = {}

    def set_parameter(self, name: str, value: Any) -> None:
        """设置参数值。

        Args:
            name: 参数名称
            value: 参数值
        """
        self._parameters[name] = value
        logger.debug("Parameter set: %s = %s", name, value)

    def get_parameter(self, name: str, default: Any = None) -> Any:
        """获取参数值。

        Args:
            name: 参数名称
            default: 默认值

        Returns:
            参数值
        """
        return self._parameters.get(name, default)

    def generate_geometry(self, params: dict[str, Any] | None = None) -> Any:
        """生成参数化几何体。

        Args:
            params: 参数字典，为None时使用内部参数

        Returns:
            生成的几何体（CadQuery Workplane 或类似对象）
        """
        if params is not None:
            self._parameters.update(params)

        # 验证参数
        is_valid, errors = self.validate_parameters()
        if not is_valid:
            raise ValueError(f"参数验证失败: {', '.join(errors)}")

        # 获取几何参数
        shape_type = self._parameters.get("shape_type", "box")
        length = self._parameters.get("length", 10.0)
        width = self._parameters.get("width", 10.0)
        height = self._parameters.get("height", 10.0)
        radius = self._parameters.get("radius", 5.0)

        try:
            import cadquery as cq

            # 根据形状类型生成基础几何体
            if shape_type == "box":
                result = cq.Workplane("XY").box(length, width, height)
            elif shape_type == "cylinder":
                result = (
                    cq.Workplane("XY")
                    .circle(radius)
                    .extrude(height)
                )
            elif shape_type == "sphere":
                result = cq.Workplane("XY").sphere(radius)
            else:
                raise ValueError(f"不支持的形状类型: {shape_type}")

            logger.info("生成参数化几何体: %s", shape_type)
            return result

        except ImportError:
            logger.warning("CadQuery 未安装，返回简化几何表示")
            # 返回简化的几何表示（用于测试或无 CadQuery 环境）
            return {
                "type": shape_type,
                "dimensions": {
                    "length": length,
                    "width": width,
                    "height": height,
                    "radius": radius,
                },
            }

    def validate_parameters(self) -> tuple[bool, list[str]]:
        """验证参数有效性。

        Returns:
            (是否有效, 错误信息列表)
        """
        errors: list[str] = []

        # 检查必需参数是否存在
        shape_type = self._parameters.get("shape_type", "box")
        if shape_type not in ["box", "cylinder", "sphere"]:
            errors.append(f"不支持的形状类型: {shape_type}")

        # 验证参数范围
        length = self._parameters.get("length", 10.0)
        width = self._parameters.get("width", 10.0)
        height = self._parameters.get("height", 10.0)
        radius = self._parameters.get("radius", 5.0)

        if length <= 0:
            errors.append(f"长度必须为正数，当前值: {length}")
        if width <= 0:
            errors.append(f"宽度必须为正数，当前值: {width}")
        if height <= 0:
            errors.append(f"高度必须为正数，当前值: {height}")
        if radius <= 0:
            errors.append(f"半径必须为正数，当前值: {radius}")

        # 检查参数依赖关系
        if shape_type in ["cylinder", "sphere"] and radius <= 0:
            errors.append(f"{shape_type} 形状需要有效的半径值")

        return len(errors) == 0, errors
