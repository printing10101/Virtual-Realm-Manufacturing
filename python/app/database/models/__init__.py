"""数据库模型定义模块。"""

# 重新导出所有模型，便于外部统一导入
from app.database.models.machining_record import Base, MachiningRecord
from app.database.models.manufacturing import (
    Material,
    Equipment,
    EquipmentAlarm,
    MaintenancePlan,
    QualityRecord,
    QualityAnomaly,
    ProductionRecord,
    WorkOrder,
    ProcessRoute,
    ProcessStep,
    Document,
)
from app.database.models.tool import Tool
from app.database.models.training_task import (
    TrainingTask,
    TaskStatusEnum,
    Role,
    Permission,
    RolePermission,
    init_db,
)

__all__ = [
    "Base",
    "MachiningRecord",
    "Material",
    "Equipment",
    "EquipmentAlarm",
    "MaintenancePlan",
    "QualityRecord",
    "QualityAnomaly",
    "ProductionRecord",
    "WorkOrder",
    "ProcessRoute",
    "ProcessStep",
    "Document",
    "Tool",
    "TrainingTask",
    "TaskStatusEnum",
    "Role",
    "Permission",
    "RolePermission",
    "init_db",
]
