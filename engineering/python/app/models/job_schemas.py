"""
Job-related Pydantic schemas for async task system.
"""

from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional, Union

# [P0-17] 公共约束：dict 字段允许的标量值类型
_ScalarValue = Union[str, int, float, bool, None]


class CreateJobRequest(BaseModel):
    task_type: str = Field(
        ..., description="任务类型: lnn_training, lnn_batch_inference"
    )
    # [P0-17] 限制任务参数键值数量与值类型，防止注入任意嵌套结构
    params: Dict[str, _ScalarValue] = Field(
        ...,
        max_length=50,
        description="任务参数键值对，最多50项，值仅支持标量",
    )


class JobResponse(BaseModel):
    job_id: str = Field(..., description="任务ID")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="任务状态")
    progress: float = Field(default=0.0, description="进度百分比")
    created_at: str = Field(..., description="创建时间")
    started_at: Optional[str] = Field(default=None, description="开始时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")
    # [P0-17] 限制响应字典键值数量，防止异常输出过大
    result: Optional[Dict[str, _ScalarValue]] = Field(
        default=None, max_length=50, description="任务结果"
    )
    error: Optional[str] = Field(default=None, description="错误信息")
    metrics: Optional[Dict[str, _ScalarValue]] = Field(
        default=None, max_length=50, description="任务指标"
    )


class JobListItem(BaseModel):
    job_id: str
    task_type: str
    status: str
    progress: float
    created_at: str
    duration_seconds: Optional[float] = None
    owner_id: Optional[str] = None


class JobListResponse(BaseModel):
    jobs: List[JobListItem]
    total: int
    has_more: bool


class CancelJobResponse(BaseModel):
    job_id: str
    status: str
    message: str


class TaskStatsResponse(BaseModel):
    total_tasks: int
    active_tasks: int
    queued_tasks: int
    completed_tasks: int
    failed_tasks: int
    max_concurrent: int
    available_slots: int
