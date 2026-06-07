# 灵境制造 (Lingjing Manufacturing) API Documentation

> Base URL: `http://localhost:8000`
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
| **Base URL** | `http://localhost:8000` |
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
