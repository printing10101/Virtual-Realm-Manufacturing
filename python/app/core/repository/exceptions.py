"""
Repository 异常处理模块

定义统一的 Repository 异常体系，为所有存储操作提供标准化的错误处理机制。
"""



class RepositoryException(Exception):
    """Repository 基础异常类"""

    def __init__(
        self,
        message: str,
        repository_type: str | None = None,
        operation: str | None = None,
        detail: str | None = None
    ):
        self.message = message
        self.repository_type = repository_type
        self.operation = operation
        self.detail = detail
        super().__init__(self.message)

    def __str__(self) -> str:
        base = f"[{self.repository_type}]" if self.repository_type else ""
        op = f" {self.operation}" if self.operation else ""
        return f"{base}{op}: {self.message}"


class ConnectionError(RepositoryException):
    """存储连接异常"""

    def __init__(self, message: str, repository_type: str | None = None, detail: str | None = None):
        super().__init__(
            message=message,
            repository_type=repository_type,
            operation="connect",
            detail=detail
        )


class TransactionError(RepositoryException):
    """事务操作异常"""

    def __init__(self, message: str, repository_type: str | None = None, detail: str | None = None):
        super().__init__(
            message=message,
            repository_type=repository_type,
            operation="transaction",
            detail=detail
        )


class RecordNotFoundError(RepositoryException):
    """记录未找到异常"""

    def __init__(self, record_id: str, repository_type: str | None = None, detail: str | None = None):
        super().__init__(
            message=f"Record not found: {record_id}",
            repository_type=repository_type,
            operation="read",
            detail=detail
        )
        self.record_id = record_id


class RecordAlreadyExistsError(RepositoryException):
    """记录已存在异常"""

    def __init__(self, record_id: str, repository_type: str | None = None, detail: str | None = None):
        super().__init__(
            message=f"Record already exists: {record_id}",
            repository_type=repository_type,
            operation="create",
            detail=detail
        )
        self.record_id = record_id


class ValidationError(RepositoryException):
    """数据验证异常"""

    def __init__(self, message: str, repository_type: str | None = None, field: str | None = None, detail: str | None = None):
        super().__init__(
            message=message,
            repository_type=repository_type,
            operation="validate",
            detail=detail
        )
        self.field = field


class StorageError(RepositoryException):
    """底层存储异常"""

    def __init__(self, message: str, repository_type: str | None = None, detail: str | None = None):
        super().__init__(
            message=message,
            repository_type=repository_type,
            operation="storage",
            detail=detail
        )


class FileIntegrityError(RepositoryException):
    """文件完整性验证异常"""

    def __init__(self, file_path: str, message: str, repository_type: str | None = None, detail: str | None = None):
        super().__init__(
            message=message,
            repository_type=repository_type,
            operation="integrity_check",
            detail=detail
        )
        self.file_path = file_path


class ConfigurationError(RepositoryException):
    """配置错误异常"""

    def __init__(self, message: str, detail: str | None = None):
        super().__init__(
            message=message,
            repository_type="Configuration",
            operation="initialize",
            detail=detail
        )
