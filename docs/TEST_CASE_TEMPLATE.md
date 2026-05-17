# 测试用例模板

## 1. Python单元测试模板

```python
"""[模块名称] 单元测试。

测试范围:
- [列出要测试的功能点1]
- [列出要测试的功能点2]

作者: [开发者]
创建日期: [日期]
"""

from __future__ import annotations

import pytest
from app.[模块路径] import [目标类或函数]


@pytest.mark.unit
@pytest.mark.[分类标记]
class Test[目标类名]:
    """[类名] 测试类。

    职责: [简述此类/模块的核心职责]
    """

    def setup_method(self):
        """每个测试方法执行前的初始化。"""
        self.target = [目标类]()

    def teardown_method(self):
        """每个测试方法执行后的清理。"""
        pass

    def test_normal_case(self):
        """正常情况: [描述测试场景]。"""
        # Arrange
        input_data = ...
        
        # Act
        result = self.target.[方法名](input_data)
        
        # Assert
        assert result == expected_output

    def test_boundary_min(self):
        """边界条件: 最小值。"""
        result = self.target.[方法名](minimum_valid_input)
        assert result is not None

    def test_boundary_max(self):
        """边界条件: 最大值。"""
        result = self.target.[方法名](maximum_valid_input)
        assert result is not None

    def test_invalid_input_raises(self):
        """异常处理: 无效输入应抛出异常。"""
        with pytest.raises([ExpectedExceptionType]):
            self.target.[方法名](invalid_input)

    def test_edge_case_empty_input(self):
        """边界条件: 空输入。"""
        result = self.target.[方法_name]()
        assert result == expected_empty_result

    def test_performance(self, performance_timer):
        """性能测试: 应在规定时间内完成。"""
        with performance_timer as t:
            self.target.[方法名](large_input)
        
        assert t.elapsed_s < 5.0, (
            f"性能不达标: 执行时间 {t.elapsed_s:.2f}s > 5.0s"
        )


@pytest.mark.unit
@pytest.mark.parametrize("input_val,expected", [
    pytest.param(正常值1, 预期结果1, id="case_1"),
    pytest.param(正常值2, 预期结果2, id="case_2"),
    pytest.param(边界值, 预期边界结果, id="boundary"),
])
def test_parametrized(input_val, expected):
    """参数化测试: 多组输入验证。"""
    result = [函数名](input_val)
    assert result == expected
```

## 2. Python集成测试模板

```python
"""[业务流程名称] 集成测试。

测试范围:
- [列出涉及的模块/服务]
- [描述业务流程]

作者: [开发者]
创建日期: [日期]
"""

from __future__ import annotations

import pytest


@pytest.mark.integration
class Test[业务流程名称]Flow:
    """[业务流程] 端到端测试。"""

    def setup_method(self):
        """初始化测试环境。"""
        pass

    def teardown_method(self):
        """清理测试环境。"""
        pass

    def test_full_flow_success(self):
        """完整流程: 成功场景。"""
        # 步骤1: 准备输入
        input_data = ...
        
        # 步骤2: 执行第一步
        intermediate_result = module1.process(input_data)
        assert intermediate_result is not None
        
        # 步骤3: 执行第二步
        final_result = module2.process(intermediate_result)
        assert final_result is not None
        
        # 步骤4: 验证最终输出
        assert final_result.meets_requirements()

    def test_partial_failure_recovery(self):
        """流程中断恢复测试。"""
        # 模拟中间步骤失败
        # 验证系统能正确处理或恢复
        pass

    def test_intermediate_result_validation(self):
        """中间结果验证。"""
        # 验证每一步的中间输出符合预期
        pass
```

## 3. Python回归测试模板

```python
"""[功能名称] 回归测试。

基准版本: [版本号]
测试范围: [描述回归测试覆盖的功能]

作者: [开发者]
创建日期: [日期]
"""

from __future__ import annotations

import pytest


REGRESSION_TOLERANCE = {
    "coordinate_precision": 0.01,
    "feed_rate_tolerance_percent": 5.0,
}


@pytest.mark.regression
class Test[功能名称]Baseline:
    """[功能] 基准回归测试。"""

    def test_baseline_comparison(self, baseline_fixture):
        """基准比对: 当前输出与历史版本对比。"""
        current_output = generate_current_output()
        baseline = load_baseline(baseline_fixture)
        
        result = compare(current_output, baseline, REGRESSION_TOLERANCE)
        
        assert result.is_within_tolerance, (
            f"回归测试失败:\n{result.differences}"
        )
        assert result.match_score >= 0.95
```

## 4. 前端组件测试模板

```typescript
/**
 * [组件名称] 单元测试
 * 
 * 测试范围:
 * - [功能点1]
 * - [功能点2]
 * 
 * 作者: [开发者]
 * 创建日期: [日期]
 */

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MyComponent from '@/components/MyComponent.vue'

// Mock外部依赖
vi.mock('axios')

describe('MyComponent.vue', () => {
  beforeEach(() => {
    // 重置Pinia store
    setActivePinia(createPinia())
  })

  describe('渲染测试', () => {
    it('should render component', () => {
      const wrapper = mount(MyComponent)
      expect(wrapper.exists()).toBe(true)
    })

    it('should display default content', () => {
      const wrapper = mount(MyComponent)
      expect(wrapper.text()).toContain('expected content')
    })
  })

  describe('Props测试', () => {
    it('should render with props', () => {
      const wrapper = mount(MyComponent, {
        props: { title: 'Test Title', value: 42 },
      })
      expect(wrapper.text()).toContain('Test Title')
    })
  })

  describe('交互测试', () => {
    it('should emit event on click', async () => {
      const wrapper = mount(MyComponent)
      const button = wrapper.find('button')
      await button.trigger('click')
      expect(wrapper.emitted('click')).toBeTruthy()
    })

    it('should update state on input change', async () => {
      const wrapper = mount(MyComponent)
      const input = wrapper.find('input')
      await input.setValue('new value')
      expect(wrapper.vm.someProperty).toBe('new value')
    })
  })

  describe('边界测试', () => {
    it('should handle empty data', () => {
      const wrapper = mount(MyComponent, {
        props: { data: [] },
      })
      expect(wrapper.find('.empty-state').exists()).toBe(true)
    })

    it('should handle large dataset', () => {
      const largeData = Array.from({ length: 1000 }, (_, i) => ({ id: i }))
      const wrapper = mount(MyComponent, {
        props: { data: largeData },
      })
      expect(wrapper.findAll('.item').length).toBe(1000)
    })
  })

  describe('快照测试', () => {
    it('should match snapshot', () => {
      const wrapper = mount(MyComponent, {
        props: { title: 'Snapshot Test' },
      })
      expect(wrapper.html()).toMatchSnapshot()
    })
  })
})
```

## 5. 测试用例检查清单

编写测试用例时，请确认以下几点：

- [ ] 测试类/文件命名以 `Test` 开头
- [ ] 测试方法命名以 `test_` 开头
- [ ] 使用了正确的 pytest 标记（`@pytest.mark.unit` 等）
- [ ] 每个测试只验证一个行为（单一职责）
- [ ] 测试独立运行，不依赖其他测试的顺序
- [ ] 使用了 Arrange-Act-Assert 模式
- [ ] 覆盖了正常情况、边界条件和异常情况
- [ ] 使用了共享 fixtures 避免重复代码
- [ ] 测试描述清晰，能说明测试意图
- [ ] 性能测试设定了合理的时间阈值
