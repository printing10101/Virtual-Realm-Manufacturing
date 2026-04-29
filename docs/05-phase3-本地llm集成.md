# Phase 3: 本地 LLM 集成（Ollama）

> **预计工期**: 3-4 小时 | **前置依赖**: Phase 2 | **下一步**: Phase 4 - 3D/CAD 引擎

## 目标

实现完整的 Ollama 本地 LLM 管理功能，包括模型管理（列表、下载、删除、详情）、GPU 信息查询、SSE 流式下载进度推送，以及前端设置页面的完整实现。

## 验证标准

- [ ] `python/app/ai/ollama_manager.py` 包含 OllamaManager 类
- [ ] `python/app/ai/ollama_routes.py` 包含所有 API 路由
- [ ] `GET /api/ollama/status` 返回 Ollama 运行状态
- [ ] `GET /api/ollama/models` 返回已安装模型列表
- [ ] `GET /api/ollama/models/recommended` 返回推荐模型列表
- [ ] `POST /api/ollama/models/pull/{name}` 返回 SSE 流式进度
- [ ] `DELETE /api/ollama/models/{name}` 成功删除模型
- [ ] `GET /api/ollama/gpu-info` 返回 GPU 信息
- [ ] 前端 Settings.vue 包含 AI 模式切换、本地模型管理、云端 API 配置

---

## 核心组件

### Ollama 管理器 (`python/app/ai/ollama_manager.py`)

```python
class OllamaManager:
    async def is_available() -> bool
    async def get_version() -> Optional[str]
    async def list_models() -> list[dict]
    async def pull_model(model_name: str) -> AsyncGenerator[dict, None]  # SSE
    async def delete_model(model_name: str) -> bool
    async def show_model_info(model_name: str) -> Optional[dict]
    async def get_gpu_info() -> dict

RECOMMENDED_MODELS = [
    {"name": "qwen2.5:7b", "size": "4.7 GB", "category": "通用"},
    {"name": "qwen2.5:3b", "size": "2.0 GB", "category": "通用"},
    {"name": "deepseek-r1:7b", "size": "4.7 GB", "category": "推理"},
    {"name": "qwen2.5-coder:7b", "size": "4.7 GB", "category": "代码"},
]
```

### API 路由 (`python/app/ai/ollama_routes.py`)

| 路由 | 方法 | 描述 |
|------|------|------|
| `/ollama/status` | GET | 获取 Ollama 服务状态 |
| `/ollama/models` | GET | 获取已安装模型列表 |
| `/ollama/models/recommended` | GET | 获取推荐模型列表 |
| `/ollama/models/pull/{model_name}` | POST | 拉取模型（SSE 流式） |
| `/ollama/models/{model_name}` | DELETE | 删除模型 |
| `/ollama/models/{model_name}/info` | GET | 获取模型详细信息 |
| `/ollama/gpu-info` | GET | 获取 GPU 信息 |

### 前端服务 (`src/services/ollama.ts`)

```typescript
export async function getOllamaStatus(): Promise<OllamaStatus>
export async function listModels(): Promise<{models: OllamaModel[]; total: number}>
export async function getRecommendedModels(): Promise<{models: RecommendedModel[]; total: number}>
export async function pullModel(modelName: string, onProgress: (progress: PullProgress) => void): Promise<void>
export async function deleteModel(modelName: string): Promise<void>
export async function getModelInfo(modelName: string): Promise<Record<string, unknown>>
export async function getGpuInfo(): Promise<GpuInfo>
```

### 前端设置页面 (`src/views/Settings.vue`)

完整实现包含：
- AI 模式切换（本地/云端/离线）
- Ollama 状态显示
- 已安装模型列表
- 推荐模型下载（带 SSE 进度条）
- 云端 API 配置
- 语言设置

---

## 验证清单

1. OllamaManager 类所有方法实现完整
2. 所有 API 路由已注册
3. SSE 流式推送正常工作
4. 前端 Settings.vue 完整实现
5. TypeScript 编译无报错

---

## 相关文档

- [Phase 2 - Python AI 后端](../04-Phase2-Python-AI后端.md)
- [Phase 4 - 3D/CAD 引擎](../06-Phase4-3D-CAD引擎.md)
