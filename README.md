<div align="center">

# 灵境制造 · Virtual Realm Manufacturing

**AI 驱动的"图纸→NC 代码"全流程桌面工具 · 数据不出厂 · 工业级可落地**

[![CI](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/ci.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/ci.yml)
[![PR Check](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/pr.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/pr.yml)
[![Release](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/release.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/release.yml)
[![Python](https://img.shields.io/badge/python-%E2%89%A53.10-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/node.js-%E2%89%A518-green?logo=node.js&logoColor=white)](https://nodejs.org/)
[![Rust](https://img.shields.io/badge/rust-%E2%89%A51.70-orange?logo=rust&logoColor=white)](https://www.rust-lang.org/)
[![Tauri](https://img.shields.io/badge/Tauri-2.0-FFC131?logo=tauri&logoColor=white)](https://v2.tauri.app/)
[![License](https://img.shields.io/badge/license-Apache--2.0-blue.svg)](LICENSE)
[![Citation](https://img.shields.io/badge/Cite-BibTeX-9cf)](CITATION.cff)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](CONTRIBUTING.md)
[![Code of Conduct](https://img.shields.io/badge/CoC-2.1-ff69b4.svg)](CODE_OF_CONDUCT.md)

</div>

---

## 为什么是灵境制造

中小型制造企业长期受困于三个矛盾:

- **门槛高**——CAM 软件贵、师资缺、年轻人不会用。
- **效率低**——一张图纸从解析、3D 重建、工艺规划到 NC 代码常需反复试切。
- **数据敏感**——工艺参数、刀具数据是企业核心资产,云端方案不可接受。

灵境制造是一个把"图纸到 NC 代码"全流程**搬到本地桌面**的 AI 工具,核心由 LNN(液体神经网络)+ 本地 LLM(Ollama)+ RAG 工艺知识库驱动。从工程三视图解析、3D 模型重建、工艺规划、刀具路径仿真到 CNC 后处理,**全程不出厂、不上云、可上机**。

> 适合人群:机械加工工艺工程师、CAM 编程员、智能制造研究者、LNN/液体神经网络方向研究生。

---

## 核心能力一览

| 能力域 | 关键特性 | 技术底座 |
|--------|---------|---------|
| **图纸智能解析** | DXF/STEP 工程图自动识别特征(孔/腔/凸台/型腔) | Python + 几何内核 + LNN 分类 |
| **3D 模型重建** | 三视图→3D 实体重建 + AABB 碰撞检测 | Three.js + 体素切削仿真 |
| **工艺规划** | 装夹方案 / 工序排序 / 刀具选择 / 物理约束验证 | 数学规划 + LLM 工艺理解 |
| **NC 代码生成** | 11 种后处理器(Fanuc/Siemens/Heidenhain/Mitsubishi/Fagor/GSK/HNC/KND 等) | 后处理 DSL + 控制器语法树 |
| **颤振预测** | 切削颤振稳定性叶瓣图 + LNN 时序预测 | LTC 网络 + Tlusty 解析法 |
| **刀具磨损预测** | PHM2010 数据集训练 + 自采 6061-T6 数据微调 | CFC/LTC 模型 + 在线推理 |
| **RAG 知识库** | 材料库 / 刀具库 / 工艺案例混合检索 | BM25 + Vector + Cross-Encoder 重排 |
| **知识图谱** | 材料/刀具/工艺参数实体抽取与关联 | LLM 抽取 + 图存储 + 查询 API |
| **DNC 集成** | MTConnect / OPC UA / MES 适配 | 统一 adapter + 协议网关 |
| **本地 LLM** | Ollama / LM Studio / llama.cpp / vLLM 多后端 | Provider Gateway + 软依赖回退 |
| **NL2CAD** | 自然语言→CAD 命令 + 工艺描述 | LLM + 规则回退 |
| **工艺解释** | AI 决策可解释化 + 置信度展示 | process_explainer + session_store |

---

## 系统架构

```
┌──────────────────────────────────────────────────────────────────┐
│                      Tauri 2 桌面外壳 (Rust)                       │
│   sidecar 进程托管 · IPC 命令 · 系统集成 · 自动更新 · 单文件分发   │
└───────────────┬──────────────────────────────────┬───────────────┘
                │                                  │
        ┌───────▼────────┐                ┌────────▼────────┐
        │   Vue 3 前端   │                │  Python 后端    │
        │  TypeScript    │   HTTP/SSE     │   FastAPI       │
        │  Pinia + EPC   │◄─────────────►│   uvicorn       │
        │  Three.js 3D   │                │  40+ REST 路由  │
        └────────────────┘                └────────┬────────┘
                                                  │
        ┌─────────────────────────────────────────┼───────────────┐
        │                  AI 内核层                │               │
        │  ┌─────────────┐  ┌──────────────┐  ┌────▼─────┐  ┌──────┴──────┐
        │  │  LNN 引擎   │  │ LLM Gateway  │  │   RAG    │  │ 知识图谱    │
        │  │  LTC / CFC  │  │ Ollama/云 API │  │ BM25+Vec│  │ Extractor   │
        │  │  量化/路由  │  │ Provider 多后端│  │ RRF+Rerank│  │ Query API   │
        │  └─────────────┘  └──────────────┘  └──────────┘  └─────────────┘
        └─────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
        │              工程计算与制造执行层                       │
        │  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐ │
        │  │ 工艺规划     │  │ 仿真引擎     │  │ 后处理 + DNC   │ │
        │  │ 特征识别     │  │ 碰撞/切削力   │  │ 11 控制器      │ │
        │  │ 工序排序     │  │ 体素切削     │  │ MTConnect/OPC │ │
        │  └─────────────┘  └──────────────┘  └────────────────┘ │
        └─────────────────────────────────────────────────────────┘
                                  │
        ┌─────────────────────────┼─────────────────────────────┐
        │              数据持久化层(全本地)                      │
        │   SQLite · ChromaDB · LFS 模型权重 · 加工数据集       │
        └─────────────────────────────────────────────────────────┘
```

**四层架构,数据完全本地化**:从 LLM 推理到工艺数据库、从 LNN 权重到 CNC 数据集,**不依赖任何云服务**即可独立运行。

---

## 快速开始

### 前置条件

| 环境 | 最低版本 | 说明 |
|------|---------|------|
| **Node.js** | ≥ 18 | 前端运行时 |
| **pnpm** | ≥ 8 | 前端包管理器 |
| **Python** | ≥ 3.10 | 后端服务与 AI 模型 |
| **Rust** | ≥ 1.70 | Tauri 桌面应用编译(可选) |
| **Ollama** | 最新版 | 本地 LLM 推理(可选但强烈推荐) |

### 一键安装

```bash
# 克隆仓库
git clone https://github.com/printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing

# 拉取 Git LFS 大文件(PyTorch 模型权重等)
git lfs install
git lfs pull

# 安装前端依赖
pnpm install

# 准备 Python 后端(建议虚拟环境)
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# (可选)拉取本地 LLM
ollama pull qwen2.5-coder:7b
```

### 启动开发环境

三个终端分别运行:

```bash
# 终端 1:前端开发服务器(默认 http://localhost:1420)
pnpm dev

# 终端 2:Python 后端(默认 http://localhost:8765)
cd python
uvicorn app.main:app --reload --port 8765

# 终端 3:Tauri 桌面应用(需先启动上述两个服务)
pnpm tauri dev
```

> **提示**:Tauri 桌面壳可选。若仅需 Web 界面,跑终端 1+2 即可。

### 运行测试

```bash
# 前端单元测试(Vitest)
pnpm test:run

# Python 后端测试
python -m pytest python/tests

# 前端组件测试已由 Vitest 覆盖,暂未启用 Playwright E2E 套件
```

### 构建生产版本

```bash
# 构建 Tauri 桌面应用(输出:src-tauri/target/release/)
pnpm tauri build

# 仅构建前端静态文件(输出:dist/)
pnpm build
```

---

## 项目结构

```
Virtual-Realm-Manufacturing/
├── src/                          # 前端 · Vue 3 + TypeScript
│   ├── components/               # CommandPalette · Copilot · Onboarding ·
│   │                             # settings(LLM 引擎/路由/AutoDetect) ·
│   │                             # toolpath-editor · plugin · goals ·
│   │                             # simulation · dxf/step_import
│   ├── views/                    # 30+ 视图:AgentDashboard · Goals ·
│   │                             # ProcessPlanning · Simulation ·
│   │                             # NLModeling · QualityInspection ·
│   │                             # PluginMarket · TaskBoard · BranchManager …
│   ├── stores/                   # Pinia:agents/auth/llmProviders/plugin/
│   │                             # processUnderstanding/project/rules/…
│   ├── composables/              # useHealthMonitor · useSovereigntySettings ·
│   │                             # useCommandPalette · useSimulationVisualization …
│   └── locales/                  # zh-CN / en(i18n)
│
├── src-tauri/                    # Tauri 2 桌面外壳 · Rust
│   └── src/                      # commands · sidecar · main · lib
│
├── python/                       # 后端 · FastAPI + PyTorch
│   ├── app/
│   │   ├── ai/
│   │   │   ├── llm/providers/    # 云:anthropic/deepseek/gemini/openai/qwen
│   │   │   │                     # 本地:ollama/lmstudio/llamacpp/vllm/tgi/…
│   │   │   ├── lnn/              # LTC/CFC/Hybrid · 训练/推理/量化/路由
│   │   │   ├── process_explainer/   # AI 决策可解释化
│   │   │   ├── process_understanding/  # 任务分类 + 知识检索 + 方案生成
│   │   │   └── unified_embedding/    # 统一嵌入空间
│   │   ├── api/v1/               # 40+ REST 路由:lnn/dnc/knowledge_graph/
│   │   │                         # nl2cad/process_explainer/sharp/
│   │   │                         # collision_check/dxf_pipeline/sse/…
│   │   ├── postprocessor/        # 11 控制器:fanuc/siemens/heidenhain/
│   │   │                         # mitsubishi/fagor/gsk/hnc/knd/xmachine
│   │   ├── dnc/                  # mtconnect/opcua/mes/unified_adapter
│   │   ├── knowledge_graph/      # llm/pdf 抽取 + 校验 + 查询
│   │   ├── rag/                  # 混合检索(BM25+Vector+RRF)+ Cross-Encoder
│   │   ├── process_planning/     # 特征识别 + 装夹 + 工序 + 物理验证
│   │   ├── simulation/           # 颤振/切削力/体素切削
│   │   ├── benchmarks/           # API · 业务 · 并发 · 数据库 · LNN 推理
│   │   └── database/             # SQLite + machining/tool/training 模型
│   ├── models/lnn/               # LNN 权重(Git LFS)
│   └── data/                     # PHM2010 + 自采 6061-T6 数据集
│
├── docs/                         # 文档体系(20+ 子目录)
│   ├── adr/                      # 架构决策记录
│   ├── ai/ api/ baseline/ development/ integrations/
│   ├── knowledge-graph/ pipelines/ prompts/ rag/ reports/
│   ├── research/ runbook/ security/ simulation/ user-guide/
│   ├── 变更摘要/                 # 18 个版本(V1.3.0 → V2.5.0)
│   └── 大创赛/论文实验/          # 学术论文 + 实验脚本
│
├── docs-site/                    # VitePress 文档站(发布镜像)
├── .github/                      # 11 个 CI 工作流 + Issue/PR 模板
├── config/                       # 运行时配置
├── tests/                        # Vitest 前端组件测试 + benchmark 基线
└── requirements.txt / package.json / Cargo.toml
```

---

## 核心技术亮点

### 1. LNN(液体神经网络)引擎

灵境制造的核心 AI 创新在于将 **LTC(Liquid Time-Constant)网络** 用于切削颤振时序预测:

- `ltc` / `cfc` / `hybrid` 三种模型变体,支持训练/推理/量化全链路
- 对比传统 RNN/LSTM,LTC 在长时间序列上表现更稳定
- `task_router` 根据任务复杂度自动选择轻量/重型模型
- 学术背景详见 [docs/大创赛/论文实验/](docs/大创赛/论文实验/)

### 2. Provider Gateway · 多 LLM 后端

一套统一接口对接 **9 种 LLM 后端**,关键 LLM 模块采用软依赖+规则回退:

| 云端 API | 本地推理 |
|----------|---------|
| Anthropic Claude | Ollama |
| DeepSeek | LM Studio |
| Google Gemini | llama.cpp |
| OpenAI | vLLM / TGI |
| 通义千问 Qwen | KoboldCpp |

### 3. RAG 混合检索 + 知识图谱

- **混合检索**:BM25 + 向量检索 + RRF 融合 + Cross-Encoder 重排
- **实体抽取**:材料(TC4/HRC52/6061-T6)、刀具参数、信号类型(振动/声发射/力)
- **统一嵌入空间**:`unified_embedding` 模块对齐多源异构数据

### 4. 11 种 CNC 后处理器

覆盖主流控制器生态:Fanuc / Siemens / Heidenhain / Mitsubishi / Fagor / GSK / HNC / KND / xmachine,基于后处理 DSL + 控制器语法树生成。

### 5. DNC 工业现场集成

- **MTConnect** 适配器 + 客户端
- **OPC UA** 适配器
- **MES** 客户端
- 统一 adapter 抽象,支持多协议并发

### 6. 数据主权设计

- 全栈本地化:LLM / 数据库 / 模型权重 / 工艺数据
- `useSovereigntySettings` composable 持续监控数据流向
- Bearer Token 认证 + 4 级权限(R/W/T/A)
- 详细安全实践见 [SECURITY.md](SECURITY.md)

---

## 学术与引用

本项目融合学术研究与工程实践,LNN 颤振预测方向有完整论文与实验支撑。若在学术工作中引用本项目:

```bibtex
@software{Lingjing_Virtual_Realm_Manufacturing,
  title  = {Virtual Realm Manufacturing: AI-Driven Drawing-to-NC Pipeline},
  author = {灵境制造 Team},
  year   = {2026},
  url    = {https://github.com/printing10101/Virtual-Realm-Manufacturing}
}
```

完整引用格式见 [CITATION.cff](CITATION.cff)。学术背景与实验数据见 [docs/大创赛/论文实验/](docs/大创赛/论文实验/)。

---

## 性能基准

`python/app/benchmarks/` 提供完整的性能基准测试套件:

| 基准 | 覆盖范围 |
|------|---------|
| `api_bench` | REST API 吞吐量与延迟 |
| `business_logic_bench` | 工艺规划/特征识别核心算法 |
| `concurrency_bench` | 高并发场景稳定性 |
| `database_bench` | SQLite/ChromaDB 读写 |
| `drawing_parse_bench` | DXF/STEP 解析速度 |
| `lnn_inference_bench` | LNN 推理延迟 |
| `nc_generation_bench` | NC 代码生成吞吐 |

---

## Git LFS 使用说明

本项目使用 [Git LFS](https://git-lfs.com/) 管理 PyTorch 模型权重、CNC 数据集等大文件。

<details>
<summary><b>📖 LFS 完整使用指南(点击展开)</b></summary>

### 前置要求

```bash
# macOS (Homebrew)
brew install git-lfs

# Ubuntu/Debian
sudo apt install git-lfs

# Windows (Scoop 或下载安装包)
scoop install git-lfs
# 或访问 https://git-lfs.com/ 下载安装包

# 初始化(全局,仅需一次)
git lfs install
```

### 克隆仓库

**完整克隆(包含所有大文件):**

```bash
git lfs install
git clone git@github.com:printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing
git lfs pull
```

**轻量级克隆(跳过大文件,适合快速浏览):**

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone git@github.com:printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing
# 后续需要某文件时按需拉取
git lfs pull --include="path/to/file.pt"
```

### LFS 管理的文件类型

| 文件类型 | 说明 |
|---------|------|
| `*.pt`, `*.pth` | PyTorch 模型权重 |
| `*.h5`, `*.hdf5` | HDF5 数据文件 |
| `*.onnx` | ONNX 模型 |
| `*.pkl` | Python Pickle |
| `*.bin` | 二进制数据 |
| `data/traces/**` | 加工轨迹数据 |
| `data/external/cnc_machining/**` | CNC 数据集 |

### 新增大文件

```bash
git lfs track "*.new_extension"
git add .gitattributes
git add your_file.new_extension
git commit -m "chore: 添加新文件类型至Git LFS"
```

CI/CD 环境已配置自动拉取 LFS,无需额外操作。

</details>

---

## 安全认证令牌

灵境制造使用 Bearer Token 进行 API 认证,**切勿将令牌提交到版本控制系统**。

<details>
<summary><b>🔐 令牌配置详情(点击展开)</b></summary>

### 令牌加载优先级

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | `LNN_TOKEN` 环境变量 | **生产环境推荐** |
| 2 | `.lnn_token` 文件 | 开发环境便捷方式 |
| 3 | 自动生成 | 首次运行自动生成 UUID |

### 配置方式

**方式一:环境变量(推荐,生产环境)**

```bash
# Windows PowerShell
$env:LNN_TOKEN = "你的UUID令牌值"

# macOS / Linux
export LNN_TOKEN="你的UUID令牌值"
```

也可写入 `.env`(确保 `.env` 已在 `.gitignore`):

```bash
LNN_TOKEN=你的UUID令牌值
```

**方式二:令牌文件(开发环境)**

```bash
python -c "import uuid; print(str(uuid.uuid4()))" > .lnn_token
```

> `.lnn_token` 和 `.lnn_token_meta.json` 已在 `.gitignore` 中,每次克隆后需重新生成。

### 令牌使用示例

```python
import requests

headers = {
    "Authorization": "Bearer 你的令牌值",
    "Content-Type": "application/json",
}
response = requests.get("http://localhost:8765/api/v1/lnn/status", headers=headers)
```

```bash
curl -H "Authorization: Bearer 你的令牌值" http://localhost:8765/api/v1/lnn/status
```

### 令牌权限级别

`R`(只读) / `W`(读写) / `T`(训练/管理) / `A`(管理员)。

### 安全最佳实践

- **永远不要**将令牌提交到 Git 仓库
- **定期轮换**令牌(建议每 30–90 天)
- 生产环境必须使用环境变量
- 团队协作时每个开发者使用独立令牌
- CI/CD 通过 GitHub Secrets 注入

</details>

---

## 路线图

- [x] LNN(LTC/CFC)训练与推理框架
- [x] 11 种 CNC 后处理器
- [x] MTConnect / OPC UA / MES 适配
- [x] RAG 混合检索 + Cross-Encoder 重排
- [x] 知识图谱抽取与查询 API
- [x] Tauri 2 桌面应用打包
- [ ] 实时颤振在线监测插件
- [ ] 工艺数字孪生(物理仿真 + 数据驱动融合)
- [ ] 多语言 UI(英/日/德)
- [ ] 移动端工艺看板

---

## 社区与贡献

我们欢迎任何形式的贡献——bug 报告、功能建议、文档完善、代码提交。

| 文档 | 用途 |
|------|------|
| [CONTRIBUTING.md](CONTRIBUTING.md) | 贡献指南 · 环境搭建 · PR 规范 · 代码规范 |
| [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | 社区行为准则 |
| [SECURITY.md](SECURITY.md) | 安全漏洞披露流程 |
| [CITATION.cff](CITATION.cff) | 学术引用格式 |
| [GitHub Issues](https://github.com/printing10101/Virtual-Realm-Manufacturing/issues) | 提交 bug 或功能建议 |

**快速贡献路径**:

1. Fork 本仓库
2. 创建分支:`git checkout -b feature/your-feature`
3. 遵循 [Conventional Commits](https://www.conventionalcommits.org/) 提交
4. 提交 PR,CI 通过后等待 Review

---

## License

本项目基于 [Apache License 2.0](LICENSE) 开源,允许商业使用与专利授权。

```
Copyright 2026 灵境制造 Contributors

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

    http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
See the License for the specific language governing permissions and
limitations under the License.
```

---

<div align="center">

**⭐ 如果这个项目对你有帮助,欢迎 star · 🍴 Fork · 📢 分享给同行**

Made with care for the manufacturing community.

</div>
