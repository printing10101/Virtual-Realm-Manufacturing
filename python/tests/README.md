# Bosch CNC 数据集集成测试说明

## 概述

本测试套件为 Bosch CNC 数据集集成系统提供全面的端到端测试,验证5个核心模块间的数据流转及功能协同正确性。

### 测试覆盖模块

1. **刀具磨损预测数据增强模块** (`bosch_cnc_loader.py` + `tool_wear_predictor.py`)
2. **RAG 知识库工艺经验注入模块** (`bosch_knowledge_builder.py` + `knowledge_base.py`)
3. **验证引擎阈值校准模块** (`validation_calibrator.py` + `validation_engine.py`)
4. **经验回放 Ground Truth 模块** (`ground_truth_adapter.py` + `experience_store.py`)
5. **模型微调领域数据模块** (`bosch_finetune_builder.py` + `model_finetuner.py`)

## 测试结构

```
python/tests/
├── conftest.py                    # 全局测试fixtures(包含Bosch测试fixtures)
├── test_bosch_integration.py      # Bosch CNC集成端到端测试
├── generate_test_data.py          # 测试样本数据生成脚本
└── data/
    └── bosch_test_samples/        # 测试样本数据目录
        ├── manifest.json
        └── data/
            ├── M01/
            │   ├── OP00/
            │   │   ├── good/
            │   │   └── bad/
            │   └── ...
            └── M02/
                └── ...
```

## 环境准备

### 1. 安装测试依赖

```bash
# 在项目根目录执行
cd python
pip install -r requirements-test.txt
```

### 2. 生成测试样本数据

```bash
# 生成合成测试数据
python tests/generate_test_data.py
```

此脚本将生成96个合成H5文件,包含:
- 2台机床 (M01, M02)
- 6道工序 (OP00~OP05)
- 2种标签 (good, bad)
- 2个时间段 (Oct_2018, Apr_2019)
- 每组合2个样本

### 3. 验证环境

```bash
# 检查pytest是否正确安装
pytest --version

# 检查测试数据是否存在
ls tests/data/bosch_test_samples/
```

## 运行测试

### 运行所有集成测试

```bash
cd python
pytest tests/test_bosch_integration.py -v
```

### 运行单个测试方法

```bash
# 运行完整流水线测试
pytest tests/test_bosch_integration.py::TestBoschCNCIntegration::test_full_pipeline -v

# 运行数据加载测试
pytest tests/test_bosch_integration.py::TestBoschCNCIntegration::test_data_loader_features -v

# 运行知识库测试
pytest tests/test_bosch_integration.py::TestBoschCNCIntegration::test_knowledge_base_enrichment -v

# 运行校准测试
pytest tests/test_bosch_integration.py::TestBoschCNCIntegration::test_validation_calibration -v

# 运行ground truth测试
pytest tests/test_bosch_integration.py::TestBoschCNCIntegration::test_ground_truth_validation -v

# 运行微调数据测试
pytest tests/test_bosch_integration.py::TestBoschCNCIntegration::test_finetune_data_quality -v
```

### 并行测试(加速执行)

```bash
# 使用pytest-xdist并行执行测试
pytest tests/test_bosch_integration.py -v -n auto
```

### 生成测试报告

```bash
# 生成HTML报告
pytest tests/test_bosch_integration.py -v --html=tests/reports/bosch_integration_report.html

# 生成代码覆盖率报告
pytest tests/test_bosch_integration.py -v --cov=app --cov-report=html
```

## 测试说明

### TestBoschCNCIntegration 测试类

| 测试方法 | 测试内容 | 成功标准 | 预计时间 |
|---------|---------|---------|---------|
| `test_full_pipeline` | 完整流水线端到端测试 | 无异常,指标达标 | <60s |
| `test_data_loader_features` | 数据加载和特征提取 | 18种特征,性能<2s | <10s |
| `test_knowledge_base_enrichment` | RAG知识库增强 | Top3命中率>90% | <30s |
| `test_validation_calibration` | 验证引擎阈值校准 | 准确率>0.9,时间<30s | <30s |
| `test_ground_truth_validation` | Ground Truth验证 | 字段完整度100% | <20s |
| `test_finetune_data_quality` | 微调数据集质量 | 相关度>95%,准确率>98% | <30s |

### 测试独立性

每个测试方法完全独立,可单独运行:
- 使用独立的临时目录(ChromaDB、规则文件、经验存储等)
- 测试间无状态干扰
- 使用固定随机种子(42)确保可复现性

### 测试数据

测试使用合成数据,特点:
- 正常样本: 低振幅(0.1g)、低噪声(0.05g)
- 异常样本: 高振幅(0.5g)、高噪声(0.3g)
- 包含500个采样点(0.25秒,2000Hz采样率)
- 三轴振动数据(X, Y, Z)

## CI/CD集成

### GitHub Actions示例

```yaml
name: Bosch CNC Integration Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3
      
      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.10'
      
      - name: Install dependencies
        run: |
          cd python
          pip install -r requirements.txt
          pip install -r requirements-test.txt
      
      - name: Generate test data
        run: |
          cd python
          python tests/generate_test_data.py
      
      - name: Run integration tests
        run: |
          cd python
          pytest tests/test_bosch_integration.py -v --cov=app --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v3
        with:
          file: ./python/coverage.xml
```

## 故障排查

### 测试数据不存在

```bash
# 重新生成测试数据
python tests/generate_test_data.py
```

### 依赖缺失

```bash
# 重新安装依赖
pip install -r requirements-test.txt
```

### ChromaDB持久化问题

```bash
# 清理ChromaDB缓存
rm -rf python/data/knowledge/chroma
```

### 测试超时

```bash
# 增加超时时间
pytest tests/test_bosch_integration.py -v --timeout=120
```

## 扩展测试

如需添加新测试,请遵循以下规范:

1. 在 `test_bosch_integration.py` 中添加新方法
2. 使用 `@pytest.fixture` 管理测试资源
3. 确保测试独立性和可复现性
4. 添加详细中文注释说明测试意图和成功标准
5. 单测试执行时间不超过60秒

## 维护者

- 测试框架: pytest 7.4+
- Python版本: 3.10+
- 最后更新: 2024
