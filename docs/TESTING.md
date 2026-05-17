# 灵境制造 - 测试体系指南

> 完整的测试框架、CI流水线配置和测试用例编写规范

## 目录

- [1. 概述](#1-概述)
- [2. 测试目录结构](#2-测试目录结构)
- [3. 本地测试环境搭建](#3-本地测试环境搭建)
- [4. 测试运行命令](#4-测试运行命令)
- [5. CI流水线说明](#5-ci流水线说明)
- [6. 测试结果解读](#6-测试结果解读)
- [7. 测试用例模板](#7-测试用例模板)
- [8. 覆盖率目标](#8-覆盖率目标)

---

## 1. 概述

本项目采用分层测试体系，包括：

| 测试类型 | 技术栈 | 覆盖率目标 | 执行环境 |
|---------|--------|-----------|---------|
| 单元测试 | pytest | ≥80% | 本地/CI |
| 集成测试 | pytest + FastAPI TestClient | - | 本地/CI |
| 回归测试 | pytest + 自定义G-code比对工具 | - | 本地/CI |
| 前端测试 | vitest + @vue/test-utils | ≥70% | 本地/CI |
| E2E测试 | Playwright | - | 本地/CI |

---

## 2. 测试目录结构

```
python/tests/
├── conftest.py              # 共享fixtures（环境配置、测试数据）
├── unit/                    # 单元测试
│   ├── __init__.py
│   ├── test_geometry_operations.py  # 几何运算测试（示例）
│   └── test_postprocessor.py        # 后处理器测试（示例）
├── integration/             # 集成测试
│   ├── __init__.py
│   └── test_machining_workflow.py   # 完整加工流程测试（示例）
├── regression/              # 回归测试
│   ├── __init__.py
│   └── test_gcode_baseline.py       # G-code基准比对测试（示例）
├── fixtures/                # 测试数据（STL模型、G-code基准等）
│   └── __init__.py
├── utils/                   # 测试辅助工具
│   ├── __init__.py
│   ├── gcode_helpers.py     # G-code解析/比对/生成
│   └── data_generators.py   # 测试数据生成器
└── [其他已有测试文件...]    # 兼容已有的 test_*.py

src/                         # 前端
├── tests/
│   └── setup.ts             # vitest全局配置和组件stubs
├── components/
│   └── step_import/
│       └── StepImportDialog.test.ts  # 组件测试（示例）
└── views/
    └── RuleEditor.test.ts            # 视图测试（示例）
```

### 目录说明

- **unit/**: 针对单一函数/类/模块的测试，不依赖外部资源，执行速度快
- **integration/**: 多模块协作测试，验证业务流程完整性
- **regression/**: 基准回归测试，确保代码变更不影响核心功能
- **fixtures/**: 存放测试数据文件（STL、G-code基准等）
- **utils/**: 共享测试工具函数（数据生成、结果验证、性能计时等）

---

## 3. 本地测试环境搭建

### 3.1 Python测试环境

```bash
# 进入python目录
cd python

# 安装项目依赖
pip install -r requirements.txt

# 安装测试专用依赖
pip install pytest pytest-cov pytest-asyncio httpx

# 验证pytest安装
pytest --version
```

### 3.2 前端测试环境

```bash
# 安装依赖
pnpm install

# 验证vitest安装
pnpm vitest --version
```

---

## 4. 测试运行命令

### 4.1 Python测试

```bash
# 运行所有测试
cd python
pytest

# 仅运行单元测试（快速）
pytest -m unit -v

# 仅运行集成测试
pytest -m integration -v

# 仅运行回归测试
pytest -m regression -v

# 运行后处理器相关测试
pytest -m postprocessor -v

# 运行几何运算相关测试
pytest -m geometry -v

# 运行特定测试文件
pytest tests/unit/test_geometry_operations.py -v

# 运行特定测试类
pytest tests/unit/test_postprocessor.py::TestFanucPostProcessor -v

# 运行特定测试方法
pytest tests/unit/test_postprocessor.py::TestFanucPostProcessor::test_header_format -v

# 带覆盖率报告运行
pytest -m unit --cov=app --cov-report=html:cov_html -v

# 带性能计时（显示最慢的10个测试）
pytest -m unit --durations=10

# 运行所有已有测试（包括根目录的 test_*.py）
pytest tests/ -v
```

### 4.2 前端测试

```bash
# 运行所有前端测试
pnpm test

# 运行并显示详细输出
pnpm vitest run -v

# 运行特定组件测试
pnpm vitest run src/components/step_import/StepImportDialog.test.ts

# 带覆盖率报告
pnpm test:run -- --coverage

# 监视模式（文件变更自动重跑）
pnpm vitest
```

### 4.3 组合命令

```bash
# 完整测试套件（Python + 前端）
pytest python/tests/ -m "not skip_ci" && pnpm vitest run

# 快速冒烟测试（仅核心单元测试）
pytest python/tests/unit/ -m "unit" --tb=short
```

---

## 5. CI流水线说明

### 5.1 触发条件

- 代码推送到 `main` / `master` / `develop` 分支时自动触发
- Pull Request 创建或更新时自动触发

### 5.2 流水线阶段

| 阶段 | 超时 | 依赖 | 说明 |
|------|------|------|------|
| Lint & Type Check | 15min | 无 | Python ruff + 前端 ESLint |
| Python Unit Tests | 30min | 无 | Python 3.9/3.10/3.11 多版本 |
| Python Integration Tests | 60min | Unit Tests | 完整业务流程 |
| Python Regression Tests | 30min | Unit Tests | G-code基准比对 |
| Frontend Tests | 20min | 无 | Vitest组件测试 |
| Full Test Suite | 45min | 无 | 主分支推送时执行 |
| Test Summary Report | 5min | 所有阶段 | 汇总报告 |

### 5.3 配置参数说明

- **Python版本**: 支持 3.9/3.10/3.11 矩阵测试，确保兼容性
- **Node.js版本**: 18.x LTS
- **依赖缓存**: pip和pnpm依赖通过GitHub Actions Cache加速
- **测试产物**: JUnit XML和覆盖率报告保留30天
- **覆盖率上传**: 自动上传到Codecov，集成到PR检查
- **通知机制**: 测试失败时GitHub自动标记PR状态

### 5.4 缓存机制

```yaml
pip缓存:
  key: ${{ runner.os }}-pip-${{ python-version }}-${{ hashFiles('requirements.txt') }}
  
pnpm缓存:
  key: ${{ runner.os }}-pnpm-${{ hashFiles('pnpm-lock.yaml') }}
```

---

## 6. 测试结果解读

### 6.1 pytest输出

```
tests/unit/test_postprocessor.py::TestFanucPostProcessor::test_header_format PASSED [100%]
```
- **PASSED**: 测试通过
- **FAILED**: 测试失败，查看错误详情
- **ERROR**: 测试本身出错（非断言失败）
- **SKIPPED**: 测试被跳过（如标记了skip_ci）
- **XFAIL**: 预期失败的测试

### 6.2 覆盖率报告解读

```
---------- coverage: platform linux, python 3.10.0 ----------
Name                        Stmts   Miss  Cover
-----------------------------------------------
app/postprocessor/fanuc.py     45      3    93%
app/postprocessor/base.py      22      0   100%
-----------------------------------------------
TOTAL                         500     85    83%
```
- **Cover < 80%**: 需要补充测试
- **Miss列**: 未覆盖的代码行数

### 6.3 CI失败排查

1. 查看GitHub Actions日志中的具体失败测试
2. 本地复现: 运行相同的 `pytest` 命令
3. 检查是否是环境差异（Python版本、依赖版本）
4. 确认测试是否依赖本地资源（标记 `skip_ci`）

---

## 7. 测试用例模板

### 7.1 Python单元测试模板

```python
"""[模块名] 单元测试。

测试范围：
- 正常情况
- 边界条件
- 异常情况
- 性能指标
"""

from __future__ import annotations

import pytest
from app.[module] import [ClassOrFunction]


@pytest.mark.unit
@pytest.mark.[category]
class Test[ClassName]:
    """[类名] 测试类。"""

    def setup_method(self):
        """每个测试方法执行前的初始化。"""
        self.target = [ClassOrFunction]()

    def test_normal_case(self):
        """正常情况测试。"""
        result = self.target.method(input_data)
        assert result == expected_output

    def test_boundary_condition(self):
        """边界条件测试。"""
        result = self.target.method(boundary_input)
        assert result == expected_boundary_output

    def test_invalid_input(self):
        """异常输入测试。"""
        with pytest.raises(ExpectedException):
            self.target.method(invalid_input)

    def test_performance(self, performance_timer):
        """性能测试。"""
        with performance_timer as t:
            self.target.method(large_input)
        assert t.elapsed_s < 5.0, f"执行时间 {t.elapsed_s}s 超出限制"


@pytest.mark.unit
@pytest.mark.[category]
def test_standalone_function():
    """独立函数测试。"""
    assert function_name(arg1, arg2) == expected


# 测试数据参数化
@pytest.mark.unit
@pytest.mark.parametrize("input_val,expected", [
    (1, 2),
    (0, 1),
    (-1, 0),
])
def test_parametrized(input_val, expected):
    """参数化测试。"""
    assert function(input_val) == expected
```

### 7.2 前端组件测试模板

```typescript
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MyComponent from '@/components/MyComponent.vue'

vi.mock('axios')

describe('MyComponent.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('renders correctly', () => {
    const wrapper = mount(MyComponent)
    expect(wrapper.exists()).toBe(true)
  })

  it('displays expected content', () => {
    const wrapper = mount(MyComponent, {
      props: { title: 'Test Title' },
    })
    expect(wrapper.text()).toContain('Test Title')
  })

  it('handles user interaction', async () => {
    const wrapper = mount(MyComponent)
    const button = wrapper.find('button')
    await button.trigger('click')
    expect(wrapper.emitted('click')).toBeTruthy()
  })
})
```

### 7.3 pytest标记说明

| 标记 | 用途 | 使用场景 |
|------|------|---------|
| `@pytest.mark.unit` | 单元测试 | 孤立测试单个函数/类 |
| `@pytest.mark.integration` | 集成测试 | 多模块协作测试 |
| `@pytest.mark.regression` | 回归测试 | 基准比对 |
| `@pytest.mark.postprocessor` | 后处理器 | CNC G-code生成 |
| `@pytest.mark.geometry` | 几何运算 | 几何操作和布尔运算 |
| `@pytest.mark.gcode` | G-code | G-code生成和验证 |
| `@pytest.mark.lnn` | LNN引擎 | 神经逻辑网络 |
| `@pytest.mark.api` | API端点 | HTTP接口测试 |
| `@pytest.mark.skip_ci` | 跳过CI | 需要本地资源的测试 |

---

## 8. 覆盖率目标

| 测试类型 | 行覆盖率 | 分支覆盖率 | 函数覆盖率 |
|---------|---------|-----------|-----------|
| 后端单元测试 | ≥80% | ≥70% | ≥85% |
| 前端组件测试 | ≥70% | ≥60% | ≥65% |

### 查看覆盖率

```bash
# Python HTML报告
pytest -m unit --cov=app --cov-report=html:cov_html
# 然后打开 cov_html/index.html

# 前端HTML报告
pnpm vitest run -- --coverage
# 然后打开 coverage/index.html
```
