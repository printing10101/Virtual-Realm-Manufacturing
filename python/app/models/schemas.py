from pydantic import BaseModel, Field

from app.core.task_manager import TaskType


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


class LNNHyperparameters(BaseModel):
    learning_rate: float = Field(
        ...,
        description="学习率",
        gt=0,
        lt=1,
    )
    epochs: int = Field(
        ...,
        description="训练轮数",
        ge=1,
    )
    batch_size: int = Field(
        ...,
        description="批次大小",
        ge=1,
    )
    optimizer: str = Field(
        ...,
        description="优化器类型",
        pattern="^(adam|sgd|rmsprop)$",
    )


class LNNPredictRequest(BaseModel):
    input_data: list[float] = Field(
        ...,
        description="预测输入数据数组",
    )
    model_name: str = Field(
        ...,
        description="要使用的模型名称",
        min_length=1,
    )
    return_confidence: bool = Field(
        default=False,
        description="是否返回预测置信度",
    )


class LNNTrainRequest(BaseModel):
    model_name: str = Field(
        ...,
        description="训练模型的名称",
        min_length=1,
    )
    data_path: str = Field(
        ...,
        description="训练数据集的存储路径",
        min_length=1,
    )
    hyperparameters: LNNHyperparameters = Field(
        ...,
        description="训练超参数集合",
    )
    device: str = Field(
        default="auto",
        description="训练设备 (auto/gpu/cpu)",
        pattern="^(auto|gpu|cuda|cpu)$",
    )


class LNNDevicePreference(BaseModel):
    device: str = Field(
        default="auto",
        description="训练设备偏好 (auto/gpu/cpu)",
        pattern="^(auto|gpu|cuda|cpu)$",
    )
    use_amp: bool = Field(
        default=True,
        description="是否启用混合精度训练",
    )


class LNNModelInfo(BaseModel):
    name: str = Field(..., description="模型名称")
    version: str = Field(..., description="模型版本")
    last_updated: str = Field(..., description="最后更新时间，ISO 8601格式")


class LNNPredictResponse(BaseModel):
    value: float | list[float] = Field(
        ...,
        description="预测结果值",
    )
    confidence: float | None = Field(
        default=None,
        description="预测置信度，范围[0, 1]",
        ge=0,
        le=1,
    )
    inference_time: float = Field(
        ...,
        description="推理耗时，单位毫秒",
    )
    model_info: LNNModelInfo = Field(
        ...,
        description="模型信息",
    )


class LNNTrainMetrics(BaseModel):
    accuracy: float = Field(..., description="准确率", ge=0, le=1)
    loss: float = Field(..., description="损失值", ge=0)
    training_time: float = Field(..., description="训练总耗时，单位秒", ge=0)
    epochs_completed: int = Field(..., description="实际完成的训练轮数", ge=0)


class LNNTrainResponse(BaseModel):
    status: str = Field(
        ...,
        description="训练状态",
        pattern="^(success|failed|in_progress)$",
    )
    message: str = Field(..., description="训练状态描述信息")
    metrics: LNNTrainMetrics | None = Field(
        default=None,
        description="训练指标，仅当status为success时返回",
    )


class LNNQuantizeRequest(BaseModel):
    quantization_type: str = Field(
        ...,
        description="量化类型",
        pattern="^(dynamic|static)$",
    )
    calibration_data_path: str | None = Field(
        default=None,
        description="校准数据集路径（仅静态量化需要）",
    )


class LNNModelSizeResponse(BaseModel):
    original_size_bytes: int = Field(..., description="原始模型大小")
    quantized_size_bytes: int | None = Field(default=None, description="量化模型大小")
    original_size_human: str = Field(..., description="原始模型大小（人类可读）")
    quantized_size_human: str | None = Field(
        default=None, description="量化模型大小（人类可读）"
    )
    size_reduction_bytes: int | None = Field(default=None, description="减少的大小")
    size_reduction_percent: float | None = Field(
        default=None, description="减少的百分比"
    )


class AlternativePlan(BaseModel):
    plan_id: str = Field(..., description="备选方案ID")
    parameters: dict = Field(..., description="方案参数配置")
    expected_outcome: str = Field(..., description="预期效果说明")
    confidence: float = Field(..., description="方案置信度", ge=0, le=1)
    reasoning: str = Field(..., description="推理过程说明")


class LNNPredictResponseExtended(BaseModel):
    value: float | list[float] = Field(..., description="预测结果值")
    confidence: float | None = Field(default=None, description="预测置信度", ge=0, le=1)
    reasoning: str | None = Field(default=None, description="AI推理过程")
    inference_time: float = Field(..., description="推理耗时，单位毫秒")
    model_info: LNNModelInfo = Field(..., description="模型信息")
    alternatives: list[AlternativePlan] | None = Field(
        default=None, description="备选方案列表"
    )


class LNNTrainDryRunRequest(BaseModel):
    model_name: str = Field(..., description="训练模型的名称", min_length=1)
    data_path: str = Field(..., description="训练数据集的存储路径", min_length=1)
    hyperparameters: LNNHyperparameters = Field(..., description="训练超参数集合")
    device: str = Field(
        default="auto", description="训练设备", pattern="^(auto|gpu|cuda|cpu)$"
    )


class TrainingPlanSummary(BaseModel):
    estimated_duration_minutes: float = Field(..., description="预估训练时长（分钟）")
    estimated_memory_mb: float = Field(..., description="预估内存占用（MB）")
    estimated_gpu_memory_mb: float | None = Field(
        default=None, description="预估GPU显存占用（MB）"
    )
    dataset_samples: int = Field(..., description="数据集样本数")
    train_val_split: dict = Field(..., description="训练集/验证集划分比例")
    potential_risks: list[str] = Field(default=[], description="潜在风险提示")
    recommendations: list[str] = Field(default=[], description="训练建议")


class LNNTrainDryRunResponse(BaseModel):
    is_dry_run: bool = Field(default=True, description="是否为dry_run模式")
    training_plan: TrainingPlanSummary = Field(..., description="训练计划概要")
    confidence: float = Field(..., description="训练成功置信度", ge=0, le=1)
    reasoning: str = Field(..., description="训练计划推理说明")


class AuditLogQueryRequest(BaseModel):
    start_time: int | None = Field(default=None, description="开始时间戳（毫秒）")
    end_time: int | None = Field(default=None, description="结束时间戳（毫秒）")
    ai_module: str | None = Field(default=None, description="AI模块过滤")
    user_decision: str | None = Field(default=None, description="用户决策过滤")
    limit: int = Field(default=100, description="返回数量", ge=1, le=1000)
    offset: int = Field(default=0, description="偏移量", ge=0)


class AuditLogSearchRequest(BaseModel):
    keyword: str = Field(..., description="搜索关键词", min_length=1)
    limit: int = Field(default=50, description="返回数量", ge=1, le=500)


class AuditLogExportRequest(BaseModel):
    format: str = Field(default="json", description="导出格式", pattern="^(json|csv)$")
    start_time: int | None = Field(default=None, description="开始时间戳（毫秒）")
    end_time: int | None = Field(default=None, description="结束时间戳（毫秒）")
    ai_module: str | None = Field(default=None, description="AI模块过滤")


class UserSovereigntySettings(BaseModel):
    ai_autonomy_level: int = Field(
        default=2,
        description="AI自主度等级（0-4）：0=完全手动, 1=建议需确认, 2=推荐（默认）, 3=半自动, 4=全自动",
        ge=0,
        le=4,
    )
    require_confirmation_for_predict: bool = Field(
        default=False,
        description="预测是否需要确认",
    )
    require_confirmation_for_train: bool = Field(
        default=True,
        description="训练是否需要确认",
    )
    show_confidence_indicator: bool = Field(
        default=True,
        description="是否显示置信度指示器",
    )
    show_alternatives: bool = Field(
        default=True,
        description="是否显示备选方案",
    )
    show_reasoning: bool = Field(
        default=True,
        description="是否显示推理过程",
    )


class AgentTokenCreateRequest(BaseModel):
    scopes: list[str] = Field(
        ...,
        description="权限范围集合（R/W/B/N/C/T 的任意组合）",
        min_length=1,
    )
    expires_in: int | None = Field(
        default=None,
        description="Token有效期（秒），None表示永不过期",
        ge=3600,
    )
    paper_only: bool = Field(
        default=True,
        description="是否仅限模拟模式",
    )


class AgentTokenResponse(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    token: str = Field(..., description="完整Token值（仅创建时显示一次）")
    scopes: list[str] = Field(..., description="权限范围")
    created_at: float = Field(..., description="创建时间戳")
    expires_at: float | None = Field(default=None, description="过期时间戳")
    paper_only: bool = Field(..., description="是否仅限模拟模式")


class AgentTokenListItem(BaseModel):
    agent_id: str = Field(..., description="Agent ID")
    token_prefix: str = Field(..., description="Token前缀（脱敏显示）")
    scopes: list[str] = Field(..., description="权限范围")
    created_at: float = Field(..., description="创建时间戳")
    expires_at: float | None = Field(default=None, description="过期时间戳")
    paper_only: bool = Field(..., description="是否仅限模拟模式")
    is_active: bool = Field(..., description="是否活跃")


class AgentPredictRequest(BaseModel):
    model_name: str = Field(..., description="模型名称", min_length=1)
    input_data: list[float] = Field(..., description="输入数据")
    return_confidence: bool = Field(default=False, description="是否返回置信度")


class AgentTrainRequest(BaseModel):
    model_name: str = Field(..., description="模型名称", min_length=1)
    data_path: str = Field(..., description="训练数据路径", min_length=1)
    hyperparameters: LNNHyperparameters = Field(..., description="超参数")
    device: str = Field(
        default="auto", description="设备", pattern="^(auto|gpu|cuda|cpu)$"
    )


class AgentExecuteRequest(BaseModel):
    machine_id: str = Field(..., description="机床ID", min_length=1)
    parameters: dict = Field(..., description="工艺参数")
    simulate: bool = Field(default=True, description="是否模拟执行")


class AgentAuditLogQueryRequest(BaseModel):
    agent_id: str | None = Field(default=None, description="Agent ID过滤")
    permission_class: str | None = Field(default=None, description="权限类别过滤")
    limit: int = Field(default=100, description="返回数量", ge=1, le=1000)
    offset: int = Field(default=0, description="偏移量", ge=0)


class LNNBatchInferenceRequest(BaseModel):
    model_name: str = Field(..., description="模型名称", min_length=1)
    input_data: list[list[float]] = Field(..., description="批量输入数据")
    batch_size: int = Field(default=32, description="批次大小", ge=1)
