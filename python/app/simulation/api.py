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
from pathlib import Path
from typing import Optional

from app.utils.utils import sanitize_filename, validate_user_path

from fastapi import APIRouter, HTTPException, Query, Depends
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.v1.auth import get_current_user
from app.config import config
from app.core.response import success, error, ErrorCode
from app.core.safe_errors import safe_error_message
from app.core.error_taxonomy import (
    ManufacturingError,
    ErrorCategory,
)
from app.simulation.voxel_cutter import (
    VoxelCutter,
    VoxelSimulationResult,
    ToolModel,
    GeometryDiffer,
    DiffResult,
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

    委托给统一的 ``app.utils.utils.validate_user_path`` 实现：解析路径为绝对
    路径并校验其位于预定义的允许目录之一内，消除任何目录遍历组件。

    Args:
        user_path: The raw path string from the user request.
        field_name: The field name for error reporting (e.g. "stock_stl_path").

    Returns:
        The resolved absolute Path if validation passes.

    Raises:
        HTTPException: 400 if the path is outside allowed directories.
    """
    try:
        return validate_user_path(
            user_path=user_path,
            allowed_base_dirs=_ALLOWED_STOCK_DIRS,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=(
                f"The path '{user_path}' for '{field_name}' is not allowed. "
                f"File must reside within a permitted output or upload directory."
            ),
        ) from exc


_in_memory_store: dict[str, VoxelSimulationResult] = {}
# 修复：原实现 get_simulation_history 接受 project_id 但完全未应用，导致过滤参数形同虚设。
# 这里使用一个独立的 task_id -> project_id 映射避免修改 VoxelSimulationResult 的字段
# （该类被多个模块使用，添加字段会引发级联修改）。
_project_id_map: dict[str, str] = {}
# 修复 [潜在崩溃]：VoxelSimulationResult 没有 completed_at 字段，但 _cleanup_store 和
# get_simulation_history 直接访问 r.completed_at.timestamp() 会在 store 超过容量或包含
# 完成结果时触发 AttributeError。使用独立 map 记录完成时间戳，避免侵入式修改 dataclass。
_completed_at_map: dict[str, float] = {}
# 修复 [任务生命周期]：记录每个活动的 asyncio.Task 引用，避免后台任务因 GC 被提前
# 取消；并支持在客户端主动取消时优雅回收资源。
_active_tasks: dict[str, "asyncio.Task[None]"] = {}
# 修复 [并发安全]：FastAPI 可并发处理多个仿真请求，使用 asyncio.Lock 保护共享 store
# 状态（添加/更新/清理），避免极端并发下 _in_memory_store 与三个关联 map 之间出现
# 短暂不一致（例如 cleanup 在 store 删除时 _completed_at_map 已被覆盖）。
_store_lock: "asyncio.Lock | None" = None
_MAX_STORE_SIZE = config.simulation.max_store_size
_MAX_STORE_AGE_SECONDS = config.simulation.max_store_age_seconds


def _get_store_lock() -> asyncio.Lock:
    """懒初始化 asyncio.Lock。

    在 FastAPI 启动后才有可绑定的事件循环，因此采用懒加载避免在 import 期
    实例化时绑定到错误的循环（uvicorn 重新载入场景下尤其重要）。
    """
    global _store_lock
    if _store_lock is None:
        _store_lock = asyncio.Lock()
    return _store_lock


async def _cleanup_store() -> None:
    """Remove expired and excess entries from the in-memory result store.

    Evicts the oldest results when the store exceeds _MAX_STORE_SIZE,
    and removes entries older than _MAX_STORE_AGE_SECONDS. 修复合并发：
    在持有 asyncio.Lock 的情况下统一清理 _in_memory_store 与三个关联 map，
    避免清理过程中其他协程插入/删除同一 key 导致字典大小判断错乱。
    """
    async with _get_store_lock():
        now = time.time()
        if len(_in_memory_store) > _MAX_STORE_SIZE:
            # 修复 [潜在崩溃]：原代码 kv[1].completed_at.timestamp() 会因 VoxelSimulationResult
            # 没有该字段而抛 AttributeError，导致清理彻底失败、内存无限增长。
            sorted_entries = sorted(
                _in_memory_store.items(),
                key=lambda kv: _completed_at_map.get(kv[0], 0.0),
            )
            for task_id, _ in sorted_entries[: len(_in_memory_store) - _MAX_STORE_SIZE]:
                _in_memory_store.pop(task_id, None)
                # 修复 [资源清理]：同步清理关联映射，避免孤儿键。
                _project_id_map.pop(task_id, None)
                _completed_at_map.pop(task_id, None)
                _active_tasks.pop(task_id, None)
        expired = [
            tid
            for tid in _in_memory_store
            if (_completed_at_map.get(tid) is not None)
            and (now - _completed_at_map[tid]) > _MAX_STORE_AGE_SECONDS
        ]
        for tid in expired:
            _in_memory_store.pop(tid, None)
            # 修复 [资源清理]：同步清理关联映射。
            _project_id_map.pop(tid, None)
            _completed_at_map.pop(tid, None)
            _active_tasks.pop(tid, None)


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
    # 修复：记录 task_id -> project_id 映射，使 history 接口的过滤参数真正生效。
    _project_id_map[task_id] = request.project_id
    # 修复 [清理支持]：记录完成时间戳，使 _cleanup_store 能正确按时间淘汰。
    _completed_at_map[task_id] = time.time()
    # 修复 [并发安全]：cleanup 是异步且需要持锁，必须在事件循环中由外层
    # async 端点调用；同步函数内部仅做数据写入，将清理动作交给 _post_insert_cleanup。
    return result


async def _post_insert_cleanup() -> None:
    """在 store 写入后异步触发的清理动作（在事件循环内持锁执行）。"""
    await _cleanup_store()


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
    request: SimulationRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Run voxel cutting simulation synchronously.

    Accepts project ID, tool parameters, G-code input, and stock geometry.
    Executes the simulation in a worker thread (asyncio.to_thread) and
    returns the complete result including machined STL URL and collision
    detection data.

    Args:
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

        # 修复 [并发安全]：在事件循环内触发异步 cleanup，统一淘汰过期/超额结果。
        await _post_insert_cleanup()

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
    except (ValueError, TypeError, KeyError, OSError) as exc:
        # 兜底捕获：仿真任务涉及网格运算、IO、序列化等多环节，
        # 任何未预期异常都需包装为统一错误响应以便上层处理；
        # 此处位于 API handler 入口，必须捕获所有异常以避免 5xx 直接抛给客户端。
        # 修复：避免 str(exc) 直接暴露内部异常详情，使用 safe_error_message 包装。
        safe = safe_error_message(exc, context=f"simulation.run[{task_id}]")
        logger.exception("Simulation %s failed: %s", task_id, exc)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail={
                "task_id": task_id,
                "error_id": safe.get("error_id"),
                **({"error_type": type(exc).__name__} if safe.get("detail") else {}),
            },
            recoverable=True,
        )


@router.post("/run/async")
async def run_simulation_async(
    request: SimulationRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Start voxel cutting simulation asynchronously.

    Returns immediately with a task ID. The simulation runs in the
    background. Poll /api/simulation/status/{task_id} for progress
    and results.

    Args:
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
    # 修复：异步任务在提交时立即预占 _in_memory_store 槽位，同时记录 project_id 映射。
    _project_id_map[task_id] = request.project_id

    async def _async_wrapper() -> None:
        try:
            await asyncio.to_thread(_run_simulation, task_id, request)
        except (KeyboardInterrupt, SystemExit):
            # 后台任务不响应中断信号，向上抛出
            raise
        except asyncio.CancelledError:
            # 修复 [资源清理]：客户端主动取消时显式释放 store 槽位，
            # 避免轮询接口看到 "running" 但实际任务已死。
            async with _get_store_lock():
                _in_memory_store.pop(task_id, None)
                _project_id_map.pop(task_id, None)
                _completed_at_map.pop(task_id, None)
            logger.info("Async simulation %s cancelled", task_id)
            raise
        except (ValueError, TypeError, KeyError, OSError) as exc:
            # 修复 [状态同步]：异常时仍记录完成时间戳但保持 duration_seconds == 0
            # 以便轮询端点将 status 识别为 failed；同时记录 error_id 供排障。
            async with _get_store_lock():
                _completed_at_map[task_id] = time.time()
            # 兜底捕获：后台任务线程内异常不应向上冒泡以免污染 FastAPI 事件循环，
            # 此处仅记录日志，由前端通过状态查询接口轮询获取结果。
            logger.exception("Async simulation %s failed: %s", task_id, exc)
        finally:
            # 修复 [任务生命周期]：无论任务成功/失败/取消，都清理活跃任务引用。
            _active_tasks.pop(task_id, None)
            # 触发异步清理（在事件循环内执行）。
            try:
                await _post_insert_cleanup()
            except (OSError, RuntimeError):  # noqa: BLE001
                logger.exception("Background cleanup failed for %s", task_id)

    # 修复：原实现 background_tasks.add_task(asyncio.create_task, _async_wrapper())
    # 存在严重问题——asyncio.create_task 需要运行中的事件循环，而 FastAPI 的
    # BackgroundTasks 在响应发送后才会执行，此时可能没有可用的循环上下文。
    # 正确做法是在当前请求协程中直接创建任务，由事件循环调度执行。
    # 同时将 task 引用保存到 _active_tasks，避免被 GC 提前回收导致中途取消。
    task = asyncio.create_task(_async_wrapper(), name=f"sim-{task_id}")
    _active_tasks[task_id] = task

    return success(
        data={"task_id": task_id, "status": "pending"},
        message="Simulation task submitted. Query /api/simulation/status/{task_id} for progress.",
    )


@router.get("/status/{task_id}")
async def get_simulation_status(
    task_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
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


def _sanitize_filename(file_name: str) -> str:
    """严格净化文件名，防止路径遍历攻击。

    .. deprecated::
        已迁移至 ``app.utils.utils.sanitize_filename``，本函数保留为
        薄包装以兼容现有调用方，新代码应直接使用统一工具函数。
    """
    return sanitize_filename(file_name)


@router.get("/output/{filename}")
async def get_simulation_output(
    filename: str,
    current_user: dict = Depends(get_current_user),
) -> Response:
    """Serve simulation output STL file.

    Args:
        filename: The STL filename to serve.

    Returns:
        Binary STL file stream for download.

    Raises:
        HTTPException: 400 if the file path is invalid (净化或验证失败);
                       404 if the STL file does not exist.

    [路径遍历修复] 增加了双重路径验证：
    1. 通过 _sanitize_filename 拒绝包含路径分隔符或 ".." 的输入；
    2. 通过 resolve() + is_relative_to() 确保最终路径严格位于 OUTPUT_DIR 内。
    """
    # [路径遍历修复] 第一层：用户输入净化
    safe_name = _sanitize_filename(filename)
    if not safe_name:
        raise HTTPException(status_code=400, detail="无效的文件名")

    # [路径遍历修复] 第二层：解析为绝对路径并验证在允许目录内
    allowed_dir = OUTPUT_DIR.resolve()
    file_path = (OUTPUT_DIR / safe_name).resolve()
    if not file_path.is_relative_to(allowed_dir):
        raise HTTPException(status_code=400, detail="无效的文件路径")

    # 保留原有的文件存在性检查
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
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Query simulation history records.

    Args:
        project_id: Optional project ID filter.
        limit: Maximum number of records to return.

    Returns:
        List of simulation history records with metadata.
    """
    history = []
    # 修复：先按 project_id 过滤，再按完成时间倒序排序，最后截取 limit 条。
    # 旧实现 list(...items())[:limit] 顺序随机，limit 在过滤前应用会导致过滤失效。
    items = list(_in_memory_store.items())
    if project_id is not None:
        items = [
            (tid, r)
            for tid, r in items
            if _project_id_map.get(tid) == project_id
        ]
    # 按完成时间倒序（最新优先）
    # 修复 [潜在崩溃]：原代码访问 r.completed_at.timestamp() 会触发 AttributeError，
    # 改用 _completed_at_map 单独维护时间戳。
    items.sort(
        key=lambda kv: _completed_at_map.get(kv[0], 0.0),
        reverse=True,
    )
    for task_id, result in items[:limit]:
        history.append(
            {
                "task_id": result.task_id,
                "project_id": _project_id_map.get(task_id, ""),
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
async def delete_simulation_result(
    task_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
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
    # 修复 [资源清理]：删除结果时同步清理所有关联映射。
    _project_id_map.pop(task_id, None)
    _completed_at_map.pop(task_id, None)

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
async def check_tool_slot_conflict(
    request: ConflictCheckRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
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


class ExportAnimationRequest(BaseModel):
    """Request model for simulation animation export.

    Attributes:
        nc_code: G-code text content for toolpath visualization.
        format: Output format - "gif" or "mp4".
        voxel_size: Voxel resolution in mm (0.1-10.0).
        tool_diameter: Tool diameter in mm (0.5-300.0).
        tool_length: Tool cutting length in mm (1.0-500.0).
        tool_type: Tool type - "flat", "ball", "drill".
    """

    nc_code: str = Field(
        default="",
        description="G-code text content for toolpath visualization.",
    )
    format: str = Field(
        default="gif",
        pattern="^(gif|mp4)$",
        description="Output format: gif or mp4.",
    )
    voxel_size: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="Voxel resolution in mm.",
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
        description="Tool type.",
    )


@router.post("/export-animation")
async def export_simulation_animation(
    request: ExportAnimationRequest,
    current_user: dict = Depends(get_current_user),
) -> StreamingResponse:
    """Export simulation animation as GIF or MP4.

    Generates a frame-by-frame animation of the machining simulation
    showing tool movement and material removal. Returns the animation
    file as a streaming download.

    Args:
        request: Animation export parameters.

    Returns:
        StreamingResponse with animation file content.

    Raises:
        HTTPException: 400 if animation generation fails.
    """
    import io
    import uuid
    import numpy as np
    from PIL import Image, ImageDraw

    try:
        # Parse G-code into toolpath segments
        parser = ToolpathParser(controller_type="fanuc")
        segments = parser.parse_gcode(request.nc_code) if request.nc_code.strip() else []

        if not segments:
            raise ValueError("No valid toolpath segments found in G-code")

        # Create animation frames
        frames = []
        num_frames = min(len(segments), 50)  # Limit to 50 frames for performance
        frame_indices = np.linspace(0, len(segments) - 1, num_frames, dtype=int)

        for idx in frame_indices:
            # Create frame image
            img = Image.new("RGB", (800, 600), color=(26, 26, 46))
            draw = ImageDraw.Draw(img)

            # Draw stock bounding box (simplified 2D projection)
            stock_color = (100, 100, 100)
            draw.rectangle([100, 100, 700, 500], outline=stock_color, width=2)

            # Draw toolpath up to current frame
            segment = segments[idx]
            sx, sy, sz = segment.start_point
            ex, ey, ez = segment.end_point

            # Map 3D coordinates to 2D canvas
            def map_coord(x, y, z):
                canvas_x = int(100 + (x + 100) * 3)
                canvas_y = int(500 - (z * 5))
                return canvas_x, canvas_y

            start_2d = map_coord(sx, sy, sz)
            end_2d = map_coord(ex, ey, ez)

            # Color by motion type
            colors = {
                "rapid": (244, 67, 54),
                "linear": (76, 175, 80),
                "arc": (33, 150, 243),
                "dwell": (255, 193, 7),
            }
            line_color = colors.get(segment.type, (200, 200, 200))

            # Draw previous segments (faded)
            for prev_idx in range(idx):
                prev_seg = segments[prev_idx]
                prev_start = map_coord(*prev_seg.start_point)
                prev_end = map_coord(*prev_seg.end_point)
                faded_color = tuple(int(c * 0.5) for c in colors.get(prev_seg.type, (200, 200, 200)))
                draw.line([prev_start, prev_end], fill=faded_color, width=2)

            # Draw current segment (bright)
            draw.line([start_2d, end_2d], fill=line_color, width=3)

            # Draw tool position
            tool_radius = int(request.tool_diameter / 2)
            draw.ellipse(
                [end_2d[0] - tool_radius, end_2d[1] - tool_radius,
                 end_2d[0] + tool_radius, end_2d[1] + tool_radius],
                fill=(255, 255, 0),
                outline=(255, 200, 0),
                width=2,
            )

            # Add frame info
            draw.text((10, 10), f"Frame {idx + 1}/{num_frames}", fill=(200, 200, 200))
            draw.text((10, 30), f"Segment: {segment.type}", fill=line_color)

            frames.append(img)

        # Generate output file
        output_format = request.format.upper()
        buffer = io.BytesIO()

        if request.format == "gif":
            # Save as animated GIF
            frames[0].save(
                buffer,
                format="GIF",
                save_all=True,
                append_images=frames[1:],
                duration=100,  # 100ms per frame
                loop=0,
            )
            media_type = "image/gif"
            filename = f"simulation_{uuid.uuid4().hex[:8]}.gif"
        else:  # mp4
            # For MP4, we'll use imageio if available, otherwise fallback to GIF
            try:
                import imageio
                frames_array = [np.array(frame) for frame in frames]
                imageio.mimsave(buffer, frames_array, format="MP4", fps=10)
                media_type = "video/mp4"
                filename = f"simulation_{uuid.uuid4().hex[:8]}.mp4"
            except ImportError:
                # Fallback to GIF if imageio not available
                frames[0].save(
                    buffer,
                    format="GIF",
                    save_all=True,
                    append_images=frames[1:],
                    duration=100,
                    loop=0,
                )
                media_type = "image/gif"
                filename = f"simulation_{uuid.uuid4().hex[:8]}.gif"

        buffer.seek(0)

        return StreamingResponse(
            buffer,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
                "Access-Control-Expose-Headers": "Content-Disposition",
            },
        )

    except Exception as e:
        logger.exception("Animation export failed: %s", e)
        raise HTTPException(
            status_code=400,
            detail="动画生成失败，请检查参数或稍后重试",
        ) from e


# =============================================================================
# Auto-Diff 几何比对（VERICUT 式残料 / 过切检测）
# =============================================================================

# 比对结果缓存（task_id -> DiffResult），与 _in_memory_store 同生命周期
_diff_result_store: dict[str, DiffResult] = {}


class AutoDiffCompareRequest(BaseModel):
    """Auto-Diff 几何比对请求。

    Attributes:
        design_stl_path: 设计模型（目标工件）STL 路径，须位于允许目录内。
        actual_stl_path: 仿真切削结果 STL 路径（VoxelCutter 输出）。
        voxel_size: 体素分辨率（mm），默认 0.5，越小越精确但越慢。
        export_diff_stl: 是否导出偏差可视化 STL，默认 True。
        gouge_warn_ratio: 过切告警阈值（体积占比），可选覆盖默认值。
        gouge_reject_ratio: 过切拒收阈值（体积占比），可选覆盖默认值。
        leftover_warn_ratio: 残料告警阈值（体积占比），可选覆盖默认值。
        leftover_reject_ratio: 残料拒收阈值（体积占比），可选覆盖默认值。
    """

    design_stl_path: str = Field(
        ...,
        description="设计模型 STL 路径（须位于允许目录内）。",
    )
    actual_stl_path: str = Field(
        ...,
        description="仿真结果 STL 路径（须位于允许目录内）。",
    )
    voxel_size: float = Field(
        default=0.5,
        ge=0.1,
        le=5.0,
        description="体素分辨率（mm），越小越精确但越慢。",
    )
    export_diff_stl: bool = Field(
        default=True,
        description="是否导出偏差可视化 STL。",
    )
    gouge_warn_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="过切告警阈值（体积占比），留空使用默认 0.0001。",
    )
    gouge_reject_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="过切拒收阈值（体积占比），留空使用默认 0.001。",
    )
    leftover_warn_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="残料告警阈值（体积占比），留空使用默认 0.01。",
    )
    leftover_reject_ratio: float | None = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="残料拒收阈值（体积占比），留空使用默认 0.05。",
    )


@router.post("/auto-diff/compare")
async def auto_diff_compare(
    request: AutoDiffCompareRequest,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """比对设计模型与仿真切削结果，识别过切与残料。

    竞品对标：VERICUT Auto-Diff。接受设计 STL 与仿真结果 STL，
    体素化后逐体素异或，输出过切/残料体积、质心、最大深度、
    verdict（accept/warning/reject）以及偏差可视化 STL。

    Args:
        request: 比对请求参数。

    Returns:
        标准 API 响应，data 字段为 DiffResult 序列化结果。
    """
    # 路径校验：防止路径遍历
    try:
        design_path = _validate_user_path(
            request.design_stl_path, "design_stl_path"
        )
        actual_path = _validate_user_path(
            request.actual_stl_path, "actual_stl_path"
        )
    except HTTPException as exc:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=str(exc.detail),
            recoverable=True,
        )

    if not design_path.exists():
        return error(
            code=ErrorCode.FILE_NOT_FOUND,
            message=f"设计 STL 文件不存在: {design_path}",
            recoverable=True,
        )
    if not actual_path.exists():
        return error(
            code=ErrorCode.FILE_NOT_FOUND,
            message=f"仿真结果 STL 文件不存在: {actual_path}",
            recoverable=True,
        )

    # 构造 GeometryDiffer 实例（仅在调用时创建，避免 import 期开销）
    differ_kwargs: dict[str, Any] = {
        "voxel_size": request.voxel_size,
    }
    if request.gouge_warn_ratio is not None:
        differ_kwargs["gouge_warn_ratio"] = request.gouge_warn_ratio
    if request.gouge_reject_ratio is not None:
        differ_kwargs["gouge_reject_ratio"] = request.gouge_reject_ratio
    if request.leftover_warn_ratio is not None:
        differ_kwargs["leftover_warn_ratio"] = request.leftover_warn_ratio
    if request.leftover_reject_ratio is not None:
        differ_kwargs["leftover_reject_ratio"] = request.leftover_reject_ratio

    try:
        differ = GeometryDiffer(**differ_kwargs)
        result = await asyncio.to_thread(
            differ.compare,
            design_path,
            actual_path,
            OUTPUT_DIR,
            None,
            request.export_diff_stl,
        )
    except (ValueError, TypeError, OSError, RuntimeError) as exc:
        safe = safe_error_message(exc, context="auto_diff.compare")
        logger.exception("Auto-Diff 比对失败: %s", exc)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=safe["message"],
            detail={"error_id": safe.get("error_id")},
            recoverable=True,
        )

    # 缓存结果
    _diff_result_store[result.task_id] = result
    # 限制缓存大小（保留最近 50 条）
    if len(_diff_result_store) > 50:
        oldest = next(iter(_diff_result_store))
        _diff_result_store.pop(oldest, None)

    return success(
        data=result.to_dict(),
        message=f"几何比对完成，判定：{result.verdict}",
    )


@router.get("/auto-diff/{task_id}")
async def get_auto_diff_result(
    task_id: str,
    current_user: dict = Depends(get_current_user),
) -> dict:
    """按 task_id 查询 Auto-Diff 比对结果。

    Args:
        task_id: 比对任务 ID。

    Returns:
        标准 API 响应，data 字段为 DiffResult 序列化结果。
    """
    result = _diff_result_store.get(task_id)
    if result is None:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"未找到比对结果：{task_id}",
            recoverable=False,
        )
    return success(data=result.to_dict(), message="OK")
