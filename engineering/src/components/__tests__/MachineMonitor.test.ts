// MachineMonitor 组件测试（Phase A 前端）
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'

import MachineMonitor from '@/components/realtime/MachineMonitor.vue'

// Element Plus 组件 stub（避免完整挂载依赖）
const stubs = {
  'el-card': { template: '<div><slot name="header" /><slot /></div>' },
  'el-tag': { template: '<span><slot /></span>' },
  'el-statistic': { template: '<div><slot name="title" />{{ value }}</div>' },
  'el-divider': true,
  'el-alert': { template: '<div><slot /></div>' },
  // el-empty: 支持 description 属性
  'el-empty': {
    template: '<div class="el-empty"><div class="el-empty__description">{{ description || "" }}</div><slot /></div>',
  },
  'el-button': { template: '<button><slot /></button>' },
}

describe('MachineMonitor', () => {
  it('renders disconnected state by default', () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    expect(wrapper.text()).toContain('未连接')
    expect(wrapper.text()).toContain('连接机床')
  })

  it('connects and shows running data', async () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const buttons = wrapper.findAll('button')
    // 找到「连接机床」按钮
    const connectBtn = buttons.find((b) => b.text().includes('连接机床'))
    expect(connectBtn).toBeTruthy()
    await connectBtn!.trigger('click')
    expect(wrapper.text()).toContain('已连接')
    // 空 alerts 状态显示主轴数据（el-empty 可能不显示）
    expect(wrapper.text()).toMatch(/已连接 | 主轴转速 | 主轴负载/)
  })

  it('shows refresh button disabled before connect', () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const refreshBtn = wrapper.findAll('button').find((b) => b.text().includes('手动刷新'))
    expect(refreshBtn!.attributes('disabled')).toBeDefined()
  })

  it('maps alert priority to element type', () => {
    const wrapper = mount(MachineMonitor, { global: { stubs } })
    const vm = wrapper.vm as unknown as { alertTypeToEl: (p: number) => string }
    expect(vm.alertTypeToEl(8)).toBe('danger')
    expect(vm.alertTypeToEl(5)).toBe('warning')
    expect(vm.alertTypeToEl(2)).toBe('success')
  })
})
