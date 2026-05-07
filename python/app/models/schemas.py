from pydantic import BaseModel, Field

from app.core.task_manager import TaskStatus, TaskType


class KnowledgeAddRequest(BaseModel):
    document: str = Field(..., description="知识文档内容")
    metadata: dict | None = Field(default=None, description="元数据")
    doc_id: str | None = Field(default=None, description="文档ID（为空则自动生成）")


class KnowledgeDeleteRequest(BaseModel):
    doc_id: str = Field(..., description="要删除的文档ID")


class KnowledgeQueryRequest(BaseModel):
    query_text: str = Field(..., description="查询文本")
    n_results: int = Field(default=5, description="返回结果数量", ge=1, le=20)


class ProcessPlanRequest(BaseModel):
    user_input: str = Field(..., description="用户需求描述")


class CadQueryRequest(BaseModel):
    material: str = Field(default="", description="材料类型")
    dimensions: dict | None = Field(default=None, description="尺寸参数")
    description: str = Field(default="", description="加工描述")
    script: str = Field(default="", description="CadQuery脚本")
    output_format: str = Field(default="stl", description="输出格式")


class CreateTaskRequest(BaseModel):
    task_type: TaskType = Field(..., description="任务类型")
    params: dict | None = Field(default=None, description="任务参数")
    timeout: float | None = Field(default=None, description="超时时间(秒)")


class AIStatusResponse(BaseModel):
    mode: str = Field(default="local", description="AI模式")
    available: bool = Field(default=False, description="AI是否可用")
    model: str = Field(default="", description="使用的模型")


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="服务状态")
    version: str = Field(default="", description="版本号")
    ai_status: AIStatusResponse | None = Field(default=None, description="AI状态")
