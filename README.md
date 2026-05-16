# Virtual-Realm-Manufacturing

[![Lint](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/lint.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/lint.yml)
[![Test](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/test.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/test.yml)
[![Build](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/build.yml/badge.svg)](https://github.com/printing10101/Virtual-Realm-Manufacturing/actions/workflows/build.yml)

灵境制造是一款面向制造行业的AI驱动桌面工具，核心解决机械加工里"图纸到NC代码"全流程效率低、门槛高、数据不安全的痛点。它能自动解析工程三视图、重建3D模型、规划加工工艺、生成可直接上机的NC代码，全程在本地设备运行，数据不上云。我们以"数据不出厂"为安全底线，集成本地大模型、工艺知识图谱与数学规划求解器，在保障企业工艺数据安全的同时，提供高精度、可落地的加工方案，让中小型制造企业也能用上工业级AI工具，真正服务于车间一线。

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
