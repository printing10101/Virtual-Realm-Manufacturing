# Phase 2: Python AI 后端（Sidecar）

> **预计工期**: 4-5 小时 | **前置依赖**: Phase 1 | **下一步**: Phase 3 - 本地 LLM 集成

## 目标

搭建完整的 Python FastAPI 后端项目，包括统一响应格式、异常处理、Pydantic 数据模型、LLM 客户端抽象层（支持 Ollama 本地模型和云端 API）、健康检查接口，以及 PyInstaller 打包脚本。

## 验证标准

- [ ] `python -m app.main` 可正常启动 FastAPI 服务
- [ ] 访问 `http://localhost:8765/health` 返回健康状态
- [ ] 访问 `http://localhost:8765/api/ai/status` 返回 AI 状态
- [ ] 访问 `http://localhost:8765/docs` 可查看 Swagger 文档
- [ ] 全局异常处理正常工作
- [ ] `pip install -r requirements.txt` 可正常安装所有依赖
- [ ] `python build.py --help` 打包脚本可正常执行

---

## 项目结构

```
python/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 应用入口
│   ├── config.py            # 配置管理
│   ├── core/
│   │   ├── response.py      # 统一响应格式
│   │   └── exceptions.py    # 自定义异常
│   ├── models/
│   │   └── schemas.py       # Pydantic 模型
│   ├── ai/
│   │   ├── llm_client.py    # LLM 客户端抽象
│   │   └── agents.py        # AI Agent（占位）
│   ├── cad/
│   │   ├── generator.py     # CAD 生成器（占位）
│   │   └── cadquery_gen.py  # CadQuery 生成（占位）
│   └── rag/
│       └── __init__.py     # RAG 知识库（占位）
├── requirements.txt
├── pyproject.toml
└── build.py                 # PyInstaller 打包脚本
```

---

## 核心组件

### 配置管理 (`app/config.py`)

```python
@dataclass
class AppConfig:
    app_name: str = "灵境制造"
    app_version: str = "4.0.0"
    offline_mode: bool = False
    server: ServerConfig = field(default_factory=ServerConfig)
    ai: AIConfig = field(default_factory=AIConfig)
    storage: StorageConfig = field(default_factory=StorageConfig)
```

### 统一响应格式 (`app/core/response.py`)

```python
class ApiResponse(BaseModel, Generic[T]):
    code: int = Field(default=ErrorCode.SUCCESS)
    message: str = Field(default="success")
    data: Optional[T] = None

def success(data: Any = None, message: str = "success") -> dict
def error(code: int, message: str, data: Any = None) -> dict
```

### LLM 客户端抽象 (`app/ai/llm_client.py`)

```python
class BaseLLMClient(ABC):
    @abc.abstractmethod
    async def chat(self, request: LLMRequest) -> LLMResponse
    @abc.abstractmethod
    async def is_available(self) -> bool

class OllamaClient(BaseLLMClient):
    # 本地 Ollama 模型支持
    async def list_models() -> list[str]
    async def get_version() -> Optional[str]

class CloudLLMClient(BaseLLMClient):
    # 云端 API 支持（OpenAI/DeepSeek 兼容）

class RuleEngineClient(BaseLLMClient):
    # 规则引擎降级方案

def get_llm_client(mode: Optional[str] = None) -> BaseLLMClient
```

### 自定义异常 (`app/core/exceptions.py`)

```python
class AppException(Exception):
    code: int
    message: str
    detail: Optional[str]

# 异常子类
class AIModelUnavailableError(AppException)
class AIModelTimeoutError(AppException)
class CADGenerationError(AppException)
class FileNotFoundException(AppException)
```

### Pydantic 数据模型 (`app/models/schemas.py`)

```python
class AIMode(str, Enum):
    LOCAL = "local"
    CLOUD = "cloud"
    RULE = "rule"

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"

class AISettings(BaseModel)
class AIStatusResponse(BaseModel)
class LLMRequest(BaseModel)
class LLMResponse(BaseModel)
class HealthResponse(BaseModel)
```

---

## API 路由

| 路由 | 方法 | 描述 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/api/ai/status` | GET | AI 状态 |
| `/api/ai/chat` | POST | LLM 对话 |
| `/api/ai/settings` | PUT | 更新 AI 设置 |
| `/api/cad/three-view-to-3d` | POST | 三视图生成（占位） |
| `/api/cad/cadquery` | POST | CadQuery 生成（占位） |
| `/api/process/route` | POST | 工艺路线（占位） |

---

## 验证清单

1. FastAPI 服务可正常启动（`python -m app.main`）
2. `/health` 返回健康状态和 AI 状态
3. `/docs` 可访问 Swagger 文档
4. 全局异常处理正常工作
5. 依赖可正常安装
6. PyInstaller 打包脚本可执行

---

## 相关文档

- [Phase 1 - Tauri 桌面壳](../03-Phase1-Tauri桌面壳与Rust后端.md)
- [Phase 3 - 本地 LLM 集成](../05-Phase3-本地LLM集成.md)
