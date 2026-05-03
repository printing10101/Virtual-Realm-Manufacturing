from fastapi import APIRouter
import asyncio

from app.core.response import success, error, ErrorCode
from app.core.task_manager import task_manager, TaskType
from app.models.schemas import ProcessPlanRequest, ProcessPlanResponse
from app.ai.workflow import orchestrator

router = APIRouter(prefix="/api/workflow", tags=["Workflow"])


@router.post("/process-plan")
async def process_plan(request: ProcessPlanRequest):
    try:
        result = await orchestrator.execute_workflow(user_input=request.user_input)
        return success(data=result, message="工艺规划工作流执行完成")
    except Exception as e:
        return error(
            code=ErrorCode.INTERNAL_ERROR,
            message=f"工作流执行失败: {str(e)}"
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
            message=f"任务创建失败: {str(e)}"
        )
