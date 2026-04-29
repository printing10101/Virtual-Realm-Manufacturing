from fastapi import APIRouter

from app.core.response import success, error, ErrorCode
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
