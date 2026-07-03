"""FastAPI router for DNC machine communication endpoints.

This module provides REST API endpoints for managing CNC machine connections,
querying real-time status, transferring NC programs, and retrieving alarm
information. It supports both OPC UA and MTConnect protocols.

Example::

    from fastapi import FastAPI
    from app.api.v1.dnc import router

    app = FastAPI()
    app.include_router(router)
"""

from __future__ import annotations

import logging
from typing import Optional
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field

from app.auth.permissions import require_permission

from app.dnc.dnc_manager import dnc_manager, ProtocolType
from app.core.response import success, error, ErrorCode

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/dnc",
    tags=["DNC 机床通信"],
    dependencies=[Depends(require_permission("dnc:read"))],
    responses={
        500: {"description": "Internal server error"},
    },
)


# ── 请求/响应模型 ──────────────────────────────────────────────

class MachineConnectRequest(BaseModel):
    """机床连接请求模型。

    Attributes:
        machine_id: 机床唯一标识
        protocol: 通信协议（opcua / mtconnect）
        endpoint: 连接端点
        username: 认证用户名（可选）
        password: 认证密码（可选）
        device_name: MTConnect 设备名称（可选，默认 Device）
    """
    machine_id: str = Field(..., description="机床唯一标识", examples=["CNC-001"])
    protocol: ProtocolType = Field(..., description="通信协议", examples=["opcua"])
    endpoint: str = Field(..., description="连接端点", examples=["opc.tcp://192.168.1.100:4840"])
    username: Optional[str] = Field(None, description="认证用户名")
    password: Optional[str] = Field(None, description="认证密码")
    device_name: Optional[str] = Field("Device", description="MTConnect 设备名称")


class NCSendRequest(BaseModel):
    """NC 程序发送请求模型。

    Attributes:
        machine_id: 目标机床 ID
        program_path: 本地 NC 程序文件路径
        program_name: 机床端存储的程序名（可选，默认使用文件名）
    """
    machine_id: str = Field(..., description="目标机床 ID", examples=["CNC-001"])
    program_path: str = Field(..., description="本地 NC 程序文件路径", examples=["/path/to/program.nc"])
    program_name: Optional[str] = Field(None, description="机床端存储的程序名（默认使用文件名）")


# ── API 路由 ──────────────────────────────────────────────────

@router.post("/machines", summary="添加机床连接")
async def connect_machine(req: MachineConnectRequest):
    """
    连接一台数控机床到 DNC 系统。

    支持 OPC UA 和 MTConnect 两种协议。
    """
    ok = await dnc_manager.add_machine(
        machine_id=req.machine_id,
        protocol=req.protocol,
        endpoint=req.endpoint,
        username=req.username,
        password=req.password,
        device_name=req.device_name,
    )
    if ok:
        return success(data={"machine_id": req.machine_id, "status": "connected"})
    return error(code=ErrorCode.INTERNAL_ERROR, message=f"无法连接到机床 {req.machine_id}")


@router.delete("/machines/{machine_id}", summary="移除机床连接")
async def disconnect_machine(machine_id: str):
    """断开并移除指定机床连接。"""
    await dnc_manager.remove_machine(machine_id)
    return success(data={"machine_id": machine_id, "status": "disconnected"})


@router.get("/machines", summary="列出已连接机床")
async def list_machines():
    """列出所有已连接的机床及其状态。"""
    machines = dnc_manager.list_machines()
    return success(data=machines)


@router.get("/machines/{machine_id}/status", summary="获取机床状态")
async def get_machine_status(machine_id: str):
    """获取指定机床的实时状态信息。"""
    status = await dnc_manager.get_machine_status(machine_id)
    if "error" in status:
        raise HTTPException(status_code=404, detail=status["error"])
    return success(data=status)


@router.get("/status", summary="获取所有机床状态")
async def get_all_status():
    """获取所有已连接机床的实时状态。"""
    all_status = await dnc_manager.get_all_machines_status()
    return success(data=all_status)


@router.post("/nc-program/send", summary="发送 NC 程序到机床")
async def send_nc_program(req: NCSendRequest):
    """
    将 NC 程序远程传输到指定机床。

    目前仅 OPC UA 协议支持程序传输。
    """
    # 验证文件存在
    program_path = Path(req.program_path)
    if not program_path.exists():
        raise HTTPException(status_code=400, detail=f"文件不存在: {req.program_path}")

    program_name = req.program_name or program_path.stem
    ok = await dnc_manager.send_nc_program(req.machine_id, str(program_path), program_name)
    if ok:
        return success(data={
            "machine_id": req.machine_id,
            "program_name": program_name,
            "status": "sent"
        })
    return error(code=ErrorCode.INTERNAL_ERROR, message="NC 程序发送失败")


@router.get("/machines/{machine_id}/alarms", summary="获取机床报警")
async def get_machine_alarms(machine_id: str):
    """获取指定机床的当前报警信息。"""
    # 目前仅 MTConnect 支持报警查询
    if machine_id not in dnc_manager.connections:
        raise HTTPException(status_code=404, detail=f"机床 {machine_id} 未连接")

    conn = dnc_manager.connections[machine_id]
    if conn["protocol"] == ProtocolType.MTCONNECT:
        alarms = await conn["client"].get_alarms()
        return success(data=alarms)
    else:
        return success(data=[], message="OPC UA 报警查询暂未实现")
