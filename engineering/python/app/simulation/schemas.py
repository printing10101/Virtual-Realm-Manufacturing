# 修复（2026-08-03 任务B）：原文件缺失 pydantic/typing 导入，运行时 NameError、
# mypy 报 478 条 name-defined 中的大量条目。该文件未被引用但属真实缺陷，补全导入。
from typing import List

from pydantic import BaseModel, Field

from app.simulation.voxel_cutter.models import VoxelSimulationResult


class SimulationRequest(BaseModel):
    """Request model for voxel cutting simulation.

    Contains all parameters needed to run a machining simulation including
    project identification, tool geometry, G-code toolpath, and stock model.

    Attributes:
        project_id: Project identifier for associating simulation jobs.
        voxel_size: Voxel resolution in mm (0.1-10.0). Smaller = higher accuracy.
        tool_diameter: Tool diameter in mm (0.5-300.0).
        tool_length: Tool cutting length in mm (1.0-500.0).
        tool_type: Tool type - "flat" (flat end mill), "ball" (ball nose), "drill".
        tool_corner_radius: Tool corner radius in mm (0.0-150.0).
        gcode: G-code text content for toolpath parsing.
        safe_z_height: Safe plane height in mm (0.0-200.0).
        stock_stl_path: Path to stock STL file (relative or absolute).
        source_file_path: Source file path (STEP/DXF) for auto-regeneration if STL is missing.
    """

    project_id: str = Field(
        default="default",
        description="Project ID for associating simulation jobs.",
    )
    voxel_size: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Voxel resolution in mm. Smaller values yield higher accuracy.",
    )
    tool_diameter: float = Field(
        default=10.0,
        ge=0.5,
        le=300.0,
        description="Tool diameter in mm.",
    )
    tool_length: float = Field(
        default=50.0,
        ge=1.0,
        le=500.0,
        description="Tool cutting length in mm.",
    )
    tool_type: str = Field(
        default="flat",
        pattern="^(flat|ball|drill)$",
        description="Tool type: flat (flat end mill), ball (ball nose), drill.",
    )
    tool_corner_radius: float = Field(
        default=0.0,
        ge=0.0,
        le=150.0,
        description="Tool corner radius in mm.",
    )
    gcode: str = Field(
        default="",
        description="G-code text content for toolpath parsing.",
    )
    safe_z_height: float = Field(
        default=10.0,
        ge=0.0,
        le=200.0,
        description="Safe plane height in mm.",
    )
    stock_stl_path: str = Field(
        default="",
        description="Path to stock STL file (server-relative or absolute).",
    )
    source_file_path: str = Field(
        default="",
        description="Source file path (STEP/DXF) for auto-regeneration when STL is missing.",
    )


class SimulationResponse(BaseModel):
    """Response model containing voxel simulation results.

    Attributes:
        task_id: Unique simulation task identifier.
        stock_stl_url: URL path to the machined workpiece STL file.
        collision_collided: Whether any collision was detected.
        collision_positions: List of [x, y, z] collision coordinates.
        collision_segment_indices: Indices of toolpath segments with collisions.
        collision_severity: Collision severity level ("none"/"warning"/"critical").
        duration_seconds: Total simulation time in seconds.
        voxel_count: Total number of voxels in the stock model.
        removed_voxel_count: Number of voxels removed during simulation.
        voxel_size: Voxel resolution used (mm).
        original_bbox: Original stock bounding box dimensions.
        toolpath_segment_count: Number of toolpath segments processed.
    """

    task_id: str = ""
    stock_stl_url: str = ""
    collision_collided: bool = False
    collision_positions: list[list[float]] = []
    collision_segment_indices: list[int] = []
    collision_severity: str = "none"
    duration_seconds: float = 0.0
    voxel_count: int = 0
    removed_voxel_count: int = 0
    voxel_size: float = 1.0
    original_bbox: dict[str, float] | None = None
    toolpath_segment_count: int = 0

    @classmethod
    def from_result(cls, r: VoxelSimulationResult) -> "SimulationResponse":
        """Create a SimulationResponse from a VoxelSimulationResult.

        Args:
            r: The voxel simulation result to convert.

        Returns:
            A SimulationResponse populated with result data.
        """
        return cls(
            task_id=r.task_id,
            stock_stl_url=r.stock_stl_url,
            collision_collided=r.collision.collided,
            collision_positions=r.collision.collision_positions,
            collision_segment_indices=r.collision.collision_segment_indices,
            collision_severity=r.collision.collision_severity,
            duration_seconds=r.duration_seconds,
            voxel_count=r.voxel_count,
            removed_voxel_count=r.removed_voxel_count,
            voxel_size=r.voxel_size,
            original_bbox=r.original_bbox,
            toolpath_segment_count=r.toolpath_segment_count,
        )


class SimulationStatusResponse(BaseModel):
    """Response model for simulation task status queries.

    Attributes:
        task_id: The simulation task identifier.
        status: Current task status ("pending"/"running"/"completed").
        progress: Task completion progress (0.0-1.0).
        result: Simulation result data, available only when completed.
    """

    task_id: str = ""
    status: str = "pending"
    progress: float = 0.0
    result: SimulationResponse | None = None


