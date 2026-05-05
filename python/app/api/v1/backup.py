"""
灵境制造 - 数据备份与恢复 API
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.core.response import ErrorCode, error, success
from app.services.backup_service import BackupService

router = APIRouter(prefix="/api/v1/backup", tags=["数据备份"])

backup_service = BackupService()


class ImportRequest(BaseModel):
    """导入备份请求"""
    backup_path: str = Field(..., description="备份文件路径")
    selective: bool = Field(default=False, description="是否选择性恢复")
    include_items: list[str] | None = Field(default=None, description="要恢复的项目列表")


class DeleteRequest(BaseModel):
    """删除备份请求"""
    backup_path: str = Field(..., description="备份文件路径")


@router.post("/auto-backup")
async def trigger_auto_backup() -> dict[str, Any]:
    """触发自动备份"""
    try:
        backup_path = backup_service.auto_backup()
        if backup_path:
            return success(
                data={"backup_path": backup_path},
                message="自动备份完成"
            )
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="自动备份失败"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"自动备份失败: {e!s}"
        )


@router.post("/export")
async def export_all_data() -> dict[str, Any]:
    """导出所有数据"""
    try:
        export_path = backup_service.export_all()
        return success(
            data={"export_path": export_path},
            message="数据导出完成"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"数据导出失败: {e!s}"
        )


@router.post("/import")
async def import_backup_data(request: ImportRequest) -> dict[str, Any]:
    """从备份导入数据"""
    try:
        results = backup_service.import_backup(
            backup_path=request.backup_path,
            selective=request.selective,
            include_items=request.include_items
        )
        return success(
            data={"results": results},
            message="数据导入完成"
        )
    except FileNotFoundError:
        return error(
            code=ErrorCode.NOT_FOUND,
            message=f"备份文件不存在: {request.backup_path}"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"数据导入失败: {e!s}"
        )


@router.get("/list")
async def list_backups() -> dict[str, Any]:
    """查看备份列表"""
    try:
        backups = backup_service.list_backups()
        return success(
            data={"backups": backups},
            message="获取备份列表成功"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取备份列表失败: {e!s}"
        )


@router.delete("/delete")
async def delete_backup(request: DeleteRequest) -> dict[str, Any]:
    """删除备份"""
    try:
        success_flag = backup_service.delete_backup(request.backup_path)
        if success_flag:
            return success(message="删除备份成功")
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message="删除备份失败"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"删除备份失败: {e!s}"
        )


@router.post("/cleanup")
async def cleanup_old_backups(days: int = 7) -> dict[str, Any]:
    """清理旧备份"""
    try:
        deleted_count = backup_service.delete_old_backups(days)
        return success(
            data={"deleted_count": deleted_count},
            message=f"清理了 {deleted_count} 个旧备份"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"清理旧备份失败: {e!s}"
        )


@router.get("/status")
async def get_backup_status() -> dict[str, Any]:
    """获取备份状态"""
    try:
        status = backup_service.get_backup_status()
        return success(
            data=status,
            message="获取备份状态成功"
        )
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"获取备份状态失败: {e!s}"
        )
