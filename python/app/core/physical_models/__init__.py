"""
统一的物理模型模块

集中管理所有切削加工相关的物理公式和常量，消除分散在各处的重复实现。

包含：
- Kienzle 切削力模型
- Taylor 刀具寿命模型
- 表面粗糙度模型
"""

from .cutting_force import KienzleModel
from .tool_life import TaylorModel
from .surface_roughness import SurfaceRoughnessModel
