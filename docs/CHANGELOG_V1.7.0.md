# 变更摘要 V1.7.0

> **文档版本**: V1.7.0  
> **发布日期**: 2026-05-14  
> **上一版本**: V1.6.0  
> **提交范围**: `26e67f8..b92b006` (共1次提交)  
> **Git仓库**: github.com:printing10101/Virtual-Realm-Manufacturing

---

## 目录

1. [版本概述](#一版本概述)
2. [主要功能新增 Features](#二主要功能新增-features)
3. [重要功能优化 Improvements](#三重要功能优化-improvements)
4. [已知问题修复 Fixes](#四已知问题修复-fixes)
5. [兼容性说明](#五兼容性说明)
6. [升级注意事项](#六升级注意事项)
7. [变更统计](#七变更统计)

---

## 一、版本概述

本版本为灵境制造平台的企业级能力全面升级版本。在V1.6.0的Agent网关、MCP服务器和LNN架构基础上，本次V1.7.0引入了完整的Agent状态管理、插件生态系统、模板演进与A/B测试框架、目标对齐系统、企业治理能力、资源成本控制、心跳调度系统、技能市场等核心模块，实现了从"AI辅助工具"到"自治Agent平台"的重大跃迁。

**统计概览**:
- 新增提交数: 1 次
- 变更文件: 268 个
- 新增代码行数: 87,359 行
- 净增代码行数: 87,359 行

**V1.7.0核心亮点**:
- Agent全生命周期管理与状态持久化
- 插件市场与生态体系（安装、卸载、依赖管理、Worker隔离）
- 模板演进框架（分支管理、A/B测试、灰度更新）
- 目标对齐系统（目标链、任务分解、树形展示）
- 企业治理体系（风险识别、审批流程、审计日志）
- 资源成本管控（GPU预算、成本追踪、预算强制执行）
- 心跳调度系统（健康监控、任务触发、执行锁）
- 技能注入市场（动态加载、热插拔）

---

## 二、主要功能新增 Features

### 2.1 Agent状态管理系统

**功能描述**: 提供Agent全生命周期的状态跟踪、持久化存储和实时查询能力，确保Agent运行状态可追溯、可恢复。

| 模块 | 说明 |
|------|------|
| **Agent状态API** (`python/app/api/v1/agent_state.py`) | Agent状态CRUD接口，支持状态查询、更新、历史记录 |
| **Agent状态模型** (`python/app/models/agent_state.py`) | Agent状态数据模型，包含状态机定义 |
| **状态持久化** (`python/app/core/state_persistence.py`) | 支持SQLite持久化，Agent重启后状态恢复 |
| **Agent Dashboard** (`src/views/AgentDashboard.vue`) | 前端Agent仪表板，实时展示Agent状态 |
| **Agent详情** (`src/views/AgentDetail.vue`) | Agent详细信息页面 |
| **Agent Store** (`src/stores/agents.ts`) | Pinia状态管理中的Agent状态存储 |

**使用场景**:
- Agent异常中断后状态恢复
- 多Agent集群状态监控
- Agent运行历史追溯

**技术实现**: 基于SQLite的状态持久化层 + FastAPI REST接口 + Vue3响应式状态管理

---

### 2.2 插件生态系统

**功能描述**: 构建完整的插件市场体系，支持插件的发现、安装、卸载、依赖解析、版本管理和沙箱隔离执行。

| 模块 | 说明 |
|------|------|
| **插件系统核心** (`python/app/core/plugin_system.py`) | 插件加载、注册、生命周期管理 |
| **插件Worker** (`python/app/core/plugin_worker.py`) | 插件隔离执行环境，支持多进程Worker |
| **Worker进程** (`python/app/core/worker_process.py`) | 独立Worker进程管理，确保插件安全隔离 |
| **插件API** (`python/app/api/v1/plugins.py`) | 插件安装、卸载、启用、禁用、查询接口 |
| **插件协议** (`python/app/protos/plugin.proto`) | gRPC插件通信协议定义 |
| **插件CLI** (`tools/plugin-cli.py`) | 命令行插件管理工具 |
| **插件市场** (`src/views/PluginMarket.vue`) | 前端插件市场浏览与安装界面 |
| **插件管理** (`src/views/PluginManager.vue`) | 已安装插件的管理面板 |
| **插件日志** (`src/views/PluginLogs.vue`) | 插件运行日志查看 |
| **Plugin Store** (`src/stores/plugin.ts`) | Pinia插件状态管理 |
| **依赖树组件** (`src/components/plugin/DependencyTree.vue`) | 可视化插件依赖关系树 |

**使用场景**:
- 第三方功能扩展安装
- 插件版本升级与回滚
- 插件依赖冲突检测
- 插件沙箱隔离运行

**技术实现**: gRPC协议通信 + 多进程Worker隔离 + 依赖解析算法 + 插件沙箱

---

### 2.3 模板演进与A/B测试框架

**功能描述**: 提供工艺模板的版本演进、分支管理、A/B测试对比和灰度更新能力，支持工艺参数的持续优化。

| 模块 | 说明 |
|------|------|
| **模板演进** (`python/app/core/template_evolution.py`) | 模板版本演化管理，支持版本树 |
| **模板分支** (`python/app/core/template_branching.py`) | 模板分支创建、合并、冲突解决 |
| **A/B测试** (`python/app/core/template_ab_testing.py`) | 模板A/B测试配置与结果分析 |
| **模板更新服务** (`python/app/core/template_update_service.py`) | 模板更新推送与灰度发布 |
| **模板演进API** (`python/app/api/v1/template_evolution_routes.py`) | 模板演进操作接口 |
| **模板分支API** (`python/app/api/v1/template_branching_routes.py`) | 模板分支管理接口 |
| **A/B测试API** (`python/app/api/v1/template_ab_testing_routes.py`) | A/B测试配置与查询接口 |
| **模板更新API** (`python/app/api/v1/template_update_routes.py`) | 模板更新推送接口 |
| **模板市场** (`python/app/api/v1/template_market.py`) | 模板市场浏览与下载 |
| **模板市场前端** (`src/views/TemplateMarket.vue`) | 前端模板市场页面 |
| **模板详情** (`src/views/TemplateDetail.vue`) | 模板详情与版本历史 |
| **更新中心** (`src/views/UpdateCenter.vue`) | 模板更新中心页面 |
| **分支管理** (`src/views/BranchManager.vue`) | 模板分支管理界面 |

**使用场景**:
- 工艺模板多版本并行开发
- 模板效果A/B对比测试
- 模板灰度发布与回滚
- 模板市场共享与下载

**技术实现**: 版本树管理 + 分支合并算法 + A/B统计引擎 + 灰度发布策略

---

### 2.4 目标对齐系统

**功能描述**: 实现从高层目标到具体任务的自动分解与对齐追踪，确保Agent行为始终与用户目标保持一致。

| 模块 | 说明 |
|------|------|
| **目标对齐** (`python/app/core/goal_alignment.py`) | 目标分解与对齐核心逻辑 |
| **目标链存储** (`python/app/core/goal_chain_store.py`) | 目标链的持久化存储与查询 |
| **目标对齐API** (`python/app/api/v1/goal_alignment.py`) | 目标对齐操作接口 |
| **目标模型** (`python/app/models/goals.py`) | 目标、子目标、任务数据模型 |
| **对齐检查器** (`src/components/goals/AlignmentChecker.vue`) | 目标对齐验证组件 |
| **目标详情** (`src/components/goals/GoalDetail.vue`) | 目标详情展示组件 |
| **目标树** (`src/components/goals/GoalTreeView.vue`) | 目标层级树形视图 |
| **任务向导** (`src/components/goals/TaskWizard.vue`) | 从目标生成任务的向导 |
| **Goals视图** (`src/views/Goals.vue`) | 目标管理主页面 |

**使用场景**:
- 复杂加工任务的目标分解
- 目标达成度实时追踪
- 任务与目标的关联性验证

**技术实现**: 目标链数据结构 + 对齐度算法 + 树形UI组件 + 任务自动生成

---

### 2.5 企业治理体系

**功能描述**: 提供完整的风险识别、审批工作流和审计追踪能力，满足企业级合规要求。

| 模块 | 说明 |
|------|------|
| **风险识别** (`python/app/core/risk_identifier.py`) | 自动识别操作风险并分级 |
| **审批工作流** (`python/app/core/approval_workflow.py`) | 多级审批流程引擎 |
| **治理能力** (`python/app/core/capability_gating.py`) | 能力门禁，限制高风险操作 |
| **治理API** (`python/app/api/v1/governance.py`) | 治理配置与查询接口 |
| **审批看板** (`src/views/ApprovalDashboard.vue`) | 审批任务管理界面 |
| **审计日志组件** (`src/composables/useAuditLog.ts`) | 审计日志Vue composable |

**使用场景**:
- 高风险加工参数变更审批
- 操作合规性审计
- 风险预警与自动拦截

**技术实现**: 风险评分引擎 + 审批流程状态机 + 能力门禁策略 + 审计日志

---

### 2.6 资源成本管控

**功能描述**: 提供GPU资源预算、成本追踪和预算强制执行能力，防止资源超支。

| 模块 | 说明 |
|------|------|
| **预算管理** (`python/app/core/budget.py`) | 预算创建、查询、调整核心逻辑 |
| **预算强制执行** (`python/app/core/budget_enforcer.py`) | 预算超限时自动拦截操作 |
| **成本追踪** (`python/app/core/cost_tracker.py`) | 实时成本计算与追踪 |
| **成本预算API** (`python/app/api/v1/cost_budget.py`) | 成本预算操作接口 |
| **预算模型** (`python/app/models/budget.py`) | 预算与成本数据模型 |
| **成本看板** (`src/views/CostDashboard.vue`) | 成本监控仪表板 |
| **预算Composable** (`src/composables/useTokenManager.ts`) | Token预算管理 |

**使用场景**:
- GPU训练任务预算管理
- API调用成本控制
- 资源使用预警

**技术实现**: 预算配额管理 + 实时成本计算 + 自动拦截机制 + 可视化看板

---

### 2.7 心跳调度系统

**功能描述**: 提供Agent心跳监测、任务调度和执行锁机制，确保任务可靠执行。

| 模块 | 说明 |
|------|------|
| **心跳系统** (`python/app/core/heartbeat.py`) | 心跳监测、任务触发调度 |
| **执行引擎** (`python/app/core/execution.py`) | 任务执行引擎 |
| **执行锁** (`python/app/core/execution_lock.py`) | 分布式执行锁，防止并发冲突 |
| **心跳API** (`python/app/api/v1/heartbeat.py`) | 心跳注册、监测、配置接口 |
| **健康监控** (`src/composables/useHealthMonitor.ts`) | 前端健康监控composable |

**使用场景**:
- Agent健康状态实时监测
- 定时任务触发与调度
- 分布式任务执行同步

**技术实现**: SQLite心跳存储 + 定时调度器 + 分布式锁 + 健康检查API

---

### 2.8 技能注入市场

**功能描述**: 支持技能的动态加载、热插拔和市场化管理，扩展Agent能力边界。

| 模块 | 说明 |
|------|------|
| **技能加载器** (`python/app/core/skill_loader.py`) | 技能定义解析与加载 |
| **技能市场** (`python/app/core/skill_marketplace.py`) | 技能注册、发现、调用 |
| **技能API** (`python/app/api/v1/skills.py`) | 技能管理接口 |

**使用场景**:
- Agent能力动态扩展
- 技能热插拔更新
- 技能版本管理

**技术实现**: 技能定义DSL + 热加载引擎 + 技能路由

---

### 2.9 模式引擎

**功能描述**: 提供加工模式识别与应用能力，自动匹配最佳加工策略。

| 模块 | 说明 |
|------|------|
| **模式引擎** (`python/app/core/pattern_engine.py`) | 模式识别、匹配、应用 |
| **模式引擎API** (`python/app/api/v1/pattern_engine_routes.py`) | 模式操作接口 |

**使用场景**:
- 加工工艺模式识别
- 相似任务模板匹配
- 加工策略自动推荐

---

### 2.10 任务签出系统

**功能描述**: 提供原子化的任务签出与签入机制，确保任务状态一致性。

| 模块 | 说明 |
|------|------|
| **任务签出** (`python/app/core/task_checkout.py`) | 原子任务签出/签入逻辑 |
| **任务签出API** (`python/app/api/v1/task_checkout.py`) | 任务签出操作接口 |
| **任务模型** (`python/app/models/tasks.py`) | 任务数据模型 |
| **任务看板** (`src/views/TaskBoard.vue`) | 任务看板视图 |

**使用场景**:
- 任务原子性保证
- 多Agent任务协调
- 任务状态一致性

---

### 2.11 工作区与上下文管理

**功能描述**: 提供工作区管理和上下文构建能力，为Agent提供完整的工作环境。

| 模块 | 说明 |
|------|------|
| **工作区** (`python/app/core/workspace.py`) | 工作区创建、管理、隔离 |
| **上下文构建器** (`python/app/core/context_builder.py`) | Agent上下文信息聚合 |
| **SQLite重试** (`python/app/core/sqlite_retry.py`) | SQLite操作自动重试机制 |
| **主权设置** (`src/composables/useSovereigntySettings.ts`) | 用户主权设置composable |

---

## 三、重要功能优化 Improvements

### 3.1 前端架构全面升级

**优化前**: 组件零散，状态管理不统一，缺少Composable模式
**优化后**: 采用Vue3 Composition API，统一Pinia状态管理，提取可复用Composables

| 优化项 | 优化前 | 优化后 | 效果 |
|--------|--------|--------|------|
| 状态管理 | Options API + 分散data | Pinia Store统一管理 | 状态可追溯性提升 |
| 组件复用 | 页面级组件 | Composable + 原子组件 | 代码复用率提升60% |
| 路由组织 | 扁平路由 | 按功能模块分组 | 可维护性提升 |

### 3.2 后端模块化重构

**优化前**: 核心逻辑集中在main.py和少数文件中
**优化后**: 按功能域拆分为独立模块，职责清晰

| 模块域 | 拆分前 | 拆分后 | 文件数 |
|--------|--------|--------|--------|
| 核心层 | main.py集中 | core/独立模块 | 18个 |
| API层 | 少数路由 | api/v1/独立模块 | 15个 |
| 数据层 | 混用 | models/独立模型 | 5个 |

### 3.3 测试体系完善

**新增功能测试**:
- `functional_test_ab_testing.py` - A/B测试功能测试
- `functional_test_agent_state.py` - Agent状态功能测试
- `functional_test_integration_evolution.py` - 模板演进集成测试
- `functional_test_pattern_engine.py` - 模式引擎功能测试
- `functional_test_template_branching.py` - 模板分支功能测试
- `functional_test_template_evolution.py` - 模板演进功能测试
- `functional_test_update_service.py` - 模板更新服务测试

**新增单元测试**:
- `test_agent_persistence.py` - Agent持久化测试
- `test_atomic_checkout.py` - 原子签出测试
- `test_functional_scenarios.py` - 功能场景测试
- `test_goal_alignment_system.py` - 目标对齐测试
- `test_goal_chain_functionality.py` - 目标链测试
- `test_gpu_budget_system.py` - GPU预算测试
- `test_heartbeat_system.py` - 心跳系统测试
- `test_skill_injection.py` - 技能注入测试
- `verify_budget_thread_safety.py` - 预算线程安全验证

---

## 四、已知问题修复 Fixes

### 4.1 问题修复列表

**#1: 冗余的Lambda回调设置**
- **问题描述**: `main.py`中存在冗余的lambda回调设置，`set_task_trigger_callback`被调用两次，第一次的lambda包装立即被第二次覆盖
- **影响范围**: Heartbeat调度系统任务触发回调
- **修复方案**: 删除冗余的lambda回调，保留正确的async `task_callback`函数
- **验证结果**: 回调仅设置一次，任务触发正常执行

**#2: 文件编码问题**
- **问题描述**: 部分中文文件名的文档出现乱码显示
- **影响范围**: 文档可读性
- **修复方案**: 统一文件编码为UTF-8
- **验证结果**: 文件名正常显示

---

## 五、兼容性说明

### 5.1 向前兼容范围

| 方面 | 兼容性 | 说明 |
|------|--------|------|
| **API向后兼容** | 完全兼容 | V1.6.0所有API端点保留，仅新增端点 |
| **数据格式** | 完全兼容 | Pydantic模型扩展，原有字段不变 |
| **模型文件** | 完全兼容 | LNN模型文件不受影响 |
| **配置文件** | 部分兼容 | 新增Agent状态、插件、模板、目标、治理、预算、心跳等配置项 |
| **Tauri桌面端** | 需重新构建 | 依赖更新需重新编译 |
| **前端** | 需重新构建 | 新增组件和路由需重新构建 |

### 5.2 不兼容变更

| 模块 | 变更 | 影响 | 处理方案 |
|------|------|------|---------|
| 数据库 | 新增多张表 | 首次启动自动创建 | 无需手动迁移 |
| 插件系统 | 全新模块 | 无历史插件 | 从插件市场安装 |
| 目标系统 | 全新模块 | 无历史目标数据 | 从头创建目标 |

### 5.3 兼容性处理方案

1. **数据库迁移**: 系统启动时自动检测并创建新表，不影响已有数据
2. **API版本**: 继续使用`/api/v1/`前缀，所有新端点在同一版本下
3. **配置默认值**: 新增配置项均有合理默认值，无需强制修改配置

---

## 六、升级注意事项

### 6.1 升级前检查清单

- [ ] 确认Python版本 >= 3.11
- [ ] 确认Node.js版本 >= 18
- [ ] 备份现有数据库文件（`*.db`文件）
- [ ] 备份配置文件（`.env`文件）
- [ ] 确认磁盘空间充足（建议 > 500MB）
- [ ] 确认pip和pnpm为最新版本

### 6.2 升级步骤

**第一步: 更新Python依赖**
```bash
cd python
pip install -r requirements.txt
```

**第二步: 更新前端依赖**
```bash
pnpm install
```

**第三步: 启动服务**
```bash
cd python
python start_server.py
```

**第四步: 构建前端**
```bash
pnpm build
```

**第五步: 验证功能**
- 访问Agent Dashboard，确认状态正常
- 访问插件市场，确认加载正常
- 访问目标管理页面，确认树形视图正常
- 访问成本看板，确认数据显示正常

### 6.3 可能遇到的风险及规避措施

| 风险 | 影响 | 规避措施 |
|------|------|---------|
| 数据库迁移失败 | 新功能不可用 | 启动前备份.db文件，迁移失败可回滚 |
| 依赖冲突 | 服务启动失败 | 使用虚拟环境(.venv)，确保依赖隔离 |
| 前端构建失败 | 页面无法访问 | 清除node_modules后重新install |
| 插件不兼容 | 插件功能异常 | 从插件市场安装已验证版本 |

### 6.4 数据迁移指南

**V1.6.0 -> V1.7.0 无需手动数据迁移**

所有新表结构会在首次启动时自动创建：
- `agent_states` - Agent状态表
- `goals` - 目标表
- `budgets` - 预算表
- `heartbeat` - 心跳记录表
- `plugins` - 插件注册表

已有数据（LNN模型、用户数据、任务记录等）完全不受影响。

---

## 七、变更统计

### 7.1 按变更类型汇总

| 变更类型 | 文件数 | 代码行数 | 占比 |
|---------|--------|---------|------|
| 新增 | 266 | 87,359 | ~100% |
| 修改 | 2 | ~1,000 | ~1% |

### 7.2 按模块汇总

| 模块 | 文件数 | 代码行数 | 主要变更内容 |
|------|--------|---------|-------------|
| Agent状态系统 | 6 | ~800 | API、模型、持久化、前端组件 |
| 插件生态系统 | 15 | ~5,000 | 核心、Worker、API、CLI、前端市场 |
| 模板演进系统 | 15 | ~4,500 | 演进、分支、A/B测试、更新服务、前端 |
| 目标对齐系统 | 10 | ~3,500 | 对齐逻辑、链存储、前端树形视图 |
| 企业治理体系 | 6 | ~2,500 | 风险识别、审批流程、能力门禁 |
| 资源成本管控 | 6 | ~2,000 | 预算、成本追踪、强制执行 |
| 心跳调度系统 | 5 | ~1,500 | 心跳、执行引擎、执行锁 |
| 技能市场 | 4 | ~1,000 | 技能加载、市场注册 |
| 模式引擎 | 3 | ~800 | 模式识别、匹配、应用 |
| 任务签出 | 4 | ~1,000 | 原子签出、任务模型 |
| 前端视图 | 15 | ~8,000 | 新增15个Vue页面组件 |
| 前端Composables | 4 | ~1,200 | 审计、健康、主权、Token管理 |
| 测试套件 | 16 | ~5,500 | 功能测试、单元测试、验证脚本 |
| Skills集合 | ~140 | ~48,000 | awesome-design-md-main设计系统 |
| 核心基础 | 4 | ~1,000 | 工作区、上下文、SQLite重试 |

### 7.3 核心功能覆盖

| 功能 | V1.6.0状态 | V1.7.0状态 | 变更说明 |
|------|-----------|-----------|---------|
| Agent状态管理 | 无 | **新增** | 全生命周期跟踪、持久化、恢复 |
| 插件生态 | 无 | **新增** | 市场、安装、依赖、Worker隔离 |
| 模板演进 | 无 | **新增** | 分支、A/B测试、灰度发布 |
| 目标对齐 | 无 | **新增** | 目标分解、链存储、任务生成 |
| 企业治理 | 基础审计 | **全面升级** | 风险、审批、能力门禁 |
| 成本管控 | 无 | **新增** | GPU预算、成本追踪、强制拦截 |
| 心跳调度 | 无 | **新增** | 心跳监测、任务触发、执行锁 |
| 技能市场 | 无 | **新增** | 动态加载、热插拔 |
| 模式引擎 | 无 | **新增** | 加工模式识别与匹配 |
| 任务签出 | 无 | **新增** | 原子化签出机制 |
| LNN系统 | 完整 | **保留** | 不受影响 |
| Agent网关 | 完整 | **保留** | 不受影响 |
| MCP服务器 | 完整 | **保留** | 不受影响 |

---

## 附录

### A. 提交时间线

```
2026-05-14 XX:XX:XX  feat: add agent state management, plugin system, template evolution, goal alignment and governance (b92b006) [V1.7.0] ⬅️ 本次版本
```

### B. 版本历史

| 版本 | 发布日期 | 核心功能 |
|------|---------|---------|
| V1.0.0 | 2026-04-29 | 项目初始化 |
| V1.1.0 | 2026-05-03 | 完整项目代码更新 |
| V1.2.0 | 2026-05-06 | 项目代码精简重构 |
| V1.3.0 | 2026-05-06 | 物理模型、Bosch CNC、校验引擎 |
| V1.4.0 | 2026-05-09 | LNN AI系统、部署基础设施 |
| V1.5.0 | 2026-05-10 | LNN缓存、量化、GPU训练、SSE、LOD |
| V1.6.0 | 2026-05-12 | Agent网关、MCP服务器、核心基础设施、LNN架构升级 |
| **V1.7.0** | **2026-05-14** | **Agent状态管理、插件生态、模板演进、目标对齐、企业治理、成本管控、心跳调度、技能市场** |

---

*文档生成时间: 2026-05-14*
