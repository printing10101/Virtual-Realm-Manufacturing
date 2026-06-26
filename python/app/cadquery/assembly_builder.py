"""装配体构建器。

提供多零件装配和约束管理功能。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AssemblyComponent:
    """装配体组件。"""

    name: str
    geometry: Any
    position: tuple[float, float, float] = (0.0, 0.0, 0.0)
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0)
    constraints: list[dict[str, Any]] = field(default_factory=list)


class AssemblyBuilder:
    """装配体构建器。"""

    def __init__(self) -> None:
        """初始化装配体构建器。"""
        self._components: dict[str, AssemblyComponent] = {}
        self._constraints: list[dict[str, Any]] = []

    def add_component(
        self,
        name: str,
        geometry: Any,
        position: tuple[float, float, float] | None = None,
        rotation: tuple[float, float, float] | None = None,
    ) -> AssemblyComponent:
        """添加组件到装配体。

        Args:
            name: 组件名称
            geometry: 组件几何体
            position: 位置坐标 (x, y, z)
            rotation: 旋转角度 (rx, ry, rz)

        Returns:
            创建的组件对象
        """
        component = AssemblyComponent(
            name=name,
            geometry=geometry,
            position=position or (0.0, 0.0, 0.0),
            rotation=rotation or (0.0, 0.0, 0.0),
        )
        self._components[name] = component
        logger.info("Component added: %s", name)
        return component

    def add_constraint(
        self,
        constraint_type: str,
        component1: str,
        component2: str,
        parameters: dict[str, Any] | None = None,
    ) -> None:
        """添加组件间约束。

        Args:
            constraint_type: 约束类型 (coincident, parallel, perpendicular, etc.)
            component1: 第一个组件名称
            component2: 第二个组件名称
            parameters: 约束参数
        """
        constraint = {
            "type": constraint_type,
            "component1": component1,
            "component2": component2,
            "parameters": parameters or {},
        }
        self._constraints.append(constraint)
        logger.debug(
            "Constraint added: %s between %s and %s",
            constraint_type,
            component1,
            component2,
        )

    def build(self) -> Any:
        """构建装配体。

        Returns:
            装配体对象
        """
        # 验证约束
        is_valid, errors = self.validate_constraints()
        if not is_valid:
            raise ValueError(f"约束验证失败: {', '.join(errors)}")

        try:
            import cadquery as cq

            # 创建 CadQuery Assembly
            assembly = cq.Assembly()

            # 添加所有组件到装配体
            for name, component in self._components.items():
                # 应用位置和旋转
                location = cq.Location(
                    cq.Vector(*component.position),
                    cq.Vector(1, 0, 0),
                    component.rotation[0],
                )
                assembly.add(
                    component.geometry,
                    name=name,
                    loc=location,
                )

            logger.info("Assembly built with %d components", len(self._components))
            return assembly

        except ImportError:
            logger.warning("CadQuery 未安装，返回简化装配表示")
            # 返回简化的装配表示（用于测试或无 CadQuery 环境）
            return {
                "type": "assembly",
                "components": [
                    {
                        "name": comp.name,
                        "position": comp.position,
                        "rotation": comp.rotation,
                    }
                    for comp in self._components.values()
                ],
                "constraints": self._constraints,
            }

    def validate_constraints(self) -> tuple[bool, list[str]]:
        """验证约束有效性。

        Returns:
            (是否有效, 错误信息列表)
        """
        errors: list[str] = []

        # Check all referenced components exist
        for constraint in self._constraints:
            comp1 = constraint["component1"]
            comp2 = constraint["component2"]
            if comp1 not in self._components:
                errors.append(f"Component '{comp1}' not found")
            if comp2 not in self._components:
                errors.append(f"Component '{comp2}' not found")

        return len(errors) == 0, errors

    def get_components(self) -> list[AssemblyComponent]:
        """获取所有组件。

        Returns:
            组件列表
        """
        return list(self._components.values())

    def get_constraints(self) -> list[dict[str, Any]]:
        """获取所有约束。

        Returns:
            约束列表
        """
        return self._constraints.copy()
