import asyncio

from fastapi import APIRouter

from app.ai.workflow import orchestrator
from app.core.input_validator import (
    validate_and_clean,
)
from app.core.response import ErrorCode, error, success
from app.core.task_manager import TaskType, task_manager
from app.models.schemas import ProcessPlanRequest

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


@router.post("/process-plan")
async def process_plan(request: ProcessPlanRequest):
    """
    工艺规划接口 - 带输入验证

    验证用户输入，确保：
    - 需求描述长度合法
    - 无XSS和SQL注入风险
    - 提取的参数经过专门验证
    """
    cleaned_input, err = validate_and_clean(request.user_input, field_name="user_input")
    if err:
        return error(
            code=ErrorCode.INVALID_REQUEST,
            message=f"输入验证失败: {err.message}",
            detail=err.to_response()
        )

    try:
        result = await orchestrator.execute_workflow(user_input=cleaned_input)
        return success(data=result, message="工艺规划工作流执行完成")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"工作流执行失败: {e!s}"
        )


@router.post("/process-plan-async")
async def process_plan_async(request: ProcessPlanRequest):
    try:
        task_id = task_manager.create_task(
            TaskType.WORKFLOW_EXECUTION,
            {"user_input": request.user_input}
        )

        asyncio.create_task(
            orchestrator.execute_workflow_with_task(request.user_input, task_id)
        )

        return success(data={"task_id": task_id}, message="任务已创建，正在后台执行")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"任务创建失败: {e!s}"
        )
