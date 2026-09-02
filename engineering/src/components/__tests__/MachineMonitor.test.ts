// MachineMonitor 组件测试（实时监控：WebSocket 数据流 + 告警消费）
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'

import MachineMonitor from '@/components/realtime/MachineMonitor.vue'

// Element Plus 组件 stub（避免完整挂载依赖）
const stubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-statistic': {
    template: '<div><slot name="title" />{{ value ?? "" }}</div>',
    props: ['value'],
  },
  'el-divider': true,
  'el-alert': { template: '<div><slot /></div>' },
  'el-empty': {
    template: '<div class="el-empty"><div class="el-empty__description">{{ description || "" }}</div><slot /></div>',
  },
  'el-button': { template: '<button><slot /></button>' },
}

/** 可控 WebSocket mock：测试侧手动触发 open/message/close，验证组件消费逻辑 */
class MockWebSocket {
  static instances: MockWebSocket[] = []
  url: string
  sent: string[] = []
  onopen: ((ev: Event) => void) | null = null
  onmessage: ((ev: MessageEvent) => void) | null = null
  onclose: ((ev: CloseEvent) => void) | null = null
  onerror: ((ev: Event) => void) | null = null

  constructor(url: string) {
    this.url = url
    MockWebSocket.instances.push(this)
  }

  send(data: string): void {
    this.sent.push(data)
  }

  close(): void {
    this.onclose?.({} as CloseEvent)
  }

// 测试辅助：模拟服务端推送
  emitOpen(): void {
    this.onopen?.({} as Event)
  }

  emitMessage(payload: unknown): void {
    this.onmessage?.({ data: JSON.stringify(payload) } as MessageEvent)
  }
}

function lastSocket(): MockWebSocket {
  const list = MockWebSocket.instances
  expect(list.length).toBeGreaterThan(0)
  return list[list.length - 1]
}

describe('MachineMonitor', () => {
  beforeEach(() => {
    MockWebSocket.instances = []
    vi.stubGlobal('WebSocket', MockWebSocket)
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('renders disconnected state by default', () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    expect(wrapper.text()).toContain('未连接')
    expect(wrapper.text()).toContain('连接机床')
  })

  it('connect opens WebSocket, sends subscribe, and marks connected', async () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const connectBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('连接机床'))!
    await connectBtn.trigger('click')

    const ws = lastSocket()
    // 测试环境无后端端口 → resolveBackendUrl 返回相对路径（浏览器 dev 走 vite proxy 同此路径）
    expect(ws.url).toContain('/api/v1/monitor/ws')

    // 未 open 前仍为未连接
    expect(wrapper.text()).toContain('未连接')

    ws.emitOpen()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('已连接')
    expect(ws.sent).toEqual([JSON.stringify({ action: 'subscribe', machine_id: 'VM-001' })])
  })

  it('consumes data event and updates spindle metrics', async () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const connectBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('连接机床'))!
    await connectBtn.trigger('click')
    lastSocket().emitOpen()

    lastSocket().emitMessage({
      event_type: 'data',
      data: { spindle_speed: 6000, spindle_load: 42.5, feedrate: 800, execution: 'ACTIVE' },
    })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).toContain('6000')
    expect(wrapper.text()).toContain('42.5')
    expect(wrapper.text()).toContain('800')
  })

  it('collects alert events and caps the list at 5', async () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const connectBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('连接机床'))!
    await connectBtn.trigger('click')
    lastSocket().emitOpen()

    const ws = lastSocket()
    for (let i = 1; i <= 6; i += 1) {
      ws.emitMessage({
        event_type: 'alert',
        event_id: `a-${i}`,
        message: `告警 ${i}`,
        priority: 6,
        alert_type: 'spindle_overload',
      })
    }
    await wrapper.vm.$nextTick()

    // 保留最近 5 条：首条被挤出
    expect(wrapper.text()).not.toContain('告警 1')
    for (let i = 2; i <= 6; i += 1) {
      expect(wrapper.text()).toContain(`告警 ${i}`)
    }
  })

  it('ignores malformed JSON and unrelated event types', async () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const connectBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('连接机床'))!
    await connectBtn.trigger('click')
    lastSocket().emitOpen()

    const ws = lastSocket()
    // 非法 JSON：不抛异常、不更新
    ws.onmessage?.({ data: '{broken' } as MessageEvent)
    // ping/status 事件：不更新数据
    ws.emitMessage({ event_type: 'ping', timestamp: '2026-08-25T00:00:00+00:00' })
    ws.emitMessage({ event_type: 'status', message: '已订阅 VM-001' })
    await wrapper.vm.$nextTick()

    expect(wrapper.text()).not.toContain('2026-08-25T00:00:00')
  })

  it('resets connected state when the socket closes', async () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const connectBtn = wrapper
      .findAll('button')
      .find((b) => b.text().includes('连接机床'))!
    await connectBtn.trigger('click')
    const ws = lastSocket()
    ws.emitOpen()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('已连接')

    ws.close()
    await wrapper.vm.$nextTick()
    expect(wrapper.text()).toContain('未连接')
  })

  it('shows refresh button disabled before connect', () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const refreshBtn = wrapper.findAll('button').find((b) => b.text().includes('手动刷新'))
    expect(refreshBtn!.attributes('disabled')).toBeDefined()
  })

  it('maps alert priority to element type', () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const vm = wrapper.vm as unknown as { alertTypeToEl: (p: number) => string }
    expect(vm.alertTypeToEl(8)).toBe('error')
    expect(vm.alertTypeToEl(5)).toBe('warning')
    expect(vm.alertTypeToEl(2)).toBe('success')
  })
})
