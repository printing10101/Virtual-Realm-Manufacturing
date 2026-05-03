from enum import Enum
from typing import Optional
from datetime import datetime

from pydantic import BaseModel, Field


class AIMode(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    RULE = "rule"


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    PROCESS_GENERATION = "process_generation"
    REPORT_GENERATION = "report_generation"
    SIMULATION_VALIDATION = "simulation_validation"
    CAD_GENERATION = "cad_generation"
    WORKFLOW_EXECUTION = "workflow_execution"


class AISettings(BaseModel):
    mode: AIMode = Field(default=AIMode.LOCAL, description="AI 运行模式")
    ollama_base_url: str = Field(default="http://localhost:11434", description="Ollama 服务地址")
    ollama_model: str = Field(default="qwen2.5-coder:7b", description="Ollama 模型名称")
    cloud_api_key: str = Field(default="", description="云端 API 密钥")
    cloud_base_url: str = Field(default="https://api.openai.com/v1", description="云端 API 地址")
    cloud_model: str = Field(default="gpt-3.5-turbo", description="云端模型名称")
    timeout: int = Field(default=60, ge=10, le=300, description="请求超时时间（秒）")


class AIStatusResponse(BaseModel):
    mode: str = Field(description="当前 AI 模式")
    available: bool = Field(description="AI 服务是否可用")
    model: str = Field(description="当前使用的模型")
    version: Optional[str] = Field(default=None, description="模型版本")


class LLMRequest(BaseModel):
    messages: list[dict] = Field(description="对话消息列表", min_length=1)
    model: Optional[str] = Field(default=None, description="指定模型名称")
    temperature: float = Field(default=0.7, ge=0, le=2, description="温度参数")
    max_tokens: int = Field(default=2048, ge=1, le=8192, description="最大 token 数")
    stream: bool = Field(default=False, description="是否流式输出")


class LLMResponse(BaseModel):
    content: str = Field(description="回复内容")
    model: str = Field(description="使用的模型")
    finish_reason: Optional[str] = Field(default=None, description="结束原因")
    usage: Optional[dict] = Field(default=None, description="使用统计")


class HealthResponse(BaseModel):
    status: str = Field(description="服务状态")
    version: str = Field(description="应用版本")
    ai_status: Optional[AIStatusResponse] = Field(default=None, description="AI 服务状态")


class ThreeViewTaskRequest(BaseModel):
    task_type: str = Field(default="three_view", description="任务类型")
    front_view: str = Field(description="正视图路径或base64")
    top_view: str = Field(description="俯视图路径或base64")
    left_view: str = Field(description="左视图路径或base64")
    output_format: str = Field(default="stl", description="输出格式: stl/obj/gltf")


class CadQueryRequest(BaseModel):
    script: str = Field(description="CadQuery 脚本代码", min_length=10)
    output_format: str = Field(default="stl", description="输出格式: stl/obj/gltf")


class TaskResponse(BaseModel):
    task_id: str = Field(description="任务 ID")
    status: str = Field(description="任务状态")
    progress: float = Field(description="进度百分比")
    message: Optional[str] = Field(default=None, description="提示信息")


class TaskStatusResponse(BaseModel):
    task_id: str = Field(description="任务 ID")
    status: str = Field(description="任务状态")
    progress: float = Field(description="进度百分比")
    task_type: str = Field(description="任务类型")
    model_path: Optional[str] = Field(default=None, description="模型路径")
    model_format: Optional[str] = Field(default=None, description="模型格式")
    error_message: Optional[str] = Field(default=None, description="错误信息")
    created_at: str = Field(description="创建时间")
    completed_at: Optional[str] = Field(default=None, description="完成时间")


class ProcessPlanRequest(BaseModel):
    user_input: str = Field(description="用户制造需求描述", min_length=10, max_length=2000)


class StageResult(BaseModel):
    status: str = Field(description="阶段状态")
    elapsed_seconds: float = Field(description="耗时（秒）")
    output_summary: Optional[dict] = Field(default=None, description="输出摘要")
    error: Optional[str] = Field(default=None, description="错误信息")


class ProcessPlanResponse(BaseModel):
    user_input: str = Field(description="用户输入")
    extracted_params: dict = Field(description="提取的参数")
    process_route: list = Field(description="工艺路线")
    cutting_parameters: dict = Field(description="切削参数")
    nc_code: str = Field(description="NC代码")
    verification_result: dict = Field(description="验证结果")
    repair_suggestions: list = Field(description="修复建议")
    stage_results: dict = Field(description="各阶段结果")
    total_stages: int = Field(description="总阶段数")
    completed_stages: int = Field(description="已完成阶段数")


class KnowledgeAddRequest(BaseModel):
    document: str = Field(description="知识内容", min_length=10)
    metadata: dict = Field(default={}, description="知识元数据")
    doc_id: Optional[str] = Field(default=None, description="知识ID")


class KnowledgeQueryRequest(BaseModel):
    query_text: str = Field(description="查询文本", min_length=1)
    n_results: int = Field(default=5, ge=1, le=20, description="返回结果数量")


class KnowledgeDeleteRequest(BaseModel):
    doc_id: str = Field(description="知识ID")


class KnowledgeResponse(BaseModel):
    documents: list = Field(description="知识文档列表")
    metadatas: list = Field(description="元数据列表")
    distances: list = Field(description="距离列表")
    ids: list = Field(description="ID列表")


class KnowledgeHealthResponse(BaseModel):
    status: str = Field(description="知识库状态")
    count: int = Field(description="知识条目数量")


class CreateTaskRequest(BaseModel):
    task_type: TaskType = Field(description="任务类型")
    params: Optional[dict] = Field(default=None, description="任务参数")
    timeout: Optional[float] = Field(default=None, description="超时时间（秒）")
