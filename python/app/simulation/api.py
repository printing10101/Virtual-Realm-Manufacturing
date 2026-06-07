"""Simulation API endpoints for voxel-based machining simulation.

Provides asynchronous execution endpoints for voxel cutting simulation,
supporting large-file simulation computation with background task processing.
Clients can submit simulation requests with tool parameters, G-code, and
stock geometry, then poll for results via task ID.

Configuration sourced from app.config.SimulationConfig:
    _MAX_STORE_SIZE: Maximum number of in-memory cached results.
    _MAX_STORE_AGE_SECONDS: Maximum validity period for cached results.

Example:
    POST /api/simulation/run - Synchronous simulation execution.
    POST /api/simulation/run/async - Asynchronous simulation submission.
    GET /api/simulation/status/{task_id} - Query task status and results.
    GET /api/simulation/output/{filename} - Download STL output file.
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from app.config import config
from app.core.response import success, error, ErrorCode
from app.core.error_taxonomy import (
    ManufacturingError,
    ErrorCategory,
)
from app.simulation.voxel_cutter import (
    VoxelCutter,
    VoxelSimulationResult,
    ToolModel,
)
from app.simulation.toolpath_parser import ToolpathParser, ToolpathSegment

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/simulation", tags=["Simulation"])

OUTPUT_DIR = Path(config.storage.output_dir) / "simulation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# Allowed base directories for user-provided file path validation.
# These prevent path traversal attacks by restricting file access to
# known output and upload directories where files are legitimately stored.
_OUTPUT_ROOT = Path(config.storage.output_dir).resolve()
_ALLOWED_STOCK_DIRS: list[Path] = [
    OUTPUT_DIR.resolve(),
    (_OUTPUT_ROOT / "step_import").resolve(),
    (_OUTPUT_ROOT / "step_import" / "_uploads").resolve(),
    (_OUTPUT_ROOT / "dxf_import").resolve(),
    (_OUTPUT_ROOT / "dxf_import" / "_uploads").resolve(),
    (_OUTPUT_ROOT / "projects").resolve(),
    (_OUTPUT_ROOT / "projects" / "_uploads").resolve(),
]


def _validate_user_path(user_path: str, field_name: str) -> Path:
    """Validate that a user-provided file path is within allowed directories.

    Resolves the path to an absolute path and checks that it falls within
    one of the pre-defined allowed directories. Paths are resolved using
    Path.resolve() to eliminate any directory traversal components.

    Args:
        user_path: The raw path string from the user request.
        field_name: The field name for error reporting (e.g. "stock_stl_path").

    Returns:
        The resolved absolute Path if validation passes.

    Raises:
        HTTPException: 400 if the path is outside allowed directories.
    """
    p = Path(user_path)
    resolved = p.resolve()
    for allowed_dir in _ALLOWED_STOCK_DIRS:
        if resolved.is_relative_to(allowed_dir):
            return resolved
    raise HTTPException(
        status_code=400,
        detail=(
            f"The path '{user_path}' for '{field_name}' is not allowed. "
            f"File must reside within a permitted output or upload directory."
        ),
    )


_in_memory_store: dict[str, VoxelSimulationResult] = {}
_MAX_STORE_SIZE = config.simulation.max_store_size
_MAX_STORE_AGE_SECONDS = config.simulation.max_store_age_seconds


def _cleanup_store() -> None:
    """Remove expired and excess entries from the in-memory result store.

    Evicts the oldest results when the store exceeds _MAX_STORE_SIZE,
    and removes entries older than _MAX_STORE_AGE_SECONDS.
    """
    now = time.time()
    if len(_in_memory_store) > _MAX_STORE_SIZE:
        sorted_entries = sorted(
            _in_memory_store.items(),
            key=lambda kv: kv[1].completed_at.timestamp() if kv[1].completed_at else 0,
        )
        for task_id, _ in sorted_entries[: len(_in_memory_store) - _MAX_STORE_SIZE]:
            _in_memory_store.pop(task_id, None)
    expired = [
        tid
        for tid, r in _in_memory_store.items()
        if r.completed_at
        and (now - r.completed_at.timestamp()) > _MAX_STORE_AGE_SECONDS
    ]
    for tid in expired:
        _in_memory_store.pop(tid, None)


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


def _run_simulation(
    task_id: str,
    request: SimulationRequest,
) -> VoxelSimulationResult:
    """Execute voxel cutting simulation synchronously for background task use.

    Parses G-code into toolpath segments, constructs the tool model,
    loads or generates the stock STL, and runs the voxel-based simulation.

    Args:
        task_id: Unique identifier for the simulation task.
        request: Simulation request parameters.

    Returns:
        VoxelSimulationResult containing the machined model and collision data.
    """
    tool = ToolModel(
        diameter=request.tool_diameter,
        cutting_length=request.tool_length,
        tool_type=request.tool_type,
        corner_radius=request.tool_corner_radius,
    )

    segments: list[ToolpathSegment] = []
    if request.gcode.strip():
        parser = ToolpathParser(controller_type="fanuc")
        segments = parser.parse_gcode(request.gcode)

    if request.stock_stl_path:
        try:
            stock_stl_path = _validate_user_path(
                request.stock_stl_path, "stock_stl_path"
            )
        except HTTPException as exc:
            raise ValueError(str(exc.detail)) from exc
    else:
        stock_stl_path = _default_stock_stl()

    source_file_paths: list[Path] | None = None
    if request.source_file_path:
        try:
            source_path = _validate_user_path(
                request.source_file_path, "source_file_path"
            )
        except HTTPException as exc:
            raise ValueError(str(exc.detail)) from exc
        if source_path.exists():
            source_file_paths = [source_path]
        else:
            logger.warning(
                "[Auto-generate STL] Specified source file does not exist: %s",
                source_path,
            )

    cutter = VoxelCutter(voxel_size=request.voxel_size)
    result = cutter.run_simulation(
        stock_stl_path=stock_stl_path,
        tool=tool,
        segments=segments,
        output_dir=OUTPUT_DIR,
        safe_z_height=request.safe_z_height,
        task_id=task_id,
        source_file_paths=source_file_paths,
    )

    _in_memory_store[task_id] = result
    _cleanup_store()
    return result


def _build_response_data(result: VoxelSimulationResult) -> dict:
    """Build a structured API response dict from simulation results.

    Restructures the raw simulation result into the format expected by
    the API response schema, including collision details and simulation
    metrics.

    Args:
        result: The completed voxel simulation result.

    Returns:
        Dictionary formatted for API response with simulation_result,
        collision_details, and metadata sections.
    """
    base = SimulationResponse.from_result(result).model_dump()
    collision_positions = base.pop("collision_positions")
    collision_segment_indices = base.pop("collision_segment_indices")
    collision_severity = base.pop("collision_severity")
    return {
        **base,
        "collision_detected": base.pop("collision_collided"),
        "simulation_result": {
            "workpiece_stl_path": base.pop("stock_stl_url"),
            "voxel_count": base["voxel_count"],
            "removed_voxel_count": base["removed_voxel_count"],
            "voxel_size": base["voxel_size"],
            "original_bbox": base.pop("original_bbox"),
        },
        "collision_details": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "positions": collision_positions,
            "segment_indices": collision_segment_indices,
            "severity": collision_severity,
            "count": len(collision_positions),
        },
    }


def _default_stock_stl() -> Path:
    """Generate a default rectangular stock STL file.

    Creates a 150x100x40mm box if trimesh is available; otherwise
    returns an empty placeholder file.

    Returns:
        Path to the generated default STL file.
    """
    try:
        import trimesh
    except ImportError:
        fallback = OUTPUT_DIR / "_default_stock.stl"
        if not fallback.exists():
            fallback.write_bytes(b"")
        return fallback

    default_path = OUTPUT_DIR / "_default_stock.stl"
    if default_path.exists():
        return default_path

    box = trimesh.creation.box(extents=[150, 100, 40])
    box.apply_translation([0, 0, 20])
    box.export(str(default_path), file_type="stl")
    return default_path


@router.post("/run")
async def run_simulation(
    background_tasks: BackgroundTasks,
    request: SimulationRequest,
) -> dict:
    """Run voxel cutting simulation synchronously.

    Accepts project ID, tool parameters, G-code input, and stock geometry.
    Executes the simulation in a background thread and returns the complete
    result including machined STL URL and collision detection data.

    Args:
        background_tasks: FastAPI background task manager.
        request: Simulation request parameters.

    Returns:
        Standard API response with simulation result data.

    Raises:
        MemoryError: If simulation exceeds available memory.
    """
    import uuid

    task_id = f"sim_{uuid.uuid4().hex[:12]}"

    if request.stock_stl_path:
        _validate_user_path(request.stock_stl_path, "stock_stl_path")
        stl_path = Path(request.stock_stl_path)
        if not stl_path.exists():
            source_path = None
            if request.source_file_path:
                _validate_user_path(request.source_file_path, "source_file_path")
                source_path = Path(request.source_file_path)
            if source_path is not None and not source_path.exists():
                logger.error(
                    "[Auto-generate STL] Both STL and source file not found: STL=%s, source=%s",
                    stl_path,
                    source_path,
                )
                return error(
                    code=ErrorCode.FILE_NOT_FOUND,
                    message="STL file and source file both not found.",
                    detail={
                        "stl_path": str(stl_path),
                        "source_file_path": str(source_path),
                        "error_type": "STL_FILE_MISSING",
                    },
                    suggestion="Please generate the stock STL via STEP/DXF import first.",
                    severity="error",
                    recoverable=True,
                )

    try:
        start = time.perf_counter()
        result = await asyncio.to_thread(_run_simulation, task_id, request)
        elapsed = time.perf_counter() - start

        logger.info(
            "Simulation %s completed in %.2fs, collision=%s, removed=%d voxels",
            task_id,
            elapsed,
            result.collision.collided,
            result.removed_voxel_count,
        )

        response_data = _build_response_data(result)
        return success(
            data=response_data,
            message="Simulation completed.",
        )
    except MemoryError:
        logger.exception("Simulation %s failed: memory error", task_id)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="Insufficient memory. Increase voxel size or simplify the model.",
            detail={"task_id": task_id},
            recoverable=True,
        )
    except Exception as exc:
        logger.exception("Simulation %s failed: %s", task_id, exc)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"Simulation error: {str(exc)}",
            detail={"task_id": task_id, "error_type": type(exc).__name__},
            recoverable=True,
        )


@router.post("/run/async")
async def run_simulation_async(
    background_tasks: BackgroundTasks,
    request: SimulationRequest,
) -> dict:
    """Start voxel cutting simulation asynchronously.

    Returns immediately with a task ID. The simulation runs in the
    background. Poll /api/simulation/status/{task_id} for progress
    and results.

    Args:
        background_tasks: FastAPI background task manager.
        request: Simulation request parameters.

    Returns:
        Standard API response with task_id and initial status.
    """
    import uuid

    task_id = f"sim_{uuid.uuid4().hex[:12]}"

    # Validate user-provided paths before scheduling the background task
    if request.stock_stl_path:
        _validate_user_path(request.stock_stl_path, "stock_stl_path")
    if request.source_file_path:
        _validate_user_path(request.source_file_path, "source_file_path")

    _in_memory_store[task_id] = VoxelSimulationResult(task_id=task_id)

    async def _async_wrapper() -> None:
        try:
            await asyncio.to_thread(_run_simulation, task_id, request)
        except Exception as exc:
            logger.exception("Async simulation %s failed: %s", task_id, exc)

    background_tasks.add_task(asyncio.create_task, _async_wrapper())

    return success(
        data={"task_id": task_id, "status": "pending"},
        message="Simulation task submitted. Query /api/simulation/status/{task_id} for progress.",
    )


@router.get("/status/{task_id}")
async def get_simulation_status(task_id: str) -> dict:
    """Query simulation task status and results.

    Args:
        task_id: The simulation task identifier.

    Returns:
        Standard API response with task status, progress, and result data.
    """
    result = _in_memory_store.get(task_id)

    if result is None:
        return success(
            data={
                "task_id": task_id,
                "status": "not_found",
                "progress": 0.0,
                "result": None,
            },
            message="Task not found or expired.",
        )

    is_complete = result.duration_seconds > 0 or result.voxel_count > 0
    status = "completed" if is_complete else "running"

    progress = 1.0 if is_complete else 0.5

    return success(
        data={
            "task_id": result.task_id,
            "status": status,
            "progress": progress,
            "result": (_build_response_data(result) if is_complete else None),
        },
        message="OK",
    )


@router.get("/output/{filename}")
async def get_simulation_output(filename: str) -> Response:
    """Serve simulation output STL file.

    Args:
        filename: The STL filename to serve.

    Returns:
        Binary STL file stream for download.

    Raises:
        HTTPException: 404 if the STL file does not exist.
        HTTPException: 400 if the file path is invalid.
    """
    safe_name = PurePosixPath(filename).name
    file_path = (OUTPUT_DIR / safe_name).resolve()
    if not file_path.is_relative_to(OUTPUT_DIR.resolve()):
        raise HTTPException(status_code=400, detail="无效的文件路径")
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="STL file not found.")

    return Response(
        content=file_path.read_bytes(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/history")
async def get_simulation_history(
    project_id: Optional[str] = Query(default=None, description="Filter by project ID."),
    limit: int = Query(default=50, ge=1, le=200, description="Maximum number of records."),
) -> dict:
    """Query simulation history records.

    Args:
        project_id: Optional project ID filter.
        limit: Maximum number of records to return.

    Returns:
        List of simulation history records with metadata.
    """
    history = []
    for task_id, result in list(_in_memory_store.items())[:limit]:
        history.append(
            {
                "task_id": result.task_id,
                "duration_seconds": result.duration_seconds,
                "collision_collided": result.collision.collided,
                "voxel_size": result.voxel_size,
                "segment_count": result.toolpath_segment_count,
            }
        )

    return success(
        data={
            "total": len(history),
            "items": history,
        },
        message="OK",
    )


@router.delete("/result/{task_id}")
async def delete_simulation_result(task_id: str) -> dict:
    """Delete a simulation result from cache and disk.

    Removes the in-memory result entry and deletes the associated
    STL output file if present.

    Args:
        task_id: The simulation task identifier to delete.

    Returns:
        Standard API response confirming deletion.
    """
    if task_id in _in_memory_store:
        del _in_memory_store[task_id]

    stl_file = OUTPUT_DIR / f"sim_result_{task_id}.stl"
    if stl_file.exists():
        stl_file.unlink()

    return success(message=f"Simulation result {task_id} deleted.")


class ConflictCheckRequest(BaseModel):
    """Request model for tool-slot compatibility check.

    Attributes:
        tool_diameter: Tool diameter in mm (0.5-300.0).
        slot_width: Slot width in mm (0.1-500.0).
        material: Workpiece material (e.g., "45 steel").
        operation: Machining operation type (e.g., "slot milling").
    """

    tool_diameter: float = Field(
        default=20.0,
        ge=0.5,
        le=300.0,
        description="Tool diameter in mm.",
    )
    slot_width: float = Field(
        default=10.0,
        ge=0.1,
        le=500.0,
        description="Slot width in mm.",
    )
    material: str = Field(
        default="45 steel",
        description="Workpiece material.",
    )
    operation: str = Field(
        default="slot milling",
        description="Machining operation type.",
    )


@router.post("/check-conflict")
async def check_tool_slot_conflict(request: ConflictCheckRequest) -> dict:
    """Check tool-slot diameter compatibility.

    Validates whether the specified tool can physically fit within
    the given slot width for machining.

    Args:
        request: Tool-slot conflict check parameters.

    Returns:
        Standard API response with compatibility result.

    Raises:
        ManufacturingError: If tool diameter exceeds slot width.
    """
    tool_d = request.tool_diameter
    slot_w = request.slot_width

    if tool_d > slot_w:
        raise ManufacturingError(
            category=ErrorCategory.NO_SUITABLE_TOOL,
            detail=(
                f"Tool diameter ({tool_d}mm) exceeds slot width ({slot_w}mm). "
                f"Cannot enter the slot for machining. Material: {request.material}, "
                f"Operation: {request.operation}"
            ),
            suggestion=(
                f"Tool diameter ({tool_d}mm) exceeds slot width ({slot_w}mm) limit. "
                f"Suggested solutions: "
                f"1) Use a smaller tool (diameter <= {slot_w}mm); "
                f"2) Change to multi-pass or layered machining strategy; "
                f"3) Redesign the part to widen the slot to >= {tool_d}mm."
            ),
            recoverable=False,
        )

    return success(
        data={
            "compatible": True,
            "tool_diameter": tool_d,
            "slot_width": slot_w,
        },
        message="Tool and slot are compatible, no conflicts.",
    )
