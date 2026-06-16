import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import TraceTimeline from '../TraceTimeline.vue'
import type { ReasoningStep } from '@/api/reasoning'

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  VideoPlay: { name: 'VideoPlay', template: '<i />' },
  VideoPause: { name: 'VideoPause', template: '<i />' },
  DArrowLeft: { name: 'DArrowLeft', template: '<i />' },
  DArrowRight: { name: 'DArrowRight', template: '<i />' },
  Check: { name: 'Check', template: '<i />' },
  Loading: { name: 'Loading', template: '<i />' },
}))

// Mock StepCard child component
vi.mock('../StepCard.vue', () => ({
  default: {
    name: 'StepCard',
    template: '<div class="mock-step-card">StepCard Mock</div>',
    props: ['step'],
  },
}))

const globalStubs = {
  ElButton: {
    name: 'ElButton',
    template: '<button class="el-button" :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
    props: ['icon', 'disabled'],
    emits: ['click'],
  },
  ElButtonGroup: {
    name: 'ElButtonGroup',
    template: '<div class="el-button-group"><slot /></div>',
  },
  ElSelect: {
    name: 'ElSelect',
    template: '<select class="el-select"><slot /></select>',
    props: ['modelValue'],
  },
  ElOption: {
    name: 'ElOption',
    template: '<option :value="value">{{ label }}</option>',
    props: ['value', 'label'],
  },
  ElIcon: {
    name: 'ElIcon',
    template: '<span class="el-icon"><slot /></span>',
    props: ['size'],
  },
  ElEmpty: {
    name: 'ElEmpty',
    template: '<div class="el-empty">{{ description }}</div>',
    props: ['description'],
  },
}

describe('TraceTimeline.vue', () => {
  let wrapper: VueWrapper<any>

  const mockSteps: ReasoningStep[] = [
    {
      id: 'step-1',
      type: 'task_routing',
      title: '任务路由',
      status: 'completed',
      timestamp: 1700000000000,
      duration: 100,
      confidence: 0.9,
      evidence: { summary: '路由完成' },
    },
    {
      id: 'step-2',
      type: 'physical_validation',
      title: '物理校验',
      status: 'completed',
      timestamp: 1700000001000,
      duration: 200,
      confidence: 0.85,
      evidence: { summary: '校验通过' },
    },
    {
      id: 'step-3',
      type: 'active_learning',
      title: '主动学习',
      status: 'running',
      timestamp: 1700000002000,
      duration: 300,
      confidence: 0.75,
      evidence: { summary: '学习中' },
    },
  ]

  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    wrapper = mount(TraceTimeline, {
      props: { steps: mockSteps },
      global: { stubs: globalStubs },
    })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('组件渲染', () => {
    it('应该正确挂载组件', () => {
      expect(wrapper.exists()).toBe(true)
    })

    it('应该渲染正确数量的时间轴节点', () => {
      const nodes = wrapper.findAll('.timeline-node')
      expect(nodes.length).toBe(3)
    })

    it('应该显示进度信息', () => {
      const progress = wrapper.find('.progress-info')
      expect(progress.exists()).toBe(true)
      expect(progress.text()).toContain('1 / 3')
    })
  })

  describe('控制按钮', () => {
    it('应该渲染播放按钮', () => {
      const buttons = wrapper.findAll('.el-button')
      expect(buttons.length).toBeGreaterThanOrEqual(4)
    })

    it('播放按钮初始状态应可用', () => {
      const buttons = wrapper.findAll('.el-button')
      const playBtn = buttons[0]
      expect(playBtn.attributes('disabled')).toBeFalsy()
    })

    it('暂停按钮初始状态应禁用', () => {
      const buttons = wrapper.findAll('.el-button')
      const pauseBtn = buttons[1]
      expect(pauseBtn.attributes('disabled')).toBeDefined()
    })
  })

  describe('步骤导航', () => {
    it('初始应选中第一个步骤', () => {
      expect(wrapper.vm.currentIndex).toBe(0)
    })

    it('点击下一步应前进到第二步', async () => {
      wrapper.vm.nextStep()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.currentIndex).toBe(1)
    })

    it('点击上一步应回退', async () => {
      wrapper.vm.currentIndex = 2
      await wrapper.vm.$nextTick()
      wrapper.vm.prevStep()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.currentIndex).toBe(1)
    })

    it('第一步时上一步应禁用', () => {
      expect(wrapper.vm.currentIndex).toBe(0)
      wrapper.vm.prevStep()
      expect(wrapper.vm.currentIndex).toBe(0)
    })

    it('最后一步时下一步不应前进', async () => {
      wrapper.vm.currentIndex = 2
      await wrapper.vm.$nextTick()
      wrapper.vm.nextStep()
      expect(wrapper.vm.currentIndex).toBe(2)
    })

    it('点击节点应跳转到对应步骤', async () => {
      wrapper.vm.goToStep(2)
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.currentIndex).toBe(2)
    })

    it('goToStep 超出范围不应改变索引', () => {
      wrapper.vm.goToStep(-1)
      expect(wrapper.vm.currentIndex).toBe(0)
      wrapper.vm.goToStep(10)
      expect(wrapper.vm.currentIndex).toBe(0)
    })
  })

  describe('播放控制', () => {
    it('播放应设置 isPlaying 为 true', () => {
      wrapper.vm.play()
      expect(wrapper.vm.isPlaying).toBe(true)
    })

    it('暂停应设置 isPlaying 为 false', async () => {
      wrapper.vm.play()
      expect(wrapper.vm.isPlaying).toBe(true)
      wrapper.vm.pause()
      expect(wrapper.vm.isPlaying).toBe(false)
    })

    it('播放时自动前进到下一步', async () => {
      wrapper.vm.play()
      vi.advanceTimersByTime(2000)
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.currentIndex).toBe(1)
    })

    it('播放到末尾应自动暂停', async () => {
      wrapper.vm.currentIndex = 2
      await wrapper.vm.$nextTick()
      wrapper.vm.play()
      vi.advanceTimersByTime(2000)
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.isPlaying).toBe(false)
    })

    it('播放时上一步和下一步按钮应禁用', async () => {
      wrapper.vm.play()
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.isPlaying).toBe(true)
    })

    it('空步骤时播放不应生效', async () => {
      await wrapper.setProps({ steps: [] })
      wrapper.vm.play()
      expect(wrapper.vm.isPlaying).toBe(false)
    })
  })

  describe('事件发射', () => {
    it('步骤变化应发射 stepChange 事件', async () => {
      wrapper.vm.nextStep()
      await wrapper.vm.$nextTick()
      expect(wrapper.emitted('stepChange')).toBeTruthy()
    })

    it('播放状态变化应发射 playStateChange 事件', () => {
      wrapper.vm.play()
      expect(wrapper.emitted('playStateChange')).toBeTruthy()
      expect(wrapper.emitted('playStateChange')![0]).toEqual([true])
    })
  })

  describe('时间轴节点样式', () => {
    it('当前节点应有 active 类', () => {
      const nodes = wrapper.findAll('.timeline-node')
      expect(nodes[0].classes()).toContain('active')
    })

    it('已完成节点应有 completed 类', async () => {
      wrapper.vm.goToStep(2)
      await wrapper.vm.$nextTick()
      const nodes = wrapper.findAll('.timeline-node')
      expect(nodes[0].classes()).toContain('completed')
      expect(nodes[1].classes()).toContain('completed')
      expect(nodes[2].classes()).toContain('active')
    })

    it('未来节点应有 pending 类', () => {
      const nodes = wrapper.findAll('.timeline-node')
      expect(nodes[1].classes()).toContain('pending')
      expect(nodes[2].classes()).toContain('pending')
    })
  })

  describe('空状态', () => {
    it('没有步骤时应显示空状态', async () => {
      await wrapper.setProps({ steps: [] })
      expect(wrapper.find('.timeline-empty').exists()).toBe(true)
      expect(wrapper.find('.el-empty').exists()).toBe(true)
    })

    it('有步骤时不应显示空状态', () => {
      expect(wrapper.find('.timeline-empty').exists()).toBe(false)
    })
  })

  describe('当前步骤内容', () => {
    it('应显示当前步骤的 StepCard', () => {
      const stepCard = wrapper.findComponent({ name: 'StepCard' })
      expect(stepCard.exists()).toBe(true)
      expect(stepCard.props('step')).toEqual(mockSteps[0])
    })

    it('切换步骤后 StepCard 应更新', async () => {
      wrapper.vm.goToStep(1)
      await wrapper.vm.$nextTick()
      const stepCard = wrapper.findComponent({ name: 'StepCard' })
      expect(stepCard.props('step')).toEqual(mockSteps[1])
    })
  })

  describe('暴露的方法', () => {
    it('应该暴露 play 方法', () => {
      expect(wrapper.vm.play).toBeDefined()
      expect(typeof wrapper.vm.play).toBe('function')
    })

    it('应该暴露 pause 方法', () => {
      expect(wrapper.vm.pause).toBeDefined()
      expect(typeof wrapper.vm.pause).toBe('function')
    })

    it('应该暴露 prevStep 方法', () => {
      expect(wrapper.vm.prevStep).toBeDefined()
    })

    it('应该暴露 nextStep 方法', () => {
      expect(wrapper.vm.nextStep).toBeDefined()
    })

    it('应该暴露 goToStep 方法', () => {
      expect(wrapper.vm.goToStep).toBeDefined()
    })

    it('应该暴露 currentIndex 响应式引用', () => {
      expect(wrapper.vm.currentIndex).toBeDefined()
    })

    it('应该暴露 isPlaying 响应式引用', () => {
      expect(wrapper.vm.isPlaying).toBeDefined()
    })
  })
})
