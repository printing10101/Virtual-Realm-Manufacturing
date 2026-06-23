"""LNN API 依赖注入和全局状态。"""

from app.services.model.registry_service import get_model_registry_service
from app.audit.audit_log import AuditLog
from app.tasks.task_system import AsyncTaskManager

# 统一服务层 - 不要直接实例化 LNNModelRegistry
registry_service = get_model_registry_service()
model_registry = registry_service.model_registry
pytorch_registry = registry_service.pytorch_registry
model_cache = registry_service.model_cache
training_tasks = registry_service.get_training_tasks()
audit_log = AuditLog()

MAX_CONCURRENT_TRAINING_TASKS = 3
# 仅用于兼容旧 health_check 端点的活跃任务计数;
# 真正的并发控制由 AsyncTaskManager._semaphore 统一管理。
_active_training_tasks: set[str] = set()

task_manager = AsyncTaskManager()
