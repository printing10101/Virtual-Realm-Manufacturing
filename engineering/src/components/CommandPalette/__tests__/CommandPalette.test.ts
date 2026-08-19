import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, VueWrapper } from '@vue/test-utils'
import CommandPalette from '@/components/CommandPalette/CommandPalette.vue'
import type { Command } from '@/types/command'

// Mock vue-i18n
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string) => key,
  }),
}))

// Mock @element-plus/icons-vue
vi.mock('@element-plus/icons-vue', () => ({
  Search: { name: 'Search', template: '<i class="icon-search" />' },
  Warning: { name: 'Warning', template: '<i class="icon-warning" />' },
  Operation: { name: 'Operation', template: '<i class="icon-operation" />' },
}))

// Mock element-plus（ElIcon / ElTag）
vi.mock('element-plus', () => ({
  ElIcon: { template: '<span class="el-icon"><slot /></span>', props: ['size'] },
  ElTag: {
    template: '<span class="el-tag"><slot /></span>',
    props: ['size', 'type', 'effect'],
  },
}))

const buildCommand = (overrides: Partial<Command> = {}): Command => ({
  id: overrides.id ?? 'cmd-1',
  name: overrides.name ?? '保存项目',
  description: overrides.description ?? '保存当前工程',
  category: overrides.category ?? '文件',
  icon: overrides.icon,
  shortcut: overrides.shortcut,
  disabled: overrides.disabled ?? false,
  action: overrides.action ?? vi.fn(),
} as unknown as Command)

describe('CommandPalette.vue', () => {
  let wrapper: VueWrapper<any>

  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
  })

  afterEach(() => {
    if (wrapper) {
      wrapper.unmount()
    }
  })

  const mountComponent = (commands: Command[] = []) => {
    wrapper = mount(CommandPalette, {
      props: { commands },
      global: {
        stubs: {
          teleport: true,
          transition: false,
        },
      },
    })
    return wrapper
  }

  describe('组件挂载', () => {
    it('应该正确挂载组件', () => {
      mountComponent([buildCommand()])
      expect(wrapper.exists()).toBe(true)
    })

    it('初始状态不可见时不渲染命令面板浮层', () => {
      mountComponent([buildCommand()])
      expect(wrapper.find('.command-palette-overlay').exists()).toBe(false)
    })
  })

  describe('filteredCommands 计算属性', () => {
    it('应返回所有未禁用的命令', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
        buildCommand({ id: 'c', name: 'Gamma', disabled: true }),
      ]
      mountComponent(cmds)
      const filtered = wrapper.vm.filteredCommands
      expect(filtered.length).toBe(2)
      expect(filtered.some((c: Command) => c.id === 'c')).toBe(false)
    })

    it('应按名称排序', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Zebra' }),
        buildCommand({ id: 'b', name: 'Apple' }),
        buildCommand({ id: 'c', name: 'Mango' }),
      ]
      mountComponent(cmds)
      const names = wrapper.vm.filteredCommands.map((c: Command) => c.name)
      expect(names).toEqual(['Apple', 'Mango', 'Zebra'])
    })

    it('查询时应进行模糊匹配过滤', async () => {
      const cmds = [
        buildCommand({ id: 'a', name: '保存项目', description: '保存当前工程' }),
        buildCommand({ id: 'b', name: '打开文件', description: '打开已有工程' }),
        buildCommand({ id: 'c', name: '导出模型', description: '导出 STL 文件' }),
      ]
      mountComponent(cmds)
      wrapper.vm.query = '保存'
      await wrapper.vm.$nextTick()
      const filtered = wrapper.vm.filteredCommands
      expect(filtered.length).toBe(1)
      expect(filtered[0].id).toBe('a')
    })

    it('查询匹配描述时应返回对应命令', async () => {
      const cmds = [
        buildCommand({ id: 'a', name: '导出', description: '导出 STL 文件' }),
        buildCommand({ id: 'b', name: '导入', description: '导入 STEP 文件' }),
      ]
      mountComponent(cmds)
      wrapper.vm.query = 'stl'
      await wrapper.vm.$nextTick()
      const filtered = wrapper.vm.filteredCommands
      expect(filtered.length).toBe(1)
      expect(filtered[0].id).toBe('a')
    })

    it('无匹配结果时应返回空数组', async () => {
      const cmds = [buildCommand({ id: 'a', name: '保存项目' })]
      mountComponent(cmds)
      wrapper.vm.query = 'xyznomatch'
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.filteredCommands.length).toBe(0)
    })

    it('查询前后空格应被去除', async () => {
      const cmds = [buildCommand({ id: 'a', name: '保存项目' })]
      mountComponent(cmds)
      wrapper.vm.query = '  保存  '
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.filteredCommands.length).toBe(1)
    })
  })

  describe('groupedCommands 计算属性', () => {
    it('应按 category 分组命令', () => {
      const cmds = [
        buildCommand({ id: 'a', name: '保存', category: '文件' }),
        buildCommand({ id: 'b', name: '打开', category: '文件' }),
        buildCommand({ id: 'c', name: '仿真', category: '仿真' }),
      ]
      mountComponent(cmds)
      const groups = wrapper.vm.groupedCommands
      expect(Object.keys(groups).length).toBe(2)
      expect(groups['文件'].length).toBe(2)
      expect(groups['仿真'].length).toBe(1)
    })

    it('未指定 category 的命令应归入默认分组', () => {
      const cmds = [buildCommand({ id: 'a', name: '保存', category: undefined })]
      mountComponent(cmds)
      const groups = wrapper.vm.groupedCommands
      expect(Object.keys(groups).length).toBe(1)
    })
  })

  describe('usageData 计算属性', () => {
    it('localStorage 无数据时返回空对象', () => {
      mountComponent([])
      expect(wrapper.vm.usageData).toEqual({})
    })

    it('localStorage 有数据时返回解析后的对象', () => {
      localStorage.setItem('command_palette_usage', JSON.stringify({ 'cmd-1': { count: 5 } }))
      mountComponent([])
      expect(wrapper.vm.usageData['cmd-1'].count).toBe(5)
    })

    it('localStorage 数据损坏时返回空对象', () => {
      localStorage.setItem('command_palette_usage', '{invalid json')
      mountComponent([])
      expect(wrapper.vm.usageData).toEqual({})
    })
  })

  describe('isSelected 方法', () => {
    it('选中索引处的命令应返回 true', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 1
      expect(wrapper.vm.isSelected(cmds[1])).toBe(true)
    })

    it('未选中索引处的命令应返回 false', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 0
      expect(wrapper.vm.isSelected(cmds[1])).toBe(false)
    })
  })

  describe('selectCommand 方法', () => {
    it('应将 selectedIndex 设置为对应命令的索引', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
        buildCommand({ id: 'c', name: 'Gamma' }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 0
      wrapper.vm.selectCommand(cmds[2])
      expect(wrapper.vm.selectedIndex).toBe(2)
    })

    it('命令不在列表中时不应修改索引', () => {
      const cmds = [buildCommand({ id: 'a', name: 'Alpha' })]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 0
      wrapper.vm.selectCommand(buildCommand({ id: 'x', name: 'Unknown' }))
      expect(wrapper.vm.selectedIndex).toBe(0)
    })
  })

  describe('executeCommand 方法', () => {
    it('应触发 execute 事件', () => {
      const cmd = buildCommand({ id: 'a', name: 'Alpha' })
      mountComponent([cmd])
      wrapper.vm.executeCommand(cmd)
      expect(wrapper.emitted('execute')).toBeTruthy()
      expect(wrapper.emitted('execute')![0]).toEqual([cmd])
    })

    it('应调用命令的 action', () => {
      const action = vi.fn()
      const cmd = buildCommand({ id: 'a', name: 'Alpha', action })
      mountComponent([cmd])
      wrapper.vm.executeCommand(cmd)
      expect(action).toHaveBeenCalled()
    })

    it('执行后应重置 query 和 selectedIndex', () => {
      const cmd = buildCommand({ id: 'a', name: 'Alpha' })
      mountComponent([cmd])
      wrapper.vm.query = 'abc'
      wrapper.vm.selectedIndex = 5
      wrapper.vm.executeCommand(cmd)
      expect(wrapper.vm.query).toBe('')
      expect(wrapper.vm.selectedIndex).toBe(0)
    })
  })

  describe('handleKeydown 方法', () => {
    it('ArrowDown 应增加 selectedIndex', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
        buildCommand({ id: 'c', name: 'Gamma' }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 0
      const event = { key: 'ArrowDown', preventDefault: vi.fn() } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(wrapper.vm.selectedIndex).toBe(1)
    })

    it('ArrowDown 在末尾不应超出范围', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 1
      const event = { key: 'ArrowDown', preventDefault: vi.fn() } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(wrapper.vm.selectedIndex).toBe(1)
    })

    it('ArrowUp 应减少 selectedIndex', () => {
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta' }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 1
      const event = { key: 'ArrowUp', preventDefault: vi.fn() } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(wrapper.vm.selectedIndex).toBe(0)
    })

    it('ArrowUp 在顶部不应小于 0', () => {
      const cmds = [buildCommand({ id: 'a', name: 'Alpha' })]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 0
      const event = { key: 'ArrowUp', preventDefault: vi.fn() } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(wrapper.vm.selectedIndex).toBe(0)
    })

    it('Enter 应执行当前选中命令', () => {
      const action = vi.fn()
      const cmds = [
        buildCommand({ id: 'a', name: 'Alpha' }),
        buildCommand({ id: 'b', name: 'Beta', action }),
      ]
      mountComponent(cmds)
      wrapper.vm.selectedIndex = 1
      const event = { key: 'Enter', preventDefault: vi.fn() } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(action).toHaveBeenCalled()
      expect(wrapper.emitted('execute')).toBeTruthy()
    })

    it('Escape 应重置 query 和 selectedIndex', () => {
      const cmds = [buildCommand({ id: 'a', name: 'Alpha' })]
      mountComponent(cmds)
      wrapper.vm.query = 'abc'
      wrapper.vm.selectedIndex = 3
      const event = { key: 'Escape', preventDefault: vi.fn() } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(wrapper.vm.query).toBe('')
      expect(wrapper.vm.selectedIndex).toBe(0)
    })

    it('应调用 preventDefault 阻止默认行为', () => {
      const cmds = [buildCommand({ id: 'a', name: 'Alpha' })]
      mountComponent(cmds)
      const preventDefault = vi.fn()
      const event = { key: 'ArrowDown', preventDefault } as unknown as KeyboardEvent
      wrapper.vm.handleKeydown(event)
      expect(preventDefault).toHaveBeenCalled()
    })
  })

  describe('open / close / toggle 方法', () => {
    it('open 应重置 query 和 selectedIndex', () => {
      const cmds = [buildCommand({ id: 'a', name: 'Alpha' })]
      mountComponent(cmds)
      wrapper.vm.query = 'abc'
      wrapper.vm.selectedIndex = 5
      wrapper.vm.open()
      expect(wrapper.vm.query).toBe('')
      expect(wrapper.vm.selectedIndex).toBe(0)
    })

    it('close 应重置 query 和 selectedIndex', () => {
      const cmds = [buildCommand({ id: 'a', name: 'Alpha' })]
      mountComponent(cmds)
      wrapper.vm.query = 'abc'
      wrapper.vm.selectedIndex = 5
      wrapper.vm.close()
      expect(wrapper.vm.query).toBe('')
      expect(wrapper.vm.selectedIndex).toBe(0)
    })

    it('toggle 应暴露为方法', () => {
      mountComponent([])
      expect(typeof wrapper.vm.toggle).toBe('function')
    })

    it('暴露的方法应包含 open/close/toggle', () => {
      mountComponent([])
      expect(typeof wrapper.vm.open).toBe('function')
      expect(typeof wrapper.vm.close).toBe('function')
      expect(typeof wrapper.vm.toggle).toBe('function')
    })
  })

  describe('fuzzyMatch 逻辑', () => {
    it('完全匹配应返回 true', async () => {
      const cmds = [buildCommand({ id: 'a', name: 'save', description: '' })]
      mountComponent(cmds)
      wrapper.vm.query = 'save'
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.filteredCommands.length).toBe(1)
    })

    it('部分子串匹配应返回 true', async () => {
      const cmds = [buildCommand({ id: 'a', name: 'save project', description: '' })]
      mountComponent(cmds)
      wrapper.vm.query = 'save'
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.filteredCommands.length).toBe(1)
    })

    it('乱序字符模糊匹配应返回 true', async () => {
      const cmds = [buildCommand({ id: 'a', name: 'save', description: '' })]
      mountComponent(cmds)
      // fuzzyMatch 顺序匹配 'sae' 在 'save' 中：s(0) a(1) e(3) -> 命中
      wrapper.vm.query = 'sae'
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.filteredCommands.length).toBe(1)
    })

    it('不匹配的查询应返回空', async () => {
      const cmds = [buildCommand({ id: 'a', name: 'save', description: '' })]
      mountComponent(cmds)
      wrapper.vm.query = 'xyz'
      await wrapper.vm.$nextTick()
      expect(wrapper.vm.filteredCommands.length).toBe(0)
    })
  })
})
