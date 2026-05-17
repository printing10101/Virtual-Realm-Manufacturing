"""仿真API接口。

提供体素化切削仿真的异步执行端点。
支持大模型文件仿真计算的异步处理。
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

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

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "output" / "simulation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

_in_memory_store: dict[str, VoxelSimulationResult] = {}
_MAX_STORE_SIZE = 500
_MAX_STORE_AGE_SECONDS = 86400


def _cleanup_store() -> None:
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
    project_id: str = Field(
        default="default",
        description="工程ID，用于关联当前工程项目",
    )
    voxel_size: float = Field(
        default=1.0,
        ge=0.1,
        le=10.0,
        description="体素分辨率(mm)，值越小精度越高",
    )
    tool_diameter: float = Field(
        default=10.0,
        ge=0.5,
        le=300.0,
        description="刀具直径(mm)",
    )
    tool_length: float = Field(
        default=50.0,
        ge=1.0,
        le=500.0,
        description="刀具刃长(mm)",
    )
    tool_type: str = Field(
        default="flat",
        pattern="^(flat|ball|drill)$",
        description="刀具类型: flat(平底刀), ball(球头刀), drill(钻头)",
    )
    tool_corner_radius: float = Field(
        default=0.0,
        ge=0.0,
        le=150.0,
        description="刀尖圆角半径(mm)",
    )
    gcode: str = Field(
        default="",
        description="G代码文本内容，用于刀轨解析",
    )
    safe_z_height: float = Field(
        default=10.0,
        ge=0.0,
        le=200.0,
        description="安全平面高度(mm)",
    )
    stock_stl_path: str = Field(
        default="",
        description="毛坯STL文件路径(服务端相对或绝对路径)",
    )


class SimulationResponse(BaseModel):
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
    def from_result(cls, r: VoxelSimulationResult) -> SimulationResponse:
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
    task_id: str = ""
    status: str = "pending"
    progress: float = 0.0
    result: SimulationResponse | None = None


def _run_simulation(
    task_id: str,
    request: SimulationRequest,
) -> VoxelSimulationResult:
    """执行体素化切削仿真(同步，供后台任务调用)。

    Args:
        task_id: 任务ID
        request: 仿真请求参数

    Returns:
        VoxelSimulationResult
    """
    tool = ToolModel(
        diameter=request.tool_diameter,
        length=request.tool_length,
        tool_type=request.tool_type,
        corner_radius=request.tool_corner_radius,
    )

    segments: list[ToolpathSegment] = []
    if request.gcode.strip():
        parser = ToolpathParser(controller_type="fanuc")
        segments = parser.parse_gcode(request.gcode)

    stock_stl_path = (
        Path(request.stock_stl_path) if request.stock_stl_path else _default_stock_stl()
    )

    cutter = VoxelCutter(voxel_size=request.voxel_size)
    result = cutter.run_simulation(
        stock_stl_path=stock_stl_path,
        tool=tool,
        segments=segments,
        output_dir=OUTPUT_DIR,
        safe_z_height=request.safe_z_height,
        task_id=task_id,
    )

    _in_memory_store[task_id] = result
    _cleanup_store()
    return result


def _build_response_data(result: VoxelSimulationResult) -> dict:
    """构建符合规范的API响应数据结构。"""
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
    """生成默认长方体毛坯STL文件。

    Returns:
        默认STL文件路径
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
    """运行体素化切削仿真。

    接受工程ID、刀具参数、G代码等输入，异步执行仿真计算。
    返回仿真任务ID、切削后STL URL、碰撞检测结果。

    Args:
        background_tasks: FastAPI后台任务管理器
        request: 仿真请求参数

    Returns:
        标准API响应，data中包含仿真结果
    """
    import uuid

    task_id = f"sim_{uuid.uuid4().hex[:12]}"

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
            message="仿真计算完成",
        )
    except MemoryError:
        logger.exception("Simulation %s failed: memory error", task_id)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="仿真计算内存不足，请增大体素尺寸或简化模型",
            detail={"task_id": task_id},
            recoverable=True,
        )
    except Exception as exc:
        logger.exception("Simulation %s failed: %s", task_id, exc)
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"仿真计算异常: {str(exc)}",
            detail={"task_id": task_id, "error_type": type(exc).__name__},
            recoverable=True,
        )


@router.post("/run/async")
async def run_simulation_async(
    background_tasks: BackgroundTasks,
    request: SimulationRequest,
) -> dict:
    """异步启动体素化切削仿真任务。

    立即返回任务ID，仿真在后台执行。
    通过 /api/simulation/status/{task_id} 查询进度和结果。

    Args:
        background_tasks: FastAPI后台任务管理器
        request: 仿真请求参数

    Returns:
        标准API响应，data中包含task_id
    """
    import uuid

    task_id = f"sim_{uuid.uuid4().hex[:12]}"

    _in_memory_store[task_id] = VoxelSimulationResult(task_id=task_id)

    async def _async_wrapper() -> None:
        try:
            await asyncio.to_thread(_run_simulation, task_id, request)
        except Exception as exc:
            logger.exception("Async simulation %s failed: %s", task_id, exc)

    background_tasks.add_task(asyncio.create_task, _async_wrapper())

    return success(
        data={"task_id": task_id, "status": "pending"},
        message="仿真任务已提交，使用 /api/simulation/status/{task_id} 查询进度",
    )


@router.get("/status/{task_id}")
async def get_simulation_status(task_id: str) -> dict:
    """查询仿真任务状态和结果。

    Args:
        task_id: 仿真任务ID

    Returns:
        任务状态、进度和结果数据
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
            message="任务不存在或已过期",
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
    """获取仿真输出的STL文件。

    Args:
        filename: STL文件名

    Returns:
        STL二进制数据流
    """
    file_path = OUTPUT_DIR / filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="STL文件不存在")

    return Response(
        content=file_path.read_bytes(),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Access-Control-Expose-Headers": "Content-Disposition",
        },
    )


@router.get("/history")
async def get_simulation_history(
    project_id: Optional[str] = Query(default=None, description="工程ID过滤"),
    limit: int = Query(default=50, ge=1, le=200, description="返回记录数上限"),
) -> dict:
    """查询仿真历史记录。

    Args:
        project_id: 按工程ID过滤(可选)
        limit: 最大返回记录数

    Returns:
        仿真历史记录列表
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
    """删除仿真结果。

    Args:
        task_id: 仿真任务ID

    Returns:
        操作结果
    """
    if task_id in _in_memory_store:
        del _in_memory_store[task_id]

    stl_file = OUTPUT_DIR / f"sim_result_{task_id}.stl"
    if stl_file.exists():
        stl_file.unlink()

    return success(message=f"仿真结果 {task_id} 已删除")


class ConflictCheckRequest(BaseModel):
    tool_diameter: float = Field(
        default=20.0,
        ge=0.5,
        le=300.0,
        description="刀具直径(mm)",
    )
    slot_width: float = Field(
        default=10.0,
        ge=0.1,
        le=500.0,
        description="槽宽(mm)",
    )
    material: str = Field(
        default="45钢",
        description="工件材料",
    )
    operation: str = Field(
        default="槽铣",
        description="加工工序",
    )


@router.post("/check-conflict")
async def check_tool_slot_conflict(request: ConflictCheckRequest) -> dict:
    tool_d = request.tool_diameter
    slot_w = request.slot_width

    if tool_d > slot_w:
        raise ManufacturingError(
            category=ErrorCategory.NO_SUITABLE_TOOL,
            detail=(
                f"刀具直径({tool_d}mm)大于槽宽({slot_w}mm)，"
                f"无法进入槽内进行加工。当前材料：{request.material}，工序：{request.operation}"
            ),
            suggestion=(
                f"刀具直径({tool_d}mm)超出槽宽({slot_w}mm)限制。"
                f"建议方案：1) 更换刀具，选用直径≤{slot_w}mm的立铣刀；"
                f"2) 调整加工工艺，改用分层加工或多刀铣削策略；"
                f"3) 修改零件设计，增大槽宽至≥{tool_d}mm。"
            ),
            recoverable=False,
        )

    return success(
        data={
            "compatible": True,
            "tool_diameter": tool_d,
            "slot_width": slot_w,
        },
        message="刀具与槽型匹配，无冲突",
    )


@router.post("/trigger-system-error")
async def trigger_system_error() -> dict:
    result = 1 / 0
    return success(data={"result": result})
