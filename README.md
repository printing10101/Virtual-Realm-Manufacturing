# Virtual-Realm-Manufacturing

[![Lint](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/lint.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/lint.yml)
[![Test](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/test.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/test.yml)
[![Build](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/build.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/build.yml)
[![Python](https://img.shields.io/badge/python-%3E%3D3.10-blue?logo=python&logoColor=white)](https://www.python.org/downloads/)
[![Node.js](https://img.shields.io/badge/node.js-%3E%3D18-green?logo=node.js&logoColor=white)](https://nodejs.org/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

灵境制造是一款面向制造行业的AI驱动桌面工具，核心解决机械加工里"图纸到NC代码"全流程效率低、门槛高、数据不安全的痛点。它能自动解析工程三视图、重建3D模型、规划加工工艺、生成可直接上机的NC代码，全程在本地设备运行，数据不上云。我们以"数据不出厂"为安全底线，集成本地大模型、工艺知识图谱与数学规划求解器，在保障企业工艺数据安全的同时，提供高精度、可落地的加工方案，让中小型制造企业也能用上工业级AI工具，真正服务于车间一线。

---

## 快速开始

### 前置条件

| 环境 | 最低版本 | 说明 |
|------|---------|------|
| **Node.js** | >= 18 | 前端运行时 |
| **pnpm** | >= 8 | 前端包管理器 |
| **Python** | >= 3.10 | 后端服务与AI模型 |
| **Rust** | >= 1.70 | Tauri 桌面应用编译（可选） |
| **Ollama** | 最新版 | 本地LLM推理（可选） |

### 一键安装

```bash
# 克隆项目代码库
git clone https://github.com/printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing

# 安装并拉取 Git LFS 大文件（PyTorch 模型权重等）
git lfs install
git lfs pull

# 安装前端项目依赖
pnpm install

# 安装 Python 后端依赖（建议使用虚拟环境）
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt

# （可选）安装 Ollama 并拉取推荐模型
# 下载地址: https://ollama.com/download
ollama pull qwen2.5-coder:7b
```

### 启动开发环境

每个命令需要在单独的终端窗口中运行：

```bash
# 终端 1：启动前端开发服务器（默认 http://localhost:1420）
pnpm dev

# 终端 2：启动 Python 后端服务（默认 http://localhost:8765）
cd python
uvicorn app.main:app --reload --port 8765

# 终端 3：启动 Tauri 桌面应用（需先启动上述两个服务）
pnpm tauri dev
```

> **提示**：Tauri 桌面应用可选。如果仅需 Web 界面，只需启动终端 1 和终端 2。

### 运行测试

```bash
# 前端单元测试（Vitest）
pnpm test:run

# Python 后端测试
pytest tests/ -v

# 端到端测试（Playwright）
npx playwright install chromium
npx playwright test
```

### 构建生产版本

```bash
# 构建 Tauri 桌面应用（输出: src-tauri/target/release/）
pnpm tauri build

# 仅构建前端静态文件（输出: dist/）
pnpm build
```

---

## Git LFS 使用说明

本项目使用 [Git LFS](https://git-lfs.com/) 管理大型二进制文件（PyTorch模型权重、CNC数据集等），以保持仓库体积轻量并加速克隆速度。

### 前置要求

在克隆仓库前，请先安装 Git LFS：

```bash
# macOS (Homebrew)
brew install git-lfs

# Ubuntu/Debian
sudo apt install git-lfs

# Windows (Scoop 或下载安装包)
scoop install git-lfs
# 或访问 https://git-lfs.com/ 下载安装包

# 初始化 Git LFS（全局，仅需执行一次）
git lfs install
```

### 克隆仓库

**完整克隆（包含所有大文件）：**

```bash
git lfs install          # 首次使用 LFS 必须执行
git clone git@github.com:printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing
git lfs pull              # 确保所有 LFS 文件已下载
```

**轻量级克隆（跳过大型文件，适合快速浏览代码）：**

```bash
GIT_LFS_SKIP_SMUDGE=1 git clone git@github.com:printing10101/Virtual-Realm-Manufacturing.git
cd Virtual-Realm-Manufacturing
# 后续需要某个文件时，按需拉取：
git lfs pull --include="path/to/file.pt"
```

**如果已克隆但缺少 LFS 文件：**

```bash
git lfs install
git lfs pull
```

### LFS 管理的文件类型

| 文件类型 | 说明 |
|---------|------|
| `*.pt`, `*.pth` | PyTorch 模型权重文件 |
| `*.h5`, `*.hdf5` | HDF5 数据文件 |
| `*.onnx` | ONNX 模型文件 |
| `*.pkl` | Python Pickle 文件 |
| `*.bin` | 二进制数据文件 |
| `data/traces/**` | 加工轨迹数据 |
| `uniwear-dataset-main/**/*.csv` | UniWear 刀具磨损数据集 |
| `CNC_Machining-main/**` | CNC 加工数据集 |

### 新增大型文件

如需添加新的二进制文件到仓库，Git LFS 会根据 `.gitattributes` 规则自动处理。手动添加：

```bash
git lfs track "*.new_extension"
git add .gitattributes
git add your_file.new_extension
git commit -m "chore: 添加新文件类型至Git LFS"
```

### CI/CD 环境

所有 GitHub Actions 工作流已配置自动拉取 LFS 文件，无需额外操作。

---

## 安全认证令牌配置

灵境制造使用 Bearer Token 进行 API 认证。每个部署实例应拥有独立的令牌，**切勿将令牌提交到版本控制系统**。

### 令牌加载优先级

系统按以下顺序查找令牌（优先级从高到低）：

| 优先级 | 来源 | 说明 |
|--------|------|------|
| 1 | `LNN_TOKEN` 环境变量 | **生产环境推荐方式** |
| 2 | `.lnn_token` 文件 | 开发环境便捷方式，自动生成 |
| 3 | 自动生成 | 首次运行时系统自动生成 UUID 令牌 |

### 配置方式

#### 方式一：环境变量（推荐，用于生产环境）

```bash
# Windows PowerShell
$env:LNN_TOKEN = "你的UUID令牌值"

# macOS / Linux
export LNN_TOKEN="你的UUID令牌值"
```

你也可以在 `.env` 文件中配置（需确保 `.env` 已在 `.gitignore` 中）：

```bash
# .env（不要提交到 Git）
LNN_TOKEN=你的UUID令牌值
```

#### 方式二：令牌文件（用于开发环境）

首次启动后端服务时，系统会自动在项目根目录生成 `.lnn_token` 文件。你也可以手动创建：

```bash
# 生成 UUID 格式的令牌
python -c "import uuid; print(str(uuid.uuid4()))" > .lnn_token
```

> **重要**：`.lnn_token` 和 `.lnn_token_meta.json` 已在 `.gitignore` 中配置，不会被 Git 追踪。请在每次克隆仓库后重新生成令牌。

### 令牌使用示例

```python
# 在 API 请求中使用令牌
import requests

headers = {
    "Authorization": "Bearer 你的令牌值",
    "Content-Type": "application/json",
}

response = requests.get("http://localhost:8765/api/v1/lnn/status", headers=headers)
```

```bash
# cURL 示例
curl -H "Authorization: Bearer 你的令牌值" http://localhost:8765/api/v1/lnn/status
```

### 令牌轮换

定期轮换令牌是安全最佳实践。可通过以下方式：

```bash
# 删除现有令牌文件，重启服务将自动生成新令牌
rm .lnn_token

# 或使用环境变量覆盖
export LNN_TOKEN=$(python -c "import uuid; print(str(uuid.uuid4()))")
```

### 安全最佳实践

- **永远不要**将令牌提交到 Git 仓库
- **定期轮换**令牌（建议每 30-90 天）
- **生产环境**必须使用环境变量方式，不要依赖自动生成
- **如果令牌被意外提交**，立即按以下步骤处理：
  1. 立即在系统中使旧令牌失效
  2. 使用 `git filter-repo` 清理 Git 历史
  3. 生成新令牌并更新所有配置
  4. 强制推送到远程仓库（通知团队成员）
- **团队协作**时，每个开发者使用独立令牌
- **CI/CD 环境**通过 Secrets 管理工具（GitHub Secrets 等）注入令牌

### 令牌元数据

令牌权限级别通过 `.lnn_token_meta.json` 文件管理：

```json
[
  {
    "token": "你的UUID令牌",
    "level": "R"
  }
]
```

权限级别：`R`（只读）、`W`（读写）、`T`（训练/管理）、`A`（管理员）
