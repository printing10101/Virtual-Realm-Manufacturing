# API 参考文档

> **自动生成**: 本文档由 `scripts/gen-api-docs.py` 自动生成
> 
> **最后更新**: 自动填充
> 
> **适用版本**: 灵境制造平台 v2.7.0

> **交叉引用**: 本文档为 API 端点总览，完整的请求/响应示例、错误码详解与认证流程见 [`docs/api/README.md`](./api/README.md)。两份文档遵循同一响应格式约定（见下文"响应格式约定"小节）。

## 概述

灵境制造平台提供 RESTful API 接口，支持 AI 模型管理、刀具磨损预测、训练任务管理等功能。

### 基础信息

| 属性 | 值 |
|------|-----|
| 基础路径 | `/api/v1` |
| 数据格式 | JSON |
| 字符编码 | UTF-8 |

### 通用请求格式

所有 POST/PUT 请求的请求体必须使用 JSON 格式，并设置请求头：

```
Content-Type: application/json
```

### 响应格式约定

所有 API 响应遵循统一格式，字段定义与 `python/app/core/response.py` 实现保持一致：

| 字段 | 类型 | 说明 |
|------|------|------|
| `code` | `number` | 数值状态码，`0` 表示成功，非 `0` 表示错误（如 `1001`、`2001`） |
| `message` | `string` | 人类可读的状态描述 |
| `data` | `any` | 成功时为业务数据，错误时通常省略或为 `null` |
| `request_id` | `string` | 请求追踪标识，对应客户端 `X-Request-ID` |

> **注意**：代码内部 `ErrorCode` 保留字符串枚举（如 `SUCCESS`、`NOT_FOUND`）以保持向后兼容，但通过 `code_to_numeric()` 映射表统一转换为数值后返回给客户端。客户端应始终以数值 `code` 判断响应状态，不应依赖字符串枚举值。

### 通用响应格式

成功响应示例：

```json
{
  "code": 0,
  "message": "操作成功",
  "data": { ... },
  "request_id": "uuid-string"
}
```

错误响应示例：

```json
{
  "code": 1001,
  "message": "资源未找到",
  "request_id": "uuid-string",
  "detail": "附加详情（可选）",
  "suggestion": "建议操作（可选）"
}
```

## 认证与授权

当前版本 API 无需额外认证。生产环境部署时建议启用 API Key 或 JWT Token 认证机制。

## 错误码参考

下表列出 `ErrorCode` 枚举与对应数值码的映射关系。客户端应以 `code`（数值）列为准。

| `ErrorCode` 枚举 | `code`（数值） | 说明 | 解决建议 |
|------------------|---------------|------|----------|
| `SUCCESS` | `0` | 操作成功 | - |
| `NOT_FOUND` | `1001` | 资源未找到 | 检查请求路径或资源标识是否正确 |
| `INVALID_REQUEST` | `1002` | 请求参数错误 | 检查请求参数格式和取值范围 |
| `UNAUTHORIZED` | `1003` | 未授权访问 | 检查认证凭据是否有效 |
| `FILE_NOT_FOUND` | `1008` | 文件不存在 | 检查文件路径是否正确 |
| `INTERNAL_ERROR` | `2001` | 服务器内部错误 | 检查服务器日志，联系技术支持 |
| `SERVICE_UNAVAILABLE` | `2002` | 服务不可用 | 检查服务状态，稍后重试 |
| `CAD_GENERATION_ERROR` | `7001` | CAD 生成失败 | 检查输入参数和模板配置 |

## LNN 模型 API

LNN（Liquid Neural Network）模型管理接口，支持模型预测、训练、量化等功能。

### `POST` `/api/v1/lnn/predict-uncertain`

**基于 Bayesian LNN（MC Dropout）的预测 + 不确定性量化。**

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `LNNPredictRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误


## 刀具磨损预测 API

刀具磨损预测和工艺优化接口，支持磨损曲线预测、剩余寿命评估等功能。

### `POST` `/api/v1/signal-fusion-kb/correlate/wear`

**将信号样本关联为 ToolWearPredictor 可消费的 sensor_features。**

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `req` | `CorrelateWearRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/tools/{tool_id}/wear`

**更新刀具磨损信息。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `tool_id` | `str` | 是 |  |

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `ToolWearUpdate` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/calibrate`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `CalibrateRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/calibrate-realtime`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `RealTimeCalibrateRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/compensation`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `CompensationRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/wear/cross-dataset-analysis`

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/wear/models`

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/predict`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `WearPredictRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/predict-from-signals`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `features` | `dict[str, float]` | `-` | 是 |  |
| `material` | `str` | `'tc4'` | 否 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/remaining-life`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `RemainingLifeRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/suggest`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `SuggestRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/threshold`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `material_type` | `str` | `'default'` | 否 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/train-uniwear`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `data_dir` | `str` | `'python/data/uniwear'` | 否 |  |
| `model_type` | `str` | `'random_forest'` | 否 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/wear/uniwear-materials`

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误


## 数据模型

API 请求和响应使用的 Pydantic 模型定义。

### `AgentStateSaveRequest`

保存 Agent 状态的请求体（白名单字段）。

仅允许更新业务字段，agent_id / created_at / updated_at / state_version
等内部字段由服务端管理，不接受客户端传入。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_task_id` | `Optional[str]` | 否 | `None` | 当前任务ID | - |
| `status` | `Optional[AgentStatus]` | 否 | `None` | Agent 状态 | - |
| `metadata` | `dict[str, Any]` | 是 | `-` | 元数据 | - |

### `CheckpointSaveRequest`

保存 Checkpoint 的请求体（白名单字段）。

checkpoint_id / created_at / file_size_bytes 由服务端管理，
不接受客户端传入。checkpoint_type 通过枚举校验防止非法值。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `epoch` | `int` | 否 | `0` | 训练轮次 | ≥ 0 |
| `step` | `int` | 否 | `0` | 训练步数 | ≥ 0 |
| `best_metric` | `Optional[float]` | 否 | `None` | 最佳指标值 | - |
| `best_metric_name` | `str` | 否 | `'loss'` | 最佳指标名称 | - |
| `state_dict_path` | `str` | 否 | `''` | 状态字典存储路径 | - |
| `optimizer_state_path` | `str` | 否 | `''` | 优化器状态存储路径 | - |
| `rng_state` | `Optional[dict[str, Any]]` | 否 | `None` | 随机数生成器状态 | - |
| `checkpoint_type` | `CheckpointType` | 是 | `-` | 检查点类型 | - |
| `metrics` | `dict[str, Any]` | 是 | `-` | 指标字典 | - |
| `metadata` | `dict[str, Any]` | 是 | `-` | 元数据 | - |

### `MemoryEntryAddRequest`

添加 MemoryEntry 的请求体（白名单字段）。

memory_id / created_at / last_accessed / access_count / embedding_ref
由服务端管理。importance 约束在 [0, 1] 区间。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `content` | `str` | 否 | `''` | 记忆内容 | - |
| `memory_type` | `str` | 否 | `'observation'` | 记忆类型 | - |
| `importance` | `float` | 否 | `0.5` | 重要性权重 [0,1] | ≥ 0.0; ≤ 1.0 |
| `tags` | `list[str]` | 是 | `-` | 标签列表 | - |
| `metadata` | `dict[str, Any]` | 是 | `-` | 元数据 | - |

### `CheckpointRollbackRequest`

回滚到指定 Checkpoint 的请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `checkpoint_id` | `str` | 是 | `-` | 目标检查点ID（必填） | - |

### `ContextUpdateRequest`

更新 Agent 会话上下文的请求体。

updates 为动态字典，由 :meth:`update_context_increment` 内部处理。
允许直接传业务字段（无 updates 键时整体作为 updates）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `updates` | `dict[str, Any]` | 是 | `-` | 上下文更新字典 | - |

### `AgentCloneRequest`

克隆 Agent 状态的请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `target_agent_id` | `str` | 是 | `-` | 目标 Agent ID（必填） | - |

### `TokenRequest`

令牌请求模型。

用于 refresh_token 和 logout 端点，替换原 body: dict 弱验证。
两个字段均默认空字符串以兼容 logout 端点的可选语义；
refresh_token 端点会在函数体内显式校验非空。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `refresh_token` | `str` | 否 | `''` | 刷新令牌 | - |
| `access_token` | `str` | 否 | `''` | 访问令牌 | - |

### `StockModelRequest`

工件模型请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `length` | `float` | 是 | `-` | 工件长度 (mm) | - |
| `width` | `float` | 是 | `-` | 工件宽度 (mm) | - |
| `height` | `float` | 是 | `-` | 工件高度 (mm) | - |
| `x_offset` | `float` | 否 | `0.0` | X方向偏移 (mm) | - |
| `y_offset` | `float` | 否 | `0.0` | Y方向偏移 (mm) | - |
| `z_offset` | `float` | 否 | `0.0` | Z方向偏移 (mm) | - |

### `ToolpathSegmentRequest`

刀路段请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `type` | `str` | 是 | `-` | 段类型 (rapid/linear/arc) | - |
| `start_point` | `tuple[float, float, float]` | 是 | `-` | 起点坐标 (x, y, z) | - |
| `end_point` | `tuple[float, float, float]` | 是 | `-` | 终点坐标 (x, y, z) | - |
| `block_number` | `int` | 否 | `0` | NC程序段号 | - |
| `feed_rate` | `float | None` | 否 | `None` | 进给率 (mm/min) | - |
| `a_angle` | `float | None` | 否 | `None` | A轴角度 (度) | - |
| `c_angle` | `float | None` | 否 | `None` | C轴角度 (度) | - |

### `CollisionCheckRequest`

碰撞检测请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `stock` | `StockModelRequest` | 是 | `-` | 工件模型 | - |
| `segments` | `list[ToolpathSegmentRequest]` | 是 | `-` | 刀路段列表 | - |
| `safe_z_height` | `float` | 否 | `10.0` | 安全Z高度 (mm) | - |
| `mode` | `str` | 否 | `'3axis'` | 检测模式 (3axis/5axis) | - |
| `workspace_limits` | `dict[str, float] | None` | 否 | `None` | 机床工作空间限制 | - |

### `CollisionCheckResponse`

碰撞检测响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `code` | `int` | 否 | `0` | 状态码 (0=成功) | - |
| `message` | `str` | 否 | `'OK'` | 状态消息 | - |
| `data` | `dict[str, Any]` | 是 | `-` | 碰撞检测报告 | - |

### `SetUnitPriceRequest`

设置单价请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `key` | `str` | 是 | `-` | 单价键名 | 最小长度: 1 |
| `value` | `float` | 是 | `-` | 单价数值 | - |

### `SetBudgetPolicyRequest`

设置预算策略请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `level` | `str` | 否 | `'global'` | 预算层级 | - |
| `scope_id` | `str` | 否 | `'default'` | 范围ID | - |
| `resource_type` | `str` | 否 | `'total_cost'` | 资源类型 | - |
| `limit` | `float` | 否 | `100.0` | 预算上限 | - |
| `period` | `str` | 否 | `'daily'` | 预算周期 | - |
| `warning_threshold` | `float` | 否 | `0.8` | 预警阈值 | - |
| `hard_stop` | `bool` | 否 | `True` | 是否硬性停止 | - |
| `auto_notify` | `bool` | 否 | `True` | 是否自动通知 | - |
| `enabled` | `bool` | 否 | `True` | 是否启用 | - |

### `AdjustBudgetRequest`

调整预算请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `level` | `str` | 是 | `-` | 预算层级 | - |
| `scope_id` | `str` | 否 | `'default'` | 范围ID | - |
| `resource_type` | `str` | 是 | `-` | 资源类型 | - |
| `new_limit` | `float` | 是 | `-` | 新预算上限 | - |
| `reason` | `str` | 否 | `''` | 调整原因 | - |
| `adjusted_by` | `str` | 否 | `'admin'` | 调整人 | - |

### `CheckBudgetRequest`

检查预算请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `level` | `str` | 否 | `'global'` | 预算层级 | - |
| `scope_id` | `str` | 否 | `'default'` | 范围ID | - |
| `resource_type` | `str` | 否 | `'total_cost'` | 资源类型 | - |
| `planned_usage` | `float` | 否 | `0.0` | 计划用量 | - |

### `CheckBudgetCascadeRequest`

级联检查预算请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 否 | `''` | Agent ID | - |
| `project_id` | `str` | 否 | `'default'` | 项目ID | - |
| `resource_type` | `str` | 否 | `'total_cost'` | 资源类型 | - |
| `planned_usage` | `float` | 否 | `0.0` | 计划用量 | - |

### `EnforceBudgetRequest`

强制预算请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `level` | `str` | 否 | `'global'` | 预算层级 | - |
| `scope_id` | `str` | 否 | `'default'` | 范围ID | - |
| `resource_type` | `str` | 否 | `'total_cost'` | 资源类型 | - |
| `planned_usage` | `float` | 否 | `0.0` | 计划用量 | - |

### `ResetBudgetPeriodRequest`

重置预算周期请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `level` | `str` | 是 | `-` | 预算层级 | - |
| `scope_id` | `str` | 否 | `'default'` | 范围ID | - |
| `resource_type` | `str` | 是 | `-` | 资源类型 | - |

### `SchemaFieldModel`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `type` | `str` | 是 | `-` |  | - |
| `required` | `bool` | 否 | `False` |  | - |
| `description` | `str` | 否 | `''` |  | - |

### `DatasetSchemaModel`

DatasetSchema 的 API 入参模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `fields` | `dict[str, SchemaFieldModel]` | 是 | `-` |  | - |
| `primary_key` | `list[str]` | 是 | `-` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` |  | - |

### `CreateDatasetRequest`

创建数据集请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` |  | - |
| `description` | `str` | 否 | `''` |  | - |
| `schema` | `DatasetSchemaModel` | 是 | `-` |  | - |
| `owner_id` | `str` | 是 | `-` |  | - |

### `CommitVersionRequest`

提交版本请求体。

records 为空且 dataset_id 是 TrainingDataLake 适配器时，
适配器会自动从 lake 加载当前全部 records。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `records` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `version` | `Optional[str]` | 否 | `None` |  | - |
| `lineage` | `Optional[LineageModel]` | 否 | `None` |  | - |

### `LineageModel`

LineageRecord 的 API 入参模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `target` | `str` | 是 | `-` |  | - |
| `source_type` | `str` | 是 | `-` |  | - |
| `source_ref` | `str` | 是 | `-` |  | - |
| `inputs` | `list[str]` | 是 | `-` |  | - |
| `outputs` | `list[str]` | 是 | `-` |  | - |
| `operation` | `str` | 否 | `''` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` |  | - |

### `MachineConnectRequest`

机床连接请求模型。

Attributes:
    machine_id: 机床唯一标识
    protocol: 通信协议（opcua / mtconnect）
    endpoint: 连接端点
    username: 认证用户名（可选）
    password: 认证密码（可选）
    device_name: MTConnect 设备名称（可选，默认 Device）

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `machine_id` | `str` | 是 | `-` | 机床唯一标识 | - |
| `protocol` | `ProtocolType` | 是 | `-` | 通信协议 | - |
| `endpoint` | `str` | 是 | `-` | 连接端点 | - |
| `username` | `Optional[str]` | 否 | `None` | 认证用户名 | - |
| `password` | `Optional[str]` | 否 | `None` | 认证密码 | - |
| `device_name` | `Optional[str]` | 否 | `'Device'` | MTConnect 设备名称 | - |

### `NCSendRequest`

NC 程序发送请求模型。

Attributes:
    machine_id: 目标机床 ID
    program_path: 本地 NC 程序文件路径
    program_name: 机床端存储的程序名（可选，默认使用文件名）

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `machine_id` | `str` | 是 | `-` | 目标机床 ID | - |
| `program_path` | `str` | 是 | `-` | 本地 NC 程序文件路径 | - |
| `program_name` | `Optional[str]` | 否 | `None` | 机床端存储的程序名（默认使用文件名） | - |

### `AutoConnectRequest`

自动探测连接请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `machine_id` | `str` | 是 | `-` | 机床唯一标识 | - |
| `endpoints` | `list[str]` | 是 | `-` | 候选端点列表，按优先级排序 | - |
| `username` | `Optional[str]` | 否 | `None` | OPC UA 用户名 | - |
| `password` | `Optional[str]` | 否 | `None` | OPC UA 密码 | - |
| `timeout` | `float` | 否 | `5.0` | 单端点连接超时 | > 0; ≤ 30 |

### `DiscoverRequest`

资产发现请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `subnet` | `str` | 否 | `'192.168.1'` | 子网前缀 | - |
| `timeout` | `float` | 否 | `0.3` | 单端口扫描超时 | > 0; ≤ 2 |

### `DocumentCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `title` | `str` | 是 | `-` |  | - |
| `category` | `str` | 是 | `-` |  | - |
| `version` | `str` | 否 | `'v1.0'` |  | - |
| `author` | `str` | 是 | `-` |  | - |
| `content` | `Optional[str]` | 否 | `None` |  | - |
| `tags` | `list[str]` | 否 | `[]` |  | - |
| `status` | `str` | 否 | `'待审核'` |  | - |

### `DocumentUpdate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `title` | `Optional[str]` | 否 | `None` |  | - |
| `category` | `Optional[str]` | 否 | `None` |  | - |
| `version` | `Optional[str]` | 否 | `None` |  | - |
| `author` | `Optional[str]` | 否 | `None` |  | - |
| `content` | `Optional[str]` | 否 | `None` |  | - |
| `tags` | `Optional[list[str]]` | 否 | `None` |  | - |
| `status` | `Optional[str]` | 否 | `None` |  | - |

### `DxfProcessRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `dxf_path` | `str` | 是 | `-` |  | - |
| `output_dir` | `Optional[str]` | 否 | `None` |  | - |
| `postprocessor` | `Optional[str]` | 否 | `'fanuc_0i'` |  | - |
| `user_id` | `Optional[str]` | 否 | `None` |  | - |

### `DxfBatchRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `dxf_paths` | `list[str]` | 是 | `-` |  | 最小长度: 1; 最大长度: 20 |
| `output_dir` | `Optional[str]` | 否 | `None` |  | - |
| `postprocessor` | `Optional[str]` | 否 | `'fanuc_0i'` |  | - |
| `user_id` | `Optional[str]` | 否 | `None` |  | - |

### `DxfE2EFixtureRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `fixtures_dir` | `str` | 否 | `'data/test_fixtures'` |  | - |
| `output_dir` | `str` | 否 | `'data/outputs/e2e'` |  | - |
| `postprocessor` | `str` | 否 | `'fanuc_0i'` |  | - |
| `user_id` | `Optional[str]` | 否 | `'e2e_runner'` |  | - |

### `WearStateRequest`

刀具磨损状态请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `tool_id` | `int` | 是 | `-` | 刀具 ID | - |
| `wear_amount` | `float` | 是 | `-` | 当前磨损量 VB (mm) | ≥ 0.0 |
| `usage_time` | `float` | 是 | `-` | 累计使用时间 (分钟) | ≥ 0.0 |
| `wear_threshold` | `float` | 否 | `0.3` | 更换阈值 (mm) | > 0.0 |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |
| `tool_diameter` | `float` | 否 | `10.0` | 刀具直径 (mm) | > 0.0 |
| `flute_count` | `int` | 否 | `2` | 齿数 | ≥ 1 |

### `CurrentParametersRequest`

当前切削参数请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `cutting_speed` | `float` | 是 | `-` | 切削速度 (m/min) | > 0.0 |
| `feed_rate` | `float` | 是 | `-` | 每转进给 (mm/rev) | > 0.0 |
| `depth_of_cut` | `float` | 是 | `-` | 轴向切深 ap (mm) | > 0.0 |
| `width_of_cut` | `float` | 否 | `0.0` | 径向切深 ae (mm) | ≥ 0.0 |
| `spindle_rpm` | `Optional[float]` | 否 | `None` | 主轴转速 (RPM, None 时由切削速度反算) | ≥ 0.0 |
| `coolant_flow` | `float` | 否 | `10.0` | 冷却液流量 (L/min) | ≥ 0.0 |

### `MachineCapabilities`

机床能力上限。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `max_spindle_speed` | `Optional[float]` | 否 | `None` | 最大主轴转速 (RPM) | ≥ 0.0 |
| `max_feed_rate` | `Optional[float]` | 否 | `None` | 最大进给速度 (mm/min) | ≥ 0.0 |
| `max_power` | `Optional[float]` | 否 | `None` | 最大功率 (kW) | ≥ 0.0 |
| `max_torque` | `Optional[float]` | 否 | `None` | 最大扭矩 (N·m) | ≥ 0.0 |

### `CalibrationInput`

实时磨损校正入参（启用「实时信号 → 磨损模型在线校正 → 决策」闭环）。

与 ToolWearPredictor.calibrate_with_real_time_data 对齐。
schema 与 SignalFusionKnowledgeBase.SignalSample.sensor_features 完全兼容。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `real_time_wear` | `float` | 是 | `-` | 实测磨损量 (mm) | ≥ 0.0 |
| `sensor_features` | `dict[str, float]` | 是 | `-` | 传感器特征字典，支持 vibration_rms (g) / cutting_force (N) / temperature (°C) / acoustic_emission 等字段 | - |
| `elapsed_time` | `float` | 是 | `-` | 自上次校正以来的加工时间 (min) | > 0.0 |

### `DecideRequest`

参数调整决策请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `wear` | `WearStateRequest` | 是 | `-` |  | - |
| `current` | `CurrentParametersRequest` | 是 | `-` |  | - |
| `machine_capabilities` | `Optional[MachineCapabilities]` | 否 | `None` | 机床能力上限（None 使用默认） | - |
| `optimization_goal` | `str` | 否 | `'tool_life'` | 优化目标：efficiency / tool_life / surface_finish | - |
| `calibration` | `Optional[CalibrationInput]` | 否 | `None` | 可选实时校正入参。提供时启用 EWMA 校正闭环，用校正后磨损值驱动决策；未提供时走原始磨损值路径 | - |

### `AdjustmentDecisionInput`

P2-批次2 修复：``RewriteNCRequest.decision`` 的强类型替代裸 dict。

原 ``decision: dict[str, Any]`` 允许任意键穿透到 ``AdjustmentDecision``
构造，存在字段缺失/类型错误仅在运行时暴露的风险。改为 Pydantic 子模型
后，请求体在进入端点前即完成结构与类型校验。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `strategy` | `Literal[no_adjustment, slight_compensation, moderate_compensation, aggressive_compensation, replace_tool]` | 否 | `'no_adjustment'` |  | - |
| `urgency` | `Literal[normal, warning, critical]` | 否 | `'normal'` |  | - |
| `new_cutting_speed` | `float` | 否 | `0.0` |  | - |
| `new_feed_rate` | `float` | 否 | `0.0` |  | - |
| `new_depth_of_cut` | `float` | 否 | `0.0` |  | - |
| `new_spindle_rpm` | `float` | 否 | `0.0` |  | - |
| `new_feed_rate_mm_min` | `float` | 否 | `0.0` |  | - |
| `life_extension_pct` | `float` | 否 | `0.0` |  | - |
| `suggestions` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `warnings` | `list[str]` | 是 | `-` |  | - |
| `reasoning` | `list[str]` | 是 | `-` |  | - |

### `RewriteNCRequest`

NC 代码改写请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `nc_code` | `str` | 是 | `-` | NC/G 代码文本 | 最小长度: 1 |
| `decision` | `AdjustmentDecisionInput` | 是 | `-` | 由 /decide 返回的决策对象 | - |
| `controller_type` | `str` | 否 | `'fanuc'` | 控制器方言 (fanuc/siemens/heidenhain) | - |
| `apply_to_motion_only` | `bool` | 否 | `True` | 仅改写切削进给段（G01/G02/G03），跳过 G00 | - |

### `ClosedLoopRequest`

端到端闭环请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `wear` | `WearStateRequest` | 是 | `-` |  | - |
| `current` | `CurrentParametersRequest` | 是 | `-` |  | - |
| `nc_code` | `str` | 是 | `-` | 待改写的 NC/G 代码文本 | 最小长度: 1 |
| `machine_capabilities` | `Optional[MachineCapabilities]` | 否 | `None` |  | - |
| `optimization_goal` | `str` | 否 | `'tool_life'` |  | - |
| `controller_type` | `str` | 否 | `'fanuc'` |  | - |
| `apply_to_motion_only` | `bool` | 否 | `True` |  | - |
| `calibration` | `Optional[CalibrationInput]` | 否 | `None` | 可选实时校正入参。提供时启用 EWMA 校正闭环，用校正后磨损值驱动决策与 NC 改写 | - |

### `CalibrateWearRequest`

实时磨损校正请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `real_time_wear` | `float` | 是 | `-` | 实测磨损量 (mm) | ≥ 0.0 |
| `sensor_features` | `dict[str, float]` | 是 | `-` | 传感器特征（vibration_rms / cutting_force / temperature 等） | - |
| `elapsed_time` | `float` | 是 | `-` | 自上次校正以来的时间 (分钟) | > 0.0 |
| `input_parameters` | `dict[str, Any]` | 是 | `-` | 当前切削参数（cutting_speed/feed_rate/depth_of_cut/material_type/tool_type/tool_diameter/current_wear） | - |

### `EquipmentUpdateRequest`

更新设备状态和指标的请求体（白名单字段）。

与 service 层 ``_EQUIPMENT_ALLOWED_FIELDS`` 保持一致。
所有字段可选，至少传一个。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `status` | `Optional[str]` | 否 | `None` | 设备状态: 运行中/待机/维护中/故障 | - |
| `temperature` | `Optional[float]` | 否 | `None` | 温度 | - |
| `vibration` | `Optional[float]` | 否 | `None` | 振动 | - |
| `rpm` | `Optional[float]` | 否 | `None` | 转速 | - |
| `power` | `Optional[float]` | 否 | `None` | 功率 | - |

### `AlarmStatusUpdateRequest`

更新告警状态的请求体。

status 必须为 ``_ALARM_VALID_STATUSES`` 之一（service 层二次校验）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `status` | `str` | 是 | `-` | 告警状态: 未处理/已确认/已解决 | - |

### `MaintenancePlanUpdateRequest`

更新维护计划的请求体（白名单字段）。

与 service 层 ``_MAINTENANCE_ALLOWED_FIELDS`` 保持一致。
所有字段可选，至少传一个。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `title` | `Optional[str]` | 否 | `None` | 计划标题 | - |
| `type` | `Optional[str]` | 否 | `None` | 计划类型 | - |
| `frequency` | `Optional[str]` | 否 | `None` | 维护频率 | - |
| `last_date` | `Optional[str]` | 否 | `None` | 上次维护日期 | - |
| `next_date` | `Optional[str]` | 否 | `None` | 下次维护日期 | - |
| `status` | `Optional[str]` | 否 | `None` | 计划状态 | - |

### `GenerateHiddenStateRequest`

生成隐状态投影解释请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_uri` | `str` | 是 | `-` | 模型 URI | 最小长度: 1; 最大长度: 256 |
| `source_snapshot_id` | `Optional[str]` | 否 | `None` | 关联实验快照 ID（可选） | 最大长度: 64 |
| `projection_method` | `str` | 是 | `-` |  | - |
| `projection_dim` | `int` | 否 | `2` | 投影维度（2 或 3，默认 2） | ≥ 2; ≤ 3 |
| `max_frames` | `int` | 否 | `1000` | 最大帧数（超过则均匀采样） | ≥ 1; ≤ 10000 |
| `created_by` | `Optional[str]` | 否 | `None` | 创建者（user_id 或 plugin_id） | 最大长度: 128 |

### `GenerateGateDynamicsRequest`

生成门控动力学解释请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_uri` | `str` | 是 | `-` | 模型 URI | 最小长度: 1; 最大长度: 256 |
| `source_snapshot_id` | `Optional[str]` | 否 | `None` | 关联实验快照 ID（可选） | 最大长度: 64 |
| `anomaly_sigma` | `float` | 否 | `2.0` | 异常检测阈值（门控值超过 mean ± sigma*std 的帧，默认 2.0） | ≥ 1.0; ≤ 5.0 |
| `created_by` | `Optional[str]` | 否 | `None` | 创建者（user_id 或 plugin_id） | 最大长度: 128 |

### `GenerateCounterfactualRequest`

生成反事实解释请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_uri` | `str` | 是 | `-` | 模型 URI | 最小长度: 1; 最大长度: 256 |
| `base_input` | `dict[str, float]` | 是 | `-` | 基准输入（特征名 → 值），至少 1 个特征 | - |
| `perturbed_feature` | `str` | 是 | `-` | 被扰动的特征名 | 最小长度: 1; 最大长度: 64 |
| `perturbation_range` | `Optional[list[float]]` | 否 | `None` | 扰动值序列（如为空则按 perturbation_step 生成） | - |
| `perturbation_step` | `float` | 否 | `0.05` | 扰动步长（相对基准值的比例，默认 0.05 即 5%） | ≥ 0.01; ≤ 0.5 |
| `source_snapshot_id` | `Optional[str]` | 否 | `None` | 关联实验快照 ID（可选） | 最大长度: 64 |
| `created_by` | `Optional[str]` | 否 | `None` | 创建者（user_id 或 plugin_id） | 最大长度: 128 |

### `GenerateConfidenceRequest`

生成置信度分布解释请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_uri` | `str` | 是 | `-` | 模型 URI | 最小长度: 1; 最大长度: 256 |
| `input_data` | `dict[str, Any]` | 是 | `-` | 输入数据（特征名 → 值） | - |
| `sample_count` | `int` | 否 | `30` | MC dropout 采样次数（默认 30） | ≥ 5; ≤ 200 |
| `source_snapshot_id` | `Optional[str]` | 否 | `None` | 关联实验快照 ID（可选） | 最大长度: 64 |
| `created_by` | `Optional[str]` | 否 | `None` | 创建者（user_id 或 plugin_id） | 最大长度: 128 |

### `CompareExplanationsRequest`

对比两个解释请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `base_explanation_id` | `str` | 是 | `-` | 基准解释记录 ID | 最小长度: 1; 最大长度: 64 |
| `compared_explanation_id` | `str` | 是 | `-` | 对比解释记录 ID | 最小长度: 1; 最大长度: 64 |
| `comparison_type` | `str` | 是 | `-` |  | - |
| `created_by` | `Optional[str]` | 否 | `None` | 创建者（user_id 或 plugin_id） | 最大长度: 128 |

### `MetricDefinition`

指标定义。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` | 指标名称 | - |
| `description` | `str` | 是 | `-` | 指标含义 | - |
| `unit` | `str` | 是 | `-` | 单位 | - |
| `range` | `str` | 是 | `-` | 取值范围 | - |
| `calculation` | `str` | 是 | `-` | 计算方式 | - |

### `FlywheelStatusResponse`

飞轮状态响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `status` | `str` | 是 | `-` | 飞轮状态: healthy / warning / critical | - |
| `data_volume` | `int` | 是 | `-` | 加工记录数（条） | - |
| `model_quality` | `float` | 是 | `-` | 模型质量（%，0-100） | - |
| `adoption_rate` | `float` | 是 | `-` | 用户采纳率（%，0-100） | - |
| `uncertainty_mean` | `float` | 是 | `-` | 不确定性均值（0-1） | - |
| `feedback_delay` | `float` | 是 | `-` | 回灌延迟（分钟） | - |
| `health_score` | `float` | 是 | `-` | 健康分数（0-100） | - |
| `timestamp` | `str` | 是 | `-` | 采集时间（ISO 8601） | - |

### `FlywheelReportResponse`

飞轮报告响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `report_type` | `str` | 是 | `-` |  | - |
| `generated_at` | `str` | 是 | `-` |  | - |
| `period` | `dict[str, str]` | 是 | `-` |  | - |
| `current_metrics` | `dict[str, Any]` | 是 | `-` |  | - |
| `trends` | `dict[str, Any]` | 是 | `-` |  | - |
| `summary` | `dict[str, Any]` | 是 | `-` |  | - |

### `MetricDefinitionsResponse`

指标定义列表响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `metrics` | `list[MetricDefinition]` | 是 | `-` |  | - |

### `GoalCreateRequest`

目标对齐创建请求模型。

字段对应 ``create_goal`` 端点原本从 ``data: dict`` 读取的键：
level/status 在端点内会再做枚举校验（GoalLevel / GoalStatus），
因此这里仅做基础字符串校验，避免重复实现枚举错误处理逻辑。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `level` | `str` | 否 | `'task'` | 目标层级: mission/strategic_goal/project/task | - |
| `status` | `str` | 否 | `'not_started'` | 目标状态: not_started/in_progress/completed/cancelled | - |
| `id` | `Optional[str]` | 否 | `None` | 目标ID（不传则自动生成） | - |
| `name` | `str` | 否 | `''` | 目标名称 | - |
| `description` | `str` | 否 | `''` | 目标描述 | - |
| `parent_id` | `Optional[str]` | 否 | `None` | 父目标ID（非 mission 必填） | - |

### `CreateApprovalRequest`

创建审批请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` | 任务 ID | - |
| `requester` | `str` | 是 | `-` | 请求人 | - |
| `context` | `dict` | 是 | `-` | 上下文 | - |
| `budget_amount` | `float` | 否 | `0.0` | 预算金额（必须 >=0） | ≥ 0.0 |
| `agent_role` | `str` | 否 | `'engineer'` | 代理角色 | - |

### `AssignApproverRequest`

指派审批人请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `approver_id` | `Optional[str]` | 否 | `None` | 审批人 ID | - |

### `MakeDecisionRequest`

审批决策请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `approver_id` | `str` | 是 | `-` | 审批人 ID | - |
| `decision` | `str` | 是 | `-` | 决策: approved/rejected/escalated/request_info | - |
| `comment` | `str` | 否 | `''` | 备注 | - |

### `EscalateRequest`

审批升级请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `escalator_id` | `str` | 否 | `'system'` | 升级操作人 ID | - |
| `reason` | `str` | 否 | `''` | 升级原因 | - |

### `AssessRiskRequest`

风险评估请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `operation_id` | `Optional[str]` | 否 | `None` | 操作 ID（None 自动生成） | - |
| `operation_type` | `str` | 是 | `-` | 操作类型（仅允许字母、数字、下划线、连字符） | 最小长度: 1; 最大长度: 100; 正则: `^[A-Za-z0-9_-]+$` |
| `context` | `dict` | 是 | `-` | 上下文 | - |
| `requester_role` | `str` | 否 | `'engineer'` | 请求人角色 | - |
| `budget_amount` | `float` | 否 | `0.0` | 预算金额（必须 >=0） | ≥ 0.0 |

### `EmergencyOverrideRequest`

紧急覆盖请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `request_id` | `str` | 是 | `-` | 关联的审批请求ID | - |
| `task_id` | `str` | 是 | `-` | 任务ID | - |
| `operator_id` | `str` | 是 | `-` | 操作员ID | - |
| `reason` | `str` | 是 | `-` | 紧急覆盖原因 | - |
| `emergency_type` | `str` | 否 | `'production_halt'` | 紧急类型 | - |

### `CompleteRetroactiveRequest`

完成事后审批请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `emergency_id` | `Optional[str]` | 否 | `None` | 紧急操作 ID | - |

### `CreateDelegationRequest`

创建委托请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `delegator_id` | `str` | 是 | `-` | 委托人 ID | - |
| `delegate_id` | `str` | 是 | `-` | 被委托人 ID | - |
| `start_time` | `float` | 是 | `-` | 开始时间（Unix 时间戳） | - |
| `end_time` | `float` | 是 | `-` | 结束时间（Unix 时间戳） | - |
| `reason` | `str` | 否 | `''` | 委托原因 | - |

### `CreateScheduledTaskRequest`

创建调度任务请求

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` | 任务唯一标识符 | 最小长度: 1 |
| `agent_id` | `str` | 是 | `-` | 执行代理ID | 最小长度: 1 |
| `schedule` | `str` | 是 | `-` | Cron表达式（分 时 日 月 星期） | 最小长度: 1 |
| `task_type` | `str` | 是 | `-` | 任务类型（lnn_inference/lnn_training/lnn_analysis） | 最小长度: 1 |
| `params` | `Dict[str, Any]` | 是 | `-` | 任务参数 | - |
| `metadata` | `Dict[str, Any]` | 是 | `-` | 任务元数据 | - |
| `max_retries` | `int` | 否 | `3` | 最大重试次数 | ≥ 0; ≤ 10 |

### `TaskResponse`

任务响应

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `agent_id` | `str` | 是 | `-` |  | - |
| `schedule` | `str` | 是 | `-` |  | - |
| `task_type` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `last_run` | `Optional[float]` | 否 | `None` |  | - |
| `next_run` | `Optional[float]` | 否 | `None` |  | - |
| `retry_count` | `int` | 否 | `0` |  | - |
| `max_retries` | `int` | 否 | `3` |  | - |
| `params` | `Dict[str, Any]` | 否 | `{}` |  | - |
| `metadata` | `Dict[str, Any]` | 否 | `{}` |  | - |

### `BudgetCheckResponse`

预算检查响应

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `passed` | `bool` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `usages` | `List[Dict[str, Any]]` | 否 | `[]` |  | - |
| `warnings` | `List[str]` | 否 | `[]` |  | - |
| `blocked_reasons` | `List[str]` | 否 | `[]` |  | - |

### `ExecutionResultResponse`

执行结果响应

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `duration_ms` | `float` | 是 | `-` |  | - |
| `result_data` | `Optional[Dict[str, Any]]` | 否 | `None` |  | - |
| `error_message` | `Optional[str]` | 否 | `None` |  | - |
| `resource_usage` | `Dict[str, Any]` | 否 | `{}` |  | - |

### `CreateJobRequest`

通用任务创建请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_type` | `str` | 是 | `-` | 任务类型（lnn_training/lnn_inference/data_processing 等） | - |
| `params` | `dict` | 是 | `-` | 任务参数 | - |
| `name` | `Optional[str]` | 否 | `None` | 任务名称（并入 params.name） | 最大长度: 128 |
| `idempotency_key` | `Optional[str]` | 否 | `None` | 幂等键 | 最大长度: 128 |

### `GraphQueryRequest`

``POST /query`` 请求体模型。

用 Pydantic 验证替代原始 dict，避免 ``**params`` 解包触发 TypeError。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `query_type` | `str` | 是 | `-` | 查询类型，如 search_nodes | - |
| `params` | `dict[str, Any]` | 是 | `-` | 查询参数键值对 | - |

### `ProviderCreateRequest`

创建/更新 Provider 请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `provider_id` | `str` | 是 | `-` | Provider 唯一标识 | - |
| `name` | `str` | 是 | `-` | 显示名称 | - |
| `provider_type` | `str` | 是 | `-` | Provider 类型（ollama/openai/...） | - |
| `base_url` | `str` | 否 | `''` | API 基地址 | - |
| `api_key` | `str` | 否 | `''` | API Key（云端 Provider 用，明文传入，服务端加密存储） | - |
| `default_model` | `str` | 否 | `''` | 默认模型名称 | - |
| `timeout` | `int` | 否 | `60` |  | ≥ 5; ≤ 600 |
| `max_retries` | `int` | 否 | `3` |  | ≥ 0; ≤ 10 |
| `retry_delay` | `float` | 否 | `1.0` |  | ≥ 0.0; ≤ 30.0 |
| `enabled` | `bool` | 否 | `True` |  | - |
| `priority` | `int` | 否 | `0` |  | ≥ 0; ≤ 100 |
| `capabilities` | `list[str]` | 是 | `-` | 能力标签列表 | - |
| `extra` | `dict[str, Any]` | 是 | `-` |  | - |

### `ProviderUpdateRequest`

部分更新 Provider 请求体（所有字段可选）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str | None` | 否 | `None` |  | - |
| `base_url` | `str | None` | 否 | `None` |  | - |
| `api_key` | `str | None` | 否 | `None` | 留空表示不更新；显式传空串表示清除 | - |
| `default_model` | `str | None` | 否 | `None` |  | - |
| `timeout` | `int | None` | 否 | `None` |  | ≥ 5; ≤ 600 |
| `max_retries` | `int | None` | 否 | `None` |  | ≥ 0; ≤ 10 |
| `retry_delay` | `float | None` | 否 | `None` |  | ≥ 0.0; ≤ 30.0 |
| `enabled` | `bool | None` | 否 | `None` |  | - |
| `priority` | `int | None` | 否 | `None` |  | ≥ 0; ≤ 100 |
| `capabilities` | `list[str] | None` | 否 | `None` |  | - |
| `extra` | `dict[str, Any] | None` | 否 | `None` |  | - |

### `ChatTestRequest`

Provider 调用测试请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `messages` | `list[dict[str, str]]` | 是 | `-` | 消息列表，例如 [{'role':'user','content':'hello'}] | - |
| `max_tokens` | `int` | 否 | `256` |  | ≥ 1; ≤ 8192 |
| `temperature` | `float` | 否 | `0.7` |  | ≥ 0.0; ≤ 2.0 |
| `model` | `str | None` | 否 | `None` | 可选，覆盖默认模型 | - |

### `MaterialCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `code` | `str` | 是 | `-` | 物料编码 | 最小长度: 1; 最大长度: 64 |
| `name` | `str` | 是 | `-` | 名称 | 最小长度: 1; 最大长度: 128 |
| `spec` | `str` | 否 | `''` | 规格 | 最大长度: 256 |
| `category` | `str` | 否 | `'原材料'` | 分类: 原材料/半成品/成品 | 最大长度: 32 |
| `quantity` | `int` | 否 | `0` | 库存数量 | ≥ 0 |
| `safe_quantity` | `int` | 否 | `0` | 安全库存 | ≥ 0 |
| `status` | `str` | 否 | `'正常'` | 状态: 正常/低库存/缺货 | 最大长度: 16 |
| `location` | `str` | 否 | `''` | 库位 | 最大长度: 64 |
| `unit` | `str` | 否 | `''` | 单位 | 最大长度: 16 |
| `supplier` | `str` | 否 | `''` | 供应商 | 最大长度: 128 |

### `MaterialUpdate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `code` | `Optional[str]` | 否 | `None` | 物料编码 | 最大长度: 64 |
| `name` | `Optional[str]` | 否 | `None` | 名称 | 最大长度: 128 |
| `spec` | `Optional[str]` | 否 | `None` | 规格 | 最大长度: 256 |
| `category` | `Optional[str]` | 否 | `None` | 分类 | 最大长度: 32 |
| `quantity` | `Optional[int]` | 否 | `None` | 库存数量 | ≥ 0 |
| `safe_quantity` | `Optional[int]` | 否 | `None` | 安全库存 | ≥ 0 |
| `status` | `Optional[str]` | 否 | `None` | 状态 | 最大长度: 16 |
| `location` | `Optional[str]` | 否 | `None` | 库位 | 最大长度: 64 |
| `unit` | `Optional[str]` | 否 | `None` | 单位 | 最大长度: 16 |
| `supplier` | `Optional[str]` | 否 | `None` | 供应商 | 最大长度: 128 |

### `StockInRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `quantity` | `int` | 是 | `-` | 入库数量 | > 0; ≤ 100000 |
| `remark` | `Optional[str]` | 否 | `None` | 入库备注 | 最大长度: 200 |

### `PurchaseRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `quantity` | `int` | 是 | `-` | 采购数量 | > 0; ≤ 100000 |
| `supplier` | `Optional[str]` | 否 | `None` | 供应商 | 最大长度: 128 |

### `ExecutionRecordRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` | Task ID | - |
| `branch_id` | `str` | 是 | `-` | Branch ID | - |
| `elements` | `Dict[str, Any]` | 是 | `-` | Execution elements | - |
| `conditions` | `Dict[str, Any]` | 是 | `-` | Execution conditions | - |
| `metrics` | `Dict[str, Any]` | 是 | `-` | Execution metrics | - |

### `ExplainProcessRequest`

工艺规划解释请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `process_plan` | `dict[str, Any]` | 是 | `-` | 工艺规划 JSON | - |
| `user_question` | `str` | 否 | `''` | 用户上下文问题 | - |
| `material` | `str` | 否 | `''` | 工件材料 | - |
| `blank_size` | `str` | 否 | `''` | 毛坯尺寸描述 | - |
| `feature_count` | `Optional[int]` | 否 | `None` | 加工特征数（None 自动推断） | ≥ 0 |
| `session_id` | `Optional[str]` | 否 | `None` | 会话 ID（None 新建） | - |

### `ExplainNCRequest`

NC 代码解释请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `nc_code` | `str` | 是 | `-` | NC/G 代码文本 | 最小长度: 1 |
| `controller_type` | `str` | 否 | `'fanuc'` | 控制器类型（fanuc/siemens/heidenhain 等） | - |
| `user_question` | `str` | 否 | `''` | 用户上下文问题 | - |
| `session_id` | `Optional[str]` | 否 | `None` | 会话 ID（None 新建） | - |

### `ChatRequest`

多轮对话请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `message` | `str` | 是 | `-` | 用户消息 | 最小长度: 1 |
| `session_id` | `Optional[str]` | 否 | `None` | 会话 ID（None 新建） | - |

### `ProcessStepCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `sequence` | `int` | 是 | `-` |  | - |
| `name` | `str` | 是 | `-` |  | - |
| `work_center` | `str` | 是 | `-` |  | - |
| `hours` | `int` | 是 | `-` |  | - |
| `equipment` | `Optional[str]` | 否 | `None` |  | - |
| `tooling` | `Optional[str]` | 否 | `None` |  | - |

### `ProcessRouteCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` |  | - |
| `part_type` | `str` | 是 | `-` |  | - |
| `status` | `str` | 否 | `'草稿'` |  | - |
| `description` | `Optional[str]` | 否 | `None` |  | - |
| `steps` | `list[ProcessStepCreate]` | 否 | `[]` |  | - |

### `ProcessRouteUpdate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `Optional[str]` | 否 | `None` |  | - |
| `part_type` | `Optional[str]` | 否 | `None` |  | - |
| `status` | `Optional[str]` | 否 | `None` |  | - |
| `description` | `Optional[str]` | 否 | `None` |  | - |
| `steps` | `Optional[list[ProcessStepCreate]]` | 否 | `None` |  | - |

### `WorkOrderUpdate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `product_name` | `Optional[str]` | 否 | `None` |  | - |
| `planned_qty` | `Optional[int]` | 否 | `None` |  | - |
| `completed_qty` | `Optional[int]` | 否 | `None` |  | - |
| `status` | `Optional[str]` | 否 | `None` |  | - |
| `priority` | `Optional[str]` | 否 | `None` |  | - |
| `start_date` | `Optional[date]` | 否 | `None` |  | - |
| `due_date` | `Optional[date]` | 否 | `None` |  | - |

### `ExportProjectRequest`

导出项目请求体（JSON）.

将项目及其引用资源打包为 ``.lomo`` 文件。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `project_id` | `str` | 是 | `-` | 源项目 ID | 最小长度: 1; 最大长度: 64 |
| `exported_by` | `str` | 是 | `-` | 导出者（user_id 或 plugin_id） | 最小长度: 1; 最大长度: 128 |
| `output_dir` | `str` | 否 | `''` | 输出目录（空字符串表示使用服务层默认目录） | 最大长度: 512 |
| `content_policy` | `str` | 是 | `-` |  | - |
| `include_datasets` | `bool` | 否 | `True` | 是否打包数据集资源 | - |
| `include_models` | `bool` | 否 | `True` | 是否打包模型产物资源 | - |
| `include_workflows` | `bool` | 否 | `True` | 是否打包工作流定义 | - |
| `include_configs` | `bool` | 否 | `True` | 是否打包配置规格 | - |
| `include_snapshots` | `bool` | 否 | `True` | 是否打包实验快照元数据 | - |
| `include_lineage` | `bool` | 否 | `True` | 是否打包血缘记录 | - |
| `max_file_size_bytes` | `int` | 是 | `-` | small_files_only 策略下的文件大小阈值（字节，默认 10MB） | ≥ 1 |
| `output_filename` | `str` | 否 | `''` | 自定义输出文件名（不含路径，空字符串使用默认模板） | 最大长度: 256 |

### `CreateProjectRequest`

创建项目请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` | 项目显示名 | 最小长度: 1; 最大长度: 256 |
| `description` | `str` | 否 | `''` | 项目描述 | 最大长度: 2048 |
| `author` | `str` | 否 | `''` | 项目作者 | 最大长度: 128 |
| `remote_url` | `str` | 否 | `''` | 远端仓库 URL（空表示纯本地仓库） | 最大长度: 1024 |
| `branch` | `str` | 否 | `'main'` | 初始分支名 | 最大长度: 128 |
| `initial_commit` | `bool` | 否 | `True` | 是否在创建时生成首个 commit | - |

### `CloneProjectRequest`

克隆远端项目请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `remote_url` | `str` | 是 | `-` | 远端仓库 URL | 最小长度: 1; 最大长度: 1024 |
| `name` | `str` | 是 | `-` | 项目显示名 | 最小长度: 1; 最大长度: 256 |
| `branch` | `str` | 否 | `'main'` | 检出分支名 | 最大长度: 128 |
| `description` | `str` | 否 | `''` | 项目描述 | 最大长度: 2048 |
| `author` | `str` | 否 | `''` | 项目作者 | 最大长度: 128 |

### `CommitRequest`

提交变更请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `message` | `str` | 是 | `-` | commit message | 最小长度: 1; 最大长度: 2048 |

### `AddResourceRequest`

添加资源引用请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `resource_type` | `str` | 是 | `-` |  | - |
| `resource_uri` | `str` | 是 | `-` | 资源 URI（如 dataset://phm2010/v3） | 最大长度: 512 |
| `sync_strategy` | `str` | 是 | `-` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` | 附加元数据 | - |

### `QualityRecordCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `batch_no` | `str` | 是 | `-` |  | - |
| `inspection_type` | `str` | 是 | `-` |  | - |
| `result` | `str` | 是 | `-` |  | - |
| `inspector` | `str` | 是 | `-` |  | - |
| `notes` | `Optional[str]` | 否 | `None` |  | - |

### `QualityAnomalyCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `record_id` | `str` | 是 | `-` |  | - |
| `anomaly_type` | `str` | 是 | `-` |  | - |
| `description` | `Optional[str]` | 否 | `None` |  | - |
| `severity` | `str` | 是 | `-` |  | - |

### `UpsertDatasetReadmeRequest`

更新数据集 README 请求体（upsert 语义）.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `readme_md` | `str` | 是 | `-` | markdown README 内容 | 最小长度: 1; 最大长度: 200000 |
| `updated_by` | `str` | 是 | `-` | 最后更新者（user_id 或 plugin_id） | 最小长度: 1; 最大长度: 128 |
| `version` | `Optional[str]` | 否 | `None` | 版本号（如 1.0.0），不传则更新数据集级 README | - |

### `RegisterModelRequest`

注册新模型产物请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_uri` | `str` | 是 | `-` | 模型 URI（model://<name>/<version>），全局唯一 | 最小长度: 1; 最大长度: 512 |
| `name` | `str` | 是 | `-` | 模型显示名 | 最小长度: 1; 最大长度: 128 |
| `model_type` | `str` | 是 | `-` |  | - |
| `version` | `str` | 是 | `-` | semver 版本号（如 1.0.0） | 最小长度: 1; 最大长度: 32 |
| `framework` | `str` | 是 | `-` | 框架版本（如 torch-2.1.0） | 最小长度: 1; 最大长度: 64 |
| `storage_uri` | `str` | 是 | `-` | 模型文件存储位置 | 最小长度: 1; 最大长度: 512 |
| `owner_id` | `str` | 是 | `-` | 所有者 ID | 最小长度: 1; 最大长度: 128 |
| `readme_md` | `str` | 否 | `''` | markdown README | 最大长度: 200000 |
| `tags` | `list[str]` | 是 | `-` | 标签数组 | - |
| `metrics` | `dict[str, Any]` | 是 | `-` | 初始指标快照（如 accuracy/loss） | - |
| `status` | `str` | 是 | `-` |  | - |

### `UpdateModelRequest`

更新模型卡片请求体（部分更新，仅非 None 字段被写入）.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `readme_md` | `Optional[str]` | 否 | `None` | markdown README | 最小长度: 1; 最大长度: 200000 |
| `tags` | `Optional[list[str]]` | 否 | `None` | 标签数组 | - |
| `status` | `Optional[str]` | 否 | `None` |  | - |
| `metrics` | `Optional[dict[str, Any]]` | 否 | `None` | 覆盖当前指标快照（不会追加到 history，请用 POST /metrics 追加） | - |
| `framework` | `Optional[str]` | 否 | `None` | 框架版本 | 最小长度: 1; 最大长度: 64 |
| `storage_uri` | `Optional[str]` | 否 | `None` | 模型文件存储位置 | 最小长度: 1; 最大长度: 512 |

### `AppendModelMetricsRequest`

追加模型指标记录请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `metrics` | `dict[str, Any]` | 是 | `-` | 指标字典（如 {'accuracy': 0.95, 'loss': 0.05}） | - |
| `timestamp` | `Optional[str]` | 否 | `None` | 自定义时间戳（ISO8601），不传则使用服务器当前时间 | - |

### `SafetyConstraintsModel`

安全约束规格（与 ``SafetyConstraintsSpec`` 对齐）.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `max_chatter_probability` | `float` | 否 | `0.3` | 最大允许颤振概率 [0, 1]，默认 0.3 | ≥ 0.0; ≤ 1.0 |
| `max_tool_wear_increment` | `float` | 否 | `0.01` | 最大允许刀具磨损增量 (mm/步)，默认 0.01 | > 0.0 |
| `min_surface_quality` | `float` | 否 | `0.8` | 最小表面质量 [0, 1]，默认 0.8 | ≥ 0.0; ≤ 1.0 |

### `RLActRequestModel`

RL 决策请求体.

与 ``app.contracts.rl_agent.RLActRequest`` 对齐，但使用 Pydantic
以获得自动校验和 OpenAPI 文档。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_state` | `dict[str, float]` | 是 | `-` | 当前加工状态（字段名见 StateField，至少包含全部 8 个状态字段） | - |
| `candidate_actions` | `list[dict[str, float]]` | 是 | `-` | 候选动作集（至少 1 个，每个动作含 4 个 delta 字段） | 最小长度: 1 |
| `optimization_target` | `str` | 是 | `-` |  | - |
| `safety_constraints` | `Optional[SafetyConstraintsModel]` | 否 | `None` | 安全约束规格（为空则使用默认值） | - |
| `model_uri` | `str` | 否 | `'model://rl_agent/1.0.0'` | RL 策略模型 URI | 最小长度: 1; 最大长度: 256 |

### `TrainingStartRequestModel`

启动训练请求体.

与 ``app.contracts.rl_agent.TrainingStartRequest`` 对齐。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `max_steps` | `int` | 否 | `100000` | 最大训练步数（1000 ~ 1000000，默认 100000） | ≥ 1000; ≤ 1000000 |
| `seed` | `Optional[int]` | 否 | `None` | 随机种子（为空则使用训练器默认 42） | ≥ 0 |
| `algorithm` | `str` | 是 | `-` |  | - |
| `optimization_target` | `str` | 是 | `-` |  | - |

### `SignalSampleRequest`

信号样本注册请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `signal_type` | `str` | 是 | `-` | 信号类型 | - |
| `source` | `str` | 是 | `-` | 数据源标识 | - |
| `features` | `list[float]` | 是 | `-` | 9 维特征向量 | 最小长度: 1 |
| `sensor_features` | `dict[str, float]` | 是 | `-` | 传感器读数（与 ToolWearPredictor 对齐） | - |
| `process_context` | `dict[str, Any]` | 是 | `-` | 工艺上下文 | - |
| `machine_id` | `str` | 否 | `''` | 机床 ID | - |
| `tool_id` | `Optional[int]` | 否 | `None` | 刀具 ID | - |
| `material` | `str` | 否 | `''` | 工件材料 | - |
| `label` | `str` | 否 | `''` | 可选标签 | - |
| `sample_id` | `Optional[str]` | 否 | `None` | 自定义样本 ID | - |
| `metadata` | `dict[str, Any]` | 是 | `-` | 额外元数据 | - |

### `BatchSamplesRequest`

批量注册请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `samples` | `list[SignalSampleRequest]` | 是 | `-` |  | 最小长度: 1; 最大长度: 500 |

### `RetrieveRequest`

相似样本检索请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `features` | `list[float]` | 是 | `-` | 9 维查询特征 | 最小长度: 1 |
| `signal_type` | `Optional[str]` | 否 | `None` | 信号类型过滤 | - |
| `machine_id` | `Optional[str]` | 否 | `None` | 机床 ID 过滤 | - |
| `material` | `Optional[str]` | 否 | `None` | 材料过滤 | - |
| `tool_id` | `Optional[int]` | 否 | `None` | 刀具 ID 过滤 | - |
| `top_k` | `int` | 否 | `10` | 返回前 K 个 | ≥ 1; ≤ 100 |

### `FuseRequest`

多源信号融合请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `sample_ids` | `list[str]` | 是 | `-` | 参与融合的样本 ID 列表（与 samples 二选一） | - |
| `samples` | `list[SignalSampleRequest]` | 是 | `-` | 直接传入样本数据（与 sample_ids 二选一） | - |
| `strategy` | `str` | 否 | `'weighted'` | 融合策略: weighted 或 attention | - |
| `weights` | `Optional[dict[str, float]]` | 否 | `None` | 自定义权重（仅 weighted 策略） | - |

### `CorrelateWearRequest`

磨损关联请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `sample_ids` | `list[str]` | 是 | `-` | 信号样本 ID 列表 | - |
| `samples` | `list[SignalSampleRequest]` | 是 | `-` | 直接传入样本数据 | - |

### `CorrelateChatterRequest`

颤振关联请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `sample_ids` | `list[str]` | 是 | `-` | 信号样本 ID 列表 | - |
| `samples` | `list[SignalSampleRequest]` | 是 | `-` | 直接传入样本数据 | - |
| `process_context` | `dict[str, Any]` | 是 | `-` | 工艺上下文覆盖（优先级高于样本内的 process_context） | - |

### `SkillContentRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_id` | `str` | 是 | `-` | 技能唯一标识符 | - |
| `content` | `str` | 是 | `-` | 技能 Markdown 完整内容 | - |
| `level` | `str` | 否 | `'project'` | 技能层级: global/project/agent | - |
| `sub_id` | `Optional[str]` | 否 | `None` | 项目ID或代理ID | - |

### `SkillExportRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_id` | `str` | 是 | `-` | 要导出的技能ID | - |

### `SkillImportRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_package` | `Dict[str, Any]` | 是 | `-` | 技能包数据 | - |
| `level` | `str` | 否 | `'project'` | 导入层级 | - |
| `sub_id` | `Optional[str]` | 否 | `None` | 项目ID或代理ID | - |

### `SkillRatingRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_id` | `str` | 是 | `-` | 技能ID | - |
| `rating` | `float` | 是 | `-` | 评分 (0-5) | ≥ 0; ≤ 5 |

### `SkillPublishRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_id` | `str` | 是 | `-` | 技能ID | - |
| `author` | `str` | 是 | `-` | 发布者 | - |

### `SkillDownloadRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_id` | `str` | 是 | `-` | 技能ID | - |
| `target_level` | `str` | 否 | `'project'` | 目标层级 | - |
| `target_sub_id` | `Optional[str]` | 否 | `None` | 目标项目/代理ID | - |

### `SkillMarketplaceRateRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `skill_id` | `str` | 是 | `-` | 技能ID | - |
| `rating` | `float` | 是 | `-` | 评分 (0-5) | ≥ 0; ≤ 5 |
| `agent_id` | `str` | 否 | `''` | 评分的代理ID | - |

### `CreateSnapshotRequest`

创建实验快照请求体。

config 中可包含 ``workflow_spec`` 字段（dict 形式的 WorkflowSpec），
用于支持后续一键复现。其余字段由调用方按实验实际填写。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `config` | `dict[str, Any]` | 是 | `-` | 实验配置，可包含 workflow_spec / hyperparams / seed 等 | - |
| `dataset_versions` | `list[str]` | 是 | `-` | 关联的数据集版本 URI 列表（dataset://<name>/<version>） | - |
| `model_uri` | `str` | 是 | `-` | 模型 URI，如 model://ltc/1.0.0 | - |
| `metrics` | `dict[str, float]` | 是 | `-` | 实验指标，如 {'mae': 0.123, 'r2': 0.956} | - |
| `created_by` | `str` | 是 | `-` | 创建者标识（用户 ID 或 agent ID） | - |
| `notes` | `str` | 否 | `''` | 备注信息 | - |

### `RegisterTaskRequest`

任务注册请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `id` | `str` | 是 | `-` | 任务 ID | - |
| `title` | `str` | 否 | `''` | 任务标题 | - |
| `description` | `str` | 否 | `''` | 任务描述 | - |
| `task_type` | `str` | 否 | `'execution'` | 任务类型 | - |
| `status` | `str` | 否 | `'pending'` | 任务状态 | - |
| `assigned_to` | `Optional[str]` | 否 | `None` | 指派给 | - |
| `parent_goal_id` | `Optional[str]` | 否 | `None` | 父目标 ID | - |
| `project_id` | `Optional[str]` | 否 | `None` | 项目 ID | - |
| `required_gpu_memory` | `float` | 否 | `0.0` | 所需 GPU 显存 | - |
| `blockers` | `Union[list[str], str]` | 是 | `-` | 阻塞依赖（列表或 JSON 字符串） | - |
| `priority` | `int` | 否 | `3` | 优先级 1-5 | ≥ 1; ≤ 5 |

### `CheckoutTaskRequest`

任务签出请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` | 任务 ID | - |
| `agent_id` | `str` | 是 | `-` | 代理 ID | - |
| `agent_mode` | `str` | 否 | `'single'` | 代理模式 | - |
| `priority` | `int` | 否 | `3` | 优先级 1-5 | ≥ 1; ≤ 5 |
| `required_gpu_memory` | `float` | 否 | `0.0` | 所需 GPU 显存 | - |
| `timeout_hours` | `float` | 否 | `4.0` | 超时小时数 | ≥ 0 |

### `HeartbeatRequest`

任务心跳请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 是 | `-` | 代理 ID | - |

### `CompleteTaskRequest`

任务完成请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 是 | `-` | 代理 ID | - |

### `FailTaskRequest`

任务失败上报请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 是 | `-` | 代理 ID | - |
| `reason` | `str` | 否 | `''` | 失败原因 | - |

### `AbandonTaskRequest`

任务放弃请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 是 | `-` | 代理 ID | - |

### `EnqueueCheckoutRequest`

签出队列入队请求模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` | 任务 ID | - |
| `agent_id` | `str` | 是 | `-` | 代理 ID | - |
| `priority` | `int` | 否 | `3` | 优先级 1-5 | ≥ 1; ≤ 5 |
| `agent_mode` | `str` | 否 | `'single'` | 代理模式 | - |
| `required_gpu_memory` | `float` | 否 | `0.0` | 所需 GPU 显存 | - |
| `timeout_hours` | `float` | 否 | `4.0` | 超时小时数 | ≥ 0 |

### `CreateExperimentRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` | Experiment name | - |
| `control_branch` | `str` | 是 | `-` | Control branch ID | - |
| `candidate_branch` | `str` | 是 | `-` | Candidate branch ID | - |
| `traffic_split` | `float` | 否 | `0.1` | Traffic split for candidate (0.0-1.0) | - |

### `RecordExecutionRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `experiment_id` | `str` | 是 | `-` | Experiment ID | - |
| `branch` | `str` | 是 | `-` | Branch used (control/candidate) | - |
| `execution_time` | `float` | 是 | `-` | Execution time in seconds | - |
| `resource_cost` | `float` | 否 | `0.0` | Resource cost | - |

### `AssignBranchRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `project_id` | `str` | 是 | `-` | Project ID | - |

### `CreateBranchRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` |  | - |
| `base_branch` | `Optional[str]` | 否 | `None` |  | - |
| `data` | `dict[str, Any]` | 是 | `-` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` |  | - |

### `MergeBranchRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_id` | `str` | 是 | `-` |  | - |
| `target_id` | `str` | 是 | `-` |  | - |
| `strategy` | `str` | 否 | `'overwrite'` |  | - |

### `UpdateBranchRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `data` | `dict[str, Any]` | 是 | `-` |  | - |

### `MetricsUpdateRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `metrics` | `Dict[str, Any]` | 是 | `-` | Metrics data | - |

### `CreateSuggestionRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `trigger_type` | `str` | 是 | `-` | Trigger type | - |
| `evidence` | `Dict[str, Any]` | 是 | `-` | Evidence data | - |
| `proposed_change` | `Dict[str, Any]` | 是 | `-` | Proposed change | - |

### `ApplySuggestionRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `suggestion_id` | `str` | 是 | `-` | Suggestion ID | - |
| `branch_id` | `str` | 是 | `-` | Target branch ID | - |

### `PublishRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `branch_id` | `str` | 是 | `-` | Branch ID to publish | - |
| `name` | `str` | 是 | `-` | Template name | - |
| `category` | `str` | 否 | `'general'` | Template category | - |
| `description` | `str` | 否 | `''` | Template description | - |

### `SubscribeRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `category` | `str` | 是 | `-` | Category to subscribe | - |
| `project_id` | `str` | 是 | `-` | Project ID | - |

### `ExportRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `branch_id` | `str` | 是 | `-` | Branch ID to export | - |
| `include_history` | `bool` | 否 | `True` | Include evolution history | - |

### `ImportRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `template_data` | `Dict[str, Any]` | 是 | `-` | Template data to import | - |
| `target_branch` | `Optional[str]` | 否 | `None` | Target branch name | - |
| `adapt_params` | `bool` | 否 | `True` | Auto-adapt parameters | - |

### `CreateNotificationRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `project_id` | `str` | 是 | `-` | Project ID | - |
| `suggestion` | `Dict[str, Any]` | 是 | `-` | Suggestion data | - |
| `priority` | `str` | 否 | `'optional'` | Priority: optional/recommended/critical | - |

### `ScanUpdatesRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `project_id` | `str` | 是 | `-` | Project ID | - |
| `suggestions` | `List[Dict[str, Any]]` | 是 | `-` | List of suggestions to check | - |

### `ToolCreate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `code` | `str` | 是 | `-` | 刀具编码 (T01, T02, ...) | 最小长度: 1; 最大长度: 32 |
| `name` | `str` | 是 | `-` | 刀具名称 | 最小长度: 1; 最大长度: 128 |
| `type` | `str` | 是 | `-` | 刀具类型: end_mill/ball_mill/drill/reamer/tap/insert/grooving/threading | 最大长度: 32 |
| `diameter` | `float` | 是 | `-` | 刀具直径 (mm) | > 0 |
| `length` | `Optional[float]` | 否 | `None` | 刀具长度 (mm) | > 0 |
| `flute_count` | `Optional[int]` | 否 | `2` | 刃数 | ≥ 1 |
| `material` | `Optional[str]` | 否 | `None` | 刀具材料: carbide/hss/ceramic/cbn/diamond | 最大长度: 32 |
| `coating` | `Optional[str]` | 否 | `None` | 涂层类型: TiN/TiAlN/AlCrN/DLC/None | 最大长度: 32 |
| `max_rpm` | `Optional[float]` | 否 | `None` | 最大允许转速 (RPM) | > 0 |
| `max_feed` | `Optional[float]` | 否 | `None` | 最大允许进给 (mm/min) | > 0 |
| `vendor` | `Optional[str]` | 否 | `None` | 供应商 | 最大长度: 128 |
| `cost` | `Optional[float]` | 否 | `None` | 采购成本 | ≥ 0 |
| `notes` | `Optional[str]` | 否 | `None` | 备注 | - |

### `ToolUpdate`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `code` | `Optional[str]` | 否 | `None` | 刀具编码 | 最大长度: 32 |
| `name` | `Optional[str]` | 否 | `None` | 刀具名称 | 最大长度: 128 |
| `type` | `Optional[str]` | 否 | `None` | 刀具类型 | 最大长度: 32 |
| `diameter` | `Optional[float]` | 否 | `None` | 刀具直径 (mm) | > 0 |
| `length` | `Optional[float]` | 否 | `None` | 刀具长度 (mm) | > 0 |
| `flute_count` | `Optional[int]` | 否 | `None` | 刃数 | ≥ 1 |
| `material` | `Optional[str]` | 否 | `None` | 刀具材料 | 最大长度: 32 |
| `coating` | `Optional[str]` | 否 | `None` | 涂层类型 | 最大长度: 32 |
| `max_rpm` | `Optional[float]` | 否 | `None` | 最大允许转速 (RPM) | > 0 |
| `max_feed` | `Optional[float]` | 否 | `None` | 最大允许进给 (mm/min) | > 0 |
| `usage_time` | `Optional[float]` | 否 | `None` | 累计使用时间 (分钟) | ≥ 0 |
| `wear_amount` | `Optional[float]` | 否 | `None` | 磨损量 (mm) | ≥ 0 |
| `status` | `Optional[str]` | 否 | `None` | 刀具状态: active/worn/broken/maintenance | 最大长度: 16 |
| `vendor` | `Optional[str]` | 否 | `None` | 供应商 | 最大长度: 128 |
| `cost` | `Optional[float]` | 否 | `None` | 采购成本 | ≥ 0 |
| `notes` | `Optional[str]` | 否 | `None` | 备注 | - |

### `ToolWearUpdate`

刀具磨损更新请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `additional_usage_time` | `float` | 否 | `0.0` | 新增使用时间 (分钟) | ≥ 0 |
| `additional_wear` | `float` | 否 | `0.0` | 新增磨损量 (mm) | ≥ 0 |
| `sharpened` | `bool` | 否 | `False` | 是否进行了刃磨 | - |

### `WearPredictRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `cutting_speed` | `float` | 否 | `150.0` | 切削速度 (m/min) | - |
| `feed_rate` | `float` | 否 | `0.2` | 进给量 (mm/rev) | - |
| `depth_of_cut` | `float` | 否 | `1.5` | 切削深度 (mm) | - |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |
| `current_wear` | `float` | 否 | `0.0` | 当前磨损量 (mm) | - |
| `time_step` | `float` | 否 | `1.0` | 时间步长 (min) | - |
| `max_time` | `float` | 否 | `300.0` | 最大预测时间 (min) | - |

### `RemainingLifeRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_wear` | `float` | 否 | `0.1` | 当前磨损量 (mm) | - |
| `cutting_speed` | `float` | 否 | `150.0` | 切削速度 (m/min) | - |
| `feed_rate` | `float` | 否 | `0.2` | 进给量 (mm/rev) | - |
| `depth_of_cut` | `float` | 否 | `1.5` | 切削深度 (mm) | - |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |

### `SuggestRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_wear` | `float` | 否 | `0.15` | 当前磨损量 (mm) | - |
| `remaining_life` | `float` | 否 | `50.0` | 剩余寿命 (min) | - |
| `cutting_speed` | `float` | 否 | `150.0` | 切削速度 (m/min) | - |
| `feed_rate` | `float` | 否 | `0.2` | 进给量 (mm/rev) | - |
| `depth_of_cut` | `float` | 否 | `1.5` | 切削深度 (mm) | - |
| `coolant_flow` | `float` | 否 | `10.0` | 冷却液流量 (L/min) | - |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |

### `CalibrateRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `measured_wear` | `float` | 否 | `0.1` | 实测磨损量 (mm) | - |
| `elapsed_time` | `float` | 否 | `30.0` | 已加工时间 (min) | - |
| `cutting_speed` | `float` | 否 | `150.0` | 切削速度 (m/min) | - |
| `feed_rate` | `float` | 否 | `0.2` | 进给量 (mm/rev) | - |
| `depth_of_cut` | `float` | 否 | `1.5` | 切削深度 (mm) | - |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |

### `RealTimeCalibrateRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `real_time_wear` | `float` | 否 | `0.12` | 实时磨损量 (mm) | - |
| `elapsed_time` | `float` | 否 | `30.0` | 已加工时间 (min) | - |
| `sensor_features` | `dict[str, float]` | 是 | `-` | 传感器特征（vibration_rms, cutting_force, temperature, acoustic_emission） | - |
| `cutting_speed` | `float` | 否 | `150.0` | 切削速度 (m/min) | - |
| `feed_rate` | `float` | 否 | `0.2` | 进给量 (mm/rev) | - |
| `depth_of_cut` | `float` | 否 | `1.5` | 切削深度 (mm) | - |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |

### `CompensationRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_wear` | `float` | 否 | `0.15` | 当前磨损量 (mm) | - |
| `cutting_speed` | `float` | 否 | `150.0` | 切削速度 (m/min) | - |
| `feed_rate` | `float` | 否 | `0.2` | 进给量 (mm/rev) | - |
| `depth_of_cut` | `float` | 否 | `1.5` | 切削深度 (mm) | - |
| `material_type` | `str` | 否 | `'steel_45'` | 材料类型 | - |
| `tool_type` | `str` | 否 | `'carbide'` | 刀具类型 | - |
| `tool_diameter` | `float` | 否 | `10.0` | 刀具直径 (mm) | - |
| `machine_capabilities` | `dict[str, float] | None` | 否 | `None` | 机床能力限制（可选） | - |

### `ArtifactModel`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` |  | - |
| `type` | `str` | 是 | `-` |  | - |
| `uri` | `str` | 是 | `-` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` |  | - |

### `WorkflowNodeModel`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `node_id` | `str` | 是 | `-` |  | - |
| `task_type` | `str` | 是 | `-` |  | - |
| `params` | `dict[str, Any]` | 是 | `-` |  | - |
| `inputs` | `dict[str, str]` | 是 | `-` |  | - |
| `retry` | `int` | 否 | `0` |  | - |
| `timeout_seconds` | `int` | 否 | `3600` |  | - |

### `WorkflowEdgeModel`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `upstream` | `str` | 是 | `-` |  | - |
| `downstream` | `str` | 是 | `-` |  | - |

### `WorkflowSpecModel`

WorkflowSpec 的 API 入参模型。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` |  | - |
| `version` | `str` | 否 | `'1.0.0'` |  | - |
| `nodes` | `list[WorkflowNodeModel]` | 是 | `-` |  | - |
| `edges` | `list[WorkflowEdgeModel]` | 是 | `-` |  | - |
| `inputs` | `dict[str, ArtifactModel]` | 是 | `-` |  | - |
| `outputs` | `dict[str, str]` | 是 | `-` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` |  | - |

### `RunRequestModel`

提交工作流请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `spec` | `WorkflowSpecModel` | 是 | `-` |  | - |
| `inputs` | `Optional[dict[str, ArtifactModel]]` | 否 | `None` |  | - |
| `owner_id` | `Optional[str]` | 否 | `None` |  | - |

### `ResumeRequestModel`

断点续跑请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `spec` | `WorkflowSpecModel` | 是 | `-` |  | - |
| `inputs` | `Optional[dict[str, ArtifactModel]]` | 否 | `None` |  | - |
| `owner_id` | `Optional[str]` | 否 | `None` |  | - |

### `WorkflowSpecModel`

WorkflowSpec 的 API 入参（与 workflows.py 对齐，但简化为 dict 投影）.

模板市场的 spec 字段允许任意结构，由 WorkflowTemplateManifest 校验
必须包含 nodes。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` |  | - |
| `version` | `str` | 否 | `'1.0.0'` |  | - |
| `nodes` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `edges` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `inputs` | `dict[str, Any]` | 是 | `-` |  | - |
| `outputs` | `dict[str, str]` | 是 | `-` |  | - |
| `metadata` | `dict[str, Any]` | 是 | `-` |  | - |

### `PublishRequestModel`

发布工作流模板请求体.

template_dict 必须满足 workflow_template.yaml 的 schema（见
workflow_template_loader.validate_template_dict），含 id / name /
version / description / author / license / spec 等字段。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `template_dict` | `dict[str, Any]` | 是 | `-` | 模板 manifest 字典（template.yaml 的反序列化形式） | - |
| `changelog` | `str` | 否 | `''` | 版本变更说明 | - |

### `RateRequestModel`

评分请求体.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `rating` | `float` | 是 | `-` | 评分（1.0-5.0） | ≥ 1.0; ≤ 5.0 |

### `WorldModelPredictRequest`

世界模型预测请求体.

与 ``app.contracts.world_model.WorldModelPredictRequest`` 对齐，
但使用 Pydantic 以获得自动校验和 OpenAPI 文档。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_state` | `dict[str, float]` | 是 | `-` | 当前加工状态（字段名见 StateField，至少包含全部 8 个状态字段）。融合模式下可为空（由 unified_state 提供状态信息） | - |
| `candidate_action` | `dict[str, float]` | 是 | `-` | 候选切削参数调整量（字段名见 ActionField，4 个 delta 字段） | - |
| `horizon` | `int` | 是 | `-` |  | - |
| `model_uri` | `str` | 否 | `'model://world_model/1.0.0'` | 世界模型 URI | 最小长度: 1; 最大长度: 256 |
| `unified_state` | `Optional[dict[str, Any]]` | 否 | `None` | ADR-020 思路 1 融合模式可选输入。包含几何特征（ADR-007）与动力学状态（ADR-013）的统一状态字典。提供时走融合路径（GeometryEncoder/DynamicsEncoder/FusionLayer）。为 None 时走原始 state_dim 字段拼接路径（向后兼容）。需配合环境变量 WORLD_MODEL_USE_FUSION=true 使用 | - |

### `TaskCreateRequest`

创建 CAM 校验任务请求体。

输入是阶段 6 G 代码报告 JSON 路径 + G 代码文件路径
+ 控制器类型 + 材料名称 + 安全 Z + 毛坯顶面 Z + CAM 后端。

若 source_gcode_generation_task_id 存在且上游任务已 SUCCEEDED，
本模块会自动从上游任务读取对应路径 + 上下文，调用方可不显式提供这些字段。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_gcode_generation_task_id` | `Optional[str]` | 否 | `None` | 上游 gcode_generation 任务 ID（可选） | - |
| `source_gcode_report_path` | `Optional[str]` | 否 | `None` | 阶段 6 G 代码报告 JSON 路径 | - |
| `source_gcode_file_path` | `Optional[str]` | 否 | `None` | 阶段 6 生成的 G 代码文件路径 | - |
| `controller_type` | `str` | 否 | `'fanuc'` | 控制器类型（fanuc / siemens / heidenhain / haas / okuma / mazak / ...） | - |
| `material_name` | `Optional[str]` | 否 | `None` | 材料名称（默认从上游 ChatterReport 推断） | - |
| `safety_z_mm` | `Optional[float]` | 否 | `None` | 安全 Z 平面高度（默认从上游 G 代码报告推断） | - |
| `stock_top_z_mm` | `Optional[float]` | 否 | `None` | 毛坯顶面 Z 高度（默认从上游 G 代码报告推断） | - |
| `cam_backend` | `Optional[str]` | 否 | `None` | CAM 后端名称（默认自动检测或使用 PyCAM） | - |

### `TaskCreateResponse`

任务创建成功响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `cam_backend` | `str` | 是 | `-` |  | - |
| `cam_backend_version` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `pending_calibration` | `bool` | 是 | `-` |  | - |
| `disclaimer` | `dict[str, str]` | 是 | `-` |  | - |

### `TaskStatusResponse`

任务状态查询响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `cam_backend` | `str` | 是 | `-` |  | - |
| `cam_backend_version` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `pending_calibration` | `bool` | 是 | `-` |  | - |
| `validation_progress` | `dict[str, int]` | 是 | `-` |  | - |
| `validation_summary` | `dict[str, int]` | 是 | `-` |  | - |
| `disclaimer` | `dict[str, str]` | 是 | `-` |  | - |
| `source_gcode_report_path` | `str` | 否 | `''` |  | - |
| `source_gcode_file_path` | `str` | 否 | `''` |  | - |
| `prediction_method` | `str` | 否 | `'analytical'` |  | - |
| `num_features` | `int` | 否 | `0` |  | - |

### `FeatureValidationResultResponse`

单个特征校验结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `gcode_segment_ids` | `list[str]` | 是 | `-` |  | - |
| `nc_file` | `list[str]` | 是 | `-` |  | - |
| `internal_error_info` | `Optional[dict[str, Any]]` | 否 | `None` |  | - |
| `out_of_gouge` | `bool` | 否 | `True` |  | - |
| `gouge_details` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `out_of_collision` | `bool` | 否 | `True` |  | - |
| `collision_details` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `out_of_travel` | `bool` | 否 | `True` |  | - |
| `travel_details` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `feed_rate_ok` | `bool` | 否 | `True` |  | - |
| `feed_rate_details` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `safety_z_ok` | `bool` | 否 | `True` |  | - |
| `safety_z_details` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `review_status` | `str` | 否 | `'pending'` |  | - |
| `corrected_params` | `Optional[dict[str, Any]]` | 否 | `None` |  | - |
| `review_notes` | `str` | 否 | `''` |  | - |
| `reviewer` | `str` | 否 | `''` |  | - |

### `TaskResultResponse`

任务校验结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `results` | `list[FeatureValidationResultResponse]` | 是 | `-` |  | - |
| `total` | `int` | 是 | `-` |  | - |
| `pass_count` | `int` | 否 | `0` |  | - |
| `fail_count` | `int` | 否 | `0` |  | - |
| `warning_count` | `int` | 否 | `0` |  | - |
| `error_count` | `int` | 否 | `0` |  | - |

### `ReviewRequest`

审核请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `review_status` | `str` | 是 | `-` | 审核结果：confirmed / rejected / edited / reviewed | - |
| `corrected_params` | `Optional[dict[str, Any]]` | 否 | `None` | 修正后的参数（review_status=edited 时需提供） | - |
| `notes` | `str` | 否 | `''` | 审核批注 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `corrected_params` | `Optional[dict[str, Any]]` | 否 | `None` |  | - |
| `message` | `str` | 是 | `-` |  | - |

### `ConfirmTaskResponse`

任务确认响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `cam_report_path` | `Optional[str]` | 否 | `None` |  | - |
| `internal_report_path` | `Optional[str]` | 否 | `None` |  | - |
| `message` | `str` | 是 | `-` |  | - |

### `TaskCreateRequest`

创建 CAM 校验任务请求体。

输入是阶段 6 G 代码报告 JSON 路径 + G 代码文件路径
+ 控制器类型 + 材料名称 + 安全 Z + 毛坯顶面 Z + CAM 后端。

若 source_gcode_generation_task_id 存在且上游任务已 SUCCEEDED，
本模块会自动从上游任务读取对应路径 + 上下文，调用方可不显式提供这些字段。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_gcode_generation_task_id` | `str` | 否 | `''` | 阶段 6 gcode_generation 任务 ID（用于追溯 G 代码报告 + 文件路径 + 控制器 / 材料 / safe_z / stock_top_z）。为空时必须显式提供 gcode_report_path。 | - |
| `gcode_report_path` | `str` | 否 | `''` | 阶段 6 输出的 G 代码审核记录 JSON 路径。为空时自动从 source_gcode_generation_task_id 任务中读取。通常位于 output/gcode_generation/{gcode_task_id}/{gcode_task_id}_report.json。 | - |
| `gcode_file_path` | `str` | 否 | `''` | 阶段 6 输出的 G 代码文件路径。为空时自动从上游任务读取，或从 gcode_report_path 的 gcode_file_path 字段读取。 | - |
| `controller_type` | `str` | 否 | `'fanuc_0i'` | 目标 CNC 控制器类型：fanuc_0i / siemens_840d / heidenhain_tnc / xmachine_xm100。仅用于 disclaimer 显示，不影响校验逻辑。 | - |
| `material_name` | `str` | 否 | `'45#钢'` | 材料名称（用于 disclaimer 显示 + 校准状态判断）。HRC52 触发 pending_calibration 标注（继承自阶段 5/6）。 | - |
| `safe_z` | `float` | 否 | `80.0` | 安全 Z 高度 (mm)，CollisionDetector 用于碰撞检测。 | - |
| `stock_top_z` | `float` | 否 | `50.0` | 毛坯顶面 Z (mm)，CollisionDetector 用于 AABB 包围盒计算。 | - |
| `cam_backend` | `str` | 否 | `'internal_only'` | CAM 后端：internal_only（仅内部预校验）/ pycam / nx_open / powermill / manual。CAM 软件不可用时自动降级到 manual。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_gcode_report_path` | `str` | 是 | `-` |  | - |
| `source_gcode_file_path` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `safe_z` | `float` | 是 | `-` |  | - |
| `stock_top_z` | `float` | 是 | `-` |  | - |
| `cam_backend_requested` | `str` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `cam_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

任务状态响应（含审核进度 + 校验统计）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_gcode_report_path` | `str` | 是 | `-` |  | - |
| `source_gcode_file_path` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `safe_z` | `float` | 是 | `-` |  | - |
| `stock_top_z` | `float` | 是 | `-` |  | - |
| `gcode_total_lines` | `int` | 是 | `-` |  | - |
| `total_features` | `int` | 是 | `-` |  | - |
| `passed_features` | `int` | 是 | `-` |  | - |
| `failed_features` | `int` | 是 | `-` |  | - |
| `pending_calibration` | `bool` | 是 | `-` |  | - |
| `prediction_method` | `str` | 是 | `-` |  | - |
| `cam_backend_requested` | `str` | 是 | `-` |  | - |
| `cam_backend_used` | `str` | 是 | `-` |  | - |
| `cam_backend_fallback_reason` | `str` | 是 | `-` |  | - |
| `pending_review_count` | `int` | 是 | `-` |  | - |
| `confirmed_count` | `int` | 是 | `-` |  | - |
| `rejected_count` | `int` | 是 | `-` |  | - |
| `edited_count` | `int` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `cam_report_path` | `str` | 是 | `-` |  | - |
| `internal_report_path` | `str` | 是 | `-` |  | - |
| `error_message` | `str` | 是 | `-` |  | - |
| `started_at` | `float` | 是 | `-` |  | - |
| `completed_at` | `float` | 是 | `-` |  | - |
| `reviewed_by` | `str` | 是 | `-` |  | - |
| `reviewed_at` | `float` | 是 | `-` |  | - |
| `warnings` | `list[str]` | 是 | `-` |  | - |
| `errors` | `list[str]` | 是 | `-` |  | - |
| `cam_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `FeatureValidationResultResponse`

单条 CAM 校验结果的响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `line_range` | `list[int]` | 是 | `-` |  | - |
| `internal_check_passed` | `bool` | 是 | `-` |  | - |
| `internal_events` | `list[dict[str, Any]]` | 是 | `-` |  | - |
| `cam_check_passed` | `bool` | 是 | `-` |  | - |
| `cam_messages` | `list[str]` | 是 | `-` |  | - |
| `cam_backend_used` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `spindle_rpm` | `float` | 是 | `-` |  | - |
| `axial_depth_mm` | `float` | 是 | `-` |  | - |
| `limit_depth_mm` | `float` | 是 | `-` |  | - |
| `stable` | `bool` | 是 | `-` |  | - |
| `safety_margin_ratio` | `float` | 是 | `-` |  | - |
| `warning` | `str` | 是 | `-` |  | - |

### `TaskResultResponse`

CAM 校验任务结果摘要（含全部特征校验结果列表）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `gcode_total_lines` | `int` | 是 | `-` |  | - |
| `total_features` | `int` | 是 | `-` |  | - |
| `passed_features` | `int` | 是 | `-` |  | - |
| `failed_features` | `int` | 是 | `-` |  | - |
| `pending_calibration` | `bool` | 是 | `-` |  | - |
| `prediction_method` | `str` | 是 | `-` |  | - |
| `cam_backend_requested` | `str` | 是 | `-` |  | - |
| `cam_backend_used` | `str` | 是 | `-` |  | - |
| `cam_backend_fallback_reason` | `str` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `cam_report_path` | `str | None` | 是 | `-` |  | - |
| `internal_report_path` | `str | None` | 是 | `-` |  | - |
| `error_message` | `str | None` | 是 | `-` |  | - |
| `feature_results` | `list[FeatureValidationResultResponse]` | 是 | `-` |  | - |
| `cam_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ReviewRequest`

工程师审核请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `action` | `str` | 是 | `-` | 审核动作：confirmed（确认特征校验结论）/ rejected（拒绝该特征，需阶段 6 重新生成 G 代码）/ edited（编辑校验参数，需同时提供 edited_params） | - |
| `edited_params` | `dict[str, Any] | None` | 否 | `None` | 工程师编辑后的参数。仅 action=edited 时必须提供。字段可为 safe_z / cam_backend / stock_top_z 的子集。edited 仅记录修改意图，不触发流水线重新执行。 | - |
| `engineer_notes` | `str` | 否 | `''` | 工程师备注（可选，便于审计追溯）。 | - |
| `reviewed_by` | `str` | 否 | `'engineer'` | 审核人标识。 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `all_reviewed` | `bool` | 是 | `-` |  | - |
| `task_status` | `str` | 是 | `-` |  | - |
| `cam_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ConfirmTaskResponse`

确认任务响应（导出 cam_report + internal_report JSON，状态置为 SUCCEEDED）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `total_features` | `int` | 是 | `-` |  | - |
| `passed_features` | `int` | 是 | `-` |  | - |
| `failed_features` | `int` | 是 | `-` |  | - |
| `cam_backend_used` | `str` | 是 | `-` |  | - |
| `cam_report_path` | `str` | 是 | `-` |  | - |
| `internal_report_path` | `str` | 是 | `-` |  | - |
| `report_download_url` | `str` | 是 | `-` |  | - |
| `internal_report_download_url` | `str` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `cam_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskCreateRequest`

创建颤振预测任务请求体。

输入是阶段 4 任务 ID（追溯用）+ ChatterParams JSON 路径 + 材料 ID。
若 source_cutting_parameters_task_id 存在且上游任务已 SUCCEEDED，
本模块会自动从上游任务读取 chatter_params_path / material_id / mesh_calibrated，
调用方可不显式提供这些字段。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_cutting_parameters_task_id` | `str` | 是 | `-` | 阶段 4 cutting_parameters 任务 ID（用于追溯 ChatterParams 来源 及查询上游 mesh_calibrated / material_id 状态）。若上游任务不存在或未完成，必须显式提供 chatter_params_path + material_id。 | - |
| `chatter_params_path` | `str` | 否 | `''` | 阶段 4 输出的 ChatterParams JSON 路径。为空时自动从 source_cutting_parameters_task_id 任务中读取。通常位于 output/cutting_parameters/{cp_task_id}/{cp_task_id}_chatter_params.json。 | - |
| `material_id` | `str` | 否 | `''` | 材料 ID：al_6061 / ti_tc4 / steel_hrc52 等。为空时自动从阶段 4 任务中读取。HRC52 触发 pending_calibration 强制降低置信度。 | - |
| `precision_tier` | `str` | 否 | `'standard'` | 精度档位（继承自阶段 1/2/3/4）：coarse / standard / high。 | - |
| `mesh_calibrated` | `bool | None` | 否 | `None` | 上游 mesh 是否已做尺度归一化。None 时通过 source_cutting_parameters_task_id 自动查询阶段 4 任务。 | - |
| `machine_type` | `str` | 否 | `'vmc_850'` | 机床类型标识（仅供追溯，不直接影响预测算法）。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_cutting_parameters_task_id` | `str` | 是 | `-` |  | - |
| `chatter_params_path` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `machine_type` | `str` | 是 | `-` |  | - |
| `ltc_model_available` | `bool` | 是 | `-` |  | - |
| `chatter_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

任务状态响应（含审核进度 + 预测方法分布）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_cutting_parameters_task_id` | `str` | 是 | `-` |  | - |
| `chatter_params_path` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `machine_type` | `str` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `predicted_count` | `int` | 是 | `-` |  | - |
| `analytical_count` | `int` | 是 | `-` |  | - |
| `neural_network_count` | `int` | 是 | `-` |  | - |
| `fallback_count` | `int` | 是 | `-` |  | - |
| `ltc_model_available` | `bool` | 是 | `-` |  | - |
| `pending_count` | `int` | 是 | `-` |  | - |
| `confirmed_count` | `int` | 是 | `-` |  | - |
| `rejected_count` | `int` | 是 | `-` |  | - |
| `edited_count` | `int` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `chatter_report_path` | `str` | 是 | `-` |  | - |
| `error_message` | `str` | 是 | `-` |  | - |
| `created_at` | `float` | 是 | `-` |  | - |
| `started_at` | `float` | 是 | `-` |  | - |
| `completed_at` | `float` | 是 | `-` |  | - |
| `chatter_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `FeatureChatterResultResponse`

单条颤振预测结果的响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `spindle_rpm` | `float` | 是 | `-` |  | - |
| `axial_depth_mm` | `float` | 是 | `-` |  | - |
| `limit_depth_mm` | `float` | 是 | `-` |  | - |
| `stable` | `bool` | 是 | `-` |  | - |
| `stability_margin` | `float` | 是 | `-` |  | - |
| `method` | `str` | 是 | `-` |  | - |
| `ltc_active` | `bool` | 是 | `-` |  | - |
| `confidence` | `float` | 是 | `-` |  | - |
| `inference_time_ms` | `float` | 是 | `-` |  | - |
| `warnings` | `list[str]` | 是 | `-` |  | - |
| `material_calibration_status` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `reviewed_by` | `str` | 是 | `-` |  | - |
| `reviewed_at` | `float` | 是 | `-` |  | - |
| `engineer_notes` | `str` | 是 | `-` |  | - |
| `source_cutting_params_task_id` | `str` | 是 | `-` |  | - |
| `machine_id` | `str` | 是 | `-` |  | - |
| `tool_id` | `str` | 是 | `-` |  | - |
| `cutting_force_coeff` | `float` | 是 | `-` |  | - |

### `TaskResultResponse`

颤振预测任务结果摘要（含全部特征预测结果列表）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_cutting_parameters_task_id` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `predicted_count` | `int` | 是 | `-` |  | - |
| `analytical_count` | `int` | 是 | `-` |  | - |
| `neural_network_count` | `int` | 是 | `-` |  | - |
| `fallback_count` | `int` | 是 | `-` |  | - |
| `ltc_model_available` | `bool` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `chatter_report_path` | `str` | 是 | `-` |  | - |
| `error_message` | `str | None` | 是 | `-` |  | - |
| `feature_results` | `list[FeatureChatterResultResponse]` | 是 | `-` |  | - |
| `chatter_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ReviewRequest`

工程师审核请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `action` | `str` | 是 | `-` | 审核动作：confirmed（确认预测结果无误）/ rejected（拒绝该特征，不进入最终 ChatterReport）/ edited（参数需修正，需同时提供 edited_params） | - |
| `edited_params` | `dict[str, Any] | None` | 否 | `None` | 工程师编辑后的参数。仅 action=edited 时必须提供。字段可为 limit_depth_mm / axial_depth_mm / stable（0/1）的子集。 | - |
| `engineer_notes` | `str` | 否 | `''` | 工程师备注（可选，便于审计追溯）。 | - |
| `reviewed_by` | `str` | 否 | `'engineer'` | 审核人标识。 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `all_reviewed` | `bool` | 是 | `-` |  | - |
| `task_status` | `str` | 是 | `-` |  | - |
| `chatter_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ExportChatterReportResponse`

导出 ChatterReport 响应（阶段 6 输入）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_cutting_parameters_task_id` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `chatter_report_path` | `str` | 是 | `-` |  | - |
| `download_url` | `str` | 是 | `-` |  | - |
| `chatter_params_ready` | `bool` | 是 | `-` |  | - |
| `cutting_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskCreateRequest`

创建切削参数推荐任务请求体。

输入是阶段 3 STEP 文件路径 + 阶段 2 confirmed_features.json 路径 + 材料 ID。
STEP 文件路径仅作追溯用，本模块不重新解析 STEP，
实际特征参数取自阶段 2 confirmed_features.json。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_parametric_geometry_task_id` | `str` | 是 | `-` | 阶段 3 parametric_geometry 任务 ID（用于追溯 STEP 文件来源 及查询上游 mesh_calibrated 状态）。若上游任务不存在或未完成，按未标定 mesh 处理。 | - |
| `step_file_path` | `str` | 是 | `-` | 阶段 3 输出的 STEP 文件路径（仅作追溯用，本模块不解析 STEP）。通常位于 output/parametric_geometry/{pg_task_id}/{pg_task_id}_final.step。 | - |
| `input_features_path` | `str` | 是 | `-` | 阶段 2 导出的 confirmed_features.json 路径。切削参数推荐基于其中的 feature_id / feature_type 字段。 | - |
| `material_id` | `str` | 是 | `-` | 材料 ID：al_6061 / ti_tc4 / steel_hrc52 等。材料数据库中 17 种材料可用，HRC52 通过内存补充数据（待自采校准）。 | - |
| `precision_tier` | `str` | 否 | `'standard'` | 精度档位（继承自阶段 1/2/3）：coarse / standard / high。 | - |
| `mesh_calibrated` | `bool | None` | 否 | `None` | 上游 mesh 是否已做尺度归一化。None 时通过 source_parametric_geometry_task_id 自动查询阶段 3 任务。 | - |
| `machine_type` | `str` | 否 | `'vmc_850'` | 机床类型标识（仅供追溯，不直接影响推荐算法）。 | - |
| `tool_diameter_mm` | `float` | 否 | `10.0` | 刀具直径 (mm)，影响主轴转速与径向切深计算。 | - |
| `num_flutes` | `int` | 否 | `4` | 齿数，影响进给速度计算 feed_rate = spindle_rpm * num_flutes * feed_per_tooth。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_parametric_geometry_task_id` | `str` | 是 | `-` |  | - |
| `step_file_path` | `str` | 是 | `-` |  | - |
| `input_features_path` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `machine_type` | `str` | 是 | `-` |  | - |
| `tool_diameter_mm` | `float` | 是 | `-` |  | - |
| `num_flutes` | `int` | 是 | `-` |  | - |
| `cutting_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

任务状态响应（含审核进度）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_parametric_geometry_task_id` | `str` | 是 | `-` |  | - |
| `step_file_path` | `str` | 是 | `-` |  | - |
| `input_features_path` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `machine_type` | `str` | 是 | `-` |  | - |
| `tool_diameter_mm` | `float` | 是 | `-` |  | - |
| `num_flutes` | `int` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `recommended_count` | `int` | 是 | `-` |  | - |
| `pending_count` | `int` | 是 | `-` |  | - |
| `confirmed_count` | `int` | 是 | `-` |  | - |
| `rejected_count` | `int` | 是 | `-` |  | - |
| `edited_count` | `int` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `chatter_params_path` | `str` | 是 | `-` |  | - |
| `error_message` | `str` | 是 | `-` |  | - |
| `created_at` | `float` | 是 | `-` |  | - |
| `started_at` | `float` | 是 | `-` |  | - |
| `completed_at` | `float` | 是 | `-` |  | - |
| `cutting_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `RecommendedParamsResponse`

单条推荐切削参数的响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `operation` | `str` | 是 | `-` |  | - |
| `spindle_speed_rpm` | `float` | 是 | `-` |  | - |
| `feed_rate_mm_per_min` | `float` | 是 | `-` |  | - |
| `feed_per_tooth_mm` | `float` | 是 | `-` |  | - |
| `cutting_speed_m_per_min` | `float` | 是 | `-` |  | - |
| `axial_depth_mm` | `float` | 是 | `-` |  | - |
| `radial_depth_mm` | `float` | 是 | `-` |  | - |
| `estimated_cutting_time_s` | `float` | 是 | `-` |  | - |
| `tool_life_estimate_min` | `float` | 是 | `-` |  | - |
| `warnings` | `list[str]` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `reviewed_by` | `str` | 是 | `-` |  | - |
| `reviewed_at` | `float` | 是 | `-` |  | - |
| `engineer_notes` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `tool_diameter_mm` | `float` | 是 | `-` |  | - |
| `num_flutes` | `int` | 是 | `-` |  | - |

### `TaskResultResponse`

切削参数任务结果摘要（含全部推荐参数列表）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_parametric_geometry_task_id` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `recommended_count` | `int` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `chatter_params_path` | `str` | 是 | `-` |  | - |
| `error_message` | `str | None` | 是 | `-` |  | - |
| `recommended_params` | `list[RecommendedParamsResponse]` | 是 | `-` |  | - |
| `cutting_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ReviewRequest`

工程师审核请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `action` | `str` | 是 | `-` | 审核动作：confirmed（确认推荐参数无误）/ rejected（拒绝该特征，不进入最终 ChatterParams）/ edited（参数需修正，需同时提供 edited_params） | - |
| `edited_params` | `dict[str, Any] | None` | 否 | `None` | 工程师编辑后的参数。仅 action=edited 时必须提供。字段可为 spindle_speed_rpm / feed_rate_mm_per_min / feed_per_tooth_mm / cutting_speed_m_per_min / axial_depth_mm / radial_depth_mm 的子集。 | - |
| `engineer_notes` | `str` | 否 | `''` | 工程师备注（可选，便于审计追溯）。 | - |
| `reviewed_by` | `str` | 否 | `'engineer'` | 审核人标识。 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `all_reviewed` | `bool` | 是 | `-` |  | - |
| `task_status` | `str` | 是 | `-` |  | - |
| `cutting_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ExportChatterParamsResponse`

导出 ChatterParams 响应（阶段 5 输入）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_parametric_geometry_task_id` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `chatter_params_path` | `str` | 是 | `-` |  | - |
| `download_url` | `str` | 是 | `-` |  | - |
| `chatter_params_ready` | `bool` | 是 | `-` |  | - |
| `cutting_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskCreateFromPathRequest`

通过 mesh 路径 + 关联重建任务 ID 创建特征提取任务（链路模式）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `mesh_path` | `str` | 是 | `-` | 输入 mesh 文件路径（PLY/STL/GLB/OBJ）。通常为 image_to_3d 任务的输出 mesh，或用户外部上传的 mesh。 | - |
| `source_reconstruction_task_id` | `str` | 否 | `''` | 关联的拍照重建任务 ID（可选）。若提供且上游任务已 SUCCEEDED，则系统自动查询 mesh 是否已做尺度归一化。若不提供或上游任务不存在，则视为外部上传，按未标定 mesh 处理。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `input_mesh_path` | `str` | 是 | `-` |  | - |
| `source_reconstruction_task_id` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `feature_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `input_mesh_path` | `str` | 是 | `-` |  | - |
| `source_reconstruction_task_id` | `str` | 是 | `-` |  | - |
| `vertex_count` | `int` | 是 | `-` |  | - |
| `face_count` | `int` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `plane_count` | `int` | 是 | `-` |  | - |
| `cylinder_count` | `int` | 是 | `-` |  | - |
| `hole_count` | `int` | 是 | `-` |  | - |
| `boss_count` | `int` | 是 | `-` |  | - |
| `plane_duration_seconds` | `float` | 是 | `-` |  | - |
| `cylinder_duration_seconds` | `float` | 是 | `-` |  | - |
| `hole_duration_seconds` | `float` | 是 | `-` |  | - |
| `total_duration_seconds` | `float` | 是 | `-` |  | - |
| `error_message` | `str` | 是 | `-` |  | - |
| `reviewed_by` | `str` | 是 | `-` |  | - |
| `reviewed_at` | `float` | 是 | `-` |  | - |
| `exported_features_path` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `feature_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `FeatureItemResponse`

单条特征的简化响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `params` | `dict[str, Any]` | 是 | `-` |  | - |
| `confidence` | `float` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `engineer_notes` | `str` | 是 | `-` |  | - |
| `edited` | `bool` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskResultResponse`

特征提取结果（含完整特征列表）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `features` | `list[FeatureItemResponse]` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `plane_count` | `int` | 是 | `-` |  | - |
| `cylinder_count` | `int` | 是 | `-` |  | - |
| `hole_count` | `int` | 是 | `-` |  | - |
| `boss_count` | `int` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `feature_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ReviewRequest`

工程师审核请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `action` | `str` | 是 | `-` | 审核动作：confirmed（确认无误）/ rejected（误识别，丢弃）/ edited（参数需修正，需同时提供 edited_params） | - |
| `edited_params` | `dict[str, Any] | None` | 否 | `None` | 工程师编辑后的参数。仅 action=edited 时必须提供，字段结构需与原始 params 一致（如 plane: normal/offset/area_mm2）。 | - |
| `engineer_notes` | `str` | 否 | `''` | 工程师备注（可选，便于审计追溯）。 | - |
| `reviewed_by` | `str` | 否 | `'engineer'` | 审核人标识（默认 'engineer'，便于多工程师协同场景区分）。 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `all_reviewed` | `bool` | 是 | `-` |  | - |
| `task_status` | `str` | 是 | `-` |  | - |
| `feature_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ExportResponse`

导出已确认特征响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `exported_features_path` | `str` | 是 | `-` |  | - |
| `confirmed_feature_count` | `int` | 是 | `-` |  | - |
| `download_url` | `str` | 是 | `-` |  | - |
| `feature_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskCreateRequest`

创建 G 代码生成任务请求体。

输入是阶段 5 ChatterReport JSON 路径 + 阶段 3 OperationPlan JSON 路径
+ 控制器类型 + 材料名称 + 程序号 + 安全 Z + 毛坯顶面 Z。

若 source_chatter_prediction_task_id / source_parametric_geometry_task_id
存在且上游任务已 SUCCEEDED，本模块会自动从上游任务读取对应路径，
调用方可不显式提供这些字段。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_chatter_prediction_task_id` | `str` | 否 | `''` | 阶段 5 chatter_prediction 任务 ID（用于追溯 ChatterReport 路径）。为空时必须显式提供 chatter_report_path。 | - |
| `source_parametric_geometry_task_id` | `str` | 否 | `''` | 阶段 3 parametric_geometry 任务 ID（用于追溯 OperationPlan 路径）。为空时必须显式提供 operation_plan_path。 | - |
| `chatter_report_path` | `str` | 否 | `''` | 阶段 5 输出的 ChatterReport JSON 路径。为空时自动从 source_chatter_prediction_task_id 任务中读取。通常位于 output/chatter_prediction/{cp_task_id}/{cp_task_id}_chatter_report.json。 | - |
| `operation_plan_path` | `str` | 否 | `''` | 阶段 3 输出的 OperationPlan JSON 路径。为空时自动从 source_parametric_geometry_task_id 任务中读取。 | - |
| `controller_type` | `str` | 否 | `'fanuc_0i'` | 目标 CNC 控制器类型：fanuc_0i / siemens_840d / heidenhain_tnc / xmachine_xm100。决定 G 代码文件扩展名（.nc / .mpf / .h）。 | - |
| `material_name` | `str` | 否 | `'45#钢'` | 材料名称（用于 G 代码注释 + 精度告知）。为空时自动从阶段 5 任务中读取 material_id。HRC52 触发 pending_calibration 标注。 | - |
| `program_number` | `int` | 否 | `1000` | G 代码程序号（O 号，Fanuc 习惯 1-9999）。 | ≥ 1; ≤ 9999 |
| `safe_z` | `float` | 否 | `80.0` | 安全 Z 高度 (mm)，G 代码在特征切换时抬至此高度。 | - |
| `stock_top_z` | `float` | 否 | `50.0` | 毛坯顶面 Z (mm)，G 代码起刀点参考。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_chatter_report_path` | `str` | 是 | `-` |  | - |
| `source_operation_plan_path` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `program_number` | `int` | 是 | `-` |  | - |
| `safe_z` | `float` | 是 | `-` |  | - |
| `stock_top_z` | `float` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `gcode_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

任务状态响应（含审核进度 + 生成统计）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_chatter_report_path` | `str` | 是 | `-` |  | - |
| `source_operation_plan_path` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `program_number` | `int` | 是 | `-` |  | - |
| `safe_z` | `float` | 是 | `-` |  | - |
| `stock_top_z` | `float` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `stable_features` | `int` | 是 | `-` |  | - |
| `unstable_features` | `int` | 是 | `-` |  | - |
| `pending_calibration` | `bool` | 是 | `-` |  | - |
| `prediction_method` | `str` | 是 | `-` |  | - |
| `pending_review_count` | `int` | 是 | `-` |  | - |
| `confirmed_count` | `int` | 是 | `-` |  | - |
| `rejected_count` | `int` | 是 | `-` |  | - |
| `edited_count` | `int` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `gcode_file_path` | `str` | 是 | `-` |  | - |
| `gcode_report_path` | `str` | 是 | `-` |  | - |
| `error_message` | `str` | 是 | `-` |  | - |
| `started_at` | `float` | 是 | `-` |  | - |
| `completed_at` | `float` | 是 | `-` |  | - |
| `reviewed_by` | `str` | 是 | `-` |  | - |
| `reviewed_at` | `float` | 是 | `-` |  | - |
| `warnings` | `list[str]` | 是 | `-` |  | - |
| `errors` | `list[str]` | 是 | `-` |  | - |
| `gcode_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `FeatureGCodeResultResponse`

单条 G 代码生成结果的响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `material_id` | `str` | 是 | `-` |  | - |
| `spindle_rpm` | `float` | 是 | `-` |  | - |
| `axial_depth_mm` | `float` | 是 | `-` |  | - |
| `limit_depth_mm` | `float` | 是 | `-` |  | - |
| `stable` | `bool` | 是 | `-` |  | - |
| `safety_margin_ratio` | `float` | 是 | `-` |  | - |
| `gcode_lines` | `list[str]` | 是 | `-` |  | - |
| `line_range` | `list[int]` | 是 | `-` |  | - |
| `warning` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskResultResponse`

G 代码生成任务结果摘要（含全部特征 G 代码段列表）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `program_number` | `int` | 是 | `-` |  | - |
| `total_features` | `int` | 是 | `-` |  | - |
| `stable_features` | `int` | 是 | `-` |  | - |
| `unstable_features` | `int` | 是 | `-` |  | - |
| `pending_calibration` | `bool` | 是 | `-` |  | - |
| `prediction_method` | `str` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `gcode_file_path` | `str | None` | 是 | `-` |  | - |
| `gcode_report_path` | `str | None` | 是 | `-` |  | - |
| `error_message` | `str | None` | 是 | `-` |  | - |
| `feature_results` | `list[FeatureGCodeResultResponse]` | 是 | `-` |  | - |
| `gcode_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ReviewRequest`

工程师审核请求体。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `action` | `str` | 是 | `-` | 审核动作：confirmed（确认 G 代码段无误）/ rejected（拒绝该特征，不进入最终 G 代码）/ edited（参数需修正，需同时提供 edited_params） | - |
| `edited_params` | `dict[str, Any] | None` | 否 | `None` | 工程师编辑后的参数。仅 action=edited 时必须提供。字段可为 axial_depth_mm / limit_depth_mm / stable（bool）的子集。edited 仅记录修改意图，不触发 G 代码重新生成。 | - |
| `engineer_notes` | `str` | 否 | `''` | 工程师备注（可选，便于审计追溯）。 | - |
| `reviewed_by` | `str` | 否 | `'engineer'` | 审核人标识。 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `all_reviewed` | `bool` | 是 | `-` |  | - |
| `task_status` | `str` | 是 | `-` |  | - |
| `gcode_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ConfirmTaskResponse`

确认任务响应（导出 G 代码 + 报告 JSON，状态置为 SUCCEEDED）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `controller_type` | `str` | 是 | `-` |  | - |
| `material_name` | `str` | 是 | `-` |  | - |
| `program_number` | `int` | 是 | `-` |  | - |
| `total_features` | `int` | 是 | `-` |  | - |
| `exported_features` | `int` | 是 | `-` |  | - |
| `gcode_file_path` | `str` | 是 | `-` |  | - |
| `gcode_report_path` | `str` | 是 | `-` |  | - |
| `download_url` | `str` | 是 | `-` |  | - |
| `report_download_url` | `str` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `gcode_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskCreateRequest`

创建任务时的可选元数据。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `calibration_anchor_distance` | `float | None` | 否 | `None` | 标定块在 SfM 无量纲坐标系下的距离。None 表示未提供，输出无量纲 mesh（仅可视化用）。如需得到带 mm 尺度的 mesh，请通过 GET /precision_info 了解标定块放置方法。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `photo_count` | `int` | 是 | `-` |  | - |
| `precision_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `photo_count` | `int` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `num_images_registered` | `int` | 是 | `-` |  | - |
| `calibrated` | `bool` | 是 | `-` |  | - |
| `scale_factor` | `float` | 是 | `-` |  | - |
| `colmap_duration_seconds` | `float` | 是 | `-` |  | - |
| `openmvs_duration_seconds` | `float` | 是 | `-` |  | - |
| `total_duration_seconds` | `float` | 是 | `-` |  | - |
| `error_message` | `str` | 是 | `-` |  | - |
| `precision_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `NL2CADRequest`

Request model for NL to CAD conversion.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `description` | `str` | 是 | `-` | 自然语言零件描述 | 最小长度: 1; 最大长度: 2000 |
| `output_format` | `str` | 否 | `'stl'` | 输出格式 | 正则: `^(stl|step|obj|gltf)$` |

### `NL2CADResponse`

Response model for NL to CAD conversion.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_path` | `str` | 是 | `-` | 生成的模型文件路径 | - |
| `params` | `dict[str, Any]` | 是 | `-` | 提取的CAD参数 | - |
| `confidence` | `float` | 是 | `-` | 参数提取置信度 | ≥ 0.0; ≤ 1.0 |

### `RefineRequest`

Request model for model refinement.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `current_params` | `dict[str, Any]` | 是 | `-` | 当前模型参数 | - |
| `instruction` | `str` | 是 | `-` | 微调指令 | 最小长度: 1; 最大长度: 1000 |
| `output_format` | `str` | 否 | `'stl'` | 输出格式 | 正则: `^(stl|step|obj|gltf)$` |

### `RefineResponse`

Response model for model refinement.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_path` | `str` | 是 | `-` | 更新后的模型文件路径 | - |
| `params` | `dict[str, Any]` | 是 | `-` | 更新后的CAD参数 | - |

### `ExtractParamsRequest`

Request model for parameter extraction only.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `description` | `str` | 是 | `-` | 自然语言零件描述 | 最小长度: 1; 最大长度: 2000 |

### `ExtractParamsResponse`

Response model for parameter extraction.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `params` | `dict[str, Any]` | 是 | `-` | 提取的CAD参数 | - |
| `confidence` | `float` | 是 | `-` | 置信度 | ≥ 0.0; ≤ 1.0 |

### `ProcessPlanningRequest`

Request model for process planning.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `cad_params` | `dict[str, Any]` | 是 | `-` | CAD参数 | - |
| `material` | `str` | 是 | `-` | 材料类型 | - |
| `machine_type` | `str` | 否 | `'cnc_mill'` | 机床类型 | - |
| `precision` | `str` | 否 | `'finish'` | 精度等级 | - |

### `ProcessPlanningResponse`

Response model for process planning.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `process_plan` | `dict[str, Any]` | 是 | `-` | 工艺规划结果 | - |

### `NCCodeRequest`

Request model for NC code generation.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `process_plan` | `dict[str, Any]` | 是 | `-` | 工艺规划 | - |
| `machine_type` | `str` | 否 | `'cnc_mill'` | 机床类型 | - |

### `NCCodeResponse`

Response model for NC code generation.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `nc_code` | `str` | 是 | `-` | 生成的NC代码 | - |

### `FullPipelineRequest`

Request model for full pipeline execution.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `description` | `str` | 是 | `-` | 自然语言零件描述 | 最小长度: 1; 最大长度: 2000 |
| `machine_type` | `str` | 否 | `'cnc_mill'` | 机床类型 | - |
| `material` | `str` | 否 | `'steel'` | 材料类型 | - |

### `FullPipelineResponse`

Response model for full pipeline execution.

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_path` | `str` | 是 | `-` | 生成的模型文件路径 | - |
| `cad_params` | `dict[str, Any]` | 是 | `-` | CAD参数 | - |
| `process_plan` | `dict[str, Any]` | 是 | `-` | 工艺规划 | - |
| `nc_code` | `str` | 是 | `-` | NC代码 | - |
| `simulation_result` | `dict[str, Any]` | 是 | `-` | 仿真结果 | - |

### `TaskCreateRequest`

创建参数化几何任务请求体。

输入是阶段 2 feature_extraction 模块导出的 confirmed_features.json 路径，
而非 mesh 文件（阶段 3 不再处理 mesh，仅处理已审核的特征参数）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `source_feature_extraction_task_id` | `str` | 是 | `-` | 阶段 2 feature_extraction 任务 ID（用于追溯 confirmed_features.json 来源 及查询上游 mesh_calibrated 状态）。若上游任务不存在或未完成，按未标定 mesh 处理。 | - |
| `input_features_path` | `str` | 是 | `-` | 阶段 2 导出的 confirmed_features.json 文件路径。通常位于 output/feature_extraction/{fe_task_id}/confirmed_features_{fe_task_id}.json。 | - |
| `precision_tier` | `str` | 否 | `'standard'` | 精度档位（继承自阶段 1/2）：coarse / standard / high。本模块不引入新档位，仅用于显示告知。 | - |
| `mesh_calibrated` | `bool | None` | 否 | `None` | 上游 mesh 是否已做尺度归一化。若不提供（None），系统自动通过 source_feature_extraction_task_id 查询阶段 1 image_to_3d 任务的 calibrated 字段。若查询失败，按未标定处理。 | - |

### `TaskCreateResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_feature_extraction_task_id` | `str` | 是 | `-` |  | - |
| `input_features_path` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `step_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `TaskStatusResponse`

任务状态响应（含完整审核进度）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_feature_extraction_task_id` | `str` | 是 | `-` |  | - |
| `input_features_path` | `str` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `pending_count` | `int` | 是 | `-` |  | - |
| `confirmed_count` | `int` | 是 | `-` |  | - |
| `rejected_count` | `int` | 是 | `-` |  | - |
| `edited_count` | `int` | 是 | `-` |  | - |
| `step_output_path` | `str | None` | 是 | `-` |  | - |
| `final_step_path` | `str | None` | 是 | `-` |  | - |
| `engine_used` | `str | None` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `error_message` | `str | None` | 是 | `-` |  | - |
| `created_at` | `float` | 是 | `-` |  | - |
| `updated_at` | `float` | 是 | `-` |  | - |
| `step_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `FeatureRefResponse`

单条已审核特征引用的响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `source_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `edited_params` | `dict[str, Any] | None` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `engineer_notes` | `str | None` | 是 | `-` |  | - |
| `reviewed_by` | `str | None` | 是 | `-` |  | - |
| `reviewed_at` | `float | None` | 是 | `-` |  | - |

### `TaskResultResponse`

参数化几何任务结果摘要（含装配信息与特征列表）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_feature_extraction_task_id` | `str` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `brep_shape_count` | `int` | 是 | `-` |  | - |
| `engine_used` | `str | None` | 是 | `-` |  | - |
| `step_output_path` | `str | None` | 是 | `-` |  | - |
| `final_step_path` | `str | None` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `cam_validation_required` | `bool` | 是 | `-` |  | - |
| `error_message` | `str | None` | 是 | `-` |  | - |
| `assembly_summary` | `dict[str, Any] | None` | 是 | `-` |  | - |
| `features` | `list[FeatureRefResponse]` | 是 | `-` |  | - |
| `step_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `ReviewRequest`

工程师审核请求体（第一轮：审核 STEP 中的特征表达）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `action` | `str` | 是 | `-` | 审核动作：confirmed（确认 STEP 表达正确）/ rejected（误识别，从最终 STEP 中移除）/ edited（参数需修正，需同时提供 edited_params） | - |
| `edited_params` | `dict[str, Any] | None` | 否 | `None` | 工程师编辑后的参数。仅 action=edited 时必须提供，字段结构需与 source_params 一致（如 cylinder: center/axis/radius_mm/height_mm）。 | - |
| `engineer_notes` | `str` | 否 | `''` | 工程师备注（可选，便于审计追溯）。 | - |
| `reviewed_by` | `str` | 否 | `'engineer'` | 审核人标识（默认 'engineer'，便于多工程师协同场景区分）。 | - |

### `ReviewResponse`

审核结果响应。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `feature_id` | `str` | 是 | `-` |  | - |
| `feature_type` | `str` | 是 | `-` |  | - |
| `review_status` | `str` | 是 | `-` |  | - |
| `effective_params` | `dict[str, Any]` | 是 | `-` |  | - |
| `all_reviewed` | `bool` | 是 | `-` |  | - |
| `task_status` | `str` | 是 | `-` |  | - |
| `step_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `FinalizeResponse`

最终化 STEP 响应（第二轮 STEP 生成结果）。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` |  | - |
| `status` | `str` | 是 | `-` |  | - |
| `source_feature_extraction_task_id` | `str` | 是 | `-` |  | - |
| `feature_count` | `int` | 是 | `-` |  | - |
| `brep_shape_count` | `int` | 是 | `-` |  | - |
| `engine_used` | `str | None` | 是 | `-` |  | - |
| `step_output_path` | `str | None` | 是 | `-` |  | - |
| `final_step_path` | `str | None` | 是 | `-` |  | - |
| `precision_tier` | `str` | 是 | `-` |  | - |
| `mesh_calibrated` | `bool` | 是 | `-` |  | - |
| `assembly_summary` | `dict[str, Any] | None` | 是 | `-` |  | - |
| `download_url` | `str` | 是 | `-` |  | - |
| `step_disclaimer` | `dict[str, Any]` | 是 | `-` |  | - |

### `KnowledgeAddRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `document` | `str` | 是 | `-` | 知识文档内容 | - |
| `metadata` | `Optional[Dict[str, _ScalarValue]]` | 否 | `None` | 元数据键值对，最多50项，值仅支持标量 | 最大长度: 50 |
| `doc_id` | `str | None` | 否 | `None` | 文档ID（为空则自动生成） | - |

### `KnowledgeDeleteRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `doc_id` | `str` | 是 | `-` | 要删除的文档ID | - |

### `KnowledgeQueryRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `query_text` | `str` | 是 | `-` | 查询文本 | - |
| `n_results` | `int` | 否 | `5` | 返回结果数量 | ≥ 1; ≤ 20 |

### `ProcessPlanRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `user_input` | `str` | 是 | `-` | 用户需求描述 | - |

### `CadQueryRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `material` | `str` | 否 | `''` | 材料类型 | 最大长度: 64 |
| `dimensions` | `Optional[Dict[str, Union[float, int]]]` | 否 | `None` | 尺寸参数键值对，最多20项，值为数值 | 最大长度: 20 |
| `description` | `str` | 否 | `''` | 加工描述 | 最大长度: 2000 |
| `script` | `str` | 否 | `''` | CadQuery脚本 | 最大长度: 50000 |
| `output_format` | `str` | 否 | `'stl'` | 输出格式 | 最大长度: 10 |

### `CreateTaskRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_type` | `TaskType` | 是 | `-` | 任务类型 | - |
| `params` | `Optional[Dict[str, _ScalarValue]]` | 否 | `None` | 任务参数键值对，最多50项，值仅支持标量 | 最大长度: 50 |
| `timeout` | `float | None` | 否 | `None` | 超时时间(秒) | - |

### `AIStatusResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `mode` | `str` | 否 | `'local'` | AI模式 | - |
| `available` | `bool` | 否 | `False` | AI是否可用 | - |
| `model` | `str` | 否 | `''` | 使用的模型 | - |

### `HealthResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `status` | `str` | 否 | `'healthy'` | 服务状态 | - |
| `version` | `str` | 否 | `''` | 版本号 | - |
| `ai_status` | `AIStatusResponse | None` | 否 | `None` | AI状态 | - |

### `LNNHyperparameters`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `learning_rate` | `float` | 是 | `-` | 学习率 | > 0; < 1 |
| `epochs` | `int` | 是 | `-` | 训练轮数 | ≥ 1 |
| `batch_size` | `int` | 是 | `-` | 批次大小 | ≥ 1 |
| `optimizer` | `str` | 是 | `-` | 优化器类型 | 正则: `^(adam|sgd|rmsprop)$` |

### `LNNPredictRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `input_data` | `list[float]` | 是 | `-` | 预测输入数据数组 | - |
| `model_name` | `str` | 是 | `-` | 要使用的模型名称 | 最小长度: 1 |
| `return_confidence` | `bool` | 否 | `False` | 是否返回预测置信度 | - |

### `LNNTrainRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 训练模型的名称 | 最小长度: 1 |
| `data_path` | `str` | 是 | `-` | 训练数据集的存储路径 | 最小长度: 1 |
| `hyperparameters` | `LNNHyperparameters` | 是 | `-` | 训练超参数集合 | - |
| `device` | `str` | 否 | `'auto'` | 训练设备 (auto/gpu/cpu) | 正则: `^(auto|gpu|cuda|cpu)$` |

### `LNNDevicePreference`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `device` | `str` | 否 | `'auto'` | 训练设备偏好 (auto/gpu/cpu) | 正则: `^(auto|gpu|cuda|cpu)$` |
| `use_amp` | `bool` | 否 | `True` | 是否启用混合精度训练 | - |

### `LNNModelInfo`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `name` | `str` | 是 | `-` | 模型名称 | - |
| `version` | `str` | 是 | `-` | 模型版本 | - |
| `last_updated` | `str` | 是 | `-` | 最后更新时间，ISO 8601格式 | - |

### `LNNPredictResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `value` | `float | list[float]` | 是 | `-` | 预测结果值 | - |
| `confidence` | `float | None` | 否 | `None` | 预测置信度，范围[0, 1] | ≥ 0; ≤ 1 |
| `inference_time` | `float` | 是 | `-` | 推理耗时，单位毫秒 | - |
| `model_info` | `LNNModelInfo` | 是 | `-` | 模型信息 | - |

### `LNNTrainMetrics`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `accuracy` | `float` | 是 | `-` | 准确率 | ≥ 0; ≤ 1 |
| `loss` | `float` | 是 | `-` | 损失值 | ≥ 0 |
| `training_time` | `float` | 是 | `-` | 训练总耗时，单位秒 | ≥ 0 |
| `epochs_completed` | `int` | 是 | `-` | 实际完成的训练轮数 | ≥ 0 |

### `LNNTrainResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `status` | `str` | 是 | `-` | 训练状态 | 正则: `^(success|failed|in_progress)$` |
| `message` | `str` | 是 | `-` | 训练状态描述信息 | - |
| `metrics` | `LNNTrainMetrics | None` | 否 | `None` | 训练指标，仅当status为success时返回 | - |

### `LNNQuantizeRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `quantization_type` | `str` | 是 | `-` | 量化类型 | 正则: `^(dynamic|static)$` |
| `calibration_data_path` | `str | None` | 否 | `None` | 校准数据集路径（仅静态量化需要） | - |

### `LNNModelSizeResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `original_size_bytes` | `int` | 是 | `-` | 原始模型大小 | - |
| `quantized_size_bytes` | `int | None` | 否 | `None` | 量化模型大小 | - |
| `original_size_human` | `str` | 是 | `-` | 原始模型大小（人类可读） | - |
| `quantized_size_human` | `str | None` | 否 | `None` | 量化模型大小（人类可读） | - |
| `size_reduction_bytes` | `int | None` | 否 | `None` | 减少的大小 | - |
| `size_reduction_percent` | `float | None` | 否 | `None` | 减少的百分比 | - |

### `AlternativePlan`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `plan_id` | `str` | 是 | `-` | 备选方案ID | - |
| `parameters` | `Dict[str, _ScalarValue]` | 是 | `-` | 方案参数配置，最多30项，值仅支持标量 | 最大长度: 30 |
| `expected_outcome` | `str` | 是 | `-` | 预期效果说明 | - |
| `confidence` | `float` | 是 | `-` | 方案置信度 | ≥ 0; ≤ 1 |
| `reasoning` | `str` | 是 | `-` | 推理过程说明 | - |

### `LNNPredictResponseExtended`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `value` | `float | list[float]` | 是 | `-` | 预测结果值 | - |
| `confidence` | `float | None` | 否 | `None` | 预测置信度 | ≥ 0; ≤ 1 |
| `reasoning` | `str | None` | 否 | `None` | AI推理过程 | - |
| `inference_time` | `float` | 是 | `-` | 推理耗时，单位毫秒 | - |
| `model_info` | `LNNModelInfo` | 是 | `-` | 模型信息 | - |
| `alternatives` | `list[AlternativePlan] | None` | 否 | `None` | 备选方案列表 | - |

### `LNNTrainDryRunRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 训练模型的名称 | 最小长度: 1 |
| `data_path` | `str` | 是 | `-` | 训练数据集的存储路径 | 最小长度: 1 |
| `hyperparameters` | `LNNHyperparameters` | 是 | `-` | 训练超参数集合 | - |
| `device` | `str` | 否 | `'auto'` | 训练设备 | 正则: `^(auto|gpu|cuda|cpu)$` |

### `TrainingPlanSummary`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `estimated_duration_minutes` | `float` | 是 | `-` | 预估训练时长（分钟） | - |
| `estimated_memory_mb` | `float` | 是 | `-` | 预估内存占用（MB） | - |
| `estimated_gpu_memory_mb` | `float | None` | 否 | `None` | 预估GPU显存占用（MB） | - |
| `dataset_samples` | `int` | 是 | `-` | 数据集样本数 | - |
| `train_val_split` | `Dict[str, Union[float, int]]` | 是 | `-` | 训练集/验证集划分比例，值为数值 | 最大长度: 10 |
| `potential_risks` | `list[str]` | 是 | `-` | 潜在风险提示 | - |
| `recommendations` | `list[str]` | 是 | `-` | 训练建议 | - |

### `LNNTrainDryRunResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `is_dry_run` | `bool` | 否 | `True` | 是否为dry_run模式 | - |
| `training_plan` | `TrainingPlanSummary` | 是 | `-` | 训练计划概要 | - |
| `confidence` | `float` | 是 | `-` | 训练成功置信度 | ≥ 0; ≤ 1 |
| `reasoning` | `str` | 是 | `-` | 训练计划推理说明 | - |

### `AuditLogQueryRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `start_time` | `int | None` | 否 | `None` | 开始时间戳（毫秒） | - |
| `end_time` | `int | None` | 否 | `None` | 结束时间戳（毫秒） | - |
| `ai_module` | `str | None` | 否 | `None` | AI模块过滤 | - |
| `user_decision` | `str | None` | 否 | `None` | 用户决策过滤 | - |
| `limit` | `int` | 否 | `100` | 返回数量 | ≥ 1; ≤ 1000 |
| `offset` | `int` | 否 | `0` | 偏移量 | ≥ 0 |

### `AuditLogSearchRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `keyword` | `str` | 是 | `-` | 搜索关键词 | 最小长度: 1 |
| `limit` | `int` | 否 | `50` | 返回数量 | ≥ 1; ≤ 500 |

### `AuditLogExportRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `format` | `str` | 否 | `'json'` | 导出格式 | 正则: `^(json|csv)$` |
| `start_time` | `int | None` | 否 | `None` | 开始时间戳（毫秒） | - |
| `end_time` | `int | None` | 否 | `None` | 结束时间戳（毫秒） | - |
| `ai_module` | `str | None` | 否 | `None` | AI模块过滤 | - |

### `UserSovereigntySettings`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `ai_autonomy_level` | `int` | 否 | `2` | AI自主度等级（0-4）：0=完全手动, 1=建议需确认, 2=推荐（默认）, 3=半自动, 4=全自动 | ≥ 0; ≤ 4 |
| `require_confirmation_for_predict` | `bool` | 否 | `False` | 预测是否需要确认 | - |
| `require_confirmation_for_train` | `bool` | 否 | `True` | 训练是否需要确认 | - |
| `show_confidence_indicator` | `bool` | 否 | `True` | 是否显示置信度指示器 | - |
| `show_alternatives` | `bool` | 否 | `True` | 是否显示备选方案 | - |
| `show_reasoning` | `bool` | 否 | `True` | 是否显示推理过程 | - |

### `AgentTokenCreateRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `scopes` | `list[str]` | 是 | `-` | 权限范围集合（R/W/B/N/C/T 的任意组合） | 最小长度: 1 |
| `expires_in` | `int | None` | 否 | `None` | Token有效期（秒），None表示永不过期 | ≥ 3600 |
| `paper_only` | `bool` | 否 | `True` | 是否仅限模拟模式 | - |

### `AgentTokenResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 是 | `-` | Agent ID | - |
| `token` | `str` | 是 | `-` | 完整Token值（仅创建时显示一次） | - |
| `scopes` | `list[str]` | 是 | `-` | 权限范围 | - |
| `created_at` | `float` | 是 | `-` | 创建时间戳 | - |
| `expires_at` | `float | None` | 否 | `None` | 过期时间戳 | - |
| `paper_only` | `bool` | 是 | `-` | 是否仅限模拟模式 | - |

### `AgentTokenListItem`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str` | 是 | `-` | Agent ID | - |
| `token_prefix` | `str` | 是 | `-` | Token前缀（脱敏显示） | - |
| `scopes` | `list[str]` | 是 | `-` | 权限范围 | - |
| `created_at` | `float` | 是 | `-` | 创建时间戳 | - |
| `expires_at` | `float | None` | 否 | `None` | 过期时间戳 | - |
| `paper_only` | `bool` | 是 | `-` | 是否仅限模拟模式 | - |
| `is_active` | `bool` | 是 | `-` | 是否活跃 | - |

### `AgentPredictRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1; 最大长度: 100; 正则: `^[A-Za-z0-9_-]+$` |
| `input_data` | `list[float]` | 是 | `-` | 输入数据 | - |
| `return_confidence` | `bool` | 否 | `False` | 是否返回置信度 | - |

### `AgentTrainRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1; 最大长度: 100; 正则: `^[A-Za-z0-9_-]+$` |
| `data_path` | `str` | 是 | `-` | 训练数据路径 | 最小长度: 1 |
| `hyperparameters` | `LNNHyperparameters` | 是 | `-` | 超参数 | - |
| `device` | `str` | 否 | `'auto'` | 设备 | 正则: `^(auto|gpu|cuda|cpu)$` |

### `AgentExecuteRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `machine_id` | `str` | 是 | `-` | 机床ID | 最小长度: 1 |
| `parameters` | `Dict[str, _ScalarValue]` | 是 | `-` | 工艺参数键值对，最多50项，值仅支持标量 | 最大长度: 50 |
| `simulate` | `bool` | 否 | `True` | 是否模拟执行 | - |
| `supervisor_confirmed` | `bool` | 否 | `False` | 班长双因子确认（实模式必填，Paper-Only 模式可忽略） | - |
| `machine_safety_status` | `Optional[Dict[str, bool]]` | 否 | `None` | 机床安全状态字典（实模式必填），包含：emergency_stop_active / guard_door_closed / light_curtain_clear / operator_present | 最大长度: 20 |

### `AgentPipelineRequest`

Agent 管线执行请求

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `pipeline_type` | `str` | 是 | `-` | 管线类型（dxf_to_gcode/process_plan） | 最小长度: 1; 最大长度: 50; 正则: `^(dxf_to_gcode|process_plan)$` |
| `input_data` | `Dict[str, _ScalarValue]` | 是 | `-` | 管线输入数据，最多50项键值对，值仅支持标量 | 最大长度: 50 |
| `mode` | `str` | 否 | `'sequential'` | 执行模式（sequential/conditional） | 正则: `^(sequential|conditional)$` |
| `agent_id` | `str | None` | 否 | `None` | Agent ID（用于审计） | - |

### `AgentAuditLogQueryRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `agent_id` | `str | None` | 否 | `None` | Agent ID过滤 | - |
| `permission_class` | `str | None` | 否 | `None` | 权限类别过滤 | - |
| `limit` | `int` | 否 | `100` | 返回数量 | ≥ 1; ≤ 1000 |
| `offset` | `int` | 否 | `0` | 偏移量 | ≥ 0 |

### `LNNBatchInferenceRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1 |
| `input_data` | `list[list[float]]` | 是 | `-` | 批量输入数据 | - |
| `batch_size` | `int` | 否 | `32` | 批次大小 | ≥ 1 |

### `LNNStreamingConfig`

流式推理配置（对应 :class:`app.ai.lnn.inference.streaming.StreamingConfig`）。

借鉴 lingbot-map GCT 思想：关键帧间隔 + 锚点漂移修正 + 轨迹记忆约束 + 窗口化推理。
所有字段可选，缺省时使用 ``StreamingConfig`` 默认值。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `keyframe_interval` | `int` | 否 | `1` | 关键帧间隔（每 N 帧一个关键帧） | ≥ 1 |
| `keyframe_mode` | `str` | 否 | `'hybrid'` | 关键帧判定策略：interval / energy / hybrid | 正则: `^(interval|energy|hybrid)$` |
| `energy_threshold` | `float` | 否 | `1.5` | 能量关键帧触发阈值（相对能量增益） | > 0 |
| `max_cache_pages` | `int` | 否 | `320` | 长期隐状态缓存最大页数（LRU 淘汰） | ≥ 1 |
| `anchor_enabled` | `bool` | 否 | `True` | 是否启用锚点漂移修正 | - |
| `anchor_update_rate` | `float` | 否 | `0.01` | 锚点 EMA 更新速率 | > 0; < 1 |
| `anchor_correction_strength` | `float` | 否 | `0.1` | 锚点漂移修正强度 [0, 1] | ≥ 0; ≤ 1 |
| `trajectory_memory_size` | `int` | 否 | `64` | 轨迹记忆窗口大小 | ≥ 1 |
| `trajectory_correction_strength` | `float` | 否 | `0.1` | 轨迹一致性约束强度 [0, 1] | ≥ 0; ≤ 1 |
| `window_size` | `int | None` | 否 | `None` | 窗口化推理窗口大小（None 表示不启用） | - |
| `overlap_keyframes` | `int` | 否 | `2` | 窗口间重叠关键帧数，用于隐状态传递 | ≥ 0 |

### `LNNStreamPredictRequest`

流式长时序推理请求（POST /api/v1/lnn/predict_stream）。

对每一帧逐次推理，通过关键帧缓存 + 锚点漂移修正保持长时序一致性。
响应为 NDJSON 流（``application/x-ndjson``），每行一帧的推理结果。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1 |
| `frames` | `list[list[float]]` | 是 | `-` | 帧序列数据，每个内层列表为一帧输入 | - |
| `config` | `LNNStreamingConfig | None` | 否 | `None` | 流式推理配置，缺省时使用默认 StreamingConfig | - |

### `LNNWindowedPredictRequest`

窗口化超长序列推理请求（POST /api/v1/lnn/predict_windowed）。

将超长序列切分为多个窗口，窗口间通过 ``overlap_keyframes`` 传递隐状态，
避免每次窗口都从零初始化。适用于跨工序连续切削、万帧以上颤振监控等场景。
响应为一次性 JSON 数组，包含完整序列的推理结果。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1 |
| `frames` | `list[list[float]]` | 是 | `-` | 完整序列数据，每个内层列表为一帧输入 | - |
| `window_size` | `int | None` | 否 | `None` | 窗口大小，缺省时使用 config.window_size | ≥ 1 |
| `overlap_keyframes` | `int | None` | 否 | `None` | 窗口间重叠关键帧数，缺省时使用 config.overlap_keyframes | ≥ 0 |
| `config` | `LNNStreamingConfig | None` | 否 | `None` | 流式推理配置，缺省时使用默认 StreamingConfig | - |

### `PermissionCheckResult`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `has_permission` | `bool` | 是 | `-` | 是否拥有权限 | - |
| `user_permissions` | `list[str]` | 是 | `-` | 用户拥有的权限列表 | - |

### `UserListItem`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `username` | `str` | 是 | `-` | 用户名 | - |
| `role` | `str` | 是 | `-` | 用户角色 | - |
| `is_active` | `bool` | 是 | `-` | 是否启用 | - |
| `created_at` | `str` | 是 | `-` | 创建时间 | - |
| `last_login` | `str | None` | 否 | `None` | 最后登录时间 | - |

### `UserListResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `total` | `int` | 是 | `-` | 用户总数 | - |
| `users` | `list[UserListItem]` | 是 | `-` | 用户列表 | - |

### `RoleAssignRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `role_code` | `str` | 是 | `-` | 角色代码 | 最小长度: 1 |

### `UncertaintyResponse`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `prediction` | `float` | 是 | `-` | 预测结果值 | - |
| `uncertainty` | `float` | 是 | `-` | 预测不确定性度量（标准差） | ≥ 0 |
| `confidence` | `float` | 是 | `-` | 置信度，范围[0, 1] | ≥ 0; ≤ 1 |

### `UserStatusRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `is_active` | `bool` | 是 | `-` | 是否启用用户 | - |


---

*本文档由 API 文档自动生成系统生成，如有疑问请联系开发团队。*
