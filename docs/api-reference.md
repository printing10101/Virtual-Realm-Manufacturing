# API 参考文档

> **自动生成**: 本文档由 `scripts/gen-api-docs.py` 自动生成
> 
> **最后更新**: 自动填充
> 
> **适用版本**: 灵境制造平台 v2.5.0

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

LNN（Liquid Neural Network，液态神经网络）模型管理接口，支持模型预测、训练、量化等功能。对应代码实现为 `DLLNNModel` 类（DL-LNN：Delay-embedded Liquid Neural Network）。

### `POST` `/api/v1/lnn/batch-inference`

**异步启动批量推理,立即返回 job_id。**

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `request` | `LNNBatchInferenceRequest` | `-` | 是 |  |
| `idempotency_key` | `Optional[str]` | `Header(...)` | 否 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `DELETE` `/api/v1/lnn/cache/clear`

**清空所有模型缓存**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/cache/stats`

**获取模型缓存统计信息**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/device/clear-cache`

**清空GPU缓存**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/device/info`

**返回系统中可用的计算设备信息**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/device/status`

**返回当前设备利用率和温度等信息**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/health`

**LNN 系统健康检查(包含持久层状态)**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/models`

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/models/{model_name}/info`

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `model_name` | `str` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/models/{model_name}/quantize`

**异步启动 INT8 量化任务,立即返回 job_id。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `model_name` | `str` | 是 |  |

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `LNNQuantizeRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/models/{model_name}/size`

**获取模型及其量化版本的大小信息。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `model_name` | `str` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/models/{model_name}/validate`

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `model_name` | `str` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/performance`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `model` | `str | None` | `None` | 否 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/predict`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `LNNPredictRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

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

### `POST` `/api/v1/lnn/quantize/{task_id}/cancel`

**取消进行中的量化任务。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `task_id` | `str` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/quantize/{task_id}/status`

**查询异步量化任务的状态与结果。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `task_id` | `str` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/tasks`

**列出所有训练任务**

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/train`

**异步启动 LNN 训练,立即返回 job_id。**

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `body` | `LNNTrainRequest` | `-` | 是 |  |
| `idempotency_key` | `Optional[str]` | `Header(...)` | 否 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/train/dry_run`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `request` | `LNNTrainDryRunRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/lnn/train/{task_id}/cancel`

**取消正在运行的训练任务。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `task_id` | `str` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `GET` `/api/v1/lnn/train/{task_id}/stream`

**SSE 端点,用于实时训练状态更新。**

**路径参数：**

| 参数名 | 类型 | 必填 | 说明 |
|--------|------|------|------|
| `task_id` | `str` | 是 |  |

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
| `request` | `CalibrateRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/calibrate-realtime`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `request` | `RealTimeCalibrateRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/compensation`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `request` | `CompensationRequest` | `-` | 是 |  |

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
| `request` | `WearPredictRequest` | `-` | 是 |  |

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
| `request` | `RemainingLifeRequest` | `-` | 是 |  |

**响应：**

- **200**: 成功响应
- **400**: 请求参数错误
- **404**: 资源未找到
- **500**: 服务器内部错误

### `POST` `/api/v1/wear/suggest`

**请求体参数：**

| 参数名 | 类型 | 默认值 | 必填 | 说明 |
|--------|------|--------|------|------|
| `request` | `SuggestRequest` | `-` | 是 |  |

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

### `RewriteNCRequest`

NC 代码改写请求。

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `nc_code` | `str` | 是 | `-` | NC/G 代码文本 | 最小长度: 1 |
| `decision` | `dict[str, Any]` | 是 | `-` | 由 /decide 返回的决策字典（decision 字段） | - |
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
| `budget_amount` | `float` | 否 | `0.0` | 预算金额 | - |
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
| `operation_type` | `str` | 是 | `-` | 操作类型 | - |
| `context` | `dict` | 是 | `-` | 上下文 | - |
| `requester_role` | `str` | 否 | `'engineer'` | 请求人角色 | - |
| `budget_amount` | `float` | 否 | `0.0` | 预算金额 | - |

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

### `ExecutionRecordRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_id` | `str` | 是 | `-` | Task ID | - |
| `branch_id` | `str` | 是 | `-` | Branch ID | - |
| `elements` | `Dict[str, Any]` | 是 | `-` | Execution elements | - |
| `conditions` | `Dict[str, Any]` | 是 | `-` | Execution conditions | - |
| `metrics` | `Dict[str, Any]` | 是 | `-` | Execution metrics | - |
| `success` | `bool` | 否 | `True` | Whether execution succeeded | - |

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
| `start_date` | `Optional[str]` | 否 | `None` |  | - |
| `due_date` | `Optional[str]` | 否 | `None` |  | - |

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
| `success` | `bool` | 否 | `True` | Whether execution succeeded | - |
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

### `KnowledgeAddRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `document` | `str` | 是 | `-` | 知识文档内容 | - |
| `metadata` | `dict | None` | 否 | `None` | 元数据 | - |
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
| `dimensions` | `dict | None` | 否 | `None` | 尺寸参数 | - |
| `description` | `str` | 否 | `''` | 加工描述 | 最大长度: 2000 |
| `script` | `str` | 否 | `''` | CadQuery脚本 | 最大长度: 50000 |
| `output_format` | `str` | 否 | `'stl'` | 输出格式 | 最大长度: 10 |

### `CreateTaskRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `task_type` | `TaskType` | 是 | `-` | 任务类型 | - |
| `params` | `dict | None` | 否 | `None` | 任务参数 | - |
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
| `parameters` | `dict` | 是 | `-` | 方案参数配置 | - |
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
| `train_val_split` | `dict` | 是 | `-` | 训练集/验证集划分比例 | - |
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
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1 |
| `input_data` | `list[float]` | 是 | `-` | 输入数据 | - |
| `return_confidence` | `bool` | 否 | `False` | 是否返回置信度 | - |

### `AgentTrainRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `model_name` | `str` | 是 | `-` | 模型名称 | 最小长度: 1 |
| `data_path` | `str` | 是 | `-` | 训练数据路径 | 最小长度: 1 |
| `hyperparameters` | `LNNHyperparameters` | 是 | `-` | 超参数 | - |
| `device` | `str` | 否 | `'auto'` | 设备 | 正则: `^(auto|gpu|cuda|cpu)$` |

### `AgentExecuteRequest`

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `machine_id` | `str` | 是 | `-` | 机床ID | 最小长度: 1 |
| `parameters` | `dict` | 是 | `-` | 工艺参数 | - |
| `simulate` | `bool` | 否 | `True` | 是否模拟执行 | - |
| `supervisor_confirmed` | `bool` | 否 | `False` | 班长双因子确认（实模式必填，Paper-Only 模式可忽略） | - |
| `machine_safety_status` | `dict[str, bool] | None` | 否 | `None` | 机床安全状态字典（实模式必填），包含：emergency_stop_active / guard_door_closed / light_curtain_clear / operator_present | - |

### `AgentPipelineRequest`

Agent 管线执行请求

| 字段名 | 类型 | 必填 | 默认值 | 说明 | 约束 |
|--------|------|------|--------|------|------|
| `pipeline_type` | `str` | 是 | `-` | 管线类型（process_planning/model_training/quality_analysis） | 最小长度: 1 |
| `input_data` | `dict[str, Any]` | 是 | `-` | 管线输入数据 | - |
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
