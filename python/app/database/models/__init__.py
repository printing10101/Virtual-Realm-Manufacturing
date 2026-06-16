"""SQLAlchemy ORM model package.

按子域拆分 ORM 模型，避免单一 ``models.py`` 文件膨胀：
    - ``machining_record``：统一加工记录（M0.4）
    - ``training_task``：训练任务相关模型
"""

from app.database.models.machining_record import (
    Base,
    MachiningRecord,
    _new_record_id,
)

from app.database.models.training_task import (
    TrainingTask,
    TaskStatusEnum,
    Role,
    Permission,
    RolePermission,
    PRESET_PERMISSIONS,
    PRESET_ROLES,
    init_db,
)

__all__ = [
    "Base",
    "MachiningRecord",
    "_new_record_id",
    "TrainingTask",
    "TaskStatusEnum",
    "Role",
    "Permission",
    "RolePermission",
    "PRESET_PERMISSIONS",
    "PRESET_ROLES",
    "init_db",
]
