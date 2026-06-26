# 灵境制造 (Lingjing Manufacturing) API Documentation

> Base URL: `http://localhost:8765`
> Framework: FastAPI
> Auto-generated docs available at:
> - Swagger UI: `/docs`
> - ReDoc: `/redoc`
> - OpenAPI JSON: `/openapi.json`

---

## Table of Contents

1. [Overview](#overview)
2. [Authentication](#authentication)
3. [Response Format](#response-format)
4. [Error Codes](#error-codes)
5. [Rate Limiting](#rate-limiting)
6. [API Endpoints](#api-endpoints)
   - [Base Routes](#base-routes)
   - [Authentication](#authentication-1)
   - [User Management](#user-management)
   - [LNN Models](#lnn-models)
   - [Wear Prediction](#wear-prediction)
   - [Async Jobs](#async-jobs)
   - [Agent Gateway](#agent-gateway)
   - [Agent State](#agent-state)
   - [User Sovereignty](#user-sovereignty)
   - [Skills](#skills)
   - [Plugins](#plugins)
   - [Cost & Budget](#cost--budget)
   - [Goal Alignment](#goal-alignment)
   - [Governance](#governance)
   - [Heartbeat](#heartbeat)
   - [Task Checkout](#task-checkout)
   - [Templates](#templates)
   - [RAG](#rag)
   - [Ollama](#ollama)
   - [Simulation](#simulation)
   - [Projects](#projects)
   - [STEP Import](#step-import)
   - [Process Rules](#process-rules)

---

## Overview

| Property | Value |
|---|---|
| **Base URL** | `http://localhost:8765` |
| **Protocol** | HTTP/1.1 + HTTPS (production) |
| **Data Format** | JSON (request/response bodies) |
| **CORS** | Configured via settings (`ALLOW_ORIGINS`) |
| **Rate Limiting** | Enabled by default via slowapi (`RATE_LIMIT_ENABLED`, `True` by default) |
| **Tracing** | Request ID injected into all responses via `X-Request-ID` header |

---

## Authentication

The API supports two authentication methods:

### JWT Bearer Token (Primary)

```
Authorization: Bearer <jwt_token>
```

Obtain a token via `POST /api/v1/auth/login`:

```json
{
  "username": "admin",
  "password": "your_password"
}
```

Response:
```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

### Agent Token

Some agent-related routes accept agent tokens:

```
Authorization: Bearer agent_<uuid>
```

---

## Response Format

### Success Response

All successful responses use the `success()` helper:

```json
{
  "code": 0,
  "message": "操作成功",
  "data": {
    "key": "value"
  }
}
```

### Error Response

All error responses use the `error()` helper:

```json
{
  "code": 1001,
  "message": "资源未找到",
  "detail": {
    "resource": "user",
    "id": "123"
  },
  "request_id": "uuid-string"
}
```

Error response fields:

| Field | Type | Description |
|---|---|---|
| `code` | int | Error code (see below) |
| `message` | string | Human-readable error message |
| `detail` | object | Optional structured error details |
| `request_id` | string | Unique request identifier |
| `recoverable` | bool | Whether the client can retry |
| `suggestion` | string | Suggested corrective action |

---

## Error Codes

| Code | Constant | Description |
|---|---|---|
| `1001` | `NOT_FOUND` | Resource not found |
| `1002` | `INVALID_REQUEST` | Invalid request parameters |
| `1003` | `UNAUTHORIZED` | Authentication required or invalid |
| `1004` | `FORBIDDEN` | Insufficient permissions |
| `1005` | `INTERNAL_ERROR` | Internal server error |
| `1007` | `RATE_LIMIT_EXCEEDED` | 请求过于频繁（速率限制触发） |
| `4001` | `MODEL_NOT_FOUND` | LNN model not found |
| `4002` | `PREDICTION_NOT_FOUND` | Wear prediction not found |
| `4004` | `USER_NOT_FOUND` | User not found |
| `4005` | `INVALID_PASSWORD` | Invalid password |
| `5001` | `JOB_NOT_FOUND` | Async job not found |
| `5002` | `JOB_ALREADY_EXISTS` | Duplicate async job |
| `7001` | `GOAL_NOT_FOUND` | Goal alignment not found |
| `8001` | `STATE_NOT_FOUND` | Agent state not found |
| `8002` | `INVALID_STATE_TRANSITION` | Invalid agent state transition |
| `8003` | `STATE_CONFLICT` | Agent state version conflict |
| `9001` | `SKILL_NOT_FOUND` | Skill not found |
| `10001` | `BUDGET_EXCEEDED` | Budget limit exceeded |

---

## Rate Limiting

系统使用 **slowapi**（基于IP的内存存储速率限制）对所有API端点提供保护。速率限制默认启用，可通过 `RATE_LIMIT_ENABLED` 环境变量关闭。

### 默认限制规则

| 端点 | 限制规则 | 说明 |
|------|---------|------|
| `POST /api/v1/auth/login` | **5次/分钟** | 登录接口，防止暴力破解 |
| `POST /api/v1/auth/register` | **3次/小时** | 注册接口，防止恶意注册 |
| `POST /api/v1/lnn/predict` | **60次/分钟** | 模型预测接口，保障推理服务稳定性 |
| `POST /api/v1/lnn/train` | **5次/小时** | 模型训练接口，防止训练请求滥用 |

其他未特殊标注的端点继承全局默认限制（100次/分钟）。

### Agent API 速率限制（独立）

Agent API（`/api/agent/v1/*`）拥有独立的速率限制逻辑，不受上述全局速率限制影响：
- 每个Agent Token **60次请求/分钟**
- 每个Agent最多 **3个并发任务**
- 由 `UnifiedAuthMiddleware` 统一管理

### 错误响应

当请求超出速率限制时，返回 **429 Too Many Requests** 状态码，响应体格式如下：

```json
{
  "code": 1007,
  "message": "请求过于频繁，请在1分钟后重试",
  "request_id": "abc123..."
}
```

响应头中包含 `Retry-After` 字段，指示客户端应在多少秒后重试。

### 配置方式

| 环境变量 | 默认值 | 说明 |
|---------|--------|------|
| `RATE_LIMIT_ENABLED` | `True` | 启用/禁用速率限制 |
| `RATE_LIMIT_REQUESTS` | `100` | 全局窗口内最大请求数 |
| `RATE_LIMIT_WINDOW` | `60` | 速率限制窗口（秒） |

---

## API Endpoints

### Base Routes

Routes defined directly in `main.py`.

#### Health Check

```
GET /health
```

**Description:** Returns the server health status, environment, version, and component health checks.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `detail` | bool | Include detailed component health info |

**Response (200):**
```json
{
  "status": "healthy",
  "environment": "development",
  "version": "1.0.0",
  "components": {
    "database": {"status": "ok", "latency_ms": 5},
    "cache": {"status": "ok", "latency_ms": 2},
    "message_queue": {"status": "ok", "latency_ms": 3}
  },
  "timestamp": 1716192000
}
```

**Status Codes:** `200 OK`, `503 Service Unavailable`

#### Liveness Probe

```
GET /health/live
```

**Description:** Kubernetes liveness probe — lightweight readiness check.

**Response (200):**
```json
{
  "status": "ok",
  "timestamp": 1716192000
}
```

#### Readiness Probe

```
GET /health/ready
```

**Description:** Kubernetes readiness probe — checks database, cache, and message queue.

**Response (200):** Same as `/health?detail=true`

**Status Codes:** `200 OK`, `503 Service Unavailable`

#### Version

```
GET /version
```

**Description:** Returns server version and environment info.

**Response (200):**
```json
{
  "version": "1.0.0",
  "environment": "development"
}
```

#### Logs

```
GET /logs/recent
```

**Description:** Returns recent log entries from memory handler.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `level` | string | | Filter by log level |
| `lines` | int | 50 | Number of lines to return |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "lines": ["2024-05-20 10:00:00 INFO ...", "..."],
    "total": 50
  }
}
```

#### Metrics

```
GET /metrics/prometheus
```

**Description:** Prometheus metrics endpoint (only when `PROMETHEUS_ENABLED` is true).

**Response (200):** Plain text Prometheus metrics

---

### Authentication

**Base Path:** `/api/v1/auth`

#### Login

```
POST /api/v1/auth/login
```

**Description:** Authenticate a user and return a JWT token.

**Request Body:**
```json
{
  "username": "string",
  "password": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "登录成功",
  "data": {
    "access_token": "eyJhbGci...",
    "token_type": "bearer",
    "expires_in": 1800
  }
}
```

**Status Codes:** `200 OK`, `401 Unauthorized`

#### Register

```
POST /api/v1/auth/register
```

**Description:** Register a new user account.

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "role": "user"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "注册成功",
  "data": {
    "user_id": "uuid",
    "username": "string"
  }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`

---

### User Management

**Base Path:** `/api/v1/users`

#### Create User

```
POST /api/v1/users/create
```

**Description:** Create a new user (admin only).

**Request Body:**
```json
{
  "username": "string",
  "email": "string",
  "password": "string",
  "role": "user"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "用户创建成功",
  "data": {
    "user_id": "uuid",
    "username": "string",
    "role": "user",
    "created_at": "timestamp"
  }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`

#### List Users

```
GET /api/v1/users/list
```

**Description:** Get paginated user list with search and sort.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (1-100) |
| `keyword` | string | | Search by username/email |
| `sort_by` | string | created_at | Sort field |
| `sort_order` | string | DESC | Sort direction (ASC/DESC) |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "users": [
      {
        "user_id": "uuid",
        "username": "string",
        "role": "user",
        "created_at": "timestamp"
      }
    ],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  }
}
```

**Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`

#### Get User

```
GET /api/v1/users/{user_id}
```

**Description:** Get a user by ID.

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | string | User UUID |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "user_id": "uuid",
    "username": "string",
    "email": "string",
    "role": "user",
    "is_active": true,
    "created_at": "timestamp",
    "last_login": "timestamp"
  }
}
```

**Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`

#### Update User

```
PUT /api/v1/users/{user_id}
```

**Description:** Update user information (admin only).

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | string | User UUID |

**Request Body:**
```json
{
  "username": "string (optional)",
  "email": "string (optional)",
  "role": "string (optional)",
  "is_active": true (optional)"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "用户更新成功",
  "data": { ... }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`

#### Delete User

```
DELETE /api/v1/users/{user_id}
```

**Description:** Delete a user (admin only).

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | string | User UUID |

**Response (200):**
```json
{
  "code": 0,
  "message": "用户删除成功"
}
```

**Status Codes:** `200 OK`, `401 Unauthorized`, `403 Forbidden`, `404 Not Found`

#### Batch Update Users

```
PUT /api/v1/users/batch-update
```

**Description:** Update multiple users in one request (admin only).

**Request Body:**
```json
{
  "user_ids": ["uuid1", "uuid2"],
  "updates": {
    "role": "admin",
    "is_active": true
  }
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "批量更新成功，2/2 个用户已更新"
}
```

#### Batch Delete Users

```
DELETE /api/v1/users/batch-delete
```

**Description:** Delete multiple users in one request (admin only).

**Request Body:**
```json
{
  "user_ids": ["uuid1", "uuid2"]
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "批量删除成功，2/2 个用户已删除"
}
```

#### User Stats

```
GET /api/v1/users/stats
```

**Description:** Get user statistics (admin only).

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "total_users": 100,
    "active_users": 80,
    "inactive_users": 20,
    "new_users_this_month": 10,
    "user_growth_rate": 0.1
  }
}
```

#### Get Current User

```
GET /api/v1/users/me
```

**Description:** Get the currently authenticated user's profile.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "user_id": "uuid",
    "username": "string",
    "role": "user"
  }
}
```

#### Update Current User

```
PUT /api/v1/users/me
```

**Description:** Update the current user's profile.

**Request Body:**
```json
{
  "username": "string (optional)",
  "email": "string (optional)"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "用户资料更新成功",
  "data": { ... }
}
```

#### Change Password

```
POST /api/v1/users/change-password
```

**Description:** Change the current user's password.

**Request Body:**
```json
{
  "old_password": "string",
  "new_password": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "密码修改成功"
}
```

#### Get Current User Tasks

```
GET /api/v1/users/me/tasks
```

**Description:** Get tasks assigned to the current user.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `status` | string | all | Filter by task status |
| `limit` | int | 50 | Max results |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "tasks": [...],
    "total": 10
  }
}
```

---

### LNN Models

**Base Path:** `/api/v1/lnn`

#### Create Model

```
POST /api/v1/lnn/models
```

**Description:** Create a new LNN model configuration.

**Request Body:**
```json
{
  "name": "string",
  "description": "string (optional)",
  "model_type": "string",
  "config": {}
}
```

**Response (201):**
```json
{
  "code": 0,
  "message": "模型创建成功",
  "data": {
    "model_id": "string",
    "name": "string",
    "status": "draft"
  }
}
```

**Status Codes:** `201 Created`, `400 Bad Request`, `401 Unauthorized`, `403 Forbidden`

#### List Models

```
GET /api/v1/lnn/models
```

**Description:** List all LNN models with filters.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status |
| `model_type` | string | Filter by type |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [
    {
      "model_id": "string",
      "name": "string",
      "model_type": "string",
      "status": "active",
      "created_at": "timestamp"
    }
  ]
}
```

#### Get Model

```
GET /api/v1/lnn/models/{model_id}
```

**Description:** Get a specific LNN model by ID.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "model_id": "string",
    "name": "string",
    "config": {},
    "status": "active"
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Update Model

```
PUT /api/v1/lnn/models/{model_id}
```

**Description:** Update an LNN model.

**Request Body:**
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "config": {} (optional)
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "模型更新成功",
  "data": { ... }
}
```

#### Delete Model

```
DELETE /api/v1/lnn/models/{model_id}
```

**Description:** Delete an LNN model.

**Response (200):**
```json
{
  "code": 0,
  "message": "模型删除成功"
}
```

#### Activate Model

```
POST /api/v1/lnn/models/{model_id}/activate
```

**Description:** Activate a model (requires admin/engineer role).

**Response (200):**
```json
{
  "code": 0,
  "message": "模型已激活",
  "data": {
    "model_id": "string",
    "status": "active",
    "activated_at": "timestamp"
  }
}
```

#### Deactivate Model

```
POST /api/v1/lnn/models/{model_id}/deactivate
```

**Description:** Deactivate a model.

**Response (200):**
```json
{
  "code": 0,
  "message": "模型已停用"
}
```

#### Predict (Inference)

```
POST /api/v1/lnn/models/{model_id}/predict
```

**Description:** Run inference on a model.

**Request Body:**
```json
{
  "input_data": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "model_id": "string",
    "prediction": {},
    "confidence": 0.95,
    "inference_time_ms": 120
  }
}
```

#### Batch Predict

```
POST /api/v1/lnn/models/{model_id}/batch-predict
```

**Description:** Run batch inference on multiple inputs.

**Request Body:**
```json
{
  "inputs": [
    {"input_data": {}},
    {"input_data": {}}
  ]
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "results": [...],
    "total": 10
  }
}
```

#### Compare Models

```
POST /api/v1/lnn/models/compare
```

**Description:** Compare multiple models on the same input.

**Request Body:**
```json
{
  "model_ids": ["model_1", "model_2"],
  "input_data": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "input_data": {},
    "comparisons": [
      {
        "model_id": "model_1",
        "prediction": {},
        "inference_time_ms": 120
      }
    ]
  }
}
```

#### Get Active Models

```
GET /api/v1/lnn/models/active
```

**Description:** List all active models.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [
    {
      "model_id": "string",
      "name": "string",
      "status": "active"
    }
  ]
}
```

#### Model Versions

```
GET /api/v1/lnn/models/{model_id}/versions
```

**Description:** Get version history of a model.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "model_id": "string",
    "versions": [
      {
        "version": "1.0.0",
        "created_at": "timestamp",
        "changes": "Initial version"
      }
    ],
    "current_version": "1.0.0"
  }
}
```

---

### Wear Prediction

**Base Path:** `/api/v1/wear`

#### Predict Tool Wear

```
POST /api/v1/wear/predict
```

**Description:** Predict tool wear based on machining parameters.

**Request Body:**
```json
{
  "cutting_speed": 150.0,
  "feed_rate": 0.2,
  "depth_of_cut": 2.0,
  "tool_material": "carbide",
  "workpiece_material": "steel",
  "coolant_type": "flood"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "prediction_id": "string",
    "predicted_wear": 0.15,
    "confidence": 0.92,
    "estimated_remaining_life": 45.0,
    "wear_stage": "normal"
  }
}
```

#### Get Prediction

```
GET /api/v1/wear/predictions/{prediction_id}
```

**Description:** Get a specific prediction result.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "prediction_id": "string",
    "input": {},
    "predicted_wear": 0.15,
    "created_at": "timestamp"
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### List Predictions

```
GET /api/v1/wear/predictions
```

**Description:** List prediction history.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `limit` | int | Max results (default 50) |
| `offset` | int | Offset for pagination |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "predictions": [...],
    "total": 100
  }
}
```

#### Delete Prediction

```
DELETE /api/v1/wear/predictions/{prediction_id}
```

**Description:** Delete a prediction record.

**Response (200):**
```json
{
  "code": 0,
  "message": "预测记录删除成功"
}
```

#### Batch Predict

```
POST /api/v1/wear/batch-predict
```

**Description:** Run wear prediction on multiple parameter sets.

**Request Body:**
```json
{
  "inputs": [
    {"cutting_speed": 150.0, "feed_rate": 0.2, ...},
    {"cutting_speed": 200.0, "feed_rate": 0.3, ...}
  ]
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "results": [...],
    "total": 2
  }
}
```

---

### Async Jobs

**Base Path:** `/api/v1/jobs`

#### Create Job

```
POST /api/v1/jobs
```

**Description:** Create an async job to run a task in background.

**Request Body:**
```json
{
  "job_id": "unique_job_id",
  "task_name": "task_name",
  "task_kwargs": {},
  "priority": "normal",
  "callback_url": "https://...",
  "callback_headers": {},
  "ttl": 3600
}
```

**Response (201):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "job_id": "string",
    "status": "pending",
    "created_at": "timestamp"
  }
}
```

**Status Codes:** `201 Created`, `400 Bad Request`, `409 Conflict`

#### Get Job Status

```
GET /api/v1/jobs/{job_id}
```

**Description:** Get the status of an async job.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "job_id": "string",
    "status": "completed",
    "progress": 100,
    "result": {...},
    "created_at": "timestamp",
    "completed_at": "timestamp"
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

---

### Agent Gateway

**Base Path:** `/api/agent/v1`

#### Agent Chat

```
POST /api/agent/v1/chat
```

**Description:** Main agent-to-agent communication endpoint. Routes to skill handlers based on `intent`.

**Request Body:**
```json
{
  "agent_id": "agent_001",
  "message": "Please analyze the current model",
  "context": {},
  "intent": "analysis",
  "metadata": {},
  "timeout": 30
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "response": "Analysis complete...",
    "agent_id": "agent_001",
    "timestamp": 1716192000,
    "metadata": {}
  }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`, `429 Too Many Requests`, `504 Gateway Timeout`

#### Agent Chat SSE

```
POST /api/agent/v1/chat/sse
```

**Description:** Streaming version of agent chat via Server-Sent Events.

**Request Body:** Same as `/chat`

**Response:** `text/event-stream` with incremental tokens

#### Register Agent Skill

```
POST /api/agent/v1/skills/register
```

**Description:** Register a skill handler for a specific intent.

**Request Body:**
```json
{
  "skill_name": "analysis",
  "description": "Analyzes manufacturing models",
  "handler_url": "https://...",
  "supported_intents": ["analysis", "diagnosis"],
  "metadata": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "技能注册成功",
  "data": {
    "skill_name": "analysis",
    "registered_at": "timestamp"
  }
}
```

#### List Skills

```
GET /api/agent/v1/skills
```

**Description:** List all registered agent skills.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [
    {
      "skill_name": "analysis",
      "description": "...",
      "supported_intents": ["analysis"]
    }
  ]
}
```

#### Agent Health

```
GET /api/agent/v1/health
```

**Description:** Check agent gateway health.

**Response (200):**
```json
{
  "status": "ok",
  "skills_count": 5,
  "active_agents": 3,
  "uptime_seconds": 86400
}
```

---

### Agent State

**Base Path:** `/agents`

#### Get Agent State

```
GET /agents/{agent_id}
```

**Description:** Get an agent's current state.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "agent_id": "agent_001",
    "status": "working",
    "context": {},
    "version": 5
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Update Agent State

```
PUT /agents/{agent_id}
```

**Description:** Update an agent's state (with optimistic locking).

**Request Body:**
```json
{
  "status": "working",
  "context": {},
  "version": 5
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "Agent 状态更新成功",
  "data": {
    "agent_id": "agent_001",
    "version": 6
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`, `409 Conflict`

#### List Agent States

```
GET /agents
```

**Description:** List all agent states with filters.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status |
| `sort_by` | string | Sort field |
| `limit` | int | Max results |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "agents": [...],
    "total": 10
  }
}
```

---

### User Sovereignty

**Base Path:** `/api/v1/user-sovereignty`

#### List User Data

```
GET /api/v1/user-sovereignty/data
```

**Description:** List all data associated with a user (for data export).

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `user_id` | string | User ID |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "user_id": "string",
    "data_categories": [
      {"category": "predictions", "count": 50},
      {"category": "models", "count": 5}
    ],
    "total_size_bytes": 1048576
  }
}
```

#### Export User Data

```
POST /api/v1/user-sovereignty/export
```

**Description:** Export all user data as a downloadable archive.

**Request Body:**
```json
{
  "user_id": "string",
  "format": "json"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "数据导出已启动",
  "data": {
    "export_id": "string",
    "status": "processing"
  }
}
```

#### Delete User Data

```
DELETE /api/v1/user-sovereignty/data
```

**Description:** Delete all user data (GDPR right to be forgotten).

**Request Body:**
```json
{
  "user_id": "string",
  "confirmation": "DELETE_ALL_DATA"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "用户数据删除完成"
}
```

---

### Skills

**Base Path:** `/api/v1/skills`

#### Create Skill

```
POST /api/v1/skills
```

**Description:** Create a new AI skill definition.

**Request Body:**
```json
{
  "name": "string",
  "description": "string",
  "category": "string",
  "config": {},
  "enabled": true
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "技能创建成功",
  "data": {
    "skill_id": "string",
    "name": "string",
    "status": "enabled"
  }
}
```

#### List Skills

```
GET /api/v1/skills
```

**Description:** List all skills with filters.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `category` | string | Filter by category |
| `enabled` | bool | Filter by enabled status |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [
    {
      "skill_id": "string",
      "name": "string",
      "category": "string",
      "enabled": true
    }
  ]
}
```

#### Get Skill

```
GET /api/v1/skills/{skill_id}
```

**Description:** Get a specific skill by ID.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "skill_id": "string",
    "name": "string",
    "description": "string",
    "config": {}
  }
}
```

#### Update Skill

```
PUT /api/v1/skills/{skill_id}
```

**Description:** Update a skill definition.

**Request Body:**
```json
{
  "name": "string (optional)",
  "description": "string (optional)",
  "config": {} (optional),
  "enabled": true (optional)
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "技能更新成功",
  "data": { ... }
}
```

#### Delete Skill

```
DELETE /api/v1/skills/{skill_id}
```

**Description:** Delete a skill.

**Response (200):**
```json
{
  "code": 0,
  "message": "技能删除成功"
}
```

#### Search Skills

```
GET /api/v1/skills/search
```

**Description:** Search skills by keyword.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `q` | string | Search query |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "results": [...],
    "total": 5
  }
}
```

#### Get Skill Statistics

```
GET /api/v1/skills/stats
```

**Description:** Get skill usage statistics.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "total_skills": 20,
    "enabled_skills": 15,
    "total_executions": 1000,
    "success_rate": 0.95
  }
}
```

---

### Plugins

**Base Path:** `/api/v1/plugins`

#### List Plugins

```
GET /api/v1/plugins
```

**Description:** List all installed plugins with status.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status (active/inactive) |
| `limit` | int | Max results (default 50) |
| `offset` | int | Offset for pagination |
| `category` | string | Filter by category |
| `keyword` | string | Search by name or description |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "plugins": [...],
    "total": 10
  }
}
```

#### Get Plugin

```
GET /api/v1/plugins/{plugin_id}
```

**Description:** Get plugin details by ID.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "plugin_id": "string",
    "name": "string",
    "version": "1.0.0",
    "status": "active",
    "config": {}
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Get Plugin Health

```
GET /api/v1/plugins/health
```

**Description:** Get health status of all plugins.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "total": 10,
    "healthy": 8,
    "unhealthy": 2,
    "details": [...]
  }
}
```

---

### Cost & Budget

**Base Path:** `/api/v1/cost-budget`

#### Get Budget Status

```
GET /api/v1/cost-budget/budget
```

**Description:** Get current budget usage and limits.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `project_id` | string | Filter by project |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "project_id": "string",
    "budget_limit": 1000.0,
    "budget_used": 450.0,
    "budget_remaining": 550.0,
    "usage_percentage": 45.0
  }
}
```

#### Set Budget

```
POST /api/v1/cost-budget/budget
```

**Description:** Set or update budget limits.

**Request Body:**
```json
{
  "project_id": "string",
  "budget_limit": 1000.0,
  "alert_threshold": 0.8
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "预算设置成功",
  "data": {
    "budget_id": "string",
    "budget_limit": 1000.0
  }
}
```

#### Log Cost

```
POST /api/v1/cost-budget/costs
```

**Description:** Log a cost entry.

**Request Body:**
```json
{
  "project_id": "string",
  "cost_type": "compute",
  "amount": 15.50,
  "description": "GPU computation",
  "metadata": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "费用记录成功",
  "data": {
    "cost_id": "string",
    "amount": 15.50
  }
}
```

#### Get Cost History

```
GET /api/v1/cost-budget/costs
```

**Description:** Get cost history with filters.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `project_id` | string | Filter by project |
| `cost_type` | string | Filter by type |
| `start_date` | string | Start date (ISO format) |
| `end_date` | string | End date (ISO format) |
| `limit` | int | Max results |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "costs": [...],
    "total": 50,
    "total_amount": 450.0
  }
}
```

#### Get Cost Statistics

```
GET /api/v1/cost-budget/stats
```

**Description:** Get aggregated cost statistics.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `project_id` | string | Filter by project |
| `group_by` | string | Group by (day/week/month/type) |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "total_cost": 1500.0,
    "average_daily_cost": 50.0,
    "cost_by_type": {
      "compute": 1000.0,
      "storage": 500.0
    }
  }
}
```

---

### Goal Alignment

**Base Path:** `/api/v1/goal-alignment`

#### Create Goal

```
POST /api/v1/goal-alignment/goals
```

**Description:** Create a new goal.

**Request Body:**
```json
{
  "name": "Optimize cutting parameters",
  "description": "string",
  "target_metrics": {
    "surface_roughness": 0.8
  },
  "priority": "high"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "目标创建成功",
  "data": {
    "goal_id": "string",
    "name": "string",
    "status": "active"
  }
}
```

#### List Goals

```
GET /api/v1/goal-alignment/goals
```

**Description:** List goals with filters.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status |
| `priority` | string | Filter by priority |
| `limit` | int | Max results |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "goals": [...],
    "total": 10
  }
}
```

#### Get Goal

```
GET /api/v1/goal-alignment/goals/{goal_id}
```

**Description:** Get a specific goal.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "goal_id": "string",
    "name": "string",
    "target_metrics": {},
    "current_metrics": {},
    "progress": 0.75
  }
}
```

#### Update Goal

```
PUT /api/v1/goal-alignment/goals/{goal_id}
```

**Description:** Update a goal.

**Request Body:**
```json
{
  "name": "string (optional)",
  "target_metrics": {} (optional),
  "priority": "string (optional)"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "目标更新成功",
  "data": { ... }
}
```

#### Delete Goal

```
DELETE /api/v1/goal-alignment/goals/{goal_id}
```

**Description:** Delete a goal.

**Response (200):**
```json
{
  "code": 0,
  "message": "目标删除成功"
}
```

#### Align Goal

```
POST /api/v1/goal-alignment/align
```

**Description:** Submit a plan for goal alignment review.

**Request Body:**
```json
{
  "goal_id": "string",
  "proposed_actions": [
    {"action": "adjust cutting speed", "expected_impact": "..."}
  ]
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "目标对齐审查已提交",
  "data": {
    "alignment_id": "string",
    "status": "pending"
  }
}
```

#### Get Alignment Status

```
GET /api/v1/goal-alignment/alignments/{alignment_id}
```

**Description:** Get the status of a goal alignment review.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "alignment_id": "string",
    "status": "approved",
    "review_notes": "..."
  }
}
```

#### Batch Get Goals

```
POST /api/v1/goal-alignment/goals/batch
```

**Description:** Get multiple goals by IDs.

**Request Body:**
```json
{
  "goal_ids": ["goal_1", "goal_2"]
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "goals": [...],
    "total": 2
  }
}
```

---

### Governance

**Base Path:** `/api/v1/governance`

#### Submit for Approval

```
POST /api/v1/governance/approvals/submit
```

**Description:** Submit an action for governance approval.

**Request Body:**
```json
{
  "action_type": "model_deployment",
  "resource_id": "string",
  "requester_id": "string",
  "justification": "Deploying updated model v2.0",
  "metadata": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "审批请求已提交",
  "data": {
    "approval_id": "string",
    "status": "pending",
    "submitted_at": "timestamp"
  }
}
```

#### Review Approval

```
POST /api/v1/governance/approvals/{approval_id}/review
```

**Description:** Review an approval request (approve/reject).

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `approval_id` | string | Approval ID |

**Request Body:**
```json
{
  "decision": "approved",
  "reviewer_id": "string",
  "comments": "Approved for production"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "审批已处理",
  "data": {
    "approval_id": "string",
    "status": "approved",
    "reviewed_at": "timestamp"
  }
}
```

#### List Approvals

```
GET /api/v1/governance/approvals
```

**Description:** List approval requests with filters.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status |
| `action_type` | string | Filter by action type |
| `limit` | int | Max results |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "approvals": [...],
    "total": 10
  }
}
```

#### Get Approval

```
GET /api/v1/governance/approvals/{approval_id}
```

**Description:** Get a specific approval request.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "approval_id": "string",
    "action_type": "model_deployment",
    "status": "pending",
    "requester_id": "string",
    "justification": "..."
  }
}
```

---

### Heartbeat

**Base Path:** `/api/v1/heartbeat`

#### Send Heartbeat

```
POST /api/v1/heartbeat
```

**Description:** Send an agent heartbeat to indicate activity.

**Request Body:**
```json
{
  "agent_id": "agent_001",
  "status": "working",
  "metadata": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "agent_id": "agent_001",
    "last_heartbeat": "timestamp"
  }
}
```

---

### Task Checkout

**Base Path:** `/api/v1/task-checkout`

#### Checkout Task

```
POST /api/v1/task-checkout
```

**Description:** Checkout a task for exclusive editing (optimistic locking).

**Request Body:**
```json
{
  "task_id": "string",
  "agent_id": "string",
  "expected_version": 5
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "任务检出成功",
  "data": {
    "checkout_id": "string",
    "task_id": "string",
    "version": 6,
    "expires_at": "timestamp"
  }
}
```

**Status Codes:** `200 OK`, `409 Conflict`

#### Checkin Task

```
POST /api/v1/task-checkout/{checkout_id}/checkin
```

**Description:** Check in a task after editing.

**Request Body:**
```json
{
  "updates": {},
  "agent_id": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "任务检入成功",
  "data": {
    "task_id": "string",
    "version": 7
  }
}
```

#### Release Checkout

```
POST /api/v1/task-checkout/{checkout_id}/release
```

**Description:** Release a task checkout without changes.

**Response (200):**
```json
{
  "code": 0,
  "message": "任务检出已释放"
}
```

---

### Templates

#### Pattern Engine

**Base Path:** `/api/v1/templates/patterns`

##### List Patterns

```
GET /api/v1/templates/patterns
```

**Description:** List all discovered patterns.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `pattern_type` | string | Filter by type |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### List Anti-Patterns

```
GET /api/v1/templates/patterns/anti_patterns
```

**Description:** List all detected anti-patterns.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### Record Execution

```
POST /api/v1/templates/patterns/record
```

**Description:** Record a task execution for pattern analysis.

**Request Body:**
```json
{
  "task_id": "string",
  "branch_id": "string",
  "elements": {},
  "conditions": {},
  "metrics": {},
  "success": true
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "task_id": "string"
  }
}
```

##### Analyze Patterns

```
POST /api/v1/templates/patterns/analyze
```

**Description:** Run pattern analysis on accumulated execution data.

**Request Body:**
```json
{
  "min_samples": 10
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "new_patterns": 3,
    "patterns": [...]
  }
}
```

##### Get Pattern

```
GET /api/v1/templates/patterns/{pattern_id}
```

**Description:** Get details of a specific pattern.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Get Pattern Suggestions

```
GET /api/v1/templates/patterns/{pattern_id}/suggestions
```

**Description:** Get auto-generated suggestions from a pattern.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

#### A/B Testing

**Base Path:** `/api/v1/templates/ab_tests`

##### Create Experiment

```
POST /api/v1/templates/ab_tests
```

**Description:** Create a new A/B experiment.

**Request Body:**
```json
{
  "name": "Speed vs Quality Test",
  "control_branch": "main",
  "candidate_branch": "experiment_v2",
  "traffic_split": 0.10
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Record Execution

```
POST /api/v1/templates/ab_tests/record
```

**Description:** Record an execution in an experiment.

**Request Body:**
```json
{
  "experiment_id": "string",
  "branch": "control",
  "execution_time": 5.2,
  "success": true,
  "resource_cost": 0.5
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "recorded": true
  }
}
```

##### Assign Branch

```
POST /api/v1/templates/ab_tests/assign
```

**Description:** Assign a project to a branch in all active experiments.

**Request Body:**
```json
{
  "project_id": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "exp_001": "control",
    "exp_002": "candidate"
  }
}
```

##### List Experiments

```
GET /api/v1/templates/ab_tests
```

**Description:** List experiments.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### Get Experiment

```
GET /api/v1/templates/ab_tests/{experiment_id}
```

**Description:** Get experiment details.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Evaluate Experiment

```
POST /api/v1/templates/ab_tests/{experiment_id}/evaluate
```

**Description:** Evaluate an experiment's results.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Conclude Experiment

```
POST /api/v1/templates/ab_tests/{experiment_id}/conclude
```

**Description:** Auto-conclude an experiment (merge or rollback).

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

#### Template Branching

**Base Path:** `/api/v1/templates/branches`

##### Create Branch

```
POST /api/v1/templates/branches/
```

**Description:** Create a new template branch.

**Request Body:**
```json
{
  "name": "feature_v2",
  "base_branch": "main",
  "data": {},
  "metadata": {}
}
```

**Response (201):**
```json
{
  "branch": { ... }
}
```

##### List Branches

```
GET /api/v1/templates/branches/
```

**Description:** List all branches.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `type_filter` | string | Filter by type |

**Response (200):**
```json
{
  "branches": [...]
}
```

##### Get Branch

```
GET /api/v1/templates/branches/{branch_id}
```

**Description:** Get a specific branch.

**Response (200):**
```json
{
  "branch": { ... }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

##### Get Commit Log

```
GET /api/v1/templates/branches/{branch_id}/log
```

**Description:** Get the commit log for a branch.

**Response (200):**
```json
{
  "commit_log": [...]
}
```

##### Merge Branch

```
POST /api/v1/templates/branches/merge
```

**Description:** Merge one branch into another.

**Request Body:**
```json
{
  "source_id": "branch_1",
  "target_id": "main",
  "strategy": "overwrite"
}
```

**Response (200):**
```json
{
  "merged_branch": { ... }
}
```

##### Update Branch

```
PUT /api/v1/templates/branches/{branch_id}
```

**Description:** Update branch data.

**Request Body:**
```json
{
  "data": {}
}
```

**Response (200):**
```json
{
  "branch": { ... }
}
```

##### Delete Branch

```
DELETE /api/v1/templates/branches/{branch_id}
```

**Description:** Delete a branch.

**Response (200):**
```json
{
  "message": "Branch deleted"
}
```

**Status Codes:** `200 OK`, `403 Forbidden`, `404 Not Found`

#### Template Evolution

**Base Path:** `/api/v1/templates/evolution`

##### List Suggestions

```
GET /api/v1/templates/evolution/suggestions
```

**Description:** List evolution suggestions.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status_filter` | string | Filter by status |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### Create Suggestion

```
POST /api/v1/templates/evolution/suggestions
```

**Description:** Create a new evolution suggestion.

**Request Body:**
```json
{
  "trigger_type": "performance_degradation",
  "evidence": {},
  "proposed_change": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Apply Suggestion

```
POST /api/v1/templates/evolution/suggestions/apply
```

**Description:** Apply an evolution suggestion to a branch.

**Request Body:**
```json
{
  "suggestion_id": "string",
  "branch_id": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Update Metrics

```
POST /api/v1/templates/evolution/metrics
```

**Description:** Update metrics for trigger evaluation.

**Request Body:**
```json
{
  "metrics": {
    "accuracy": 0.95,
    "latency_ms": 120
  }
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "updated": 2
  }
}
```

##### Evaluate Triggers

```
POST /api/v1/templates/evolution/triggers/evaluate
```

**Description:** Evaluate all evolution triggers.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "new_suggestions": 1,
    "suggestions": [...]
  }
}
```

##### Get History

```
GET /api/v1/templates/evolution/history
```

**Description:** Get evolution history.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `branch_id` | string | Filter by branch |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

#### Template Marketplace

**Base Path:** `/api/v1/template_market`

##### Get Trending

```
GET /api/v1/template_market/trending
```

**Description:** Get trending templates based on adoption rate.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### Get Template Metrics

```
GET /api/v1/template_market/templates/{branch_id}/metrics
```

**Description:** Get effectiveness metrics for a template.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "branch_id": "string",
    "name": "string",
    "success_rate": 0.95,
    "total_experiments": 10,
    "adoption_count": 50,
    "last_updated": "timestamp"
  }
}
```

##### Publish Template

```
POST /api/v1/template_market/publish
```

**Description:** Publish a validated template to the marketplace.

**Request Body:**
```json
{
  "branch_id": "string",
  "name": "string",
  "category": "general",
  "description": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Subscribe

```
POST /api/v1/template_market/subscribe
```

**Description:** Subscribe to template category updates.

**Request Body:**
```json
{
  "category": "machining",
  "project_id": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Get Subscriptions

```
GET /api/v1/template_market/subscriptions/{project_id}
```

**Description:** Get subscriptions for a project.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### Export Template

```
POST /api/v1/template_market/export/{branch_id}
```

**Description:** Export a template with optional evolution history.

**Request Body:**
```json
{
  "branch_id": "string",
  "include_history": true
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Import Template

```
POST /api/v1/template_market/import
```

**Description:** Import a template with optional parameter adaptation.

**Request Body:**
```json
{
  "template_data": {},
  "target_branch": "string",
  "adapt_params": true
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "branch_id": "string",
    "name": "string"
  }
}
```

##### Sync Changes

```
GET /api/v1/template_market/sync/{branch_id}
```

**Description:** Get incremental changes for a branch (delta sync).

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "branch_id": "string",
    "content_hash": "string",
    "updated_at": "timestamp",
    "changes": [...]
  }
}
```

#### Template Updates

**Base Path:** `/api/v1/templates/updates`

##### Get Notifications

```
GET /api/v1/templates/updates/{project_id}
```

**Description:** Get update notifications for a project.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `status` | string | Filter by status |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": [...]
}
```

##### Scan for Updates

```
POST /api/v1/templates/updates/scan
```

**Description:** Scan for applicable updates for a project.

**Request Body:**
```json
{
  "project_id": "string",
  "suggestions": [...]
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "new_notifications": 2,
    "notifications": [...]
  }
}
```

##### Apply Update

```
POST /api/v1/templates/updates/apply/{notification_id}
```

**Description:** Apply an update notification.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

##### Dismiss Notification

```
POST /api/v1/templates/updates/dismiss/{notification_id}
```

**Description:** Dismiss an update notification.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "dismissed": true
  }
}
```

##### Preview Update

```
GET /api/v1/templates/updates/preview/{notification_id}
```

**Description:** Preview an update notification.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

---

### RAG

**Base Path:** `/api/rag`

#### Query Knowledge Base

```
POST /api/rag/query
```

**Description:** Query the RAG knowledge base.

**Request Body:**
```json
{
  "query": "How to optimize cutting speed?",
  "top_k": 5,
  "filters": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "results": [
      {
        "content": "...",
        "score": 0.92,
        "source": "doc_001"
      }
    ],
    "query": "string"
  }
}
```

#### Query Knowledge Base (GET)

```
GET /api/rag/query
```

**Description:** Query via GET request.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Search query |
| `top_k` | int | Number of results (default 5) |

**Response (200):** Same as POST

#### List Knowledge Collections

```
GET /api/rag/collections
```

**Description:** List all knowledge collections.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "collections": [
      {
        "name": "manufacturing_guides",
        "document_count": 50,
        "last_updated": "timestamp"
      }
    ],
    "total": 3
  }
}
```

#### Query Knowledge Collection

```
GET /api/rag/collections/{collection_name}/query
```

**Description:** Query a specific knowledge collection.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `query` | string | Search query |
| `top_k` | int | Number of results (default 5) |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "collection": "manufacturing_guides",
    "results": [...],
    "total": 5
  }
}
```

---

### Ollama

**Base Path:** `/api/ollama`

#### Chat

```
POST /api/ollama/chat
```

**Description:** Send a chat message to the Ollama model.

**Request Body:**
```json
{
  "message": "Explain the machining process",
  "stream": false,
  "model": "llama3"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "response": "The machining process involves...",
    "model": "llama3",
    "done": true
  }
}
```

#### Chat Stream

```
POST /api/ollama/chat/stream
```

**Description:** Stream a chat response from Ollama via SSE.

**Request Body:**
```json
{
  "message": "Explain the machining process",
  "stream": true
}
```

**Response:** `text/event-stream`

#### Health Check

```
GET /api/ollama/health
```

**Description:** Check if Ollama service is available.

**Response (200):**
```json
{
  "code": 0,
  "message": "Ollama 服务正常",
  "data": {
    "ollama_available": true
  }
}
```

---

### Simulation

**Base Path:** `/api/simulation`

#### Start Simulation

```
POST /api/simulation/start
```

**Description:** Start a new simulation job.

**Request Body:**
```json
{
  "toolpaths": [...],
  "workpiece": {},
  "simulation_params": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "仿真任务已启动",
  "data": {
    "job_id": "string",
    "status": "queued"
  }
}
```

#### Check Simulation Status

```
GET /api/simulation/status
```

**Description:** Check the status of a simulation job.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `job_id` | string | Job ID |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "job_id": "string",
    "status": "running",
    "progress": 0.65
  }
}
```

#### Get Simulation Result

```
GET /api/simulation/result
```

**Description:** Get the result of a completed simulation.

**Query Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `job_id` | string | Job ID |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "job_id": "string",
    "status": "completed",
    "result": { ... }
  }
}
```

---

### Projects

**Base Path:** `/api/projects`

#### Create Project

```
POST /api/projects/new
```

**Description:** Create a new blank project.

**Request Body:**
```json
{
  "name": "未命名工程",
  "author": "string",
  "description": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "工程 \"name\" 创建成功",
  "data": {
    "project_id": "proj_xxx",
    "manifest": { ... },
    "version": "1.0"
  }
}
```

#### Open Project

```
POST /api/projects/open
```

**Description:** Open a `.ljm` project file (by path or Base64 upload).

**Request Body:**
```json
{
  "file_path": "/path/to/project.ljm",
  "upload_data": "base64_encoded_data"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "工程 \"name\" 打开成功",
  "data": {
    "manifest": { ... },
    "file_path": "/path/to/project.ljm",
    "version": "1.0"
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Save Project

```
POST /api/projects/save
```

**Description:** Save a project as a `.ljm` file.

**Request Body:**
```json
{
  "manifest": { ... },
  "project_id": "proj_xxx",
  "output_name": "project.ljm"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "工程保存成功",
  "data": {
    "project_id": "proj_xxx",
    "file_path": "/path/to/project.ljm",
    "file_name": "project.ljm",
    "file_size": 102400,
    "version": "1.0"
  }
}
```

#### Save As Project

```
POST /api/projects/save-as
```

**Description:** Save a project as a new `.ljm` file.

**Request Body:**
```json
{
  "manifest": { ... },
  "output_name": "project_copy.ljm"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "工程另存为 \"project_copy.ljm\" 成功",
  "data": {
    "file_path": "/path/to/project_copy.ljm",
    "file_name": "project_copy.ljm",
    "file_size": 102400,
    "version": "1.0"
  }
}
```

#### List Projects

```
GET /api/projects/list
```

**Description:** List all project files.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "total": 10,
    "items": [...]
  }
}
```

#### Delete Project

```
DELETE /api/projects/{project_name}
```

**Description:** Delete a project file.

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `project_name` | string | Project filename (with .ljm extension) |

**Response (200):**
```json
{
  "code": 0,
  "message": "工程 project.ljm 已删除"
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Download Project

```
GET /api/projects/download/{project_name}
```

**Description:** Download a project file.

**Response:** `application/zip` file stream

**Status Codes:** `200 OK`, `404 Not Found`

#### Upload Resource

```
POST /api/projects/upload-resource
```

**Description:** Upload a resource file to the temp directory.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `resource_type` | string | model | Resource type (drawing/model/toolpath/simulation/postprocessor/extension) |

**Request Body:** Multipart form with file

**Response (200):**
```json
{
  "code": 0,
  "message": "资源上传成功",
  "data": {
    "resource_id": "res_xxx",
    "temp_path": "/path/to/file",
    "file_name": "model.step",
    "file_size": 102400,
    "resource_type": "model"
  }
}
```

---

### STEP Import

**Base Path:** `/api/import/step`

#### Import STEP File

```
POST /api/import/step
POST /api/import/step/
```

**Description:** Upload a STEP file for parsing and format conversion (STL/BREP).

**Form Data:**

| Field | Type | Default | Description |
|---|---|---|---|
| `file` | file | Required | STEP file (.step/.stp), max 50MB |
| `output_format` | string | stl | Output format (stl/brep) |
| `precision` | string | medium | Precision level (low/medium/high) |
| `use_cache` | bool | true | Enable caching |

**Response (200):**
```json
{
  "code": 0,
  "message": "STEP文件导入成功",
  "data": {
    "file_name": "model.step",
    "file_size": 1024000,
    "parse_time_ms": 250.5,
    "conversion_time_ms": 180.3,
    "model_info": {
      "volume": 0.001,
      "surface_area": 0.5,
      "bounding_box": {
        "length": 100.0,
        "width": 50.0,
        "height": 30.0,
        "min_point": [0, 0, 0],
        "max_point": [100, 50, 30]
      },
      "center_of_mass": {"x": 50, "y": 25, "z": 15},
      "entity_count": 5,
      "face_count": 120,
      "vertex_count": 5000,
      "edge_count": 300,
      "shell_count": 5,
      "solid_count": 5
    },
    "entities": [...],
    "is_assembly": true,
    "stl_files": [
      {
        "file_name": "entity_1.stl",
        "stl_url": "/api/import/step/output/entity_1.stl",
        "format": "stl",
        "face_count": 100,
        "vertex_count": 3000
      }
    ],
    "brep_files": [],
    "status": {
      "success": true,
      "message": "解析和转换完成",
      "entity_count": 5,
      "face_count": 120,
      "vertex_count": 5000,
      "errors": []
    },
    "warnings": [],
    "cached": false,
    "import_id": "abc123",
    "format": "stl"
  }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `413 Payload Too Large`, `500 Internal Server Error`

#### Get Output File

```
GET /api/import/step/output/{file_name}
```

**Description:** Download a converted output file (STL/BREP).

**Response:** File stream (`application/sla` for STL, `application/octet-stream` for BREP)

**Status Codes:** `200 OK`, `404 Not Found`

#### Get Cache Stats

```
GET /api/import/step/cache/stats
```

**Description:** Get STEP parsing cache statistics.

**Response (200):**
```json
{
  "code": 0,
  "message": "缓存统计获取成功",
  "data": {
    "hits": 50,
    "misses": 10,
    "hit_rate": 0.83,
    "size": 20,
    "max_size": 100
  }
}
```

#### Clear Cache

```
DELETE /api/import/step/cache
```

**Description:** Clear the STEP parsing cache.

**Response (200):**
```json
{
  "code": 0,
  "message": "缓存已清空，移除 20 个条目",
  "data": {
    "cleared_entries": 20
  }
}
```

#### Get Import History

```
GET /api/import/step/history
```

**Description:** Get STEP import history.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `limit` | int | 20 | Number of records (1-100) |

**Response (200):**
```json
{
  "code": 0,
  "message": "导入历史获取成功",
  "data": {
    "history": [...],
    "total": 20
  }
}
```

#### Delete Import File

```
DELETE /api/import/step/history/{file_name}
```

**Description:** Delete an imported file.

**Response (200):**
```json
{
  "code": 0,
  "message": "文件 model.stl 已删除"
}
```

**Status Codes:** `200 OK`, `404 Not Found`

---

### Process Rules

**Base Path:** `/api/rules`

#### Create Rule

```
POST /api/rules/create
```

**Description:** Create a new process rule.

**Request Body:**
```json
{
  "name": "Speed Limit Rule",
  "description": "Limit cutting speed for hardened steel",
  "group_id": 1,
  "conditions": [
    {
      "parameter": "cutting_speed",
      "operator": ">",
      "value": "200",
      "unit": "m/min"
    }
  ],
  "logic_operator": "AND",
  "result": {
    "parameter": "cutting_speed",
    "operator": "<=",
    "value": "200",
    "unit": "m/min"
  },
  "status": "active",
  "priority": 10
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "规则创建成功",
  "data": {
    "id": 1,
    "name": "Speed Limit Rule",
    "conditions": [...],
    "result": {...},
    "status": "active",
    "preview_text": "IF cutting_speed > 200 m/min THEN cutting_speed <= 200 m/min",
    "warnings": []
  }
}
```

#### List Rules

```
GET /api/rules/list
```

**Description:** List process rules with pagination and filters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `group_id` | int | | Filter by group |
| `status` | string | | Filter by status (active/inactive/draft) |
| `keyword` | string | | Search keyword |
| `sort_by` | string | updated_at | Sort field |
| `sort_order` | string | DESC | Sort direction |
| `page` | int | 1 | Page number |
| `page_size` | int | 20 | Items per page (1-100) |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "rules": [...],
    "total": 100,
    "page": 1,
    "page_size": 20,
    "total_pages": 5
  }
}
```

#### Get Rule

```
GET /api/rules/detail/{rule_id}
```

**Description:** Get a specific rule by ID.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "id": 1,
    "name": "Speed Limit Rule",
    "conditions": [...],
    "result": {...},
    "status": "active",
    "preview_text": "..."
  }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Update Rule

```
PUT /api/rules/update/{rule_id}
```

**Description:** Update a process rule.

**Path Parameters:**

| Parameter | Type | Description |
|---|---|---|
| `rule_id` | int | Rule ID |

**Request Body:** (all fields optional)
```json
{
  "name": "string",
  "description": "string",
  "group_id": 1,
  "conditions": [...],
  "logic_operator": "AND",
  "result": {...},
  "status": "active",
  "priority": 10
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "规则更新成功",
  "data": { ... }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Delete Rule

```
DELETE /api/rules/delete/{rule_id}
```

**Description:** Delete a process rule.

**Response (200):**
```json
{
  "code": 0,
  "message": "规则删除成功"
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### List Groups

```
GET /api/rules/groups/list
```

**Description:** List all rule groups.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "groups": [
      {
        "id": 1,
        "name": "Cutting Parameters",
        "description": "...",
        "rule_count": 10
      }
    ],
    "total": 3
  }
}
```

#### Create Group

```
POST /api/rules/groups/create
```

**Description:** Create a new rule group.

**Request Body:**
```json
{
  "name": "Cooling Parameters",
  "description": "Rules for coolant settings"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "分组创建成功",
  "data": {
    "id": 2,
    "name": "Cooling Parameters",
    "rule_count": 0
  }
}
```

#### Update Group

```
PUT /api/rules/groups/update/{group_id}
```

**Description:** Update a rule group.

**Request Body:**
```json
{
  "name": "string",
  "description": "string"
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "分组更新成功",
  "data": { ... }
}
```

**Status Codes:** `200 OK`, `404 Not Found`

#### Delete Group

```
DELETE /api/rules/groups/delete/{group_id}
```

**Description:** Delete a rule group (must be empty).

**Response (200):**
```json
{
  "code": 0,
  "message": "分组删除成功"
}
```

**Status Codes:** `200 OK`, `400 Bad Request` (if group has rules), `404 Not Found`

#### Import Rules

```
POST /api/rules/import
```

**Description:** Import rules from a JSON file.

**Request Body:** Multipart form with JSON file

**Response (200):**
```json
{
  "code": 0,
  "message": "导入成功: 10 条规则, 2 个分组",
  "data": {
    "imported_rules": 10,
    "imported_groups": 2
  }
}
```

#### Export Rules

```
GET /api/rules/export
```

**Description:** Export all rules as a JSON file.

**Response:** `application/json` file download

#### Backup Database

```
POST /api/rules/backup
```

**Description:** Backup the rules database.

**Response (200):**
```json
{
  "code": 0,
  "message": "数据库备份成功",
  "data": {
    "backup_path": "/path/to/backup.db"
  }
}
```

#### Get Stats

```
GET /api/rules/stats
```

**Description:** Get rule statistics.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "total_rules": 100,
    "active_rules": 80,
    "inactive_rules": 10,
    "draft_rules": 10,
    "total_groups": 5
  }
}
```

#### Preview Rule Text

```
GET /api/rules/preview
```

**Description:** Preview a rule in human-readable text format.

**Query Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `conditions` | string | Required | JSON array of conditions |
| `logic_operator` | string | AND | Logic operator (AND/OR) |
| `result` | string | Required | JSON object of result |

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "preview_text": "IF cutting_speed > 200 m/min THEN cutting_speed <= 200 m/min"
  }
}
```

---

## SSE (Server-Sent Events)

**Base Path:** `/api/v1/sse`

#### Verify Connection

```
GET /api/v1/sse/verify
```

**Description:** Verify SSE connection with server.

**Response:** `text/event-stream` with `connected` event

#### Create Task

```
POST /api/v1/sse/tasks
```

**Description:** Create an SSE task for streaming events.

**Request Body:**
```json
{
  "task_id": "string",
  "task_type": "simulation",
  "metadata": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "SSE任务创建成功",
  "data": {
    "task_id": "string",
    "status": "created"
  }
}
```

#### Connect to SSE Stream

```
GET /api/v1/sse/connect/{task_id}
```

**Description:** Connect to the SSE stream for a specific task.

**Response:** `text/event-stream`

#### Get Task Status

```
GET /api/v1/sse/tasks/{task_id}
```

**Description:** Get the status of an SSE task.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "task_id": "string",
    "status": "completed",
    "created_at": "timestamp"
  }
}
```

#### List SSE Tasks

```
GET /api/v1/sse/tasks
```

**Description:** List all SSE tasks.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "tasks": [...],
    "total": 10
  }
}
```

#### Send SSE Event

```
POST /api/v1/sse/send/{task_id}
```

**Description:** Send an event to an SSE task stream.

**Request Body:**
```json
{
  "event_type": "progress",
  "data": {"progress": 0.5}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "事件发送成功"
}
```

#### Delete SSE Task

```
DELETE /api/v1/sse/tasks/{task_id}
```

**Description:** Delete an SSE task.

**Response (200):**
```json
{
  "code": 0,
  "message": "SSE任务删除成功"
}
```

---

## Additional Routes

### DXF Processing

**Base Path:** `/api/dxf`

#### Upload DXF

```
POST /api/dxf/upload
```

**Description:** Upload and process a DXF file.

**Request Body:** Multipart form with DXF file

**Response (200):**
```json
{
  "code": 0,
  "message": "DXF文件处理成功",
  "data": {
    "entities": [...],
    "bounding_box": {...}
  }
}
```

#### Get DXF Info

```
GET /api/dxf/info/{file_id}
```

**Description:** Get information about a processed DXF file.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

### Process Planning

**Base Path:** `/api/process`

#### Generate Process Plan

```
POST /api/process/generate
```

**Description:** Generate a process plan from CAD data.

**Request Body:**
```json
{
  "model_data": {},
  "constraints": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "工艺规划生成成功",
  "data": {
    "plan_id": "string",
    "operations": [...]
  }
}
```

### AI Agents

**Base Path:** `/api/agents`

#### List Agents

```
GET /api/agents
```

**Description:** List all registered AI agents.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "agents": [...],
    "total": 5
  }
}
```

#### Get Agent

```
GET /api/agents/{agent_id}
```

**Description:** Get a specific AI agent.

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": { ... }
}
```

### AI Chat

**Base Path:** `/api/ai`

#### Chat

```
POST /api/ai/chat
```

**Description:** Send a chat message to the AI assistant.

**Request Body:**
```json
{
  "message": "What's the best cutting speed for aluminum?",
  "context": {}
}
```

**Response (200):**
```json
{
  "code": 0,
  "message": "OK",
  "data": {
    "response": "For aluminum, the recommended cutting speed is...",
    "timestamp": 1716192000
  }
}
```

---

## Appendix

### Resource Type Enum (Project Upload)

| Value | Description |
|---|---|
| `drawing` | Engineering drawing |
| `model` | 3D model |
| `toolpath` | CNC toolpath |
| `simulation` | Simulation result |
| `postprocessor` | Postprocessor config |
| `extension` | Extension file |

### Rule Status Enum

| Value | Description |
|---|---|
| `active` | Rule is active |
| `inactive` | Rule is inactive |
| `draft` | Rule is in draft |

### Rule Operators

| Operator | Description |
|---|---|
| `=` | Equal |
| `<` | Less than |
| `>` | Greater than |
| `<=` | Less than or equal |
| `>=` | Greater than or equal |
| `!=` | Not equal |

### Rule Logic Operators

| Value | Description |
|---|---|
| `AND` | All conditions must match |
| `OR` | Any condition can match |

### STEP File Constraints

| Constraint | Value |
|---|---|
| Max file size | 50 MB |
| Allowed extensions | `.step`, `.stp` |
| Supported formats | AP203, AP214, AP242 |
| Output formats | STL, BREP |
| Precision levels | `low`, `medium`, `high` |
---

## API 路由补全（自动同步）

> 本节由 `scripts/sync_api_docs.py` 根据 `api-sync-report.json` 自动生成。
>
> 用于将 `docs/API.md` 与 `python/app/**` 中的实际 FastAPI 路由保持同步。
>
> **补全状态**: 208 个缺失路由 / 67 个需复核

### 模块索引

1. [Agent Gateway](#agent-gateway) — 13 个路由
2. [Agent State](#agent-state) — 16 个路由
3. [Async Jobs](#async-jobs) — 4 个路由
4. [Authentication](#authentication) — 3 个路由
5. [Base Routes](#base-routes) — 6 个路由
6. [Cost & Budget](#cost-and-budget) — 20 个路由
7. [Goal Alignment](#goal-alignment) — 13 个路由
8. [Governance](#governance) — 17 个路由
9. [Heartbeat](#heartbeat) — 12 个路由
10. [LNN Models](#lnn-models) — 20 个路由
11. [Ollama](#ollama) — 2 个路由
12. [Plugins](#plugins) — 13 个路由
13. [RAG](#rag) — 13 个路由
14. [Simulation](#simulation) — 7 个路由
15. [Skills](#skills) — 13 个路由
16. [Task Checkout](#task-checkout) — 15 个路由
17. [User Management](#user-management) — 4 个路由
18. [User Sovereignty](#user-sovereignty) — 8 个路由
19. [Wear Prediction](#wear-prediction) — 9 个路由

### Agent Gateway (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 13 条。

#### GET /api/agent/v1/audit-log

```
GET /api/agent/v1/audit-log
```

**Description:** get audit log.

**Handler:** `get_audit_log` (`agent_gateway.py:458`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/agent/v1/execute

```
POST /api/agent/v1/execute
```

**Description:** agent execute.

**Handler:** `agent_execute` (`agent_gateway.py:420`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/agent/v1/models

```
GET /api/agent/v1/models
```

**Description:** list models.

**Handler:** `list_models` (`agent_gateway.py:57`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/agent/v1/models/{name}/info

```
GET /api/agent/v1/models/{name}/info
```

**Description:** model info.

**Handler:** `model_info` (`agent_gateway.py:78`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/agent/v1/predict

```
POST /api/agent/v1/predict
```

**Description:** agent predict.

**Handler:** `agent_predict` (`agent_gateway.py:100`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/agent/v1/tokens

```
GET /api/agent/v1/tokens
```

**Description:** list agent tokens.

**Handler:** `list_agent_tokens` (`agent_gateway.py:523`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/agent/v1/tokens

```
POST /api/agent/v1/tokens
```

**Description:** create agent token.

**Handler:** `create_agent_token` (`agent_gateway.py:484`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/agent/v1/tokens/revoke-t-all

```
POST /api/agent/v1/tokens/revoke-t-all
```

**Description:** revoke all t tokens.

**Handler:** `revoke_all_t_tokens` (`agent_gateway.py:538`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/agent/v1/tokens/{agent_id}

```
DELETE /api/agent/v1/tokens/{agent_id}
```

**Description:** revoke agent token.

**Handler:** `revoke_agent_token` (`agent_gateway.py:530`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/agent/v1/train

```
POST /api/agent/v1/train
```

**Description:** agent train.

**Handler:** `agent_train` (`agent_gateway.py:314`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/agent/v1/train/{job_id}

```
GET /api/agent/v1/train/{job_id}
```

**Description:** get train status.

**Handler:** `get_train_status` (`agent_gateway.py:364`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/agent/v1/train/{job_id}/stream

```
GET /api/agent/v1/train/{job_id}/stream
```

**Description:** stream training.

**Handler:** `stream_training` (`agent_gateway.py:400`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/agents/info

```
GET /api/agents/info
```

**Description:** get agents info.

**Handler:** `get_agents_info` (`agents.py:866`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Agent State (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 16 条。

#### GET /agents/

```
GET /agents/
```

**Description:** list agents.

**Handler:** `list_agents` (`agent_state.py:105`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /agents/{agent_id}/checkpoints

```
GET /agents/{agent_id}/checkpoints
```

**Description:** list checkpoints.

**Handler:** `list_checkpoints` (`agent_state.py:207`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/checkpoints/cleanup

```
POST /agents/{agent_id}/checkpoints/cleanup
```

**Description:** cleanup checkpoints.

**Handler:** `cleanup_checkpoints` (`agent_state.py:246`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/checkpoints/rollback

```
POST /agents/{agent_id}/checkpoints/rollback
```

**Description:** rollback checkpoint.

**Handler:** `rollback_checkpoint` (`agent_state.py:221`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/checkpoints/save

```
POST /agents/{agent_id}/checkpoints/save
```

**Description:** save checkpoint.

**Handler:** `save_checkpoint` (`agent_state.py:183`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/clone

```
POST /agents/{agent_id}/clone
```

**Description:** clone agent.

**Handler:** `clone_agent` (`agent_state.py:317`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/context/update

```
POST /agents/{agent_id}/context/update
```

**Description:** update context.

**Handler:** `update_context` (`agent_state.py:257`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/heartbeat/start

```
POST /agents/{agent_id}/heartbeat/start
```

**Description:** start heartbeat.

**Handler:** `start_heartbeat` (`agent_state.py:161`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/heartbeat/stop

```
POST /agents/{agent_id}/heartbeat/stop
```

**Description:** stop heartbeat.

**Handler:** `stop_heartbeat` (`agent_state.py:172`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /agents/{agent_id}/history

```
GET /agents/{agent_id}/history
```

**Description:** get state history.

**Handler:** `get_state_history` (`agent_state.py:365`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/memory/add

```
POST /agents/{agent_id}/memory/add
```

**Description:** add memory.

**Handler:** `add_memory` (`agent_state.py:270`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/memory/prune

```
POST /agents/{agent_id}/memory/prune
```

**Description:** prune memory.

**Handler:** `prune_memory` (`agent_state.py:293`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/resume

```
POST /agents/{agent_id}/resume
```

**Description:** resume agent.

**Handler:** `resume_agent` (`agent_state.py:304`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/rollback

```
POST /agents/{agent_id}/rollback
```

**Description:** rollback state.

**Handler:** `rollback_state` (`agent_state.py:352`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/save

```
POST /agents/{agent_id}/save
```

**Description:** save agent state.

**Handler:** `save_agent_state` (`agent_state.py:131`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /agents/{agent_id}/snapshot

```
POST /agents/{agent_id}/snapshot
```

**Description:** create snapshot.

**Handler:** `create_snapshot` (`agent_state.py:339`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Async Jobs (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 4 条。

#### GET /api/v1/jobs/stats

```
GET /api/v1/jobs/stats
```

**Description:** get task stats.

**Handler:** `get_task_stats` (`jobs.py:181`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/jobs/{job_id}/cancel

```
POST /api/v1/jobs/{job_id}/cancel
```

**Description:** cancel job.

**Handler:** `cancel_job` (`jobs.py:99`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/jobs/{job_id}/progress

```
GET /api/v1/jobs/{job_id}/progress
```

**Description:** get job progress.

**Handler:** `get_job_progress` (`jobs.py:39`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/jobs/{job_id}/stream

```
GET /api/v1/jobs/{job_id}/stream
```

**Description:** stream job events.

**Handler:** `stream_job_events` (`jobs.py:59`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Authentication (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 3 条。

#### POST /api/v1/auth/logout

```
POST /api/v1/auth/logout
```

**Description:** logout.

**Handler:** `logout` (`auth.py:199`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/auth/me

```
GET /api/v1/auth/me
```

**Description:** get me.

**Handler:** `get_me` (`auth.py:214`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/auth/refresh

```
POST /api/v1/auth/refresh
```

**Description:** refresh token.

**Handler:** `refresh_token` (`auth.py:159`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Base Routes (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 6 条。

#### GET /api/metrics

```
GET /api/metrics
```

**Description:** get metrics.

**Handler:** `get_metrics` (`main.py:276`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/health/quick

```
GET /api/v1/health/quick
```

**Description:** quick health.

**Handler:** `quick_health` (`health.py:240`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/health/system

```
GET /api/v1/health/system
```

**Description:** system health.

**Handler:** `system_health` (`health.py:116`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/logs/stats

```
GET /api/v1/logs/stats
```

**Description:** get log stats.

**Handler:** `get_log_stats` (`main.py:286`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/logs/{buffer_type}

```
GET /api/v1/logs/{buffer_type}
```

**Description:** query logs.

**Handler:** `query_logs` (`main.py:296`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/version

```
GET /api/v1/version
```

**Description:** get version.

**Handler:** `get_version` (`main.py:281`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Cost & Budget (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 20 条。

#### POST /api/v1/cost-budget/adjust-budget

```
POST /api/v1/cost-budget/adjust-budget
```

**Description:** adjust budget.

**Handler:** `adjust_budget` (`cost_budget.py:144`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/adjustment-history

```
GET /api/v1/cost-budget/adjustment-history
```

**Description:** get adjustment history.

**Handler:** `get_adjustment_history` (`cost_budget.py:165`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/alerts

```
GET /api/v1/cost-budget/alerts
```

**Description:** get budget alerts.

**Handler:** `get_budget_alerts` (`cost_budget.py:255`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/alerts/read-all

```
POST /api/v1/cost-budget/alerts/read-all
```

**Description:** mark all alerts read.

**Handler:** `mark_all_alerts_read` (`cost_budget.py:274`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/v1/cost-budget/alerts/{alert_id}

```
DELETE /api/v1/cost-budget/alerts/{alert_id}
```

**Description:** delete alert.

**Handler:** `delete_alert` (`cost_budget.py:281`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/alerts/{alert_id}/read

```
POST /api/v1/cost-budget/alerts/{alert_id}/read
```

**Description:** mark alert read.

**Handler:** `mark_alert_read` (`cost_budget.py:267`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/check

```
POST /api/v1/cost-budget/check
```

**Description:** check budget.

**Handler:** `check_budget` (`cost_budget.py:172`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/check-cascade

```
POST /api/v1/cost-budget/check-cascade
```

**Description:** check budget cascade.

**Handler:** `check_budget_cascade` (`cost_budget.py:189`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/enforce

```
POST /api/v1/cost-budget/enforce
```

**Description:** enforce budget.

**Handler:** `enforce_budget` (`cost_budget.py:209`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/enforcement-log

```
GET /api/v1/cost-budget/enforcement-log
```

**Description:** get enforcement log.

**Handler:** `get_enforcement_log` (`cost_budget.py:298`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/policies

```
GET /api/v1/cost-budget/policies
```

**Description:** get budget policies.

**Handler:** `get_budget_policies` (`cost_budget.py:106`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/policies

```
POST /api/v1/cost-budget/policies
```

**Description:** set budget policy.

**Handler:** `set_budget_policy` (`cost_budget.py:119`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/reset

```
POST /api/v1/cost-budget/reset
```

**Description:** reset budget period.

**Handler:** `reset_budget_period` (`cost_budget.py:236`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/reset-log

```
GET /api/v1/cost-budget/reset-log
```

**Description:** get reset log.

**Handler:** `get_reset_log` (`cost_budget.py:305`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/suggestions

```
GET /api/v1/cost-budget/suggestions
```

**Description:** get optimization suggestions.

**Handler:** `get_optimization_suggestions` (`cost_budget.py:288`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/summary

```
GET /api/v1/cost-budget/summary
```

**Description:** get cost summary.

**Handler:** `get_cost_summary` (`cost_budget.py:28`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/task/{task_id}

```
GET /api/v1/cost-budget/task/{task_id}
```

**Description:** get task costs.

**Handler:** `get_task_costs` (`cost_budget.py:52`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/trend

```
GET /api/v1/cost-budget/trend
```

**Description:** get cost trend.

**Handler:** `get_cost_trend` (`cost_budget.py:67`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/cost-budget/unit-prices

```
GET /api/v1/cost-budget/unit-prices
```

**Description:** get unit prices.

**Handler:** `get_unit_prices` (`cost_budget.py:77`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/cost-budget/unit-prices

```
POST /api/v1/cost-budget/unit-prices
```

**Description:** set unit price.

**Handler:** `set_unit_price` (`cost_budget.py:83`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Goal Alignment (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 13 条。

#### GET /api/v1/goal-alignment/goals/tree

```
GET /api/v1/goal-alignment/goals/tree
```

**Description:** get goal tree.

**Handler:** `get_goal_tree` (`goal_alignment.py:97`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/goals/{goal_id}/chain

```
GET /api/v1/goal-alignment/goals/{goal_id}/chain
```

**Description:** get goal chain.

**Handler:** `get_goal_chain` (`goal_alignment.py:125`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/goals/{goal_id}/children

```
GET /api/v1/goal-alignment/goals/{goal_id}/children
```

**Description:** get goal children.

**Handler:** `get_goal_children` (`goal_alignment.py:132`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/goals/{goal_id}/history

```
GET /api/v1/goal-alignment/goals/{goal_id}/history
```

**Description:** get goal history.

**Handler:** `get_goal_history` (`goal_alignment.py:151`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/goals/{goal_id}/progress

```
GET /api/v1/goal-alignment/goals/{goal_id}/progress
```

**Description:** get goal progress.

**Handler:** `get_goal_progress` (`goal_alignment.py:142`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/goal-alignment/goals/{goal_id}/propagate

```
POST /api/v1/goal-alignment/goals/{goal_id}/propagate
```

**Description:** propagate goal change.

**Handler:** `propagate_goal_change` (`goal_alignment.py:451`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/progress/all

```
GET /api/v1/goal-alignment/progress/all
```

**Description:** get all progress.

**Handler:** `get_all_progress` (`goal_alignment.py:441`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/goal-alignment/scan

```
POST /api/v1/goal-alignment/scan
```

**Description:** run alignment scan.

**Handler:** `run_alignment_scan` (`goal_alignment.py:425`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/summary

```
GET /api/v1/goal-alignment/summary
```

**Description:** get alignment summary.

**Handler:** `get_alignment_summary` (`goal_alignment.py:433`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/goal-alignment/tasks

```
POST /api/v1/goal-alignment/tasks
```

**Description:** create task.

**Handler:** `create_task` (`goal_alignment.py:264`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/tasks/{task_id}/alignment

```
GET /api/v1/goal-alignment/tasks/{task_id}/alignment
```

**Description:** check task alignment.

**Handler:** `check_task_alignment` (`goal_alignment.py:396`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/goal-alignment/tasks/{task_id}/context

```
GET /api/v1/goal-alignment/tasks/{task_id}/context
```

**Description:** get task context.

**Handler:** `get_task_context` (`goal_alignment.py:383`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/goal-alignment/tasks/{task_id}/status

```
POST /api/v1/goal-alignment/tasks/{task_id}/status
```

**Description:** update task status.

**Handler:** `update_task_status` (`goal_alignment.py:338`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Governance (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 17 条。

#### GET /api/v1/governance/approval-dashboard

```
GET /api/v1/governance/approval-dashboard
```

**Description:** get approval dashboard.

**Handler:** `get_approval_dashboard` (`governance.py:177`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/approval-requests

```
GET /api/v1/governance/approval-requests
```

**Description:** list approval requests.

**Handler:** `list_approval_requests` (`governance.py:25`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/approval-requests

```
POST /api/v1/governance/approval-requests
```

**Description:** create approval request.

**Handler:** `create_approval_request` (`governance.py:59`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/approval-requests/my

```
GET /api/v1/governance/approval-requests/my
```

**Description:** get my approval requests.

**Handler:** `get_my_approval_requests` (`governance.py:166`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/approval-requests/{request_id}

```
GET /api/v1/governance/approval-requests/{request_id}
```

**Description:** get approval request.

**Handler:** `get_approval_request` (`governance.py:50`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/approval-requests/{request_id}/assign

```
POST /api/v1/governance/approval-requests/{request_id}/assign
```

**Description:** assign approver.

**Handler:** `assign_approver` (`governance.py:108`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/approval-requests/{request_id}/decide

```
POST /api/v1/governance/approval-requests/{request_id}/decide
```

**Description:** make decision.

**Handler:** `make_decision` (`governance.py:121`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/approval-requests/{request_id}/escalate

```
POST /api/v1/governance/approval-requests/{request_id}/escalate
```

**Description:** escalate request.

**Handler:** `escalate_request` (`governance.py:147`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/approval-timeout-handler

```
POST /api/v1/governance/approval-timeout-handler
```

**Description:** handle approval timeout.

**Handler:** `handle_approval_timeout` (`governance.py:159`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/audit-log/export

```
GET /api/v1/governance/audit-log/export
```

**Description:** export audit log.

**Handler:** `export_audit_log` (`governance.py:343`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/delegations

```
GET /api/v1/governance/delegations
```

**Description:** get delegations.

**Handler:** `get_delegations` (`governance.py:285`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/delegations

```
POST /api/v1/governance/delegations
```

**Description:** create delegation.

**Handler:** `create_delegation` (`governance.py:302`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/emergency-override

```
POST /api/v1/governance/emergency-override
```

**Description:** emergency override.

**Handler:** `emergency_override` (`governance.py:245`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/emergency-retroactive-approval

```
POST /api/v1/governance/emergency-retroactive-approval
```

**Description:** complete retroactive approval.

**Handler:** `complete_retroactive_approval` (`governance.py:272`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/reports/governance

```
GET /api/v1/governance/reports/governance
```

**Description:** get governance report.

**Handler:** `get_governance_report` (`governance.py:329`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/governance/risk-assess

```
POST /api/v1/governance/risk-assess
```

**Description:** assess operation risk.

**Handler:** `assess_operation_risk` (`governance.py:203`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/governance/risk-categories

```
GET /api/v1/governance/risk-categories
```

**Description:** get risk categories.

**Handler:** `get_risk_categories` (`governance.py:230`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Heartbeat (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 12 条。

#### GET /api/v1/heartbeat/budget/notifications

```
GET /api/v1/heartbeat/budget/notifications
```

**Description:** get budget notifications.

**Handler:** `get_budget_notifications` (`heartbeat.py:260`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/heartbeat/budget/{agent_id}

```
GET /api/v1/heartbeat/budget/{agent_id}
```

**Description:** check budget.

**Handler:** `check_budget` (`heartbeat.py:243`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/heartbeat/recovery/orphaned

```
POST /api/v1/heartbeat/recovery/orphaned
```

**Description:** recover orphaned tasks.

**Handler:** `recover_orphaned_tasks` (`heartbeat.py:288`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/heartbeat/stats

```
GET /api/v1/heartbeat/stats
```

**Description:** get scheduler stats.

**Handler:** `get_scheduler_stats` (`heartbeat.py:271`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/heartbeat/tasks

```
GET /api/v1/heartbeat/tasks
```

**Description:** list scheduled tasks.

**Handler:** `list_scheduled_tasks` (`heartbeat.py:141`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/heartbeat/tasks

```
POST /api/v1/heartbeat/tasks
```

**Description:** create scheduled task.

**Handler:** `create_scheduled_task` (`heartbeat.py:74`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/v1/heartbeat/tasks/{task_id}

```
DELETE /api/v1/heartbeat/tasks/{task_id}
```

**Description:** delete task.

**Handler:** `delete_task` (`heartbeat.py:214`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/heartbeat/tasks/{task_id}

```
GET /api/v1/heartbeat/tasks/{task_id}
```

**Description:** get scheduled task.

**Handler:** `get_scheduled_task` (`heartbeat.py:115`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/heartbeat/tasks/{task_id}/history

```
GET /api/v1/heartbeat/tasks/{task_id}/history
```

**Description:** get task history.

**Handler:** `get_task_history` (`heartbeat.py:228`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/heartbeat/tasks/{task_id}/pause

```
POST /api/v1/heartbeat/tasks/{task_id}/pause
```

**Description:** pause task.

**Handler:** `pause_task` (`heartbeat.py:185`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/heartbeat/tasks/{task_id}/resume

```
POST /api/v1/heartbeat/tasks/{task_id}/resume
```

**Description:** resume task.

**Handler:** `resume_task` (`heartbeat.py:200`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/heartbeat/tasks/{task_id}/trigger

```
POST /api/v1/heartbeat/tasks/{task_id}/trigger
```

**Description:** trigger task now.

**Handler:** `trigger_task_now` (`heartbeat.py:171`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### LNN Models (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 20 条。

#### POST /api/v1/lnn/batch-inference

```
POST /api/v1/lnn/batch-inference
```

**Description:** batch inference.

**Handler:** `batch_inference` (`lnn.py:1788`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/v1/lnn/cache/clear

```
DELETE /api/v1/lnn/cache/clear
```

**Description:** clear cache.

**Handler:** `clear_cache` (`lnn.py:909`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/cache/stats

```
GET /api/v1/lnn/cache/stats
```

**Description:** get cache stats.

**Handler:** `get_cache_stats` (`lnn.py:887`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/device/clear-cache

```
POST /api/v1/lnn/device/clear-cache
```

**Description:** clear device cache.

**Handler:** `clear_device_cache` (`lnn.py:1036`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/device/info

```
GET /api/v1/lnn/device/info
```

**Description:** get device info.

**Handler:** `get_device_info` (`lnn.py:967`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/device/status

```
GET /api/v1/lnn/device/status
```

**Description:** get device status endpoint.

**Handler:** `get_device_status_endpoint` (`lnn.py:998`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/health

```
GET /api/v1/lnn/health
```

**Description:** health check.

**Handler:** `health_check` (`lnn.py:829`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/models/{model_name}/info

```
GET /api/v1/lnn/models/{model_name}/info
```

**Description:** get model info.

**Handler:** `get_model_info` (`lnn.py:753`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/models/{model_name}/quantize

```
POST /api/v1/lnn/models/{model_name}/quantize
```

**Description:** quantize model.

**Handler:** `quantize_model` (`lnn.py:1317`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/models/{model_name}/size

```
GET /api/v1/lnn/models/{model_name}/size
```

**Description:** get model size.

**Handler:** `get_model_size` (`lnn.py:1446`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/models/{model_name}/validate

```
POST /api/v1/lnn/models/{model_name}/validate
```

**Description:** validate model.

**Handler:** `validate_model` (`lnn.py:782`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/performance

```
GET /api/v1/lnn/performance
```

**Description:** get performance.

**Handler:** `get_performance` (`lnn.py:925`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/predict

```
POST /api/v1/lnn/predict
```

**Description:** predict lnn.

**Handler:** `predict_lnn` (`lnn.py:90`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/quantize/{task_id}/cancel

```
POST /api/v1/lnn/quantize/{task_id}/cancel
```

**Description:** cancel quantization task.

**Handler:** `cancel_quantization_task` (`lnn.py:1415`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/quantize/{task_id}/status

```
GET /api/v1/lnn/quantize/{task_id}/status
```

**Description:** get quantization status.

**Handler:** `get_quantization_status` (`lnn.py:1392`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/tasks

```
GET /api/v1/lnn/tasks
```

**Description:** list training tasks.

**Handler:** `list_training_tasks` (`lnn.py:858`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/train

```
POST /api/v1/lnn/train
```

**Description:** train lnn.

**Handler:** `train_lnn` (`lnn.py:657`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/train/dry_run

```
POST /api/v1/lnn/train/dry_run
```

**Description:** dry run training.

**Handler:** `dry_run_training` (`lnn.py:315`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/lnn/train/{task_id}/cancel

```
POST /api/v1/lnn/train/{task_id}/cancel
```

**Description:** cancel training task.

**Handler:** `cancel_training_task` (`lnn.py:1100`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/lnn/train/{task_id}/stream

```
GET /api/v1/lnn/train/{task_id}/stream
```

**Description:** stream training status.

**Handler:** `stream_training_status` (`lnn.py:1074`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Ollama (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 2 条。

#### GET /api/ollama/models

```
GET /api/ollama/models
```

**Description:** list ollama models.

**Handler:** `list_ollama_models` (`ollama_routes.py:59`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/ollama/status

```
GET /api/ollama/status
```

**Description:** get ollama status.

**Handler:** `get_ollama_status` (`ollama_routes.py:20`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Plugins (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 13 条。

#### GET /api/v1/plugins/marketplace

```
GET /api/v1/plugins/marketplace
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/plugins/marketplace/{plugin_id}/install

```
POST /api/v1/plugins/marketplace/{plugin_id}/install
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/plugins/workers

```
GET /api/v1/plugins/workers
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/plugins/workers/{plugin_id}/start

```
POST /api/v1/plugins/workers/{plugin_id}/start
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/plugins/workers/{plugin_id}/stop

```
POST /api/v1/plugins/workers/{plugin_id}/stop
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/plugins/{plugin_id}/capabilities

```
GET /api/v1/plugins/{plugin_id}/capabilities
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### PUT /api/v1/plugins/{plugin_id}/capabilities/{capability}

```
PUT /api/v1/plugins/{plugin_id}/capabilities/{capability}
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### PUT /api/v1/plugins/{plugin_id}/config

```
PUT /api/v1/plugins/{plugin_id}/config
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/plugins/{plugin_id}/dependencies

```
GET /api/v1/plugins/{plugin_id}/dependencies
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/plugins/{plugin_id}/disable

```
POST /api/v1/plugins/{plugin_id}/disable
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/plugins/{plugin_id}/enable

```
POST /api/v1/plugins/{plugin_id}/enable
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/plugins/{plugin_id}/logs

```
GET /api/v1/plugins/{plugin_id}/logs
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/plugins/{plugin_id}/reload

```
POST /api/v1/plugins/{plugin_id}/reload
```

**Description:** API operation.

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### RAG (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 13 条。

#### POST /api/rag/add

```
POST /api/rag/add
```

**Description:** add knowledge.

**Handler:** `add_knowledge` (`routes.py:60`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/backup/export

```
POST /api/rag/backup/export
```

**Description:** export backup.

**Handler:** `export_backup` (`routes.py:178`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/backup/import

```
POST /api/rag/backup/import
```

**Description:** import backup.

**Handler:** `import_backup` (`routes.py:189`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/import/file

```
POST /api/rag/import/file
```

**Description:** import document.

**Handler:** `import_document` (`routes.py:144`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/rag/list

```
GET /api/rag/list
```

**Description:** list documents.

**Handler:** `list_documents` (`routes.py:91`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/load/default

```
POST /api/rag/load/default
```

**Description:** load default knowledge.

**Handler:** `load_default_knowledge` (`routes.py:100`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/load/json

```
POST /api/rag/load/json
```

**Description:** load rag json.

**Handler:** `load_rag_json` (`routes.py:110`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/maintenance/cleanup

```
POST /api/rag/maintenance/cleanup
```

**Description:** cleanup orphaned.

**Handler:** `cleanup_orphaned` (`routes.py:215`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/rag/maintenance/optimize

```
POST /api/rag/maintenance/optimize
```

**Description:** optimize index.

**Handler:** `optimize_index` (`routes.py:204`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/rag/search

```
GET /api/rag/search
```

**Description:** search by source.

**Handler:** `search_by_source` (`routes.py:120`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/rag/source/{source}

```
DELETE /api/rag/source/{source}
```

**Description:** delete by source.

**Handler:** `delete_by_source` (`routes.py:134`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/rag/stats

```
GET /api/rag/stats
```

**Description:** get stats.

**Handler:** `get_stats` (`routes.py:50`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/rag/{doc_id}

```
DELETE /api/rag/{doc_id}
```

**Description:** delete knowledge.

**Handler:** `delete_knowledge` (`routes.py:77`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Simulation (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 7 条。

#### POST /api/simulation/check-conflict

```
POST /api/simulation/check-conflict
```

**Description:** check tool slot conflict.

**Handler:** `check_tool_slot_conflict` (`api.py:856`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/simulation/history

```
GET /api/simulation/history
```

**Description:** get simulation history.

**Handler:** `get_simulation_history` (`api.py:746`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/simulation/output/{filename}

```
GET /api/simulation/output/{filename}
```

**Description:** get simulation output.

**Handler:** `get_simulation_output` (`api.py:703`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/simulation/result/{task_id}

```
DELETE /api/simulation/result/{task_id}
```

**Description:** delete simulation result.

**Handler:** `delete_simulation_result` (`api.py:798`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/simulation/run

```
POST /api/simulation/run
```

**Description:** run simulation.

**Handler:** `run_simulation` (`api.py:458`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/simulation/run/async

```
POST /api/simulation/run/async
```

**Description:** run simulation async.

**Handler:** `run_simulation_async` (`api.py:557`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/simulation/status/{task_id}

```
GET /api/simulation/status/{task_id}
```

**Description:** get simulation status.

**Handler:** `get_simulation_status` (`api.py:633`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Skills (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 13 条。

#### POST /api/v1/skills/create

```
POST /api/v1/skills/create
```

**Description:** create skill.

**Handler:** `create_skill` (`skills.py:146`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/export

```
POST /api/v1/skills/export
```

**Description:** export skill.

**Handler:** `export_skill` (`skills.py:285`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/import

```
POST /api/v1/skills/import
```

**Description:** import skill.

**Handler:** `import_skill` (`skills.py:299`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/inject

```
POST /api/v1/skills/inject
```

**Description:** inject skills endpoint.

**Handler:** `inject_skills_endpoint` (`skills.py:341`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/marketplace/download

```
POST /api/v1/skills/marketplace/download
```

**Description:** marketplace download.

**Handler:** `marketplace_download` (`skills.py:407`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/skills/marketplace/list

```
GET /api/v1/skills/marketplace/list
```

**Description:** marketplace list.

**Handler:** `marketplace_list` (`skills.py:368`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/marketplace/publish

```
POST /api/v1/skills/marketplace/publish
```

**Description:** marketplace publish.

**Handler:** `marketplace_publish` (`skills.py:392`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/marketplace/rate

```
POST /api/v1/skills/marketplace/rate
```

**Description:** marketplace rate.

**Handler:** `marketplace_rate` (`skills.py:425`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/skills/marketplace/search

```
GET /api/v1/skills/marketplace/search
```

**Description:** marketplace search.

**Handler:** `marketplace_search` (`skills.py:380`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/v1/skills/marketplace/{skill_id}

```
DELETE /api/v1/skills/marketplace/{skill_id}
```

**Description:** marketplace unpublish.

**Handler:** `marketplace_unpublish` (`skills.py:442`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/rate

```
POST /api/v1/skills/rate
```

**Description:** rate skill.

**Handler:** `rate_skill` (`skills.py:326`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/skills/reload

```
POST /api/v1/skills/reload
```

**Description:** reload skills.

**Handler:** `reload_skills` (`skills.py:249`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/skills/{skill_id}/versions

```
GET /api/v1/skills/{skill_id}/versions
```

**Description:** get skill versions.

**Handler:** `get_skill_versions` (`skills.py:263`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Task Checkout (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 15 条。

#### GET /api/v1/task-checkout/agents/{agent_id}/status

```
GET /api/v1/task-checkout/agents/{agent_id}/status
```

**Description:** get agent status.

**Handler:** `get_agent_status` (`task_checkout.py:267`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/task-checkout/board

```
GET /api/v1/task-checkout/board
```

**Description:** get task board.

**Handler:** `get_task_board` (`task_checkout.py:221`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/checkout

```
POST /api/v1/task-checkout/checkout
```

**Description:** checkout task.

**Handler:** `checkout_task` (`task_checkout.py:73`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/cleanup

```
POST /api/v1/task-checkout/cleanup
```

**Description:** cleanup expired.

**Handler:** `cleanup_expired` (`task_checkout.py:348`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/task-checkout/locks

```
GET /api/v1/task-checkout/locks
```

**Description:** list locks.

**Handler:** `list_locks` (`task_checkout.py:228`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### DELETE /api/v1/task-checkout/locks/{task_id}

```
DELETE /api/v1/task-checkout/locks/{task_id}
```

**Description:** force release lock.

**Handler:** `force_release_lock` (`task_checkout.py:235`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/task-checkout/queue

```
GET /api/v1/task-checkout/queue
```

**Description:** get queue status.

**Handler:** `get_queue_status` (`task_checkout.py:341`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/queue/enqueue

```
POST /api/v1/task-checkout/queue/enqueue
```

**Description:** enqueue checkout.

**Handler:** `enqueue_checkout` (`task_checkout.py:274`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/queue/process

```
POST /api/v1/task-checkout/queue/process
```

**Description:** process queue.

**Handler:** `process_queue` (`task_checkout.py:322`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/tasks

```
POST /api/v1/task-checkout/tasks
```

**Description:** register task.

**Handler:** `register_task` (`task_checkout.py:38`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/tasks/{task_id}/abandon

```
POST /api/v1/task-checkout/tasks/{task_id}/abandon
```

**Description:** abandon task.

**Handler:** `abandon_task` (`task_checkout.py:197`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/tasks/{task_id}/complete

```
POST /api/v1/task-checkout/tasks/{task_id}/complete
```

**Description:** complete task.

**Handler:** `complete_task` (`task_checkout.py:148`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/tasks/{task_id}/fail

```
POST /api/v1/task-checkout/tasks/{task_id}/fail
```

**Description:** fail task.

**Handler:** `fail_task` (`task_checkout.py:172`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/task-checkout/tasks/{task_id}/heartbeat

```
POST /api/v1/task-checkout/tasks/{task_id}/heartbeat
```

**Description:** heartbeat.

**Handler:** `heartbeat` (`task_checkout.py:130`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/task-checkout/tasks/{task_id}/history

```
GET /api/v1/task-checkout/tasks/{task_id}/history
```

**Description:** get checkout history.

**Handler:** `get_checkout_history` (`task_checkout.py:256`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### User Management (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 4 条。

#### GET /api/v1/users

```
GET /api/v1/users
```

**Description:** list users.

**Handler:** `list_users` (`users.py:31`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/users/me/permissions

```
GET /api/v1/users/me/permissions
```

**Description:** my permissions.

**Handler:** `my_permissions` (`users.py:52`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### PUT /api/v1/users/{username}/role

```
PUT /api/v1/users/{username}/role
```

**Description:** assign role.

**Handler:** `assign_role` (`users.py:66`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### PUT /api/v1/users/{username}/status

```
PUT /api/v1/users/{username}/status
```

**Description:** set user status.

**Handler:** `set_user_status` (`users.py:91`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### User Sovereignty (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 8 条。

#### DELETE /api/v1/user-sovereignty/audit-log/clear

```
DELETE /api/v1/user-sovereignty/audit-log/clear
```

**Description:** clear audit logs.

**Handler:** `clear_audit_logs` (`user_sovereignty.py:497`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/user-sovereignty/audit-log/export

```
POST /api/v1/user-sovereignty/audit-log/export
```

**Description:** export audit logs.

**Handler:** `export_audit_logs` (`user_sovereignty.py:436`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/user-sovereignty/audit-log/query

```
POST /api/v1/user-sovereignty/audit-log/query
```

**Description:** query audit logs.

**Handler:** `query_audit_logs` (`user_sovereignty.py:365`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/user-sovereignty/audit-log/record

```
POST /api/v1/user-sovereignty/audit-log/record
```

**Description:** record user decision.

**Handler:** `record_user_decision` (`user_sovereignty.py:270`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/user-sovereignty/audit-log/search

```
POST /api/v1/user-sovereignty/audit-log/search
```

**Description:** search audit logs.

**Handler:** `search_audit_logs` (`user_sovereignty.py:403`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/user-sovereignty/audit-log/statistics

```
GET /api/v1/user-sovereignty/audit-log/statistics
```

**Description:** get audit log statistics.

**Handler:** `get_audit_log_statistics` (`user_sovereignty.py:471`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/user-sovereignty/predict

```
POST /api/v1/user-sovereignty/predict
```

**Description:** predict with sovereignty.

**Handler:** `predict_with_sovereignty` (`user_sovereignty.py:29`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/user-sovereignty/settings

```
GET /api/v1/user-sovereignty/settings
```

**Description:** get user sovereignty settings.

**Handler:** `get_user_sovereignty_settings` (`user_sovereignty.py:523`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

### Wear Prediction (Routes补全)

> 以下路由已存在于 `python/app/**` 中但未在本文档前面章节记录。共 9 条。

#### POST /api/v1/wear/calibrate

```
POST /api/v1/wear/calibrate
```

**Description:** calibrate prediction.

**Handler:** `calibrate_prediction` (`wear_prediction.py:220`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/wear/cross-dataset-analysis

```
GET /api/v1/wear/cross-dataset-analysis
```

**Description:** get cross dataset analysis.

**Handler:** `get_cross_dataset_analysis` (`wear_prediction.py:301`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/wear/models

```
GET /api/v1/wear/models
```

**Description:** get supported models.

**Handler:** `get_supported_models` (`wear_prediction.py:160`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/wear/predict-from-signals

```
POST /api/v1/wear/predict-from-signals
```

**Description:** predict wear from signal features.

**Handler:** `predict_wear_from_signal_features` (`wear_prediction.py:275`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/wear/remaining-life

```
POST /api/v1/wear/remaining-life
```

**Description:** predict remaining life.

**Handler:** `predict_remaining_life` (`wear_prediction.py:92`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/wear/suggest

```
POST /api/v1/wear/suggest
```

**Description:** suggest adjustment.

**Handler:** `suggest_adjustment` (`wear_prediction.py:127`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/wear/threshold

```
POST /api/v1/wear/threshold
```

**Description:** get threshold.

**Handler:** `get_threshold` (`wear_prediction.py:197`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### POST /api/v1/wear/train-uniwear

```
POST /api/v1/wear/train-uniwear
```

**Description:** train uniwear model.

**Handler:** `train_uniwear_model` (`wear_prediction.py:250`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

#### GET /api/v1/wear/uniwear-materials

```
GET /api/v1/wear/uniwear-materials
```

**Description:** get uniwear materials.

**Handler:** `get_uniwear_materials` (`wear_prediction.py:321`)

**Response (200):**
```json
{
  "code": 0,
  "message": "操作成功",
  "data": { }
}
```

**Status Codes:** `200 OK`, `400 Bad Request`, `401 Unauthorized`

---

### 仅在文档中存在（需复核）

> 以下路径在 `docs/API.md` 中被记录但未在代码中匹配到，可能为：
>
> - 旧版 API（已废弃 / 重构）
> - 通过中间件或别名注册
> - 文档笔误
>
> 共 **67** 条，需要人工复核。

- `/agents`
- `/api/agent/v1/chat`
- `/api/agent/v1/chat/sse`
- `/api/agent/v1/skills`
- `/api/agent/v1/skills/register`
- `/api/agents`
- `/api/agents/{agent_id}`
- `/api/ai/chat`
- `/api/dxf/info/{file_id}`
- `/api/dxf/upload`
- `/api/ollama/chat`
- `/api/ollama/chat/stream`
- `/api/ollama/health`
- `/api/process/generate`
- `/api/rag/collections`
- `/api/rag/collections/{collection_name}/query`
- `/api/simulation/result`
- `/api/simulation/start`
- `/api/simulation/status`
- `/api/v1/cost-budget/budget`
- `/api/v1/cost-budget/costs`
- `/api/v1/cost-budget/stats`
- `/api/v1/goal-alignment/align`
- `/api/v1/goal-alignment/alignments/{alignment_id}`
- `/api/v1/goal-alignment/goals/batch`
- `/api/v1/governance/approvals`
- `/api/v1/governance/approvals/submit`
- `/api/v1/governance/approvals/{approval_id}`
- `/api/v1/governance/approvals/{approval_id}/review`
- `/api/v1/heartbeat`
- `/api/v1/lnn/models/active`
- `/api/v1/lnn/models/compare`
- `/api/v1/lnn/models/{model_id}`
- `/api/v1/lnn/models/{model_id}/activate`
- `/api/v1/lnn/models/{model_id}/batch-predict`
- `/api/v1/lnn/models/{model_id}/deactivate`
- `/api/v1/lnn/models/{model_id}/predict`
- `/api/v1/lnn/models/{model_id}/versions`
- `/api/v1/skills/search`
- `/api/v1/sse/connect/{task_id}`
- `/api/v1/sse/send/{task_id}`
- `/api/v1/sse/tasks`
- `/api/v1/sse/tasks/{task_id}`
- `/api/v1/sse/verify`
- `/api/v1/task-checkout`
- `/api/v1/task-checkout/{checkout_id}/checkin`
- `/api/v1/task-checkout/{checkout_id}/release`
- `/api/v1/user-sovereignty/data`
- `/api/v1/user-sovereignty/export`
- `/api/v1/users/batch-delete`
- `/api/v1/users/batch-update`
- `/api/v1/users/change-password`
- `/api/v1/users/create`
- `/api/v1/users/list`
- `/api/v1/users/me`
- `/api/v1/users/me/tasks`
- `/api/v1/users/stats`
- `/api/v1/users/{user_id}`
- `/api/v1/wear/batch-predict`
- `/api/v1/wear/predictions`
- `/api/v1/wear/predictions/{prediction_id}`
- `/health`
- `/health/live`
- `/health/ready`
- `/logs/recent`
- `/metrics/prometheus`
- `/version`

---

*本节由 scripts/sync_api_docs.py 自动生成于 2026-06-11。源数据：api-sync-report.json*
