import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import RecommendationCard from '../RecommendationCard.vue'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => {
      const translations: Record<string, string> = {
        'copilot.card.title': 'AI 推荐',
        'copilot.card.recommendation': '推荐内容',
        'copilot.card.reasoning': '决策依据',
        'copilot.card.alternatives': '备选方案',
        'copilot.messages.accepted': '已采纳',
        'copilot.messages.modifyRequested': '已请求修改',
        'copilot.messages.rejected': '已拒绝',
      }
      return translations[key] || key
    },
  }),
}))

// Mock Element Plus
vi.mock('element-plus', () => ({
  ElMessage: {
    success: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
  },
}))

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Promotion: { name: 'Promotion' },
  ChatDotRound: { name: 'ChatDotRound' },
  ArrowDown: { name: 'ArrowDown' },
}))

// Mock child components
vi.mock('../CopilotConfidenceIndicator.vue', () => ({
  default: {
    name: 'CopilotConfidenceIndicator',
    template: '<div class="mock-confidence-indicator"></div>',
    props: ['confidence'],
  },
}))

vi.mock('../DecisionActions.vue', () => ({
  default: {
    name: 'DecisionActions',
    template: '<div class="mock-decision-actions"></div>',
    props: ['disabled'],
    emits: ['accept', 'modify', 'reject'],
  },
}))

// Mock utils
vi.mock('@/utils/formatters', () => ({
  formatTimestamp: vi.fn((_ts: number) => '2024-01-01 12:00:00'),
}))

vi.mock('@/utils/statusHelpers', () => ({
  getConfidenceTagType: vi.fn((confidence: number) => {
    if (confidence >= 0.8) return 'success'
    if (confidence >= 0.5) return 'warning'
    return 'danger'
  }),
}))

describe('RecommendationCard.vue', () => {
  let wrapper: VueWrapper<any>

  const mockRecommendation = {
    feed_rate: 800,
    depth_of_cut: 2.5,
    spindle_speed: 12000,
  }

  const mockAlternatives = [
    {
      label: '方案 A',
      description: '高速低切深',
      confidence: 0.85,
    },
    {
      label: '方案 B',
      description: '低速高切深',
      confidence: 0.6,
    },
  ]

  beforeEach(() => {
    vi.clearAllMocks()
    wrapper = mount(RecommendationCard, {
      props: {
        recommendation: mockRecommendation,
        confidence: 0.75,
        reasoning: '基于材料硬度和刀具磨损状态的综合分析',
        alternatives: mockAlternatives,
      },
    })
  })

  describe('组件渲染', () => {
    it('应该正确挂载组件', () => {
      expect(wrapper.exists()).toBe(true)
    })

    it('应该显示卡片标题', () => {
      const title = wrapper.find('.card-title')
      expect(title.exists()).toBe(true)
      expect(title.text()).toBe('AI 推荐')
    })

    it('应该显示时间戳', () => {
      const timestamp = wrapper.find('.timestamp')
      expect(timestamp.exists()).toBe(true)
    })
  })

  describe('推荐内容展示', () => {
    it('应该显示推荐内容区域', () => {
      const section = wrapper.find('.recommendation-section')
      expect(section.exists()).toBe(true)
    })

    it('应该显示推荐内容标签', () => {
      const label = wrapper.find('.recommendation-section .section-label')
      expect(label.text()).toBe('推荐内容')
    })

    it('应该以 JSON 格式展示推荐内容', () => {
      const json = wrapper.find('.recommendation-json')
      expect(json.exists()).toBe(true)
      expect(json.text()).toContain('feed_rate')
      expect(json.text()).toContain('800')
    })
  })

  describe('置信度展示', () => {
    it('应该渲染置信度指示器', () => {
      const indicator = wrapper.find('.confidence-section')
      expect(indicator.exists()).toBe(true)
    })

    it('应该传递正确的置信度值', () => {
      const indicator = wrapper.findComponent({ name: 'CopilotConfidenceIndicator' })
      expect(indicator.exists()).toBe(true)
      expect(indicator.props('confidence')).toBe(0.75)
    })
  })

  describe('决策依据展开/折叠', () => {
    it('应该显示决策依据区域', () => {
      const section = wrapper.find('.reasoning-section')
      expect(section.exists()).toBe(true)
    })

    it('决策依据默认应该展开', () => {
      expect(wrapper.vm.isReasoningExpanded).toBe(true)
    })

    it('应该能够点击标题切换展开/折叠', async () => {
      const header = wrapper.find('.reasoning-header')
      expect(header.exists()).toBe(true)

      await header.trigger('click')
      expect(wrapper.vm.isReasoningExpanded).toBe(false)

      await header.trigger('click')
      expect(wrapper.vm.isReasoningExpanded).toBe(true)
    })

    it('展开时应该显示决策依据内容', () => {
      const content = wrapper.find('.reasoning-content')
      expect(content.exists()).toBe(true)
      expect(content.isVisible()).toBe(true)
    })

    it('折叠时应该隐藏决策依据内容', async () => {
      wrapper.vm.isReasoningExpanded = false
      await wrapper.vm.$nextTick()

      const content = wrapper.find('.reasoning-content')
      expect(content.isVisible()).toBe(false)
    })

    it('应该显示决策依据文本', () => {
      const text = wrapper.find('.reasoning-text')
      expect(text.exists()).toBe(true)
      expect(text.text()).toBe('基于材料硬度和刀具磨损状态的综合分析')
    })

    it('折叠图标应该有正确的旋转样式', async () => {
      const icon = wrapper.find('.collapse-icon')
      expect(icon.classes()).toContain('is-expanded')

      wrapper.vm.isReasoningExpanded = false
      await wrapper.vm.$nextTick()
      expect(wrapper.find('.collapse-icon').classes()).not.toContain('is-expanded')
    })
  })

  describe('备选方案', () => {
    it('有备选方案时应该显示备选方案区域', () => {
      const section = wrapper.find('.alternatives-section')
      expect(section.exists()).toBe(true)
    })

    it('应该渲染正确数量的备选方案', () => {
      const items = wrapper.findAll('.alternative-item')
      expect(items.length).toBe(2)
    })

    it('应该显示备选方案标签', () => {
      const labels = wrapper.findAll('.alternative-label')
      expect(labels[0].text()).toBe('方案 A')
      expect(labels[1].text()).toBe('方案 B')
    })

    it('应该显示备选方案描述', () => {
      const descriptions = wrapper.findAll('.alternative-description')
      expect(descriptions[0].text()).toBe('高速低切深')
      expect(descriptions[1].text()).toBe('低速高切深')
    })

    it('没有备选方案时不应显示备选方案区域', async () => {
      await wrapper.setProps({ alternatives: [] })
      const section = wrapper.find('.alternatives-section')
      expect(section.exists()).toBe(false)
    })
  })

  describe('操作按钮交互', () => {
    it('应该渲染决策操作区域', () => {
      const actions = wrapper.find('.card-actions')
      expect(actions.exists()).toBe(true)
    })

    it('应该渲染 DecisionActions 组件', () => {
      const actions = wrapper.findComponent({ name: 'DecisionActions' })
      expect(actions.exists()).toBe(true)
    })

    it('采纳事件应该正确冒泡', async () => {
      const actions = wrapper.findComponent({ name: 'DecisionActions' })
      await actions.vm.$emit('accept')

      expect(wrapper.emitted('accept')).toBeTruthy()
      expect(wrapper.emitted('accept')![0]).toEqual([mockRecommendation])
    })

    it('修改事件应该正确冒泡', async () => {
      const actions = wrapper.findComponent({ name: 'DecisionActions' })
      await actions.vm.$emit('modify')

      expect(wrapper.emitted('modify')).toBeTruthy()
      expect(wrapper.emitted('modify')![0]).toEqual([mockRecommendation])
    })

    it('拒绝事件应该正确冒泡', async () => {
      const actions = wrapper.findComponent({ name: 'DecisionActions' })
      await actions.vm.$emit('reject')

      expect(wrapper.emitted('reject')).toBeTruthy()
      expect(wrapper.emitted('reject')![0]).toEqual([mockRecommendation])
    })
  })

  describe('actionsDisabled 属性', () => {
    it('默认 actionsDisabled 为 false', () => {
      const actions = wrapper.findComponent({ name: 'DecisionActions' })
      expect(actions.props('disabled')).toBe(false)
    })

    it('应该传递 actionsDisabled 到子组件', async () => {
      await wrapper.setProps({ actionsDisabled: true })
      const actions = wrapper.findComponent({ name: 'DecisionActions' })
      expect(actions.props('disabled')).toBe(true)
    })
  })

  describe('暴露的方法', () => {
    it('应该暴露 setActionsLoading 方法', () => {
      expect(wrapper.vm.setActionsLoading).toBeDefined()
      expect(typeof wrapper.vm.setActionsLoading).toBe('function')
    })
  })

  describe('样式', () => {
    it('卡片应该有正确的类名', () => {
      expect(wrapper.find('.copilot-recommendation-card').exists()).toBe(true)
    })

    it('卡片头部应该有渐变背景样式', () => {
      const header = wrapper.find('.card-header')
      expect(header.exists()).toBe(true)
    })

    it('操作区域应该有分隔线', () => {
      const actions = wrapper.find('.card-actions')
      expect(actions.exists()).toBe(true)
    })
  })
})
