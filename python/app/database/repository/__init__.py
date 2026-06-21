"""Repository package for SQLAlchemy-based data access.

各领域模型对应一个仓库类，统一封装 CRUD 与常见查询语义。

包内同时提供基于 JSON 文件的泛型仓储基类 ``JsonRepository``，
供 MachineDatabase、ToolDatabase、MaterialDatabase 等继承使用。
"""

from app.database.repository.json_repository import JsonRepository
from app.database.repository.machining_record_repo import (
    MachiningRecordRepository,
)

__all__ = ["JsonRepository", "MachiningRecordRepository"]
