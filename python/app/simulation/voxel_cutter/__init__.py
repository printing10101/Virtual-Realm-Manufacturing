"""体素切割器仿真模块。"""

from app.simulation.voxel_cutter.cutter import (
    HAS_NUMBA,
    MAX_STL_RETRIES,
    STL_RETRY_INTERVAL,
    VoxelCutter,
    _apply_tool_mask_batch,
    _apply_tool_mask_single,
    _generate_stl_from_dxf,
    _generate_stl_from_step,
    _infer_source_paths,
)
from app.simulation.voxel_cutter.models import VoxelSimulationResult, CollisionInfo
from app.simulation.voxel_cutter.mesher import HAS_SKIMAGE, ToolModel, reconstruct_mesh

__all__ = [
    "VoxelCutter",
    "VoxelSimulationResult",
    "ToolModel",
    "CollisionInfo",
    "reconstruct_mesh",
    "_apply_tool_mask_single",
    "_apply_tool_mask_batch",
    "_generate_stl_from_step",
    "_generate_stl_from_dxf",
    "_infer_source_paths",
    "MAX_STL_RETRIES",
    "STL_RETRY_INTERVAL",
    "HAS_NUMBA",
    "HAS_SKIMAGE",
]
