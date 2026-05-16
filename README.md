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

# 终端 2：启动 Python 后端服务（默认 http://localhost:8000）
cd python
uvicorn app.main:app --reload --port 8000

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
