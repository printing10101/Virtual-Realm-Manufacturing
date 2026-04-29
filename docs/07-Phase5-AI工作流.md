# Phase 5: PhyCo-Agent 架构（AI 工作流）

> **预计工期**: 6-8 小时 | **前置依赖**: Phase 3 | **下一步**: Phase 6 - 用户界面
> **完成状态**: 已完成
> **最后更新**: 2026-04-29

## 目标

实现基于论文《知识图谱与数学规划耦合的工艺生成方法研究》的六 Agent 协同工作流，包含 RAG 知识库、工艺规划 Agent、NC 代码生成、验证与修复功能。

## 验证标准

- [x] ChromaDB 知识库初始化成功
- [x] 六 Agent 协同工作流正常运行
- [x] `POST /api/workflow/process-plan` 返回完整工艺规划结果
- [x] 工艺验证与修复功能正常
- [x] 前端 ProcessPlan.vue 展示工作流进度与结果

---

## 核心架构

### 六 Agent 协同工作流

```
用户输入 → UnderstandingAgent → PlanningAgent → ParameterAgent
                                            ↓
                                      NCAgent → VerificationAgent → RepairAgent
                                            ↓
                                         输出
```

### Agent 类型与职责

| Agent | 职责 | 输入 | 输出 |
|-------|------|------|------|
| UnderstandingAgent | 理解用户需求，提取关键参数 | 用户自然语言描述 | 结构化参数（材料、零件类型、尺寸、公差、粗糙度等） |
| PlanningAgent | 制定加工工艺路线 | 提取的参数 | 工艺路线（工序序列：步骤、操作、设备、说明） |
| ParameterAgent | 计算切削参数 | 工艺路线、材料 | 切削参数（速度v、进给f、背吃刀量ap、转速n） |
| NCAgent | 生成 NC 代码 | 工艺路线、切削参数 | G代码/M代码程序 |
| VerificationAgent | 验证工艺合理性 | 完整工艺方案 | 验证结果（是否有效、问题列表、总结） |
| RepairAgent | 根据验证结果优化方案 | 验证问题列表 | 优化建议与修复方案 |

### 工作流编排器 (`python/app/ai/workflow.py`)

工作流编排器负责协调六个 Agent 的顺序执行，跟踪每个阶段的进度和状态：

```python
class WorkflowOrchestrator:
    async def execute_workflow(user_input: str, progress_callback=None) -> dict:
        """执行完整工作流，返回包含所有阶段结果的完整响应"""
        pass
```

**工作流程**：
1. 初始化 `AgentContext` 上下文对象
2. 按顺序执行六个 Agent
3. 每个阶段更新进度回调
4. 收集各阶段结果并返回

### RAG 知识库 (`python/app/rag/knowledge_base.py`)

基于 ChromaDB 的向量知识库，支持语义相似度检索：

```python
class KnowledgeBase:
    def __init__(self, persist_dir: str = "./chroma_db")
    def add_knowledge(document: str, metadata: dict = None, doc_id: str = None) -> str
    def query(query_text: str, n_results: int = 5) -> dict
    def delete(doc_id: str)
    def count() -> int
    def load_default_knowledge()
```

**关键特性**：
- 使用 ChromaDB 持久化存储
- 支持语义向量检索
- 自动加载默认制造工艺知识（10 条基础条目）
- 支持动态添加/删除知识

### 默认工艺知识（10 条）

| ID | 类型 | 内容 |
|----|------|------|
| turning_basic | 车削加工 | 车削基本原理与切削用量 |
| milling_basic | 铣削加工 | 铣削方法分类与参数定义 |
| drilling_basic | 钻孔加工 | 钻头选择与切削参数 |
| grinding_basic | 磨削加工 | 磨削分类与磨削用量 |
| steel_45_properties | 材料参数 | 45钢化学成分与力学性能 |
| aluminum_6061_properties | 材料参数 | 6061铝合金成分与T6状态参数 |
| surface_roughness | 标准 | 表面粗糙度 Ra 等级体系 |
| it_tolerance | 标准 | IT 公差等级体系（IT6-IT14） |
| gcode_basic | NC代码 | 常用G代码（G00-G90） |
| mcode_basic | NC代码 | 常用M代码（M00-M30） |

### Agent 上下文模型 (`AgentContext`)

```python
class AgentContext(BaseModel):
    user_input: str              # 用户原始输入
    extracted_params: dict       # UnderstandingAgent 提取的参数
    process_route: list          # PlanningAgent 生成的工艺路线
    cutting_parameters: dict     # ParameterAgent 计算的切削参数
    nc_code: str                 # NCAgent 生成的 NC 代码
    verification_result: dict    # VerificationAgent 验证结果
    repair_suggestions: list     # RepairAgent 优化建议
    current_stage: str           # 当前执行阶段
    stage_status: str            # 当前阶段状态
```

---

## 实现的文件

### 后端 Python 文件

| 文件路径 | 描述 |
|----------|------|
| `python/app/rag/__init__.py` | RAG 模块初始化 |
| `python/app/rag/knowledge_base.py` | ChromaDB 知识库实现 |
| `python/app/rag/routes.py` | 知识库 API 路由 |
| `python/app/ai/agents.py` | 六个 Agent 实现 |
| `python/app/ai/workflow.py` | 工作流编排器 |
| `python/app/ai/workflow_routes.py` | 工作流 API 路由 |
| `python/app/models/schemas.py` | 数据模型（新增 ProcessPlanRequest 等） |
| `python/app/main.py` | 注册新路由（workflow_router, knowledge_router） |
| `python/requirements.txt` | 新增 chromadb>=0.4.0 依赖 |

### 前端 Vue 文件

| 文件路径 | 描述 |
|----------|------|
| `src/views/ProcessPlan.vue` | 工艺规划页面（完整实现） |

---

## API 路由详解

### 工作流路由 (`/api/workflow`)

| 路由 | 方法 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/workflow/process-plan` | POST | 触发完整工艺规划工作流 | `{user_input: string}` | `{user_input, extracted_params, process_route, cutting_parameters, nc_code, verification_result, repair_suggestions, stage_results, total_stages, completed_stages}` |

### 知识库路由 (`/api/knowledge`)

| 路由 | 方法 | 描述 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/api/knowledge/health` | GET | 知识库健康检查 | - | `{status: string, count: int}` |
| `/api/knowledge/add` | POST | 添加知识条目 | `{document, metadata, doc_id}` | `{doc_id: string}` |
| `/api/knowledge/query` | POST | 查询相关知识 | `{query_text, n_results}` | `{documents, metadatas, distances, ids}` |
| `/api/knowledge/delete` | POST | 删除知识条目 | `{doc_id}` | - |
| `/api/knowledge/count` | GET | 获取知识数量 | - | `{count: int}` |
| `/api/knowledge/init` | POST | 加载默认知识 | - | `{count: int}` |

---

## 前端页面实现 (`src/views/ProcessPlan.vue`)

### 功能清单

- [x] 用户输入制造需求（多行文本框）
- [x] 显示工作流六阶段进度（Steps 组件）
- [x] 显示进度百分比（Progress 组件）
- [x] 展示提取的参数（Descriptions 组件）
- [x] 展示工艺路线（Table 组件）
- [x] 展示切削参数（Table 组件）
- [x] 展示 NC 代码（代码高亮块）
- [x] 展示验证结果（Alert + Table）
- [x] 展示修复建议（内容区）
- [x] 重置表单功能
- [x] 加载状态管理

### 技术栈

- Vue 3 Composition API (`<script setup>`)
- Element Plus UI 组件库
- Axios HTTP 客户端

---

## 部署与运行

### 1. 安装依赖

```bash
cd python
pip install -r requirements.txt
```

新增依赖：`chromadb>=0.4.0`

### 2. 启动后端服务

```bash
cd python
python -m app.main
```

服务默认运行在 `http://127.0.0.1:8765`

### 3. 初始化知识库（可选）

```bash
curl -X POST http://127.0.0.1:8765/api/knowledge/init
```

### 4. 测试 API

```bash
# 健康检查
curl http://127.0.0.1:8765/api/knowledge/health

# 触发工艺规划
curl -X POST http://127.0.0.1:8765/api/workflow/process-plan \
  -H "Content-Type: application/json" \
  -d '{"user_input": "需要加工一个45钢材质的传动轴，直径30mm，长度100mm，公差IT7，表面粗糙度Ra0.8"}'
```

### 5. 启动前端

```bash
pnpm dev
```

访问 `http://localhost:5173` 查看前端页面。

---

## 验证清单

| # | 验证项 | 状态 | 说明 |
|---|--------|------|------|
| 1 | ChromaDB 知识库初始化成功 | ✅ | `KnowledgeBase` 类已实现，支持持久化存储 |
| 2 | 六 Agent 协同工作流正常运行 | ✅ | `WorkflowOrchestrator` 已实现顺序执行 |
| 3 | 工作流 API 返回完整结果 | ✅ | `POST /api/workflow/process-plan` 返回所有字段 |
| 4 | 前端页面完整实现 | ✅ | `ProcessPlan.vue` 展示完整工作流 |
| 5 | 知识库 CRUD 功能正常 | ✅ | 支持 add/query/delete/count/init |
| 6 | 工艺验证功能正常 | ✅ | `VerificationAgent` 验证并返回问题列表 |
| 7 | 修复建议功能正常 | ✅ | `RepairAgent` 根据问题生成优化建议 |

---

## 技术决策

### 为什么选择 ChromaDB？

1. **轻量级**：无需外部数据库服务，本地持久化
2. **向量检索**：支持语义相似度搜索，适合知识检索
3. **Python 原生**：与 FastAPI 集成简单
4. **嵌入模型**：内置默认嵌入模型，开箱即用

### Agent 执行模式

采用**顺序执行**模式，每个 Agent 的输出作为下一个 Agent 的输入，确保：
- 数据流清晰
- 调试方便
- 支持中间状态保存
- 进度实时反馈

### 错误处理策略

- 每个 Agent 内部捕获异常，返回默认值确保流程继续
- 工作流编排器捕获整体异常，返回已完成阶段的结果
- API 层统一错误响应格式

---

## 后续优化方向

1. **并行执行**：ParameterAgent 和 NCAgent 可考虑并行化
2. **缓存机制**：相似需求的工艺结果缓存
3. **流式输出**：SSE 实时推送工作流进度
4. **知识库管理**：前端可视化知识管理界面
5. **模型微调**：针对制造工艺知识微调专用模型
6. **验证规则引擎**：基于规则的确定性验证替代 LLM 验证

---

## 相关文档

- [Phase 3 - 本地 LLM 集成](../05-Phase3-本地LLM集成.md)
- [Phase 6 - 用户界面](../08-Phase6-用户界面.md)
- [Phase 4 - 3D CAD 引擎](../06-Phase4-3D-CAD引擎.md)
- [文档索引](../00-文档索引.md)
