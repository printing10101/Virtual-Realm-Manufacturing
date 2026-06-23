"""体素化切削仿真引擎。

基于numpy体素化算法实现材料去除仿真。
核心流程：体素化毛坯 → 刀具几何体素化 → 遍历刀位点 → 体素切削 → 重建网格。
"""

from app.simulation.voxel_cutter.cutter import VoxelCutter
from app.simulation.voxel_cutter.mesher import ToolModel
from app.simulation.voxel_cutter.models import (
    CollisionInfo,
    VoxelSimulationResult,
)

__all__ = [
    "VoxelCutter",
    "ToolModel",
    "CollisionInfo",
    "VoxelSimulationResult",
]
