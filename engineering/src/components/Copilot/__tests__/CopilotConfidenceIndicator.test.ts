import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import CopilotConfidenceIndicator from '../CopilotConfidenceIndicator.vue'

// 测试用别名（保持测试用例书写简洁）
const ConfidenceIndicator = CopilotConfidenceIndicator

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'copilot.confidence.label': '置信度',
        'copilot.confidence.high': '高置信度',
        'copilot.confidence.medium': '中置信度',
        'copilot.confidence.low': '低置信度',
      }
      return translations[key] || key
    },
  }),
}))

describe('ConfidenceIndicator.vue', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('组件渲染', () => {
    it('应该正确挂载组件', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.75 },
      })
      expect(wrapper.exists()).toBe(true)
    })

    it('应该显示置信度标签', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.75 },
      })
      const label = wrapper.find('.confidence-label')
      expect(label.exists()).toBe(true)
    })

    it('应该显示置信度百分比数值', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.75 },
      })
      const value = wrapper.find('.confidence-value')
      expect(value.exists()).toBe(true)
      expect(value.text()).toContain('75.0%')
    })
  })

  describe('进度条显示', () => {
    it('应该渲染进度条背景', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.5 },
      })
      const barBg = wrapper.find('.confidence-bar-bg')
      expect(barBg.exists()).toBe(true)
    })

    it('应该渲染进度条填充', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.5 },
      })
      const barFill = wrapper.find('.confidence-bar-fill')
      expect(barFill.exists()).toBe(true)
    })

    it('应该根据置信度设置正确的宽度', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.6 },
      })
      const barFill = wrapper.find('.confidence-bar-fill')
      const style = barFill.attributes('style')
      expect(style).toContain('width: 60%')
    })

    it('应该显示刻度标记', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.5 },
      })
      const markers = wrapper.findAll('.marker')
      expect(markers.length).toBe(3)
      expect(markers[0].text()).toBe('0%')
      expect(markers[1].text()).toBe('50%')
      expect(markers[2].text()).toBe('100%')
    })
  })

  describe('颜色编码', () => {
    it('高置信度(>=0.8)应该使用绿色', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.9 },
      })
      const value = wrapper.find('.confidence-value')
      const style = value.attributes('style')
      expect(style).toContain('#67c23a')
    })

    it('中置信度(0.5-0.8)应该使用橙色', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.6 },
      })
      const value = wrapper.find('.confidence-value')
      const style = value.attributes('style')
      expect(style).toContain('#e6a23c')
    })

    it('低置信度(<0.5)应该使用红色', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.3 },
      })
      const value = wrapper.find('.confidence-value')
      const style = value.attributes('style')
      expect(style).toContain('#f56c6c')
    })
  })

  describe('置信度描述', () => {
    it('高置信度应该显示对应文本', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.9 },
      })
      const desc = wrapper.find('.confidence-description')
      expect(desc.text()).toContain('高置信度')
    })

    it('中置信度应该显示对应文本', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.6 },
      })
      const desc = wrapper.find('.confidence-description')
      expect(desc.text()).toContain('中置信度')
    })

    it('低置信度应该显示对应文本', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.2 },
      })
      const desc = wrapper.find('.confidence-description')
      expect(desc.text()).toContain('低置信度')
    })
  })

  describe('边界值', () => {
    it('应该处理置信度为0', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0 },
      })
      const value = wrapper.find('.confidence-value')
      expect(value.text()).toContain('0.0%')
    })

    it('应该处理置信度为1', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 1 },
      })
      const value = wrapper.find('.confidence-value')
      expect(value.text()).toContain('100.0%')
    })

    it('应该处理边界值0.8', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.8 },
      })
      const value = wrapper.find('.confidence-value')
      const style = value.attributes('style')
      expect(style).toContain('#67c23a')
    })

    it('应该处理边界值0.5', () => {
      wrapper = mount(ConfidenceIndicator, {
        props: { confidence: 0.5 },
      })
      const value = wrapper.find('.confidence-value')
      const style = value.attributes('style')
      expect(style).toContain('#e6a23c')
    })
  })
})
