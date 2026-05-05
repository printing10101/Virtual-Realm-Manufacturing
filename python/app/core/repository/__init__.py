"""
Repository 模式模块

提供统一的存储访问层，支持四种存储方式：
- SQLite: 结构化数据持久化
- ChromaDB: 向量知识库存储
- JSON 文件: 配置和统计数据
- 文件系统: 二进制文件管理

用法示例:
    from app.core.repository import get_repository_factory

    factory = get_repository_factory()
    settings_repo = factory.get_repository("setting")
    settings_repo.create({"id": "theme", "value": "dark"})
"""

from app.core.repository.base import Repository
from app.core.repository.chroma_repository import ChromaRepository
from app.core.repository.config import (
    RepositoryConfig,
    get_repository_config,
    set_repository_config,
)
from app.core.repository.exceptions import (
    ConfigurationError,
    ConnectionError,
    FileIntegrityError,
    RecordAlreadyExistsError,
    RecordNotFoundError,
    RepositoryException,
    StorageError,
    TransactionError,
    ValidationError,
)
from app.core.repository.factory import RepositoryFactory, get_repository_factory
from app.core.repository.file_repository import FileRepository
from app.core.repository.json_repository import JsonRepository
from app.core.repository.models import Base, ProjectRecord, SettingRecord
from app.core.repository.sqlite_repository import SQLiteRepository

__all__ = [
    "Base",
    "ChromaRepository",
    "ConfigurationError",
    "ConnectionError",
    "FileIntegrityError",
    "FileRepository",
    "JsonRepository",
    "ProjectRecord",
    "RecordAlreadyExistsError",
    "RecordNotFoundError",
    "Repository",
    "RepositoryConfig",
    "RepositoryException",
    "RepositoryFactory",
    "SQLiteRepository",
    "SettingRecord",
    "StorageError",
    "TransactionError",
    "ValidationError",
    "get_repository_config",
    "get_repository_factory",
    "set_repository_config",
]
