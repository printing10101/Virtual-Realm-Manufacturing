# 灵境制造优化蓝图 → Trae Solo 提示词集

> **目的**：把 [OPTIMIZATION_BLUEPRINT.md](OPTIMIZATION_BLUEPRINT.md) 拆解为 Trae Solo 模式可直接执行的提示词。
> **原则**：每一步都有明确的"目标 / 范围 / 输入 / 输出 / 验收标准 / 完成定义"，可独立执行。
> **用法**：按顺序或并行给 Solo 投喂，每步完成必须通过验收再进入下一步。

---

## 〇、Solo 任务设计规范（先读这一段）

### 0.1 什么是"好的 Solo 任务"
- **单一目标**：一个任务只解决一个明确问题
- **可验证**：有可量化的验收标准
- **有边界**：明确"做什么"和"不做什么"
- **可降级**：失败时有 fallback 路径
- **有产物**：产出明确的代码/文档/配置

### 0.2 任务结构（每个 Solo 任务必须包含）
```
1. 上下文：项目背景 + 当前阶段
2. 目标：一句话说明
3. 范围：做什么 / 不做什么
4. 输入：要读的文件、要用的工具
5. 输出：要创建/修改的文件
6. 验收标准：可量化的检查点
7. 验收步骤：具体的命令/操作
8. 完成定义：什么状态算"完成"
9. 注意事项：易踩的坑
```

### 0.3 通用前置（每个任务开头都引用）
> 在执行任何任务前，必须先读：
> 1. `docs/wiki/README.md` — 项目 Code Wiki 入口
> 2. `docs/wiki/03-目录结构与代码地图.md` — 目录结构
> 3. 对应模块的 Code Wiki（如做 LNN 就读 `05-AI-LNN推理引擎.md`）
> 4. `docs/OPTIMIZATION_BLUEPRINT.md` — 整体蓝图
> 5. 上一阶段的"完成报告"（如有）

### 0.4 通用禁止
- ❌ 不修改未在"范围"内列出的文件
- ❌ 不引入未声明的新依赖
- ❌ 不删现有功能（除非明确允许）
- ❌ 不重写未要求重构的代码
- ❌ 不写未要求的前端/后端代码

---

## 一、主线任务（M0-M6）

### 阶段总览

| 阶段 | 目标 | 步骤数 |
|------|------|--------|
| **M0 基础设施** | 数据底座就绪 | 5 |
| **M1 知识图谱** | 工艺知识图谱 V1 | 5 |
| **M2 数字孪生** | 仿真引擎上线 | 5 |
| **M3 智能推理** | 贝叶斯 LNN + 主动学习 | 5 |
| **M4 闭环飞轮** | 自进化数据流 | 4 |
| **M5 体验生态** | 工艺师 Co-pilot + 协议 | 5 |
| **M6 商业化** | 商业模式 + 标准化 | 4 |

**总 33 个主线任务** + 7 个 L2 并行轨道。

---

## 二、M0 基础设施（数据底座）

### 任务 M0.1：现状评估与基线测量

**上下文**：APT 的核心是"数据飞轮"。启动任何代码改动前，必须先量化"现在"是什么样。

**目标**：建立"现状基线"，作为后续所有改进的对照基准。

**范围**：
- ✅ 梳理现有 LNN 推理路径，统计平均耗时
- ✅ 梳理现有工艺规划流程，记录"方案生成成功率"
- ✅ 梳理现有用户操作路径，记录"工艺师规划耗时"
- ✅ 检查现有日志、审计、错误样本
- ❌ 不写任何新代码

**输入**：
- `python/app/`（后端代码）
- `src/`（前端代码）
- `logs/audit/audit_log.jsonl`（审计日志）
- `data/trace_log.jsonl`（轨迹日志）

**输出**：
- `docs/baseline/baseline-report-v1.md`：包含以下数据
  - LNN 推理平均/中位/P95 耗时
  - 工艺规划任务的成功率
  - 工艺师规划耗时分布
  - 错误类型 Top 10
  - 现有功能清单 + 覆盖率

**验收标准**：
- 报告文件存在
- 报告包含上述 5 类数据
- 每类数据至少有具体数字（不是"未知"）
- 数据采集方法可复现

**验收步骤**：
```bash
# 1. 检查报告存在
test -f docs/baseline/baseline-report-v1.md

# 2. 检查报告完整性
grep -E "LNN 推理|工艺规划|工艺师规划|错误类型|功能清单" docs/baseline/baseline-report-v1.md
# 期望：5 行都匹配

# 3. 报告字数 > 2000 字
wc -w docs/baseline/baseline-report-v1.md | awk '{print $1}' | grep -E "^[2-9][0-9]{3}|[1-9][0-9]{4,}"
```

**完成定义**：基线报告通过上述 3 个检查项。

**注意事项**：
- 没有数据时，**写"未采集"**而不是编造
- 时间窗口说明清楚（用了多少天的日志）
- LLM 不要做主观判断，只做数据呈现

---

### 任务 M0.2：TDengine 时序数据库引入

**上下文**：APT 需要存储机床时序数据（主轴转速、振动、温度等）。PostgreSQL 存这类数据效率低。

**目标**：在本地 docker-compose 部署 TDengine，验证可写入、可查询。

**范围**：
- ✅ 在 `docker-compose.yml` 新增 `lnn-tdengine` 服务
- ✅ 创建 Python 客户端封装（`python/app/services/tdengine_client.py`）
- ✅ 编写连接 + 写入 + 查询的最小测试
- ✅ 与 FastAPI 集成（提供 `get_tdengine()` 依赖）
- ❌ 不实现任何业务写入逻辑
- ❌ 不修改现有 LNN / RAG / DXF 代码

**输入**：
- `docker-compose.yml`
- `python/app/services/redis_client.py`（参考其实现风格）
- `python/app/database/connection.py`（参考其依赖注入风格）

**输出**：
- `docker-compose.yml`（修改，新增 tdengine service）
- `python/app/services/tdengine_client.py`（新建）
- `python/app/services/tests/test_tdengine_client.py`（新建）
- `python/requirements.txt`（如需新增依赖则添加，注明原因）

**验收标准**：
- TDengine 容器可启动
- Python 客户端可连接
- 可创建一个测试表并写入 1000 条数据
- 可按时间范围查询这 1000 条数据
- 单元测试通过

**验收步骤**：
```bash
# 1. 启动 TDengine
docker compose up -d lnn-tdengine

# 2. 等待健康
docker compose ps lnn-tdengine | grep "Up" | grep "healthy"

# 3. 运行测试
cd python && python -m pytest app/services/tests/test_tdengine_client.py -v
# 期望：所有测试 PASS

# 4. 手动验证连接
cd python && python -c "from app.services.tdengine_client import get_tdengine; c = get_tdengine(); print('OK')"
# 期望：输出 "OK"（或对应连接信息）
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- TDengine 容器初始化可能需要 10-30 秒，**写脚本时加重试**
- 不要在 `requirements.txt` 锁定小版本（避免冲突）
- 健康检查用 `taos` 命令行 + `/api/health` 端点
- 如 TDengine 启动失败，记录具体错误信息到 `docs/baseline/tdengine-setup-issues.md`

---

### 任务 M0.3：MTConnect 适配器 V1

**上下文**：从机床采集主轴转速、进给、功率等数据是 APT 数据底座的核心。

**目标**：实现一个能连接 MTConnect Agent（模拟器）并采集数据的 Python 适配器。

**范围**：
- ✅ 实现 `python/app/integrations/mtconnect/adapter.py`
- ✅ 解析 MTConnect XML/HTTP 响应
- ✅ 支持基本数据项：spindle_speed、spindle_load、feedrate、execution
- ✅ 写入 TDengine（用 M0.2 的客户端）
- ✅ 提供简单的 CLI 测试脚本
- ❌ 不实现与具体机型的协议层
- ❌ 不实现错误恢复（先 happy path）
- ❌ 不写前端

**输入**：
- `python/app/services/tdengine_client.py`（M0.2 产物）
- MTConnect 协议文档（标准 1.5+）
- 测试用的 MTConnect Agent（公开的 demo 即可）

**输出**：
- `python/app/integrations/__init__.py`（新建）
- `python/app/integrations/mtconnect/__init__.py`（新建）
- `python/app/integrations/mtconnect/adapter.py`（新建）
- `python/app/integrations/mtconnect/parser.py`（新建）
- `python/app/integrations/mtconnect/cli.py`（新建，提供 `python -m ...mtconnect.cli`）
- `python/app/integrations/mtconnect/tests/test_adapter.py`（新建）
- `docs/integrations/mtconnect-usage.md`（使用说明）

**验收标准**：
- 适配器可连接公开 demo MTConnect Agent
- 解析 4 类数据项
- 实时数据写入 TDengine 成功
- 单元测试通过
- CLI 可手动运行并打印采集数据

**验收步骤**：
```bash
# 1. 运行单元测试
cd python && pytest app/integrations/mtconnect/tests/ -v

# 2. CLI 手动运行（用 demo agent）
cd python && timeout 30 python -m app.integrations.mtconnect.cli --agent http://demo.mtconnect.org:80 --duration 20 --output tds://localhost:6030/test.mtconnect
# 期望：看到实时数据流输出和"已写入 N 条"消息

# 3. 查询验证
cd python && python -c "
from app.services.tdengine_client import get_tdengine
c = get_tdengine()
result = c.query('SELECT COUNT(*) FROM test.mtconnect')
print('Records:', result)
"
# 期望：记录数 > 0
```

**完成定义**：3 个验收步骤全部通过 + 使用文档存在。

**注意事项**：
- MTConnect 协议是 XML over HTTP，**不要用正则解析 XML**，用 `lxml` 或 `xml.etree.ElementTree`
- 数据采样频率默认 1Hz，**可配置**
- TDengine 写入要批量（**不要每条都 commit**）
- 失败重试用指数退避，**不要无限重试**
- **本任务成功标准是"能跑通 demo"，不是"能上生产"**

---

### 任务 M0.4：MachiningRecord 统一数据模型

**上下文**：车间数据需要统一结构才能分析、回灌、训练。

**目标**：定义完整的 MachiningRecord 数据模型，落地为 Pydantic + SQLAlchemy 双实现。

**范围**：
- ✅ Pydantic 模型 `python/app/models/machining_record.py`
- ✅ SQLAlchemy ORM `python/app/database/models/machining_record.py`
- ✅ Alembic 迁移脚本
- ✅ Repository 模式封装 CRUD
- ✅ 与 TDengine 时序数据关联
- ❌ 不实现数据回灌逻辑（后续任务）
- ❌ 不写 API 端点

**输入**：
- `python/app/models/schemas.py`（参考 Pydantic 风格）
- `python/app/database/models.py`（参考 SQLAlchemy 风格）
- `python/app/database/connection.py`（参考依赖注入）
- 优化蓝图 3.1.3 节的 dataclass 定义

**输出**：
- `python/app/models/machining_record.py`
- `python/app/database/models/machining_record.py`
- `python/alembic/versions/xxxx_add_machining_records.py`（迁移）
- `python/app/database/repository/machining_record_repo.py`
- `python/app/models/tests/test_machining_record.py`

**验收标准**：
- Pydantic 模型可序列化/反序列化
- SQLAlchemy 模型可建表
- 迁移可执行（`alembic upgrade head` 成功）
- 可插入/查询/更新/删除
- 单元测试覆盖主要路径

**验收步骤**：
```bash
# 1. 迁移执行
cd python && alembic upgrade head
# 期望：无错误

# 2. 验证表存在
docker compose exec -T lnn-postgres psql -U postgres -d lnn -c "\dt machining_records"
# 期望：表存在

# 3. 运行单元测试
cd python && pytest app/models/tests/test_machining_record.py -v

# 4. CRUD 集成测试
cd python && python -c "
from app.database.repository.machining_record_repo import MachiningRecordRepository
from app.models.machining_record import MachiningRecordCreate
# 创建、查询、更新、删除
print('CRUD OK')
"
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- **JSON 字段**用 PostgreSQL `JSONB`（不是 TEXT）
- **时序字段**存的是引用 ID，**不存实际数据**（实际数据在 TDengine）
- **索引**：machine_id、tool_id、material、timestamp 都加索引
- **数据验证**：用 Pydantic 验证范围（如 spindle_speed >= 0）
- **不要过度设计**：5-7 个核心字段足够

---

### 任务 M0.5：数据采集管道 V1

**上下文**：有了模型，需要从"能存"到"能采"。

**目标**：构建从 MTConnect 适配器到 MachiningRecord 的端到端采集管道。

**范围**：
- ✅ 实现 `python/app/pipelines/machining_collector.py`
- ✅ MTConnect 数据 → MachiningRecord 转换器
- ✅ 后台任务：定时拉取 + 批量写入
- ✅ 与 AsyncTaskManager 集成
- ❌ 不做实时分析
- ❌ 不做数据清洗
- ❌ 不写前端监控

**输入**：
- M0.3 的 MTConnect 适配器
- M0.4 的 MachiningRecord 模型
- `python/app/tasks/task_system.py`（参考任务模式）

**输出**：
- `python/app/pipelines/__init__.py`
- `python/app/pipelines/machining_collector.py`
- `python/app/pipelines/converter.py`
- `python/app/pipelines/tests/test_collector.py`
- `docs/pipelines/collector-usage.md`

**验收标准**：
- 可启动后台采集任务
- 模拟数据流过完整管道
- 数据正确写入 PostgreSQL + TDengine
- 任务可停止、可查询状态
- 异常不导致进程崩溃

**验收步骤**：
```bash
# 1. 启动采集任务
cd python && python -c "
import asyncio
from app.pipelines.machining_collector import start_collector
asyncio.run(start_collector(duration=60, agent_url='http://demo.mtconnect.org:80'))
"

# 2. 等待 60 秒后查询
docker compose exec -T lnn-postgres psql -U postgres -d lnn -c "SELECT COUNT(*) FROM machining_records;"

# 3. 单元测试
cd python && pytest app/pipelines/tests/test_collector.py -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **批量写入**：每 5 秒或 100 条 flush 一次
- **时序数据 → 关系数据映射**：考虑时序是 N 条记录 vs 关系是 1 条加工记录
- **采样频率**：默认 1Hz，可配置
- **错误处理**：MTConnect 断线重连，TDengine/PG 写入失败入队重试
- **不要做数据清洗**（那是后续任务）

---

## 三、M1 知识图谱（5 个任务）

### 任务 M1.1：极简本体设计

**上下文**：知识图谱不是"导入 JSON 就能用"，需要先设计本体。

**目标**：定义 4 类核心实体（Material/Tool/Feature/Process）+ 4 类关系的本体 schema。

**范围**：
- ✅ 设计 schema（JSON Schema 或 Pydantic）
- ✅ 4 类实体的属性定义
- ✅ 4 类关系的属性定义（含"可信度"）
- ✅ 文档化 schema
- ❌ 不实现存储
- ❌ 不导入数据

**输入**：
- 优化蓝图 3.2.1 节
- `python/app/data/materials.json`、`tools.json`、`process_rules.json`
- `python/app/database/data/machines.json`

**输出**：
- `docs/knowledge-graph/ontology-v1.md`（本体说明文档）
- `python/app/models/knowledge_graph.py`（Pydantic 模型）

**验收标准**：
- 文档描述了 4 类实体的所有属性
- 4 类关系定义清晰
- 有图示（用 mermaid 即可）
- Pydantic 模型可验证

**验收步骤**：
```bash
# 1. 文档存在
test -f docs/knowledge-graph/ontology-v1.md

# 2. Pydantic 模型可导入
cd python && python -c "from app.models.knowledge_graph import Material, Tool, Feature, Process; print('OK')"

# 3. 包含 mermaid 图
grep -E "```mermaid" docs/knowledge-graph/ontology-v1.md
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **极简**：4 类实体、4 类关系，**不要扩展**
- **每个属性都要可空或有默认**，避免后续数据缺失阻塞
- **关系要有 source 字段**：是来自 rule、llm、实测、还是 manual
- **不要发明新术语**，用制造业通用术语

---

### 任务 M1.2：NetworkX 图存储 + PG 持久化

**上下文**：先简单后扩展，NetworkX + 持久化到 PG 是最稳的起步。

**目标**：实现图存储层，支持基本 CRUD 与查询。

**范围**：
- ✅ NetworkX 图封装
- ✅ 与 PostgreSQL 双向同步（graph ↔ tables）
- ✅ Repository 模式
- ✅ 基本查询：按实体类型、关系类型、可信度
- ❌ 不做图算法（最短路径、PageRank）
- ❌ 不做分布式

**输入**：
- M1.1 的 Pydantic 模型
- `python/app/database/connection.py`（参考依赖注入）
- `python/app/database/repository/`（参考风格）

**输出**：
- `python/app/knowledge_graph/__init__.py`
- `python/app/knowledge_graph/graph_store.py`
- `python/app/knowledge_graph/persistence.py`
- `python/app/knowledge_graph/repository.py`
- `python/app/knowledge_graph/tests/test_graph_store.py`
- `python/alembic/versions/xxxx_add_kg_tables.py`（迁移）

**验收标准**：
- 可创建节点、关系
- 可按 ID 查询节点
- 可按类型查询节点
- 可按关系类型查询
- 数据持久化到 PG，重启后不丢失

**验收步骤**：
```bash
# 1. 迁移
cd python && alembic upgrade head

# 2. 单元测试
cd python && pytest app/knowledge_graph/tests/test_graph_store.py -v

# 3. 端到端测试
cd python && python -c "
from app.knowledge_graph.graph_store import GraphStore
g = GraphStore()
g.add_node('material', 'M-45steel', {'name': '45 steel'})
g.add_node('tool', 'T-endmill-10', {'name': 'Endmill D10'})
g.add_edge('T-endmill-10', 'M-45steel', 'SUITABLE_FOR', {'confidence': 0.9})
# 重启
g2 = GraphStore()
print('Node count:', g2.node_count())
"
# 期望：>= 2
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **节点 ID 用字符串**，用 `<type>-<slug>` 格式
- **不要用 NetworkX 自带的存储**（不支持事务），自行序列化到 PG
- **JSON 字段**：属性存 JSONB
- **索引**：node_id、node_type、edge_type
- **本任务不要做查询优化**，先正确再说

---

### 任务 M1.3：从现有 JSON 导入

**上下文**：现有 4 个 JSON 是图谱的冷启动数据源。

**目标**：把现有 JSON 转换为图谱节点和关系，写入图谱。

**范围**：
- ✅ 4 个 JSON 的导入脚本
- ✅ 实体映射规则（材料、刀具、机床、规则）
- ✅ 关系推断（基于规则 IF-THEN 结构）
- ✅ 重复检测
- ❌ 不做数据清洗
- ❌ 不做冲突解决（先取第一个）

**输入**：
- `python/app/data/materials.json`
- `python/app/data/tools.json`
- `python/app/database/data/machines.json`
- `python/app/data/process_rules.json`
- M1.1 Pydantic 模型
- M1.2 图存储

**输出**：
- `python/app/knowledge_graph/importer/__init__.py`
- `python/app/knowledge_graph/importer/json_importer.py`
- `python/app/knowledge_graph/importer/rule_parser.py`
- `python/app/knowledge_graph/importer/tests/test_importer.py`
- `docs/knowledge-graph/import-results.md`（导入结果统计）

**验收标准**：
- 4 个 JSON 全部导入
- 至少生成 30 个节点 + 50 条关系
- 重复数据被识别
- 导入结果有统计报告

**验收步骤**：
```bash
# 1. 运行导入
cd python && python -m app.knowledge_graph.importer.json_importer
# 期望：输出"导入完成：X 节点 Y 关系"

# 2. 验证节点数
cd python && python -c "
from app.knowledge_graph.graph_store import GraphStore
g = GraphStore()
print('Nodes:', g.node_count())
print('Edges:', g.edge_count())
"
# 期望：节点 >= 30，关系 >= 50

# 3. 单元测试
cd python && pytest app/knowledge_graph/importer/tests/ -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **每个 JSON 一个独立导入函数**，不要写"通用 JSON 解析器"
- **规则解析**：IF-THEN 拆出"条件"和"动作"，对应 1-2 条关系
- **去重键**：material 用名称，tool 用型号+直径，machine 用 ID
- **导入失败要可重试**（不要一半一半）
- **生成统计报告**，列出来源 JSON、节点类型分布

---

### 任务 M1.4：LLM 辅助抽取（PDF/Word 文档）

**上下文**：车间有大量历史工艺文档（PDF/Word），是知识图谱的扩展源。

**目标**：用 LLM 从历史 PDF 工艺文档中抽取实体和关系。

**范围**：
- ✅ PDF/Word 文本提取
- ✅ LLM 抽取 prompt 模板
- ✅ 抽取结果验证
- ✅ 人工审核界面（基础版）
- ❌ 不做自动审核
- ❌ 不做实时抽取

**输入**：
- M1.1 Pydantic 模型
- M1.2 图存储
- 现有 LLM 客户端（`python/app/ai/llm_client.py`）
- 测试用 PDF 文档（2-3 个真实工艺卡片）

**输出**：
- `python/app/knowledge_graph/extractor/__init__.py`
- `python/app/knowledge_graph/extractor/pdf_extractor.py`
- `python/app/knowledge_graph/extractor/llm_extractor.py`
- `python/app/knowledge_graph/extractor/prompts.py`
- `python/app/knowledge_graph/extractor/validator.py`
- `python/app/knowledge_graph/extractor/tests/test_extractor.py`
- `docs/knowledge-graph/llm-extraction-guide.md`

**验收标准**：
- 可读取 PDF
- 可用本地 LLM 抽取实体/关系
- 抽取结果有可信度评分
- 单元测试通过
- 文档说明使用方式

**验收步骤**：
```bash
# 1. 准备测试 PDF（如果没有，从仓库 docs/knowledge-graph/samples/ 取）
# 2. 运行抽取
cd python && python -m app.knowledge_graph.extractor.llm_extractor \
  --input docs/knowledge-graph/samples/sample-process-card.pdf \
  --output /tmp/extraction-result.json
# 期望：输出 JSON 包含 entities 和 relations

# 3. 验证结果有内容
cat /tmp/extraction-result.json | python -c "
import json, sys
data = json.load(sys.stdin)
assert len(data['entities']) > 0, 'no entities'
assert len(data['relations']) > 0, 'no relations'
print('OK')
"

# 4. 单元测试
cd python && pytest app/knowledge_graph/extractor/tests/ -v
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- **Prompt 要具体**：给 LLM 明确的 entity types 和 relation types
- **批量处理**：PDF 一次不要传超过 10 页
- **失败重试**：LLM 调用失败要重试 3 次
- **抽取结果默认未审核**，写图谱前要标记 `unverified`
- **不要追求 100% 准确**，目标 70%+ 即可
- **采样 PDF 要脱敏**（不含真实客户信息）

---

### 任务 M1.5：图谱健康检查

**上下文**：图谱会随时间"老化"，需要定期检查。

**目标**：实现图谱健康检查系统，识别孤立节点、矛盾关系、老旧数据。

**范围**：
- ✅ 孤立节点检测（无任何关系）
- ✅ 矛盾关系检测（A→B 关系 vs B→A 关系）
- ✅ 老旧数据检测（5 年未更新）
- ✅ 报告生成（Markdown）
- ❌ 不做自动修复
- ❌ 不做实时监控

**输入**：
- M1.2 图存储
- M1.1 Pydantic 模型

**输出**：
- `python/app/knowledge_graph/health/__init__.py`
- `python/app/knowledge_graph/health/checker.py`
- `python/app/knowledge_graph/health/report.py`
- `python/app/knowledge_graph/health/tests/test_checker.py`
- `docs/knowledge-graph/health-check-results.md`（首次检查报告）

**验收标准**：
- 可识别孤立节点
- 可识别矛盾关系
- 可识别老旧数据
- 生成可读报告
- 单元测试覆盖

**验收步骤**：
```bash
# 1. 注入测试数据（孤立节点、矛盾关系等）
# 2. 运行健康检查
cd python && python -m app.knowledge_graph.health.checker --output docs/knowledge-graph/health-check-results.md
# 期望：报告生成成功

# 3. 检查报告内容
grep -E "孤立|矛盾|老旧" docs/knowledge-graph/health-check-results.md

# 4. 单元测试
cd python && pytest app/knowledge_graph/health/tests/ -v
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- **健康检查要快**：< 30 秒
- **不要修改图谱**，只读
- **报告要可读**，不是 JSON
- **可定时运行**（后续接 cron）

---

## 四、M2 数字孪生仿真（5 个任务）

### 任务 M2.1：切削力 PINN 实现

**上下文**：数字孪生最基础的是"算力"。

**目标**：实现一个用 PINN（物理约束神经网络）预测切削力的模块。

**范围**：
- ✅ Kienzle 切削力公式（解析部分）
- ✅ PyTorch 神经网络（残差学习）
- ✅ 物理损失 + 数据损失
- ✅ 训练脚本（用合成数据）
- ✅ 推理接口
- ❌ 不做实测数据训练（后续任务）
- ❌ 不做温度/振动

**输入**：
- Kienzle 公式（标准切削力学）
- PyTorch 现有训练模式（参考 `python/app/ai/lnn/training/`）
- 优化蓝图 3.3.2 节

**输出**：
- `python/app/simulation/__init__.py`
- `python/app/simulation/cutting_force/__init__.py`
- `python/app/simulation/cutting_force/kienzle.py`（解析公式）
- `python/app/simulation/cutting_force/pinn.py`（PINN 模型）
- `python/app/simulation/cutting_force/trainer.py`（训练）
- `python/app/simulation/cutting_force/predictor.py`（推理）
- `python/app/simulation/cutting_force/tests/`
- `docs/simulation/cutting-force-usage.md`

**验收标准**：
- PINN 模型可训练（loss 下降）
- 推理速度 < 50ms / 次
- 物理损失项生效（解析公式预测的 Fz 方向与神经网络接近）
- 单元测试通过
- 使用文档完整

**验收步骤**：
```bash
# 1. 训练模型（合成数据）
cd python && python -m app.simulation.cutting_force.trainer --epochs 100
# 期望：loss 持续下降

# 2. 推理测试
cd python && python -c "
from app.simulation.cutting_force.predictor import predict_cutting_force
result = predict_cutting_force(material='45steel', tool='endmill_d10', params={'speed': 3500, 'feed': 1200, 'depth': 1.5})
print(result)
"
# 期望：返回 {Fx, Fy, Fz} 数值

# 3. 性能测试
cd python && python -c "
import time
from app.simulation.cutting_force.predictor import predict_cutting_force
start = time.time()
for _ in range(100):
    predict_cutting_force(material='45steel', tool='endmill_d10', params={'speed': 3500, 'feed': 1200, 'depth': 1.5})
print(f'Avg: {(time.time() - start) / 100 * 1000:.2f}ms')
"
# 期望：< 50ms

# 4. 单元测试
cd python && pytest app/simulation/cutting_force/tests/ -v
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- **PINN 的物理损失项权重**：先 0.1，看 loss 曲线再调
- **Kienzle 系数 kc1.1**：从 `process_rules.json` 取或硬编码常用值
- **模型要小**（< 100K 参数），不要做大模型
- **输入归一化**：切削参数先归一化到 [0, 1]
- **不要追求 99% 准确率**，目标 80%+ 即可

---

### 任务 M2.2：振动/颤振稳定性模块

**上下文**：颤振是加工失效主因之一，必须能预测。

**目标**：实现颤振稳定性极限预测。

**范围**：
- ✅ 稳定性叶图算法（解析法）
- ✅ 神经网络加速预测
- ✅ 输入：主轴/刀具刚性、转速、切深
- ✅ 输出：稳定/不稳定 + 极限切深
- ❌ 不做时域仿真
- ❌ 不做多模态耦合

**输入**：
- 切削动力学（稳定性叶图理论）
- M2.1 的 simulation 模块结构

**输出**：
- `python/app/simulation/chatter/__init__.py`
- `python/app/simulation/chatter/stability.py`（解析）
- `python/app/simulation/chatter/predictor.py`（神经网络）
- `python/app/simulation/chatter/tests/`
- `docs/simulation/chatter-usage.md`

**验收标准**：
- 解析法和神经网络结果接近
- 推理 < 50ms
- 单元测试通过
- 使用文档

**验收步骤**：
```bash
# 1. 推理测试
cd python && python -c "
from app.simulation.chatter.predictor import predict_stability
result = predict_stability(spindle_rpm=8000, machine='VMC-850', tool='endmill_d10', workpiece='aluminum')
print(result)
"
# 期望：返回 {stable: bool, limit_depth: float}

# 2. 单元测试
cd python && pytest app/simulation/chatter/tests/ -v
```

**完成定义**：2 个验收步骤全部通过。

**注意事项**：
- **稳定性的解析法**：基于 Tlusty 公式
- **机器刚性参数**：从 `machines.json` 读取，没有则用默认值
- **本任务相对独立**，可以单独验证
- **不要引入 scipy 之外的科学计算库**

---

### 任务 M2.3：仿真器与工艺规划集成

**上下文**：仿真是"独立模块"没用，要集成到工艺规划流程。

**目标**：让现有工艺规划流程能调用仿真器。

**范围**：
- ✅ 在 `app/process_planning/` 中添加仿真调用点
- ✅ 仿真结果作为方案评估的一部分
- ✅ 仿真失败的方案标记为"不推荐"
- ✅ 仿真接口封装
- ❌ 不修改现有工艺规划算法
- ❌ 不修改前端

**输入**：
- M2.1 切削力预测
- M2.2 颤振稳定性
- 现有工艺规划代码（`python/app/process_planning/`）

**输出**：
- `python/app/process_planning/sim_integration.py`（仿真集成）
- `python/app/process_planning/tests/test_sim_integration.py`
- `docs/simulation/integration-guide.md`

**验收标准**：
- 工艺规划结果包含仿真评分
- 不通过仿真的方案被标记
- 仿真超时/失败时不阻塞主流程
- 单元测试通过

**验收步骤**：
```bash
# 1. 端到端测试
cd python && python -c "
from app.process_planning.pipeline import plan_process
plan = plan_process(feature='pocket_cavity', material='45steel', tool='endmill_d10')
assert 'simulation' in plan, 'no simulation in plan'
assert 'score' in plan['simulation'], 'no simulation score'
print('OK')
"

# 2. 单元测试
cd python && pytest app/process_planning/tests/test_sim_integration.py -v
```

**完成定义**：2 个验收步骤全部通过。

**注意事项**：
- **仿真超时**：默认 5 秒，超时 fallback 到"未仿真"标记
- **不要强依赖仿真**：仿真失败工艺规划仍要返回结果
- **仿真结果存哪里**：与 plan 同结构，不另存数据库

---

### 任务 M2.4：与 LNN 并行运行

**上下文**：仿真不能替代 LNN，要并行给工艺师"两种声音"。

**目标**：让 LNN 和仿真结果并行展示，标记差异。

**范围**：
- ✅ 对比接口：LNN 输出 vs 仿真输出
- ✅ 差异计算与标记
- ✅ 显著差异（> 30%）标记为"待人工审核"
- ✅ API 端点
- ❌ 不做冲突自动解决
- ❌ 不做前端

**输入**：
- M2.3 集成结果
- 现有 LNN 推理代码
- `python/app/ai/lnn/inference/`

**输出**：
- `python/app/simulation/comparison.py`
- `python/app/api/v1/simulation_comparison.py`
- `python/app/simulation/tests/test_comparison.py`
- `docs/simulation/comparison-guide.md`

**验收标准**：
- API 可返回 LNN + 仿真 + 差异
- 差异阈值可配置
- 单元测试覆盖

**验收步骤**：
```bash
# 1. API 测试
curl -X POST http://localhost:8000/api/v1/simulation/compare \
  -H "Content-Type: application/json" \
  -d '{"feature": "pocket_cavity", "material": "45steel", "tool": "endmill_d10", "lnn_params": {"speed": 3500, "feed": 1200}}'
# 期望：返回 LNN 预测 + 仿真预测 + 差异评分

# 2. 单元测试
cd python && pytest app/simulation/tests/test_comparison.py -v
```

**完成定义**：2 个验收步骤全部通过。

**注意事项**：
- **差异阈值**：默认 30%，可配置
- **不要合并 LNN 和仿真输出**，各自独立
- **不要在前端做特殊处理**（本任务不写前端）

---

### 任务 M2.5：仿真结果可视化（前端）

**上下文**：仿真结果必须"看得见"才有价值。

**目标**：在 Three.js 视图中高亮显示仿真预测的力/温度/振动。

**范围**：
- ✅ Three.js 场景扩展（云图着色器）
- ✅ 仿真结果数据格式
- ✅ 前端组件：仿真查看器
- ✅ 时间轴（如果有动态仿真）
- ❌ 不做 AR 增强
- ❌ 不做剖面视图

**输入**：
- M2.1 切削力预测
- 现有 `src/components/ThreeViewer.vue`
- `src/composables/useThreeScene.ts`

**输出**：
- `src/components/SimulationViewer.vue`（新建）
- `src/composables/useSimulationVisualization.ts`
- `src/api/simulation.ts`（API 客户端）
- `src/components/__tests__/SimulationViewer.test.ts`

**验收标准**：
- 仿真数据可在 3D 视图渲染
- 至少支持力矢量（用箭头表示）
- 性能：单次渲染 < 200ms
- 单元测试覆盖

**验收步骤**：
```bash
# 1. 前端构建
pnpm build

# 2. 单元测试
pnpm test:run -- SimulationViewer

# 3. 手动验证
pnpm dev
# 打开浏览器，访问 /workspace，选择工件，触发仿真，验证 3D 视图有变化
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **着色器复用现有**，不要重写 Three.js 渲染管线
- **颜色映射**：力用蓝→红渐变，温度用相同
- **性能优先**：复杂场景用 LOD
- **本任务只做"显示"，不做"交互"**

---

## 五、M3 智能推理（5 个任务）

### 任务 M3.1：贝叶斯 LNN 改造

**上下文**：LNN 现在是"点估计"，无法表达不确定性。

**目标**：把 LNN 改造为支持 MC Dropout 的贝叶斯近似版本。

**范围**：
- ✅ `BayesianLNN` 类（基于现有 LNN）
- ✅ MC Dropout 推理（50 次采样）
- ✅ 输出 mean + std
- ✅ 保留原 LNN 接口（向后兼容）
- ❌ 不改变训练流程（先用原 LNN 训练）
- ❌ 不替换所有 LNN（先在 1 个端点试）

**输入**：
- `python/app/ai/lnn/models/torch_cfc_model.py`（参考）
- `python/app/ai/lnn/models/torch_ltc_model.py`
- `python/app/ai/lnn/inference/predictor.py`

**输出**：
- `python/app/ai/lnn/models/bayesian_lnn.py`
- `python/app/ai/lnn/inference/bayesian_predictor.py`
- `python/app/ai/lnn/tests/test_bayesian.py`
- `docs/ai/bayesian-lnn-guide.md`

**验收标准**：
- 贝叶斯 LNN 可加载原 LNN 权重
- 推理返回 mean + std
- 推理时间 < 原 LNN × 5（因为 50 次采样）
- 单元测试覆盖
- 文档说明

**验收步骤**：
```bash
# 1. 单元测试
cd python && pytest app/ai/lnn/tests/test_bayesian.py -v

# 2. 推理测试
cd python && python -c "
from app.ai.lnn.inference.bayesian_predictor import BayesianPredictor
import torch
predictor = BayesianPredictor(model_path='models/cfc_v1.pt')
mean, std = predictor.predict_with_uncertainty(torch.randn(1, 8), n_samples=50)
print(f'mean: {mean.shape}, std: {std.shape}')
assert std.abs().max() > 0, 'std should be > 0'
"

# 3. 性能测试（确认 < 5x 原 LNN）
cd python && python -c "
import time
from app.ai.lnn.inference.bayesian_predictor import BayesianPredictor
predictor = BayesianPredictor(model_path='models/cfc_v1.pt')
start = time.time()
for _ in range(10):
    predictor.predict_with_uncertainty(torch.randn(1, 8), n_samples=50)
print(f'Bayesian: {(time.time()-start)/10*1000:.2f}ms')
"
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **不要重新训练**：复用现有 LNN 权重 + MC Dropout 层
- **dropout 概率**：默认 0.1
- **采样数 n_samples**：默认 50，可配置
- **保留原 LNN**：本任务不删除原 LNN 类
- **不要替换所有 LNN 端点**：先在 1 个测试端点试

---

### 任务 M3.2：不确定性量化 API

**上下文**：贝叶斯 LNN 的输出要暴露给上游使用。

**目标**：提供不确定性量化的 API 端点。

**范围**：
- ✅ API 端点：`/api/v1/lnn/predict-uncertain`
- ✅ 返回结构：`{prediction, uncertainty, confidence}`
- ✅ 集成到现有 LNN API
- ❌ 不做前端展示
- ❌ 不做批量

**输入**：
- M3.1 的贝叶斯 LNN
- 现有 LNN API（`python/app/api/v1/lnn.py`）

**输出**：
- `python/app/api/v1/lnn_uncertain.py`（新增端点）
- `python/app/models/schemas.py`（添加 UncertaintyResponse）
- `python/app/api/v1/tests/test_lnn_uncertain.py`

**验收标准**：
- API 返回不确定性
- confidence 字段计算正确（基于 std）
- 单元测试覆盖

**验收步骤**：
```bash
# 1. 启动后端
cd python && uvicorn app.main:app --reload --port 8000

# 2. API 测试
curl -X POST http://localhost:8000/api/v1/lnn/predict-uncertain \
  -H "Content-Type: application/json" \
  -d '{"task": "predict_speed", "input_data": {"material": "45steel", "tool": "endmill_d10"}}'
# 期望：返回 {prediction, uncertainty, confidence}

# 3. 单元测试
cd python && pytest app/api/v1/tests/test_lnn_uncertain.py -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **confidence 计算**：`confidence = 1 - (std / mean).clamp(0, 1)`
- **响应格式**：与现有 LNN API 兼容
- **不修改现有 `/lnn/predict`**，新增端点
- **不要做端点级限流覆盖**（除非必要）

---

### 任务 M3.3：主动学习触发器

**上下文**：有了不确定性，就要知道什么时候"问"工艺师。

**目标**：实现主动学习的触发逻辑。

**范围**：
- ✅ 5 类触发场景的检测器
- ✅ 触发条件可配置
- ✅ 触发后产生"提问事件"
- ❌ 不实现 UI
- ❌ 不做自动学习

**输入**：
- M3.2 不确定性 API
- M1 知识图谱
- 优化蓝图 3.5.1 节

**输出**：
- `python/app/ai/active_learning/__init__.py`
- `python/app/ai/active_learning/triggers.py`
- `python/app/ai/active_learning/events.py`
- `python/app/ai/active_learning/tests/test_triggers.py`
- `docs/ai/active-learning-triggers.md`

**验收标准**：
- 5 类触发全部实现
- 触发事件有结构化格式
- 单元测试覆盖
- 文档说明

**验收步骤**：
```bash
# 1. 单元测试
cd python && pytest app/ai/active_learning/tests/ -v

# 2. 端到端测试
cd python && python -c "
from app.ai.active_learning.triggers import ActiveLearningTrigger
trigger = ActiveLearningTrigger()
# 模拟低置信度
event = trigger.check_uncertainty(confidence=0.3, context={'material': 'titanium'})
print(event)
assert event is not None, 'should trigger'
"
```

**完成定义**：2 个验收步骤全部通过。

**注意事项**：
- **5 类触发独立实现**，不要写"通用触发器"
- **触发事件格式统一**：`{type, reason, context, suggested_action}`
- **不直接调用 UI**，通过事件总线

---

### 任务 M3.4：工艺师 Co-pilot V1（前端）

**上下文**：主动学习的"提问"要在前端呈现。

**目标**：实现 Co-pilot 基础界面：决策透明 + 一键采纳/修改/拒绝。

**范围**：
- ✅ 决策展示组件（"AI 推荐"卡片）
- ✅ 三按钮：采纳/修改/拒绝
- ✅ 决策依据展开
- ✅ 不确定性可视化（进度条）
- ❌ 不做主动提问 UI（V2 再做）
- ❌ 不做 re-simulation 实时联动

**输入**：
- M3.2 不确定性 API
- M3.3 触发器
- 现有 Vue 组件（参考 `src/components/`）

**输出**：
- `src/components/Copilot/RecommendationCard.vue`
- `src/components/Copilot/ConfidenceIndicator.vue`（已有但复用）
- `src/components/Copilot/DecisionActions.vue`
- `src/components/Copilot/__tests__/`
- `docs/ui/copilot-v1-usage.md`

**验收标准**：
- 组件可独立运行
- 三按钮可触发回调
- 决策依据可展开/折叠
- 单元测试覆盖
- 文档

**验收步骤**：
```bash
# 1. 前端构建
pnpm build

# 2. 单元测试
pnpm test:run -- Copilot

# 3. 手动验证
pnpm dev
# 访问 /workspace，触发 AI 推荐，验证 UI 显示
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **不要修改现有大组件**，新组件独立
- **置信度可视化**：用颜色 + 进度条，不用纯数字
- **决策依据**：折叠默认展开（用户要看懂）
- **本任务不接入后端逻辑**（只接 M3.2 API）

---

### 任务 M3.5：提问体验设计（被动记录）

**上下文**：99% 时间是"被动记录"，工艺师改参数时系统默默学习。

**目标**：实现"参数变更自动捕获"功能。

**范围**：
- ✅ 前端参数变更监听
- ✅ 变更事件上报后端
- ✅ 后端记录到审计日志
- ✅ 与主动学习事件区分
- ❌ 不做主动提示 UI
- ❌ 不做工艺师信任建模

**输入**：
- M3.3 事件总线
- `python/app/audit/audit_log.py`
- 工艺规划相关 Vue 组件

**输出**：
- `src/composables/useParameterChangeTracker.ts`
- `python/app/api/v1/parameter_changes.py`
- `python/app/audit/parameter_change_logger.py`
- 单元测试

**验收标准**：
- 参数变更可被自动捕获
- 上报到后端成功
- 审计日志有记录
- 单元测试覆盖

**验收步骤**：
```bash
# 1. 单元测试
cd python && pytest app/audit/ -v
pnpm test:run -- useParameterChangeTracker

# 2. 端到端测试
# 启动后端 + 前端，访问 /workspace，修改参数，验证审计日志有新条目
grep "PARAMETER_CHANGED" logs/audit/audit_log.jsonl
```

**完成定义**：2 个验收步骤全部通过。

**注意事项**：
- **不要影响主流程**：变更捕获是"观察者模式"，不阻塞
- **节流上报**：1 秒内多次变更合并为一次
- **隐私**：不记录参数值的明文（除非必要）
- **本任务为后续"主动学习"打基础**

---

## 六、M4 闭环飞轮（4 个任务）

### 任务 M4.1：实测数据回灌管线

**上下文**：闭环飞轮的第一环：把"加工结果"喂回来。

**目标**：把 MachiningRecord（实测）回灌到知识图谱和训练数据。

**范围**：
- ✅ 回灌触发：加工完成
- ✅ 数据转换：实测 → 训练样本
- ✅ 写入知识图谱（更新 Process 节点）
- ✅ 写入训练数据存储
- ❌ 不做自动训练
- ❌ 不做数据清洗

**输入**：
- M0.5 数据采集
- M0.4 MachiningRecord
- M1 知识图谱
- 优化蓝图 3.1 节

**输出**：
- `python/app/pipelines/feedback_loop.py`
- `python/app/knowledge_graph/feedback_updater.py`
- `python/app/training/data_lake.py`
- `python/app/pipelines/tests/test_feedback_loop.py`

**验收标准**：
- 实测数据可触发回灌
- 知识图谱节点被更新
- 训练数据被存储
- 单元测试覆盖

**验收步骤**：
```bash
# 1. 端到端测试
cd python && python -c "
import asyncio
from app.pipelines.feedback_loop import ingest_machining_record
record = {
    'machine_id': 'M-001',
    'tool_id': 'T-endmill-10',
    'workpiece_material': 'M-45steel',
    'process_plan': {...},
    'first_pass_acceptance': True,
    'actual_dimensions': [...],
    'surface_roughness': 1.6
}
asyncio.run(ingest_machining_record(record))
print('OK')
"

# 2. 验证知识图谱更新
cd python && python -c "
from app.knowledge_graph.graph_store import GraphStore
g = GraphStore()
# 查询 Process 节点的可信度
print(g.get_node('process', '...'))
"

# 3. 单元测试
cd python && pytest app/pipelines/tests/test_feedback_loop.py -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **不要阻塞加工流程**：回灌是异步的
- **去重**：相同 record_id 不重复处理
- **失败重试**：入队 + 重试机制
- **本任务只做"数据搬运"，不做"分析"**

---

### 任务 M4.2：自动模型微调流水线

**上下文**：有了新数据，要让模型自动"用上"。

**目标**：实现模型自动微调流水线（每周/每日触发）。

**范围**：
- ✅ 微调触发器（定时 + 数据量阈值）
- ✅ 训练数据准备（从 data lake）
- ✅ 训练任务提交（用 AsyncTaskManager）
- ✅ 训练结果评估
- ✅ 模型版本管理
- ❌ 不做实时训练
- ❌ 不做 A/B 测试

**输入**：
- M4.1 数据回灌
- `python/app/ai/lnn/training/trainer.py`
- `python/app/tasks/task_system.py`
- `python/app/services/model_registry_service.py`

**输出**：
- `python/app/ai/auto_retrain/__init__.py`
- `python/app/ai/auto_retrain/scheduler.py`
- `python/app/ai/auto_retrain/data_prep.py`
- `python/app/ai/auto_retrain/evaluator.py`
- `python/app/ai/auto_retrain/tests/`
- `docs/ai/auto-retrain-guide.md`

**验收标准**：
- 可触发微调任务
- 训练数据自动准备
- 训练完成后模型注册
- 单元测试覆盖
- 文档

**验收步骤**：
```bash
# 1. 手动触发
cd python && python -m app.ai.auto_retrain.scheduler --trigger-now
# 期望：任务已提交

# 2. 查询任务
curl http://localhost:8000/api/v1/jobs | grep "auto_retrain"
# 期望：找到对应任务

# 3. 单元测试
cd python && pytest app/ai/auto_retrain/tests/ -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **新模型必须评估**：在验证集上达标才能注册
- **老模型不删除**：保留 N 个历史版本
- **不要每次都微调**：数据量 < 阈值时不触发
- **不要改训练算法**：复用现有 LNNTrainer

---

### 任务 M4.3：飞轮仪表盘

**上下文**：要让团队看到"飞轮在转"。

**目标**：实现 Grafana 仪表盘 + 飞轮状态 API。

**范围**：
- ✅ 关键指标采集（数据量、模型质量、采纳率）
- ✅ Grafana 仪表盘 JSON
- ✅ 飞轮状态 API
- ✅ 每周飞轮报告生成
- ❌ 不做实时大屏
- ❌ 不做预测分析

**输入**：
- M0-M3 所有产出
- `deploy/prometheus/`
- Grafana 现有配置

**输出**：
- `deploy/grafana/dashboards/flywheel.json`（仪表盘配置）
- `python/app/api/v1/flywheel.py`（状态 API）
- `python/app/metrics/flywheel_metrics.py`
- `docs/operations/flywheel-dashboard.md`

**验收标准**：
- 仪表盘可导入 Grafana
- 状态 API 返回关键指标
- 报告生成可用
- 文档完整

**验收步骤**：
```bash
# 1. 启动 Prometheus + Grafana
docker compose --profile monitoring up -d

# 2. 导入仪表盘
# 访问 http://localhost:3000，导入 flywheel.json

# 3. 状态 API 测试
curl http://localhost:8000/api/v1/flywheel/status
# 期望：返回 {data_volume, model_quality, adoption_rate, ...}

# 4. 报告生成
cd python && python -m app.metrics.flywheel_metrics --report weekly
# 期望：报告文件生成
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- **关键指标至少 5 个**：加工记录数、模型质量、用户采纳率、不确定性均值、回灌延迟
- **不要追求花哨**，清晰可比即可
- **文档说明每个指标的含义和取值范围**

---

### 任务 M4.4：端到端测试

**上下文**：M0-M3 完成后必须有端到端测试。

**目标**：覆盖"数据进 → 工艺出 → 加工回 → 模型更新"完整链路。

**范围**：
- ✅ E2E 测试用例（5-10 个）
- ✅ 模拟数据生成器
- ✅ 自动化运行脚本
- ✅ 测试报告
- ❌ 不做性能压测
- ❌ 不做安全测试

**输入**：
- M0-M3 所有产出
- `e2e/` 现有测试
- Playwright 配置

**输出**：
- `e2e/flywheel.spec.ts`
- `python/app/tests/e2e/test_flywheel.py`
- `scripts/run_flywheel-e2e.sh`
- `e2e/reports/flywheel-e2e-report.md`

**验收标准**：
- 5+ 个 E2E 用例覆盖完整链路
- 全流程可自动化运行
- 报告清晰

**验收步骤**：
```bash
# 1. 启动所有服务
docker compose --profile full up -d

# 2. 跑后端 E2E
cd python && pytest app/tests/e2e/test_flywheel.py -v

# 3. 跑前端 E2E
npx playwright test e2e/flywheel.spec.ts

# 4. 生成报告
bash scripts/run_flywheel-e2e.sh
```

**完成定义**：4 个验收步骤全部通过。

**注意事项**：
- **每个用例不超过 5 分钟**
- **测试间状态隔离**（用新数据库）
- **失败用例要可重试**
- **本任务是"质量门"，必须严格**

---

## 七、M5 体验与生态（5 个任务）

### 任务 M5.1：3D 视图高亮

**上下文**：工艺师要看到"AI 看到的是什么"。

**目标**：在 3D 视图中高亮 AI 关注的特征。

**范围**：
- ✅ 选中特征高亮
- ✅ 多窗口视图（设计图 / 仿真）
- ✅ 鼠标悬停显示信息
- ❌ 不做 AR
- ❌ 不做剖面

**输入**：
- M2.5 仿真可视化
- `src/components/ThreeViewer.vue`

**输出**：
- `src/components/HighlightViewer.vue`
- `src/composables/useFeatureHighlight.ts`
- 单元测试

**验收标准**：
- 特征可被高亮
- 性能：选中响应 < 100ms
- 单元测试

**验收步骤**：
```bash
# 1. 前端构建
pnpm build

# 2. 单元测试
pnpm test:run -- HighlightViewer

# 3. 手动验证
pnpm dev
# 访问 /workspace，验证特征高亮
```

**完成定义**：3 个验收步骤全部通过。

---

### 任务 M5.2：推理过程可视化

**上下文**：用户要看懂 AI 是怎么想的。

**目标**：可视化"任务路由 → 物理校验 → 主动学习"决策路径。

**范围**：
- ✅ 决策树展示
- ✅ 每步的依据（相似案例 / 物理校验结果）
- ✅ 时间轴回放
- ❌ 不做完整 Execution Trace
- ❌ 不做对比分析

**输入**：
- M3.3 触发器事件
- M3.4 Co-pilot 组件

**输出**：
- `src/components/ReasoningTrace/TraceTimeline.vue`
- `src/components/ReasoningTrace/StepCard.vue`
- `src/api/reasoning.ts`
- 单元测试

**验收标准**：
- 推理步骤可被可视化
- 每步有依据展示
- 单元测试

**验收步骤**：
```bash
# 1. 前端构建
pnpm build

# 2. 单元测试
pnpm test:run -- ReasoningTrace

# 3. 手动验证
pnpm dev
# 触发一次 AI 推荐，验证推理过程展示
```

**完成定义**：3 个验收步骤全部通过。

---

### 任务 M5.3：PDF/Excel 工艺理解

**上下文**：90% 工艺师用 PDF/Excel。

**目标**：解析 PDF 工艺文档和 Excel 表格，提取结构化数据。

**范围**：
- ✅ PDF 文本提取（`pymupdf`）
- ✅ Excel 表格提取（`camelot` 或 `openpyxl`）
- ✅ 表格结构识别
- ✅ 与知识图谱对接
- ❌ 不做图片中的表格（OCR）
- ❌ 不做实时解析

**输入**：
- M1.4 LLM 抽取
- `python/app/rag/document_importer.py`（参考）

**输出**：
- `python/app/rag/pdf_parser.py`
- `python/app/rag/excel_parser.py`
- `python/app/rag/tests/test_parsers.py`
- `docs/rag/document-parsing.md`

**验收标准**：
- 可解析测试 PDF/Excel
- 提取表格结构
- 与知识图谱对接
- 单元测试

**验收步骤**：
```bash
# 1. 测试 PDF 解析
cd python && python -c "
from app.rag.pdf_parser import parse_pdf
result = parse_pdf('docs/knowledge-graph/samples/sample-process-card.pdf')
print(f'Tables: {len(result[\"tables\"])}')
"

# 2. 测试 Excel 解析
cd python && python -c "
from app.rag.excel_parser import parse_excel
result = parse_excel('docs/knowledge-graph/samples/sample-process.xlsx')
print(f'Rows: {len(result[\"rows\"])}')
"

# 3. 单元测试
cd python && pytest app/rag/tests/test_parsers.py -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **先支持中文**，英文之后
- **不要追求 100% 表格识别**，目标 80%+
- **失败优雅降级**：解析不了的部分不阻塞

---

### 任务 M5.4：OPC UA 适配

**上下文**：欧洲客户和工业 4.0 需求。

**目标**：OPC UA 协议适配器（与 MTConnect 并行）。

**范围**：
- ✅ OPC UA 客户端
- ✅ 节点订阅
- ✅ 数据转换
- ✅ 与 M0.5 采集管道集成
- ❌ 不做 OPC UA 服务端
- ❌ 不做复杂类型

**输入**：
- M0.3 MTConnect 适配器（参考模式）
- M0.5 采集管道

**输出**：
- `python/app/integrations/opcua/__init__.py`
- `python/app/integrations/opcua/adapter.py`
- `python/app/integrations/opcua/tests/`
- `docs/integrations/opcua-usage.md`

**验收标准**：
- 可连接 OPC UA 服务器
- 可订阅数据节点
- 单元测试

**验收步骤**：
```bash
# 1. 单元测试
cd python && pytest app/integrations/opcua/tests/ -v

# 2. 连接测试（用 opc ua simulator）
cd python && python -m app.integrations.opcua.cli --endpoint opc.tcp://localhost:4840
# 期望：可连接并读取数据
```

**完成定义**：2 个验收步骤全部通过。

---

### 任务 M5.5：.vrm 规范 V1

**上下文**：.vrm 是项目核心数据格式。

**目标**：发布 .vrm 规范的 V1 版本（JSON Schema）。

**范围**：
- ✅ JSON Schema 定义
- ✅ 规范文档
- ✅ Python SDK（读/写）
- ✅ TypeScript SDK（读/写）
- ❌ 不做加密
- ❌ 不做版本迁移

**输入**：
- 现有工程存储代码
- 优化蓝图 6.1 节

**输出**：
- `docs/vrm-spec/vrm-spec-v1.md`（规范文档）
- `docs/vrm-spec/vrm-schema-v1.json`（JSON Schema）
- `python/app/vrm_sdk/__init__.py`
- `python/app/vrm_sdk/reader.py`
- `python/app/vrm_sdk/writer.py`
- `src/vrm-sdk/reader.ts`
- `src/vrm-sdk/writer.ts`
- 单元测试

**验收标准**：
- JSON Schema 验证工具通过
- Python SDK 可读/写 .vrm
- TypeScript SDK 可读/写 .vrm
- 文档完整
- 单元测试

**验收步骤**：
```bash
# 1. 验证 JSON Schema
npx ajv validate -s docs/vrm-spec/vrm-schema-v1.json -d test-sample.vrm

# 2. Python SDK 测试
cd python && pytest app/vrm_sdk/ -v

# 3. TypeScript SDK 测试
pnpm test:run -- vrm-sdk
```

**完成定义**：3 个验收步骤全部通过。

---

## 八、M6 商业化（4 个任务）

### 任务 M6.1：Community/Pro 版本边界

**上下文**：开源与商业的边界决定项目未来。

**目标**：定义 Community 版与 Pro 版的功能边界。

**范围**：
- ✅ 功能清单
- ✅ 许可证管理
- ✅ 版本检测
- ✅ 功能开关
- ❌ 不做付费墙
- ❌ 不做许可证服务器

**输入**：
- 优化蓝图 6.5 节
- 现有后端模块

**输出**：
- `docs/business/edition-boundary.md`
- `python/app/licensing/__init__.py`
- `python/app/licensing/feature_flags.py`
- `python/app/licensing/detector.py`
- 单元测试

**验收标准**：
- 边界文档清晰
- 功能开关可用
- Community 版功能完全可用
- Pro 功能可启用/禁用

**验收步骤**：
```bash
# 1. 文档存在
test -f docs/business/edition-boundary.md

# 2. 功能开关测试
cd python && python -c "
from app.licensing.feature_flags import is_enabled, set_edition
set_edition('community')
print('auto_retrain:', is_enabled('auto_retrain'))  # 期望 False
set_edition('pro')
print('auto_retrain:', is_enabled('auto_retrain'))  # 期望 True
"

# 3. 单元测试
cd python && pytest app/licensing/ -v
```

**完成定义**：3 个验收步骤全部通过。

**注意事项**：
- **核心功能必须 Community**：DXF/STEP/后处理/工艺规划
- **Pro 功能**：自动微调、联邦学习、高级可视化
- **不要 hard-code**，用 feature flag

---

### 任务 M6.2：授权与计费基础

**上下文**：Pro 版要有授权和计费。

**目标**：实现基础授权系统（许可证验证 + 用量统计）。

**范围**：
- ✅ 许可证文件格式
- ✅ 离线验证
- ✅ 用量上报（可选）
- ✅ 过期处理
- ❌ 不做支付集成
- ❌ 不做云端授权

**输入**：
- M6.1 边界
- 现有后端

**输出**：
- `python/app/licensing/license.py`
- `python/app/licensing/usage_tracker.py`
- `python/app/api/v1/license.py`
- 单元测试

**验收标准**：
- 许可证可加载/验证
- 用量可统计
- 过期功能自动禁用

**验收步骤**：
```bash
# 1. 生成测试许可证
cd python && python -c "
from app.licensing.license import generate_license
lic = generate_license('test-org', 'pro', days=30)
print(lic)
"

# 2. 验证许可证
cd python && python -c "
from app.licensing.license import verify_license
print(verify_license('xxx'))
"

# 3. 单元测试
cd python && pytest app/licensing/ -v
```

**完成定义**：3 个验收步骤全部通过。

---

### 任务 M6.3：文档站

**上下文**：用户和开发者需要好的文档。

**目标**：基于 VitePress 或 Docusaurus 的文档站。

**范围**：
- ✅ 文档站基础
- ✅ 用户文档
- ✅ 开发者文档
- ✅ API 文档（自动生成）
- ❌ 不做博客
- ❌ 不做评论

**输入**：
- 现有 `docs/`
- 优化蓝图全文档

**输出**：
- `docs-site/`（新建 VitePress 项目）
- `docs-site/docs/`（文档源）
- 部署配置

**验收标准**：
- 文档站可本地启动
- 至少 20 个文档页
- API 文档自动生成
- 搜索可用

**验收步骤**：
```bash
# 1. 启动文档站
cd docs-site && pnpm install && pnpm dev
# 访问 http://localhost:5173

# 2. 构建
cd docs-site && pnpm build
# 期望：build 成功

# 3. 检查页面数
find docs-site/docs -name "*.md" | wc -l
# 期望：>= 20
```

**完成定义**：3 个验收步骤全部通过。

---

### 任务 M6.4：ISO 23247 数字孪生标准准备

**上下文**：ISO 23247 是数字孪生国际标准，APT 高度契合。

**目标**：梳理项目与 ISO 23247 的对应关系，准备认证材料。

**范围**：
- ✅ 标准条款分析
- ✅ 项目对应实现梳理
- ✅ 合规差距报告
- ❌ 不启动正式认证
- ❌ 不做咨询公司引入

**输入**：
- ISO 23247 标准（公开摘要）
- M0-M5 全部产出

**输出**：
- `docs/compliance/iso-23247-mapping.md`
- `docs/compliance/gap-analysis.md`
- `docs/compliance/certification-roadmap.md`

**验收标准**：
- 三个文档齐全
- 差距分析有具体改进项
- 路线图有时间节点

**验收步骤**：
```bash
# 1. 文档存在
test -f docs/compliance/iso-23247-mapping.md
test -f docs/compliance/gap-analysis.md
test -f docs/compliance/certification-roadmap.md

# 2. 文档字数检查
wc -w docs/compliance/*.md
# 期望：每个 > 1000 字
```

**完成定义**：2 个验收步骤全部通过。

---

## 九、L2 并行轨道（7 个独立任务）

这些任务**与主线并行**，任何阶段都可启动。每个都是 1-2 周的工量。

### 任务 L2.1：错误处理与可观测性

**目标**：统一错误处理，全链路可追踪。

**输出**：
- `python/app/core/error_handler.py`（统一错误响应）
- `src/utils/error-handler.ts`（前端错误处理）
- `src/composables/useDiagnostics.ts`（诊断信息）
- 单元测试

**验收标准**：
- 所有 API 错误结构化
- 前端有"复制诊断信息"按钮
- 单元测试覆盖

**验收步骤**：
```bash
cd python && pytest app/core/tests/ -v
pnpm test:run -- error-handler
```

---

### 任务 L2.2：测试覆盖

**目标**：核心模块单测覆盖率 ≥ 80%。

**输出**：
- 现有测试补充
- `coverage-reports/`

**验收标准**：
- AI/LNN 覆盖率 ≥ 80%
- DXF 流水线 ≥ 70%
- 后处理 ≥ 80%

**验收步骤**：
```bash
cd python && pytest --cov=app/ai/lnn --cov-report=html
# 期望：覆盖率 ≥ 80%
```

---

### 任务 L2.3：文档体系

**目标**：建立分层文档 + ADR。

**输出**：
- `docs/adr/`（ADR 目录，至少 3 个 ADR）
- `docs/runbook/`（运维手册）
- `docs/dev/`（开发者指南）

**验收标准**：
- ADR 模板存在
- 至少 3 个真实 ADR
- Runbook 涵盖常见故障

---

### 任务 L2.4：DevOps 流水线

**目标**：PR 阶段、合并后、发版三段流水线。

**输出**：
- `.github/workflows/pr.yml`
- `.github/workflows/post-merge.yml`
- `.github/workflows/release.yml`

**验收标准**：
- 三个 workflow 文件存在
- PR 阶段运行测试和 lint
- 合并后自动部署 staging

---

### 任务 L2.5：安全加固

**目标**：依赖安全 + Secret 管理 + 渗透测试准备。

**输出**：
- Dependabot 配置
- Secret 扫描配置
- 渗透测试报告模板

**验收标准**：
- Dependabot PR 可生成
- Secret 扫描在 CI 运行
- 报告模板可用

---

### 任务 L2.6：性能优化

**目标**：前端首屏 < 3 秒，AI 推理 P95 < 500ms。

**输出**：
- 性能基线报告
- 优化 PR

**验收标准**：
- 前端 Lighthouse > 80
- AI 推理 P95 < 500ms

**验收步骤**：
```bash
# Lighthouse
npx lighthouse http://localhost:1420 --output json
# 期望：performance > 80
```

---

### 任务 L2.7：UX 最后一公里

**目标**：引导流程 + 示例工程 + 命令面板。

**输出**：
- `src/components/Onboarding/Tour.vue`
- `src/examples/`（10+ 真实示例工程）
- `src/composables/useCommandPalette.ts`

**验收标准**：
- 引导流程 5 步
- 10+ 示例工程
- Cmd+K 命令面板

---

## 十、Solo 投喂模板

### 10.1 标准化投喂格式

把以下格式复制到 Solo 提示框，填入对应任务信息：

```markdown
## Solo 任务：[任务编号 + 名称]

### 上下文
[从优化蓝图相关章节粘贴]

### 目标
[任务的目标]

### 范围
- ✅ 做：[具体事项]
- ❌ 不做：[明确边界]

### 输入
[相关文件路径]

### 输出
[要创建/修改的文件]

### 验收步骤
```bash
[具体的命令]
```

### 完成定义
[什么状态算"完成"]

### 注意事项
[易踩的坑]

### 通用前置
执行前先读：
- docs/wiki/README.md
- docs/wiki/03-目录结构与代码地图.md
- docs/OPTIMIZATION_BLUEPRINT.md
```

### 10.2 并行调度建议

```
并行组 1（无依赖）：
  - M0.2 TDengine
  - M0.3 MTConnect
  - L2.4 DevOps
  - L2.5 安全

并行组 2（依赖 M0）：
  - M0.4 MachiningRecord
  - M0.5 采集管道
  - M1.1 本体设计
  - L2.1 错误处理

并行组 3（依赖 M1）：
  - M1.2-1.5 图谱实施
  - M2.1 切削力 PINN
  - L2.2 测试覆盖

并行组 4（依赖 M2）：
  - M2.2-2.5 仿真深化
  - M3.1 贝叶斯 LNN
  - L2.6 性能

并行组 5（依赖 M3）：
  - M3.2-3.5 推理 + Co-pilot
  - L2.7 UX

并行组 6（依赖 M4）：
  - M4.x 闭环
  - M5.x 体验

并行组 7（依赖 M5）：
  - M6.x 商业化
```

### 10.3 Solo 失败应对

| 失败类型 | 应对 |
|---------|------|
| 验收不通过 | 重投喂原任务，附上失败日志 |
| 部分完成 | 拆分为更小的子任务重投喂 |
| 范围蔓延 | 立即停止，回退到定义清晰的子任务 |
| 上下文丢失 | 提供"前序任务完成报告"链接 |
| 性能问题 | 增加性能验收步骤 |

---

## 十一、追踪与状态

### 11.1 任务状态追踪表

每个 Solo 任务完成后，更新以下表格：

| 任务 ID | 名称 | 状态 | 完成日期 | 备注 |
|--------|------|------|---------|------|
| M0.1 | 现状评估 | ⬜ | | |
| M0.2 | TDengine | ⬜ | | |
| ... | ... | ⬜ | | |

### 11.2 完成报告模板

每个任务完成后输出：

```markdown
# 任务 [ID] 完成报告

## 完成时间
[YYYY-MM-DD]

## 产出文件
- [文件路径]

## 验收结果
- [ ] 验收步骤 1：通过 / 失败
- [ ] 验收步骤 2：通过 / 失败
- ...

## 偏差说明
（如有）实际产出与计划的差异

## 后续任务
下一个可启动的任务
```

---

## 十二、关键提醒

1. **不要跳步**：每个任务都有依赖关系，跳步会失败
2. **不要超范围**：验收标准外的功能"以后再做"
3. **不要忽略测试**：测试是 Solo 任务的"完成定义"的一部分
4. **不要忽略文档**：每个任务都有文档输出要求
5. **不要一个人全做**：并行轨道让多人/多 Solo 同时工作
6. **不要追求完美**：80% 完成度 > 100% 计划
7. **不要忘记录入基线**：M0.1 必须先做

---

## 附录：Solo 提示词速查

### 主线任务（33 个）
M0.1 → M0.2 → M0.3 → M0.4 → M0.5  
→ M1.1 → M1.2 → M1.3 → M1.4 → M1.5  
→ M2.1 → M2.2 → M2.3 → M2.4 → M2.5  
→ M3.1 → M3.2 → M3.3 → M3.4 → M3.5  
→ M4.1 → M4.2 → M4.3 → M4.4  
→ M5.1 → M5.2 → M5.3 → M5.4 → M5.5  
→ M6.1 → M6.2 → M6.3 → M6.4

### 并行轨道（7 个）
L2.1 → L2.2 → L2.3 → L2.4 → L2.5 → L2.6 → L2.7

### 必做前置
- **M0.1 必须最先做**（基线测量）
- **任何模块改动前先读对应 Code Wiki**

### 完成报告位置
- 任务完成后：更新状态表 + 输出完成报告
- 完成报告存放：`docs/task-reports/M[X].[Y]-report.md`
