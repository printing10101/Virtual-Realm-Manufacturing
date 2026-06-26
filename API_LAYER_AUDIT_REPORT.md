# API 层深度排查报告

> 排查时间: 2026-06-23  
> 排查范围: `c:\Users\Lenovo\Desktop\灵境制造（上线版）\python\app`

---

## 一、已知问题确认

| # | 问题 | 文件 | 行号 | 风险 | 状态 |
|---|------|------|------|------|------|
| 1 | 端口配置不一致 | `app/config.py` / `app/main.py` | L14 / L末尾 | **高** | 已确认 |
| 2 | OLLAMA_BASE_URL 容器不可达 | `app/config.py` | L23 | **高** | 已确认 |
| 3 | 部分 UploadFile 端点缺少校验 | 多文件 | 见下文 | **高** | 已确认 |

### 1.1 端口配置不一致

**文件**: `app/config.py:14` vs `app/main.py` (末尾 uvicorn.run)

```python
# config.py
class ServerConfig:
    port: int = field(default_factory=lambda: int(_env("SERVER_PORT", "8765")))

# main.py (末尾)
uvicorn.run("app.main:app", host="0.0.0.0", port=8765, reload=True)
```

**风险**: 高 — 配置文件定义的 8765 端口完全被忽略，实际始终以 8765 启动。容器编排（Dockerfile EXPOSE、docker-compose ports）若按 8765 配置将导致服务不可达。

**修复建议**: `main.py` 改为读取 `config.server.port`。

### 1.2 OLLAMA_BASE_URL 容器不可达

**文件**: `app/config.py:23`

```python
ollama_base_url: str = field(
    default_factory=lambda: _env("OLLAMA_BASE_URL", "http://localhost:11434")
)
```

**风险**: 高 — 容器内 `localhost` 指向容器自身而非宿主机，Ollama 调用将全部超时。

**修复建议**: 默认值改为 `http://host.docker.internal:11434`（Docker Desktop）或通过 `--network host` / Docker Compose service name 解决。

### 1.3 UploadFile 端点校验情况汇总

| 端点 | 文件 | 文件大小校验 | 文件类型校验 | 风险 |
|------|------|:---:|:---:|------|
| `POST /api/import/step` | `step_import/api.py:58-83` | ✅ MAX_FILE_SIZE=50MB | ✅ .step/.stp | 低 |
| `POST /api/dxf/*` (多个) | `dxf/api.py:85-110` | ✅ MAX_FILE_SIZE=50MB | ✅ .dxf | 低 |
| `POST /api/rules/import` | `rules/api.py:425-433` | ❌ 无大小限制 | ✅ 仅检查 .json 后缀 | **中** |
| `POST /api/rag/import/file` | `rag/routes.py:150-181` | ❌ 无大小限制 | ❌ 无任何校验 | **高** |
| `POST /api/projects/upload-resource` | `projects/project_api.py:412-449` | ❌ 无大小限制 | ❌ 无任何校验 | **高** |

---

## 二、8 项深度排查结果

### 2.1 API 规范与文档

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 4 | 无 API 废弃（deprecation）机制 | `app/api/v1/lnn.py` | L311, L1333 | **低** | 仅有 log 级别的 deprecated 警告，无 HTTP `Deprecation` 响应头，无 OpenAPI `deprecated: true` 标记 |
| 5 | API 版本管理不完整 | `app/api/v1/` 目录 | - | **低** | 所有路由均在 `v1` 下，但 `step_import/api.py`、`dxf/api.py`、`rag/routes.py`、`rules/api.py`、`projects/project_api.py` 使用独立前缀（`/api/import/step`、`/api/dxf`、`/api/rag`、`/api/rules`、`/api/projects`），未统一纳入 `v1` 版本体系 |

**详情**:

```python
# lnn.py:311 — 仅日志警告，客户端无法感知
logger.warning(
    message="run_training_task v1 is deprecated; use task_manager.execute_task with run_training_task_v2 instead."
)
```

**路由前缀不一致**:
- `api/v1/` 下的路由: `/api/v1/jobs`, `/api/v1/lnn`, `/api/v1/auth` 等
- 独立路由: `/api/import/step`, `/api/dxf`, `/api/rag`, `/api/rules`, `/api/projects`

### 2.2 输入验证与序列化

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 6 | RAG 文档上传无任何校验 | `rag/routes.py` | L150-181 | **高** | 无文件大小限制、无类型检查，可上传任意文件 |
| 7 | 项目资源上传无校验 | `projects/project_api.py` | L412-449 | **高** | 无文件大小限制、无类型检查 |
| 8 | 规则导入无文件大小限制 | `rules/api.py` | L425-433 | **中** | 仅检查 `.json` 后缀，无大小限制，大文件可导致内存溢出 |
| 9 | 请求体大小无全局限制 | `app/main.py` | - | **中** | 未配置 `request.max_size` 或中间件级别的全局请求体限制 |

### 2.3 错误响应与状态码

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 10 | `api_response` 装饰器吞没异常细节 | `core/api_response.py` | wrapper 函数 | **低** | 所有异常统一返回 500 + `INTERNAL_ERROR`，部分可恢复异常（如 ValidationException 422）被错误映射为 500 |
| 11 | 部分端点混用 HTTPException 和 error() | 多文件 | - | **低** | `step_import/api.py` 使用 `HTTPException`，`api/v1/` 下使用 `error()` 函数，响应格式不完全一致 |

**整体评价**: 错误码体系（`exceptions.py`）设计完善，覆盖 1xxx-7xxx 共 27 个错误码。`error_handler.py` 提供了统一的异常到 HTTP 响应映射。主要问题是 `api_response` 装饰器的异常捕获过于宽泛。

### 2.4 速率限制与防护

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 12 | 文件上传端点无独立速率限制 | `rag/routes.py`, `projects/project_api.py` | - | **中** | 大文件上传端点未设置更严格的速率限制，攻击者可连续上传耗尽磁盘/内存 |
| 13 | PermissionChecker 速率限制仅内存态 | `auth/permissions.py` | L57-67 | **中** | `RateLimitState` 使用内存 list 存储，多进程/多 worker 部署下限制失效，且无持久化 |
| 14 | 无 DDoS 防护层 | `app/main.py` | - | **中** | 无 IP 黑名单、无连接数限制、无请求队列机制 |

**亮点**: `rate_limiter.py` 使用 slowapi 实现了基于 `get_remote_address` 的全局限流，429 响应格式规范（含 `Retry-After` 头）。`auth.py` 登录端点有独立的 `@limiter.limit("5/minute")` 防暴力破解。

### 2.5 认证与授权

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 15 | 独立路由模块未纳入统一认证 | `step_import/api.py`, `dxf/api.py`, `rag/routes.py` 等 | - | **高** | `unified_auth.py` 中间件仅对 `/api/v1/` 路径生效，独立前缀的路由可能绕过认证 |
| 16 | JWT 密钥强制校验存在绕过风险 | `auth/security.py` | L131-141 | **低** | `_reset_secret_for_testing` 函数在生产环境可被调用（虽标记"仅供单元测试"） |

**亮点**:
- JWT 密钥管理严格：强制环境变量、最小 32 字符、随机性检测
- RBAC 体系完善：6 级权限（R/W/B/N/C/T）+ 数据库角色权限 + 缓存
- Token 黑名单机制：支持 JTI 级别的 token 撤销
- `PaperOnlyGuard` 对 T 级操作（机器参数下发）有双重确认机制

### 2.6 分页与过滤

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 17 | `list_jobs` 的 `total` 计算错误 | `api/v1/jobs.py` | L152 | **高** | `total = len(tasks)` 返回的是当前分页的数量，而非满足查询条件的总数 |
| 18 | 分页参数无默认上限保护 | `api/v1/jobs.py` | L128 | **低** | `limit` 上限 200（`le=200`），已做保护，但其他列表端点未检查 |

**代码片段**:

```python
# jobs.py:149-152
tasks = await task_manager.list_tasks(
    task_type=tt, status=st, owner_id=owner_id, limit=limit, offset=offset
)
total = len(tasks)  # BUG: 这是当前页的数量，不是总数
```

**修复建议**: `list_tasks` 应返回 `(tasks, total_count)` 元组，或在 DB 层做 `COUNT(*)` 查询。

### 2.7 异步与流式响应

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| 19 | SSE 背压处理粗暴 | `api/v1/sse.py` | broadcast 方法 | **中** | `QueueFull` 时直接移除客户端，无重试机制，无客户端通知 |
| 20 | SSE 流无最大连接数限制 | `api/v1/sse.py` | - | **中** | 单 task_id 可无限订阅，恶意客户端可创建大量连接耗尽内存 |
| 21 | SSE heartbeat 间隔硬编码 | `api/v1/jobs.py` | L71 | **低** | `timeout=30.0` 硬编码，不可配置 |

**代码片段**:

```python
# sse.py broadcast 方法
try:
    await client.queue.put(event)
except (asyncio.QueueFull, RuntimeError, AttributeError) as e:
    logger.warning(f"Failed to send SSE event to client {client_id}: {e}")
    clients_to_remove.append(client_id)  # 直接移除，无通知
```

### 2.8 跨域与 CORS

| # | 问题 | 文件 | 行号 | 风险 | 说明 |
|---|------|------|------|------|------|
| - | 无显著问题 | `middleware/cors_config.py` | - | - | CORS 配置完善 |

**亮点**:
- `validate_cors_config` 严格禁止 `allow_origins=["*"]` 与 `allow_credentials=True` 组合使用
- 支持 `allow_origin_regex` 动态匹配
- 环境变量感知：开发/生产环境自动调整默认 origin
- 预检请求 `max_age` 可配置

---

## 三、问题汇总（按风险排序）

### 高风险（共 5 项）

| # | 问题 | 文件 | 修复建议 |
|---|------|------|----------|
| 1 | 端口配置不一致 (8765 vs 8765) | `config.py` / `main.py` | `main.py` 读取 `config.server.port` |
| 2 | OLLAMA_BASE_URL 容器不可达 | `config.py:23` | 默认改为 `host.docker.internal` |
| 6 | RAG 文档上传无任何校验 | `rag/routes.py:150` | 添加大小/类型校验 |
| 7 | 项目资源上传无校验 | `projects/project_api.py:412` | 添加大小/类型校验 |
| 15 | 独立路由模块可能绕过认证 | `step_import/`, `dxf/`, `rag/` 等 | 将路由统一纳入 `/api/v1/` 或扩展认证中间件路径匹配 |
| 17 | `list_jobs` total 计算错误 | `jobs.py:152` | DB 层返回真实总数 |

### 中风险（共 6 项）

| # | 问题 | 文件 | 修复建议 |
|---|------|------|----------|
| 8 | 规则导入无文件大小限制 | `rules/api.py:425` | 添加 `MAX_FILE_SIZE` 检查 |
| 9 | 无全局请求体大小限制 | `main.py` | 配置 `request.max_size` 或中间件 |
| 12 | 文件上传端点无独立速率限制 | 多文件 | 对上传端点设置更严格的 limit |
| 13 | PermissionChecker 速率限制仅内存态 | `permissions.py:57` | 改用 Redis 存储 |
| 14 | 无 DDoS 防护层 | `main.py` | 引入 IP 黑名单/连接数限制 |
| 19 | SSE 背压处理粗暴 | `sse.py` | 添加重试机制和客户端通知 |
| 20 | SSE 无最大连接数限制 | `sse.py` | 设置单 task_id 最大订阅数 |

### 低风险（共 6 项）

| # | 问题 | 文件 | 修复建议 |
|---|------|------|----------|
| 4 | 无 API 废弃机制 | `lnn.py` | 添加 `Deprecation` 响应头 |
| 5 | API 版本管理不完整 | 多文件 | 统一所有路由到 `/api/v1/` |
| 10 | `api_response` 异常映射过宽 | `api_response.py` | 区分业务异常和系统异常 |
| 11 | 混用 HTTPException 和 error() | 多文件 | 统一使用 `error()` |
| 16 | `_reset_secret_for_testing` 暴露风险 | `security.py:131` | 添加 `if not DEBUG` 保护 |
| 21 | SSE heartbeat 间隔硬编码 | `jobs.py:71` | 提取为配置项 |

---

## 四、优先修复建议

1. **立即修复**: 端口不一致 (#1)、RAG/项目上传无校验 (#6, #7)、认证绕过 (#15)
2. **短期修复**: OLLAMA_BASE_URL (#2)、total 计算错误 (#17)、全局请求体限制 (#9)
3. **中期优化**: SSE 背压 (#19, #20)、速率限制持久化 (#13)、API 版本统一 (#5)
