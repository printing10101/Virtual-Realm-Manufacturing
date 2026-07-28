import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import DecisionActions from '../DecisionActions.vue'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

// Mock Element Plus icons
vi.mock('@element-plus/icons-vue', () => ({
  Check: { name: 'Check' },
  Edit: { name: 'Edit' },
  Close: { name: 'Close' },
}))

describe('DecisionActions.vue', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    vi.clearAllMocks()
  })

  describe('组件渲染', () => {
    it('应该正确挂载组件', () => {
      wrapper = mount(DecisionActions)
      expect(wrapper.exists()).toBe(true)
    })

    it('应该渲染三个操作按钮', () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      expect(buttons.length).toBe(3)
    })

    it('采纳按钮应该存在', () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      expect(buttons[0].exists()).toBe(true)
    })

    it('修改按钮应该存在', () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      expect(buttons[1].exists()).toBe(true)
    })

    it('拒绝按钮应该存在', () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      expect(buttons[2].exists()).toBe(true)
    })
  })

  describe('按钮点击事件', () => {
    it('点击采纳按钮应该触发 accept 事件', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      await buttons[0].trigger('click')
      
      expect(wrapper.emitted('accept')).toBeTruthy()
      expect(wrapper.emitted('accept')?.length).toBe(1)
    })

    it('点击修改按钮应该触发 modify 事件', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      await buttons[1].trigger('click')
      
      expect(wrapper.emitted('modify')).toBeTruthy()
      expect(wrapper.emitted('modify')?.length).toBe(1)
    })

    it('点击拒绝按钮应该触发 reject 事件', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      await buttons[2].trigger('click')
      
      expect(wrapper.emitted('reject')).toBeTruthy()
      expect(wrapper.emitted('reject')?.length).toBe(1)
    })
  })

  describe('disabled 属性', () => {
    it('当 disabled 为 true 时，点击采纳按钮不应触发事件', async () => {
      wrapper = mount(DecisionActions, {
        props: { disabled: true },
      })
      const buttons = wrapper.findAll('button')
      await buttons[0].trigger('click')
      
      expect(wrapper.emitted('accept')).toBeFalsy()
    })

    it('当 disabled 为 true 时，点击修改按钮不应触发事件', async () => {
      wrapper = mount(DecisionActions, {
        props: { disabled: true },
      })
      const buttons = wrapper.findAll('button')
      await buttons[1].trigger('click')
      
      expect(wrapper.emitted('modify')).toBeFalsy()
    })

    it('当 disabled 为 true 时，点击拒绝按钮不应触发事件', async () => {
      wrapper = mount(DecisionActions, {
        props: { disabled: true },
      })
      const buttons = wrapper.findAll('button')
      await buttons[2].trigger('click')
      
      expect(wrapper.emitted('reject')).toBeFalsy()
    })

    it('当 disabled 为 false 时，按钮应该可以正常点击', async () => {
      wrapper = mount(DecisionActions, {
        props: { disabled: false },
      })
      const buttons = wrapper.findAll('button')
      await buttons[0].trigger('click')
      
      expect(wrapper.emitted('accept')).toBeTruthy()
    })
  })

  describe('loading 状态', () => {
    it('应该暴露 setLoading 方法', () => {
      wrapper = mount(DecisionActions)
      expect(wrapper.vm.setLoading).toBeDefined()
      expect(typeof wrapper.vm.setLoading).toBe('function')
    })

    it('setLoading 方法应该能够设置 loading 状态', () => {
      wrapper = mount(DecisionActions)
      wrapper.vm.setLoading(true)
      expect(wrapper.vm.loading).toBe(true)
      
      wrapper.vm.setLoading(false)
      expect(wrapper.vm.loading).toBe(false)
    })
  })

  describe('多次点击', () => {
    it('采纳按钮可以被多次点击', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      
      await buttons[0].trigger('click')
      await buttons[0].trigger('click')
      await buttons[0].trigger('click')
      
      expect(wrapper.emitted('accept')?.length).toBe(3)
    })

    it('修改按钮可以被多次点击', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      
      await buttons[1].trigger('click')
      await buttons[1].trigger('click')
      
      expect(wrapper.emitted('modify')?.length).toBe(2)
    })

    it('拒绝按钮可以被多次点击', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      
      await buttons[2].trigger('click')
      await buttons[2].trigger('click')
      await buttons[2].trigger('click')
      await buttons[2].trigger('click')
      
      expect(wrapper.emitted('reject')?.length).toBe(4)
    })
  })

  describe('事件独立性', () => {
    it('点击采纳按钮不应触发其他事件', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      await buttons[0].trigger('click')
      
      expect(wrapper.emitted('accept')).toBeTruthy()
      expect(wrapper.emitted('modify')).toBeFalsy()
      expect(wrapper.emitted('reject')).toBeFalsy()
    })

    it('点击修改按钮不应触发其他事件', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      await buttons[1].trigger('click')
      
      expect(wrapper.emitted('accept')).toBeFalsy()
      expect(wrapper.emitted('modify')).toBeTruthy()
      expect(wrapper.emitted('reject')).toBeFalsy()
    })

    it('点击拒绝按钮不应触发其他事件', async () => {
      wrapper = mount(DecisionActions)
      const buttons = wrapper.findAll('button')
      await buttons[2].trigger('click')
      
      expect(wrapper.emitted('accept')).toBeFalsy()
      expect(wrapper.emitted('modify')).toBeFalsy()
      expect(wrapper.emitted('reject')).toBeTruthy()
    })
  })
})
