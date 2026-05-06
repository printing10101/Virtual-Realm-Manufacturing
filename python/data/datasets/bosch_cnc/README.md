# Bosch CNC Machining Dataset

## 数据集来源

本数据集来自 [boschresearch/CNC_Machining](https://github.com/boschresearch/CNC_Machining) GitHub 仓库，是以下论文的配套数据集：

> Tnani, Mohamed-Ali; Feil, Michael; Diepold, Klaus. Smart Data Collection System for Brownfield CNC Milling Machines: A New Benchmark Dataset for Data-Driven Machine Monitoring. Procedia CIRP 2022, 107, 131–136.

论文地址: https://doi.org/10.1016/j.procir.2022.04.022

## 数据集简介

这是一个真实工业 CNC 铣床振动数据集，由博世 (Bosch) 研究团队采集。数据集包含：

- **3台机床**: M01, M02, M03
- **15种工序**: OP00 至 OP14
- **6个时间跨度**: 2018年10月至2021年8月，每个跨度约6个月
- **数据标签**: good (正常振动数据), bad (异常振动数据)
- **传感器**: 三轴加速度计 (Bosch CISS Sensor)，采样率 2kHz
- **数据格式**: HDF5 (.h5) 文件，包含 ndarray 维度为 (acc_values, n_channels)，n_channels 为 3 (X/Y/Z 轴)

## 目录结构

数据集的标准目录结构如下：

```
bosch_cnc/
├── manifest.json          # 数据集元数据信息
├── README.md              # 本文档
└── data/                  # 实际数据文件（需手动下载）
    ├── M01/               # 机床 M01 数据
    │   ├── OP00/
    │   │   ├── bad/
    │   │   │   └── *.h5
    │   │   └── good/
    │   │       └── *.h5
    │   ├── OP01/
    │   │   └── bad/
    │   │       └── *.h5
    │   │       └── good/
    │   │           └── *.h5
    │   ├── ... (OP02-OP14)
    ├── M02/               # 机床 M02 数据
    │   └── ... (同上结构)
    └── M03/               # 机床 M03 数据
        └── ... (同上结构)
```

文件命名规则: `机床号_时间_工序号_序号.h5`，例如 `M02_Aug_2019_OP03_000.h5`

## 数据用途与适用场景

本数据集适用于以下研究和应用场景：

- **刀具磨损预测**: 利用振动数据分析和预测刀具磨损状态
- **设备状态监测**: 实时监测 CNC 机床运行状态
- **预测性维护**: 基于振动特征的故障预测和维护策略
- **异常检测**: 识别加工过程中的异常振动模式
- **RAG 知识库**: 作为工业设备维护知识的检索增强生成数据源
- **验证引擎**: 为算法和模型提供真实工业数据验证基准

## 许可证信息

- **数据集许可证**: [Creative Commons Attribution 4.0 International License (CC-BY-4.0)](http://creativecommons.org/licenses/by/4.0/)
- **代码许可证**: BSD-3-Clause

使用本数据集时，请保留所有版权和引用信息。如在学术研究中使用，请引用上述论文。

## 数据集下载说明

> **注意**: 由于数据集文件较大且数量众多，无法通过自动化脚本完整下载。请按以下步骤手动下载：

### 方法一：Git 克隆 (推荐)

```bash
cd python/data/datasets/bosch_cnc

# 使用 sparse-checkout 只下载 data 目录
git init
git remote add origin https://github.com/boschresearch/CNC_Machining.git
git config core.sparseCheckout true
echo "data/" >> .git/info/sparse-checkout
git pull origin main --depth 1

# 完成后删除 .git 目录以节省空间
rm -rf .git
```

### 方法二：GitHub CLI

```bash
cd python/data/datasets/bosch_cnc
gh repo clone boschresearch/CNC_Machining temp -- --sparse --filter=blob:none
cd temp
git sparse-checkout set data
mv data ../
cd ..
rm -rf temp
```

### 方法三：直接下载 ZIP

1. 访问 https://github.com/boschresearch/CNC_Machining
2. 点击 "Code" -> "Download ZIP"
3. 解压后将 `CNC_Machining-main/data/` 目录内容复制到此 `bosch_cnc/` 目录下

### 验证下载完整性

下载完成后，应包含以下结构：

- `data/M01/` - 包含 OP00 至 OP14 共15个工序目录
- `data/M02/` - 包含 OP00 至 OP14 共15个工序目录
- `data/M03/` - 包含 OP00 至 OP14 共15个工序目录

每个工序目录下应有 `good/` 和/或 `bad/` 子目录，包含若干 `.h5` 文件。

## 数据加载示例

```python
import h5py
import numpy as np

# 加载单个 HDF5 文件
with h5py.File('data/M01/OP00/good/M01_Oct_2018_OP00_000.h5', 'r') as f:
    # 获取振动数据
    data = f['acc_values'][:]  # 形状: (n_samples, 3)
    # 3个通道分别对应: 0=X轴, 1=Y轴, 2=Z轴
```

更多加载和可视化方法请参考原仓库中的 `utils/data_loader_utils.py` 和 `Data_explorer.ipynb`。
