// ParameterRecommendPanel 组件测试（Phase D 前端）
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'

import ParameterRecommendPanel from '@/components/optimizer/ParameterRecommendPanel.vue'
import * as api from '@/api/parameterOptimizer'

vi.mock('@/api/parameterOptimizer', () => ({
  recommendParameters: vi.fn(),
}))

const mockedRecommend = vi.mocked(api.recommendParameters)

const stubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-form': { template: '<form><slot /></form>' },
  'el-form-item': { template: '<div><slot /></div>' },
  'el-input': {
    template: '<input :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" />',
  },
  'el-select': { template: '<select><slot /></select>' },
  'el-option': { template: '<option :value="value"><slot /></option>' },
  'el-row': { template: '<div><slot /></div>' },
  'el-col': { template: '<div><slot /></div>' },
  'el-button': { template: '<button><slot /></button>' },
  'el-divider': true,
  'el-statistic': { template: '<div><slot name="title" />{{ value }}</div>' },
  'el-alert': { template: '<div><slot /></div>' },
}

describe('ParameterRecommendPanel', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders form with material input and recommend button', () => {
    const wrapper = mount(ParameterRecommendPanel, { global: { stubs } })
    expect(wrapper.text()).toContain('切削参数推荐')
    expect(wrapper.text()).toContain('获取推荐')
  })

  it('shows error when material is empty', async () => {
    const wrapper = mount(ParameterRecommendPanel, { global: { stubs } })
    const btn = wrapper.findAll('button').find((b) => b.text().includes('获取推荐'))
    await btn!.trigger('click')
    expect(wrapper.text()).toContain('请输入材料名称')
    expect(mockedRecommend).not.toHaveBeenCalled()
  })

  it('calls recommend API and shows result', async () => {
    mockedRecommend.mockResolvedValue({
      depth_of_cut_mm: 2.0,
      feed_mm_per_rev: 0.2,
      spindle_rpm: 8000,
      cutting_speed_m_min: 300,
      strategy: 'L0_baseline',
      confidence: 0.5,
      basis: [],
      clamped: false,
    } as never)

    const wrapper = mount(ParameterRecommendPanel, { global: { stubs } })
    // 输入材料
    const input = wrapper.find('input')
    await input.setValue('AL6061')
    const btn = wrapper.findAll('button').find((b) => b.text().includes('获取推荐'))
    await btn!.trigger('click')

    expect(mockedRecommend).toHaveBeenCalledWith(
      expect.objectContaining({ material: 'AL6061' }),
    )
    // 等待异步更新
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('经验基线')
  })

  it('clear button resets state', async () => {
    const wrapper = mount(ParameterRecommendPanel, { global: { stubs } })
    const clearBtn = wrapper.findAll('button').find((b) => b.text().includes('清空'))
    await clearBtn!.trigger('click')
    expect(wrapper.text()).not.toContain('置信度')
  })
})
