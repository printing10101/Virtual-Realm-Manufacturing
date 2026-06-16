import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { nextTick } from 'vue'
import Tour from '../src/components/Onboarding/Tour.vue'
import { createI18n } from 'vue-i18n'

const i18n = createI18n({
  legacy: false,
  locale: 'zh',
  messages: {
    zh: {
      tour: {
        prev: '上一步',
        next: '下一步',
        skip: '跳过',
        finish: '完成'
      }
    }
  }
})

// Helper: mount with Teleport stubbed to render inline
function mountTour(props: Record<string, unknown> = {}) {
  return mount(Tour, {
    props,
    global: {
      plugins: [i18n],
      stubs: {
        Teleport: {
          template: '<div class="teleport-stub"><slot /></div>'
        }
      }
    }
  })
}

describe('Tour', () => {
  const mockSteps = [
    {
      title: '步骤 1',
      description: '这是第一个步骤',
      target: '#target1'
    },
    {
      title: '步骤 2',
      description: '这是第二个步骤',
      target: '#target2'
    },
    {
      title: '步骤 3',
      description: '这是第三个步骤'
    }
  ]

  beforeEach(() => {
    localStorage.clear()
    document.body.innerHTML = `
      <div id="target1">目标 1</div>
      <div id="target2">目标 2</div>
    `
  })

  afterEach(() => {
    document.body.innerHTML = ''
    localStorage.clear()
  })

  it('应该正确渲染组件', () => {
    const wrapper = mountTour({ steps: mockSteps })
    expect(wrapper.exists()).toBe(true)
  })

  it('初始状态下应该不可见', () => {
    const wrapper = mountTour({ steps: mockSteps })
    expect(wrapper.find('.tour-overlay').exists()).toBe(false)
  })

  it('调用 start 方法后应该显示引导', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    expect(wrapper.find('.tour-overlay').exists()).toBe(true)
    expect(wrapper.find('.tour-title').text()).toBe('步骤 1')
  })

  it('应该支持前进导航', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    expect(wrapper.find('.tour-title').text()).toBe('步骤 1')

    // 点击"下一步"按钮（跳过"上一步"和"跳过"，第三个按钮是"下一步"）
    const buttons = wrapper.findAll('.tour-actions button')
    const nextBtn = buttons.find(b => b.text() === '下一步')
    expect(nextBtn).toBeDefined()
    await nextBtn!.trigger('click')
    await nextTick()

    expect(wrapper.find('.tour-title').text()).toBe('步骤 2')
  })

  it('应该支持后退导航', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    // 前进到第二步
    let buttons = wrapper.findAll('.tour-actions button')
    let nextBtn = buttons.find(b => b.text() === '下一步')
    await nextBtn!.trigger('click')
    await nextTick()

    expect(wrapper.find('.tour-title').text()).toBe('步骤 2')

    // 后退到第一步
    buttons = wrapper.findAll('.tour-actions button')
    const prevBtn = buttons.find(b => b.text() === '上一步')
    expect(prevBtn).toBeDefined()
    await prevBtn!.trigger('click')
    await nextTick()

    expect(wrapper.find('.tour-title').text()).toBe('步骤 1')
  })

  it('应该支持跳过功能', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    // 点击跳过按钮
    const buttons = wrapper.findAll('.tour-actions button')
    const skipBtn = buttons.find(b => b.text() === '跳过')
    expect(skipBtn).toBeDefined()
    await skipBtn!.trigger('click')
    await nextTick()
    // Transition 会保留 DOM 直到动画结束，检查内部状态
    expect((wrapper.vm as any).visible).toBe(false)
    expect(wrapper.emitted('skip')).toBeTruthy()
  })

  it('应该支持完成功能', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    // 前进到最后一步
    for (let i = 0; i < mockSteps.length - 1; i++) {
      const buttons = wrapper.findAll('.tour-actions button')
      const nextBtn = buttons.find(b => b.text() === '下一步')
      if (nextBtn) {
        await nextBtn.trigger('click')
        await nextTick()
      }
    }

    // 点击完成按钮
    const buttons = wrapper.findAll('.tour-actions button')
    const finishBtn = buttons.find(b => b.text() === '完成')
    expect(finishBtn).toBeDefined()
    await finishBtn!.trigger('click')
    await nextTick()

    // Transition 会保留 DOM 直到动画结束，检查内部状态
    expect((wrapper.vm as any).visible).toBe(false)
    expect(wrapper.emitted('finish')).toBeTruthy()
  })

  it('应该保存和恢复进度', async () => {
    const storageKey = 'test_tour_progress'

    // 第一次访问，前进到第二步
    const wrapper1 = mountTour({ steps: mockSteps, storageKey })
    const vm1 = wrapper1.vm as any
    vm1.start()
    await nextTick()

    let buttons = wrapper1.findAll('.tour-actions button')
    let nextBtn = buttons.find(b => b.text() === '下一步')
    await nextBtn!.trigger('click')
    await nextTick()

    // 验证进度已保存
    const savedProgress = localStorage.getItem(storageKey)
    expect(savedProgress).toBeTruthy()
    const progress = JSON.parse(savedProgress!)
    expect(progress.currentStep).toBe(1)

    wrapper1.unmount()

    // 第二次访问，应该恢复到第二步
    const wrapper2 = mountTour({ steps: mockSteps, storageKey })
    const vm2 = wrapper2.vm as any
    vm2.start()
    await nextTick()

    expect(wrapper2.find('.tour-title').text()).toBe('步骤 2')
    wrapper2.unmount()
  })

  it('应该显示步骤指示器', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    const indicators = wrapper.findAll('.tour-indicator')
    expect(indicators.length).toBe(3)
    expect(indicators[0].classes()).toContain('tour-indicator--active')
  })

  it('应该正确更新指示器状态', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    // 第一步：第一个激活
    let indicators = wrapper.findAll('.tour-indicator')
    expect(indicators[0].classes()).toContain('tour-indicator--active')

    // 前进到第二步
    const buttons = wrapper.findAll('.tour-actions button')
    const nextBtn = buttons.find(b => b.text() === '下一步')
    await nextBtn!.trigger('click')
    await nextTick()

    indicators = wrapper.findAll('.tour-indicator')
    expect(indicators[0].classes()).toContain('tour-indicator--completed')
    expect(indicators[1].classes()).toContain('tour-indicator--active')
  })

  it('应该响应窗口大小变化', async () => {
    const wrapper = mountTour({ steps: mockSteps })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    window.dispatchEvent(new Event('resize'))
    await nextTick()

    expect(wrapper.exists()).toBe(true)
  })

  it('应该支持自动开始', async () => {
    vi.useFakeTimers()
    const wrapper = mountTour({ steps: mockSteps, autoStart: true })
    await nextTick()

    // 触发 setTimeout 500ms 延迟
    vi.advanceTimersByTime(600)
    await nextTick()

    expect(wrapper.find('.tour-overlay').exists()).toBe(true)
    vi.useRealTimers()
  })

  it('应该正确处理空步骤数组', () => {
    const wrapper = mountTour({ steps: [] })
    const vm = wrapper.vm as any
    vm.start()

    expect(wrapper.find('.tour-overlay').exists()).toBe(false)
  })

  it('应该正确清理进度', async () => {
    const storageKey = 'test_tour_progress'
    localStorage.setItem(storageKey, JSON.stringify({ currentStep: 1, timestamp: Date.now() }))

    const wrapper = mountTour({ steps: mockSteps, storageKey })
    const vm = wrapper.vm as any
    vm.start()
    await nextTick()

    // 前进到最后一步
    for (let i = 0; i < mockSteps.length - 1; i++) {
      const buttons = wrapper.findAll('.tour-actions button')
      const nextBtn = buttons.find(b => b.text() === '下一步')
      if (nextBtn) {
        await nextBtn.trigger('click')
        await nextTick()
      }
    }

    // 点击完成按钮
    const buttons = wrapper.findAll('.tour-actions button')
    const finishBtn = buttons.find(b => b.text() === '完成')
    if (finishBtn) {
      await finishBtn.trigger('click')
      await nextTick()
    }

    // 进度应该被清理
    expect(localStorage.getItem(storageKey)).toBeNull()
  })
})
