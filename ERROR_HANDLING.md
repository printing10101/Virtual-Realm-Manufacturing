# 错误处理与可观测性实施文档

## 概述

本文档描述了灵境制造项目的统一错误处理机制和全链路可追踪能力的实现。

## 架构设计

### 错误分类体系

系统采用三级错误分类体系：

1. **错误类型 (ErrorType)**
   - `BUSINESS`: 业务逻辑错误
   - `SYSTEM`: 系统内部错误
   - `EXTERNAL`: 外部服务错误
   - `VALIDATION`: 数据验证错误
   - `NETWORK`: 网络连接错误

2. **错误严重程度 (ErrorSeverity)**
   - `LOW`: 低优先级，不影响核心功能
   - `MEDIUM`: 中等优先级，影响部分功能
   - `HIGH`: 高优先级，影响核心功能
   - `CRITICAL`: 严重错误，系统不可用

3. **HTTP 状态码映射**
   - 400: 参数错误、验证失败
   - 401: 认证失败
   - 403: 权限不足
   - 404: 资源不存在
   - 409: 资源冲突
   - 422: 参数验证失败
   - 429: 请求过于频繁
   - 500: 系统内部错误
   - 502: 网关错误
   - 503: 服务不可用
   - 504: 网关超时

### 结构化错误响应格式

所有 API 错误均返回以下标准化格式：

```json
{
  "success": false,
  "code": 400001,
  "message": "参数错误",
  "error_type": "VALIDATION",
  "severity": "LOW",
  "timestamp": "2026-06-15T10:30:00.000Z",
  "request_id": "req_abc123",
  "error_id": "err_xyz789",
  "details": {
    "field": "email",
    "reason": "invalid_format"
  }
}
```

## 后端实现

### 核心模块

#### 1. error_handler.py

位置：`python/app/core/error_handler.py`

**主要功能：**
- 错误分类和严重程度评估
- 结构化错误响应构建
- 错误上下文收集
- 诊断信息生成
- 增强的错误日志记录

**关键函数：**
- `classify_error_by_code()`: 根据错误码分类
- `classify_severity()`: 评估错误严重程度
- `build_error_response()`: 构建标准化错误响应
- `build_error_response_from_exception()`: 从异常构建错误响应
- `ErrorContext`: 错误上下文收集类
- `generate_diagnostic_text()`: 生成诊断信息文本
- `log_error()`: 增强的错误日志记录

#### 2. 集成点

- `exceptions.py`: 基础异常类定义
- `request_id.py`: 请求 ID 管理
- `api_response.py`: API 响应装饰器
- `exception_handlers.py`: 异常处理器注册

### 使用示例

```python
from app.core.error_handler import (
    build_error_response,
    build_error_response_from_exception,
    ErrorContext,
    log_error
)

# 从异常构建错误响应
try:
    # 业务逻辑
    pass
except Exception as e:
    response = build_error_response_from_exception(e, request_id="req_123")
    log_error(e, request_id="req_123")

# 手动构建错误响应
response = build_error_response(
    status_code=400,
    code="PARAM_ERROR",
    message="参数错误",
    error_type="VALIDATION",
    severity="LOW",
    request_id="req_123",
    details={"field": "email"}
)

# 收集错误上下文
context = ErrorContext()
context.collect_request_info(request)
context.collect_user_info(user)
context.collect_error_details(error)
diagnostic_text = context.generate_diagnostic_text()
```

## 前端实现

### 核心模块

#### 1. error-handler.ts

位置：`src/utils/error-handler.ts`

**主要功能：**
- 前端错误分类
- 标准化错误对象构建
- 从 Axios 响应和错误提取信息
- 诊断信息收集和复制

**关键函数：**
- `classifyErrorByCode()`: 根据错误码分类
- `classifySeverity()`: 评估错误严重程度
- `buildErrorFromResponse()`: 从 Axios 响应构建错误
- `buildErrorFromAxiosError()`: 从 Axios 错误构建
- `buildErrorFromError()`: 从标准 Error 构建
- `collectDiagnosticContext()`: 收集诊断上下文
- `generateDiagnosticText()`: 生成诊断信息文本
- `copyDiagnosticText()`: 复制诊断信息到剪贴板

#### 2. useDiagnostics.ts

位置：`src/composables/useDiagnostics.ts`

**主要功能：**
- Vue 组合式 API 形式的诊断信息收集
- 错误历史记录管理
- 简化的诊断信息复制功能

**主要接口：**
- `useDiagnostics()`: 诊断信息收集组合式函数
- `useDiagnosticCopy()`: 诊断信息复制组合式函数

#### 3. ErrorNotification.vue

位置：`src/components/ErrorNotification.vue`

**新增功能：**
- "复制诊断信息"按钮
- 一键复制完整错误上下文
- 复制状态反馈

### 使用示例

```typescript
import { buildErrorFromAxiosError, copyDiagnosticText } from '@/utils/error-handler';
import { useDiagnosticCopy } from '@/composables/useDiagnostics';

// 在 Axios 拦截器中使用
axios.interceptors.response.use(
  response => response,
  error => {
    const standardError = buildErrorFromAxiosError(error);
    // 处理标准错误对象
    return Promise.reject(standardError);
  }
);

// 在组件中使用
const { copyDiagnostic } = useDiagnosticCopy();

const handleError = async (error: StandardError) => {
  const success = await copyDiagnostic(error);
  if (success) {
    // 显示成功提示
  }
};

// 直接复制诊断信息
const diagnosticText = await copyDiagnosticText(error);
```

## 全链路追踪

### 请求 ID 传播

1. 后端生成唯一请求 ID（通过 `X-Request-ID` 头或自动生成）
2. 请求 ID 包含在所有 API 响应中
3. 前端从响应头或响应体提取请求 ID
4. 前端错误对象包含请求 ID 用于追踪

### 错误追踪流程

```
前端错误发生
  ↓
收集错误上下文（包括请求 ID）
  ↓
生成诊断信息
  ↓
用户点击"复制诊断信息"
  ↓
后端记录错误（包含请求 ID）
  ↓
通过请求 ID 关联前后端错误
```

## 测试覆盖

### 后端测试

位置：`python/tests/test_error_handler.py`

**测试内容：**
- 错误类型分类测试
- 严重程度评估测试
- 错误码映射测试
- 错误响应构建测试
- 错误上下文收集测试
- 日志记录测试

**运行命令：**
```bash
cd python && pytest tests/test_error_handler.py -v
```

### 前端测试

位置：`src/utils/__tests__/error-handler.test.ts`

**测试内容：**
- 错误分类测试
- 严重程度评估测试
- 错误对象构建测试
- 诊断信息生成测试
- 诊断信息复制测试

**运行命令：**
```bash
pnpm test:run -- error-handler
```

## 验收标准

✅ 所有 API 错误均返回标准化的结构化响应
✅ 前端错误展示界面包含功能正常的"复制诊断信息"按钮
✅ 单元测试覆盖率达到 80% 以上
✅ 错误追踪能够贯穿从前端到后端的完整调用链路

## 最佳实践

1. **错误处理原则**
   - 所有错误都应该被捕获和处理
   - 不要暴露敏感信息给客户端
   - 提供有意义的错误消息
   - 记录详细的错误上下文

2. **日志记录原则**
   - 使用适当的日志级别
   - 包含请求 ID 用于追踪
   - 记录足够的上下文信息
   - 避免记录敏感数据

3. **用户体验原则**
   - 提供友好的错误提示
   - 允许用户复制诊断信息
   - 根据错误严重程度采取不同措施
   - 提供错误恢复建议

## 未来改进

1. 集成错误监控系统（如 Sentry）
2. 实现错误聚合和分析
3. 添加错误恢复建议
4. 实现错误统计仪表板
5. 支持错误重试机制
