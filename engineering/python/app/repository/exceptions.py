"""Repository 层异常（V3.0: 继承自 core.AppException）。

实现依赖反转原则：core 定义抽象异常基类，repository 实现具体异常。
FastAPI 的 AppException handler 自动处理所有继承自 AppException 的异常。
"""

from __future__ import annotations

from app.core.exceptions import AppException


class RepositoryError(AppException):
    """数据仓库操作异常基类。"""

    def __init__(
        self,
        message: str = "数据仓库操作异常",
        repository_type: str = "generic",
        detail: str | None = None,
    ):
        super().__init__(code=3001, message=message, status_code=500, detail=detail)
        self.repository_type = repository_type


class RecordNotFoundError(RepositoryError):
    """数据记录未找到（404）。"""

    def __init__(self, record_id: str, repository_type: str = "generic"):
        super().__init__(
            message=f"Record not found: {record_id}",
            repository_type=repository_type,
        )
        self.record_id = record_id


class StorageError(RepositoryError):
    """存储操作失败。"""

    def __init__(self, message: str = "存储操作失败", repository_type: str = "generic"):
        super().__init__(message=message, repository_type=repository_type)


class ValidationError(RepositoryError):
    """数据校验失败（400）。"""

    def __init__(
        self, message: str = "数据校验失败", repository_type: str = "generic"
    ):
        super().__init__(
            code=3003,
            message=message,
            status_code=400,
            repository_type=repository_type,
        )
