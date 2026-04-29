from app.core.response import success

from app.models.schemas import TaskStatus

# 工艺路线占位实现
router = None


def generate_process_route(item: str) -> dict:
    return {
        "status": TaskStatus.PENDING,
        "message": "工艺路线生成功能尚未实现",
        "item": item
    }
