# Hermes Agent 全面调研报告（重点：安装方式）

> 调研时间：2026-08-03｜信息来源：GitHub 官方仓库、hermes-agent.nousresearch.com 官方文档、hermesagents.net 安装页、社区技术文章（36氪/极客公园等）
> 结论：你关注的「Hermes」即 **Nous Research 开发的 Hermes Agent**——开源 MIT、自托管的自主 AI 智能体，与你此前提出的「本地算力 + 本地大模型 + 靠数据自我进化」需求高度契合。

---

## 一、软件定位与背景

| 项目 | 内容 |
|---|---|
| 名称 | Hermes Agent |
| 开发方 | Nous Research（去中心化 AI 研究实验室） |
| 性质 | 开源、MIT 许可、自托管（self-hosted）自主 AI 智能体 |
| 核心理念 | "与你一同成长的 Agent"（the agent that grows with you）——内置学习闭环，从任务中自动提炼技能、跨会话持久记忆、越用越强 |
| 首次开源 | 2026 年 2 月底 |
| GitHub 热度 | 增长极快（社区文章记录 4.7 万→10 万+→101K+ stars 不同时间点）。**以官方仓库 github.com/NousResearch/hermes-agent 为准**，第三方镜像站（如 hermes-agent.live）明确标注 "Not affiliated with Nous Research"，星标数据不可轻信 |
| 前身 | OpenClaw 的官方继任者（OpenClaw 已停止积极维护），提供 `hermes claw migrate` 一键迁移 |

---

## 二、核心能力

1. **持久化记忆 / 自改进学习闭环**：跨会话记住偏好、项目、环境；自动把复杂任务沉淀为可复用 Skill；Skill 在使用中自我优化；FTS5 全文检索历史会话；Honcho 用户画像建模。
2. **自动技能创建**：兼容 agentskills.io 开放标准，技能可搜索、分享、发布到 Skills Hub。
3. **多渠道网关**：Telegram、Discord、Slack、WhatsApp、Signal、飞书、企业微信、Email 等 15+ 平台，单网关进程统一接入；跨平台对话延续（在 Telegram 开聊可在终端续接）。
4. **定时自动化**：内置 cron 调度器，自然语言定义，投递到任意平台（每日报告、夜间备份、周审计等）。
5. **并行子代理**：spawn 隔离子代理并行工作流，支持 RPC 调用自身工具。
6. **终端后端（6–7 种）**：local、Docker、SSH、Singularity、Modal、Daytona、Vercel Sandbox；支持沙箱隔离，远程机无法读取自身代码/密钥。
7. **内置工具 47+**：网络搜索、浏览器自动化、代码执行、图像生成（FLUX）、TTS、语音转写等。
8. **MCP 集成**：可挂载外部 MCP 服务器扩展工具（含白名单 include/exclude 过滤）。
9. **模型无关**：Nous Portal、OpenRouter（200+ 模型）、OpenAI、Anthropic、z.ai/GLM、Kimi/Moonshot、MiniMax、阿里云 DashScope，以及本地 **Ollama / vLLM / SGLang / llama.cpp** 等 OpenAI 兼容端点。`hermes model` 一键切换，无代码改动、无锁定。
10. **研究导向**：批量生成工具调用轨迹、Atropos RL 环境、轨迹压缩导出（ShareGPT 格式）用于微调。

---

## 三、安装方式（重点）

### 3.1 系统要求

- **操作系统**：Linux、macOS、**原生 Windows（现已完整支持）**、WSL2、Android（Termux）、Nix/NixOS。
- **唯一手动前置依赖**：`git`（Windows 原生安装器会自带便携 MinGit ~45MB，无需管理员权限）。
- **安装脚本自动处理**：`uv`（Python 包管理器）、**Python 3.11**（pyproject 要求 `>=3.11`）、**Node.js v22**、ripgrep、ffmpeg。
- **资源**：≥ 2GB RAM（跑本地模型需更多）；~1GB 磁盘。
- **上下文要求**：代理使用工具至少需要 **64,000 tokens** 上下文（本地模型需在服务端提升，详见 3.7）。

### 3.2 方式一：一键脚本（官方推荐，适合绝大多数用户）

**Linux / macOS / WSL2 / Termux：**
```bash
curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
```
（GitHub raw 等效地址：`https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh`）

**Windows 原生（PowerShell）：**
```powershell
iex (irm https://hermes-agent.nousresearch.com/install.ps1)
```

脚本会自动完成：安装 uv → 通过 uv 装 Python 3.11 → 克隆到 `~/.hermes/hermes-agent`（含子模块 mini-swe-agent、tinker-atropos）→ 建 venv → 装全部依赖 → 把 `hermes` 软链到 `~/.local/bin`（Windows 为 `%LOCALAPPDATA%\hermes`）→ 运行交互式设置向导。**无需 sudo**。安装后：
```bash
source ~/.bashrc   # 或 source ~/.zshrc
hermes             # 启动对话
```

### 3.3 方式二：pip 安装（v0.14.0 起新增）

```bash
pip install -U hermes-agent
```
升级同样可用此命令；适合已习惯 Python 环境的用户。

### 3.4 方式三：手动 git 克隆（贡献者 / 想审阅每一行）

```bash
git clone --recurse-submodules https://github.com/NousResearch/hermes-agent.git
cd hermes-agent
curl -LsSf https://astral.sh/uv/install.sh | sh
uv venv venv --python 3.11
export VIRTUAL_ENV="$(pwd)/venv"
uv pip install -e ".[all]"
mkdir -p ~/.local/bin && ln -sf "$(pwd)/venv/bin/hermes" ~/.local/bin/hermes
hermes model
```
> 注意 `--recurse-submodules` **不可省略**（含 mini-swe-agent、tinker-atropos）。可按需只装部分 extras（如 `[messaging]`、`[voice]`、`[mcp]`）替代 `.[all]`。

### 3.5 方式四：自定义安装目录 / Docker

- **自定义目录**：安装前设 `HERMES_INSTALL_DIR`，或脚本加 `--dir`：
```bash
HERMES_INSTALL_DIR=/opt/hermes-agent bash -c "$(curl -fsSL https://raw.githubusercontent.com/NousResearch/hermes-agent/main/scripts/install.sh)"
```
- **Docker**：官方**无预置镜像**，但支持 Docker 作为"终端后端"（沙箱执行命令）。容器内源码升级：`cd ~/.hermes/hermes-agent && git pull && uv pip install -e ".[all]"`，或直接重跑一键脚本。

### 3.6 安装后初始化配置

```bash
hermes model     # 交互选择提供商与模型
hermes tools     # 配置启用的内置工具
hermes setup     # 全量设置向导（API key、网关连接）
```
也可直接编辑 `~/.hermes/config.yaml`，或用 `hermes config set KEY VALUE`。

### 3.7 本地模型（Ollama）配置 —— 你的核心诉求

Hermes 支持**完全离线**运行本地模型，无需 API key：

**交互式：**
```bash
hermes model
# 选 "Custom endpoint (self-hosted / VLLM / etc.)"
# URL:      http://localhost:11434/v1
# API key:  跳过（Ollama 不需要）
# Model:    qwen2.5-coder:32b   （举例）
```

**或直接改 `~/.hermes/config.yaml`：**
```yaml
model:
  default: qwen2.5-coder:32b
  provider: custom
  base_url: http://localhost:11434/v1
  context_length: 64000
```

> ⚠ **关键坑**：Ollama 默认上下文极短（显存 < 24GB 时仅 4096），必须**在 Ollama 服务端**提升，否则无法满足 Hermes 工具调用所需的 64K 上下文：
> ```bash
> OLLAMA_CONTEXT_LENGTH=64000 ollama serve
> ```
> 该值无法经 OpenAI 兼容 API 设置。
> WSL2 用户注意：若 Ollama 服务端跑在 Windows 宿主而非 WSL2 内，需用宿主 IP（或镜像网络）替代 `localhost`。

> 注：旧版文档曾用 `OPENAI_BASE_URL` / `OPENAI_API_KEY` 环境变量配置自定义端点；**新版以 `config.yaml` 的 `model.base_url` 为唯一真源**，`OPENAI_BASE_URL` 仅对 `openai-api` provider 生效。建议以新版为准。

### 3.8 验证 / 升级 / 卸载

**验证：**
```bash
hermes version    # 应 ≥ 0.14.0
hermes doctor     # 诊断依赖与配置（Python/uv/Node/ripgrep/ffmpeg/.env）
hermes status     # 打印当前配置（provider/工具/网关）
```

**升级：**
```bash
hermes update                 # 内置更新器（提示新配置）
pip install -U hermes-agent   # 或 pip
```

**卸载：**
```bash
hermes uninstall                                        # 一键（可保留配置）
rm ~/.local/bin/hermes && rm -rf ~/.hermes/hermes-agent  # 手动
rm -rf ~/.hermes                                        # 删全部用户数据（会话/记忆/技能/密钥，先备份！）
```
Windows 删数据：`Remove-Item -Recurse -Force "$env:LOCALAPPDATA\hermes"`

---

## 四、平台支持与安装路径

| 平台 | 支持状态 | 安装命令 | 安装路径 |
|---|---|---|---|
| 原生 Windows | 完整支持（CLI/gateway/TUI/tools 原生运行） | PowerShell `iex(irm ...)` | `%LOCALAPPDATA%\hermes` |
| WSL2 | 支持（用 Linux 命令） | `curl ... \| bash` | `~/.hermes` |
| Linux / macOS | 完整支持 | `curl ... \| bash` | `~/.hermes` |
| Termux (Android) | 支持（自动检测，装 `.[termux]` extra） | 同 curl 命令 | `~/.hermes` |

- 安装器会向 shell rc 文件追加 `export PATH="$HOME/.local/bin:$PATH"`；若 `hermes: command not found`，重载 shell 或检查 PATH。
- 原生 Windows 若杀软误报 `uv.exe` 为恶意（Astral 的 uv 包管理器），可加白名单：`Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\hermes\bin"`。

---

## 五、与你需求的契合度

对照你此前提出的「本地算力 + 本地大模型驱动 + 靠我给的数据不断进化」：

- ✅ **本地模型**：Ollama / vLLM 完全离线，无数据出网。
- ✅ **自我进化**：自动 Skill 沉淀 + 跨会话持久记忆（SQLite + FTS5，重启不丢失）。
- ✅ **数据自有**：所有记忆/会话/技能存于本地 `~/.hermes`，MIT 协议、无云锁定。
- ⚠ **平台建议**：你本机为 Windows。早期版本"不支持 Windows 原生"，现已有 PowerShell 安装器（已完整支持）；但若求最稳妥，仍可用 **WSL2（推荐 Ubuntu 22.04）** 跑 Linux 命令。
- ⚠ **资源**：本地跑 32B 级模型需足够显存；本体机若为笔记本独显，建议先用 OpenRouter 云模型验证流程，再切本地。

---

## 六、争议与风险提示（客观陈述）

1. **团队背景**：Nous Research 核心成员多有 Web3 背景（CEO 来自以太坊 MEV 基础设施 Eden Network），融资带代币计价特征；官方**未发行代币**，但链上已出现非官方 "NOUS" 代币。**任何与 NOUS 代币相关的交易、投资或高收益承诺都需高度警惕**。
2. **镜像站点**：部分第三方站点（hermes-agent.live 等）标注"Not affiliated with Nous Research"，下载与星标数据以**官方仓库 github.com/NousResearch/hermes-agent** 为准。
3. **项目阶段**：功能迭代极快（42 天 v0.1→v0.8），但记忆噪音、技能质量、训练闭环稳定性仍处早期，距离"普通用户无感使用"尚有距离。
