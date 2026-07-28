"""向后兼容 shim：``project_sync_service`` 模块 → ``project_sync_service`` 包.

原 2092 行单文件已拆分为同名包（``app/services/project_sync_service/``），
业务逻辑分布于 9 个 Mixin 模块。本文件仅做重导出，保持外部导入路径不变：

    from app.services.project_sync_service import ProjectSyncService
    from app.services.project_sync_service import ProjectNotFoundError

新代码应直接从包导入；本 shim 仅为兼容旧调用点保留。
"""
from __future__ import annotations

from app.services.project_sync_service._exceptions import (
    GitOperationError,
    GitUnavailableError,
    InvalidProjectStateError,
    ProjectAlreadyExistsError,
    ProjectNotFoundError,
    ProjectSyncError,
    ResourceRefAlreadyExistsError,
    ResourceRefNotFoundError,
)
from app.services.project_sync_service.service import (
    ProjectSyncService,
    get_project_sync_service,
)

__all__ = [
    "ProjectSyncService",
    "get_project_sync_service",
    # 异常类
    "ProjectSyncError",
    "ProjectNotFoundError",
    "ProjectAlreadyExistsError",
    "GitUnavailableError",
    "GitOperationError",
    "ResourceRefNotFoundError",
    "ResourceRefAlreadyExistsError",
    "InvalidProjectStateError",
]
