from fastapi import APIRouter
from pydantic import BaseModel, Field
from typing import Optional
import asyncio

from app.core.response import success, error, ErrorCode
from app.core.container import container

router = APIRouter(prefix="/api/v1/reports", tags=["Report Generation"])


class GenerateReportRequest(BaseModel):
    process_task_id: Optional[str] = Field(default=None, description="关联的工艺任务ID")


class GenerateReportResponse(BaseModel):
    task_id: str
    status: str
    message: str


@router.post("/generate", response_model=GenerateReportResponse)
async def generate_report(request: GenerateReportRequest):
    report_service = container.get_service("report_service")
    task_manager = container.get_service("task_manager")

    task_id = task_manager.create_task(
        task_type=task_manager.TaskType.REPORT_GENERATION,
        params={"process_task_id": request.process_task_id}
    )

    asyncio.create_task(
        report_service.generate_react_report(task_id, request.process_task_id)
    )

    return GenerateReportResponse(
        task_id=task_id,
        status="pending",
        message="ReACT 报告生成任务已创建"
    )


@router.get("/{task_id}")
async def get_report(task_id: str):
    report_service = container.get_service("report_service")

    report = report_service.get_report(task_id)
    if not report:
        return error(code=ErrorCode.NOT_FOUND, message=f"报告 {task_id} 不存在")

    return success(data=report)


@router.get("/{task_id}/reasoning")
async def get_reasoning_steps(task_id: str):
    report_service = container.get_service("report_service")

    steps = report_service.get_reasoning_steps(task_id)
    if steps is None:
        return error(code=ErrorCode.NOT_FOUND, message=f"推理过程 {task_id} 不存在")

    return success(data={"reasoning_steps": steps})
