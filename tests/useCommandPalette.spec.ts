import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { useCommandPalette } from '../src/composables/useCommandPalette'
import type { Command } from '../src/composables/useCommandPalette'

describe('useCommandPalette', () => {
  const mockCommands: Command[] = [
    {
      id: 'cmd1',
      name: '新建项目',
      description: '创建一个新的工程项目',
      category: '文件',
      action: vi.fn()
    },
    {
      id: 'cmd2',
      name: '打开项目',
      description: '打开已有的工程项目',
      category: '文件',
      action: vi.fn()
    },
    {
      id: 'cmd3',
      name: '保存项目',
      description: '保存当前工程项目',
      category: '文件',
      action: vi.fn()
    },
    {
      id: 'cmd4',
      name: '导出G代码',
      description: '将工具路径导出为G代码文件',
      category: '工具路径',
      action: vi.fn()
    }
  ]

  beforeEach(() => {
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('应该正确初始化', () => {
    const palette = useCommandPalette()
    expect(palette.commands.value).toEqual([])
    expect(palette.state.value.visible).toBe(false)
    expect(palette.state.value.query).toBe('')
    expect(palette.state.value.selectedIndex).toBe(0)
  })

  it('应该支持注册单个命令', () => {
    const palette = useCommandPalette()
    palette.registerCommand(mockCommands[0])

    expect(palette.commands.value.length).toBe(1)
    expect(palette.commands.value[0].id).toBe('cmd1')
  })

  it('应该支持批量注册命令', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)

    expect(palette.commands.value.length).toBe(4)
  })

  it('应该支持更新已存在的命令', () => {
    const palette = useCommandPalette()
    palette.registerCommand(mockCommands[0])
    
    const updatedCmd = { ...mockCommands[0], name: '新建工程' }
    palette.registerCommand(updatedCmd)

    expect(palette.commands.value.length).toBe(1)
    expect(palette.commands.value[0].name).toBe('新建工程')
  })

  it('应该支持注销命令', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    
    palette.unregisterCommand('cmd2')

    expect(palette.commands.value.length).toBe(3)
    expect(palette.commands.value.find(cmd => cmd.id === 'cmd2')).toBeUndefined()
  })

  it('应该支持打开和关闭面板', () => {
    const palette = useCommandPalette()
    
    palette.open()
    expect(palette.state.value.visible).toBe(true)

    palette.close()
    expect(palette.state.value.visible).toBe(false)
  })

  it('应该支持切换面板状态', () => {
    const palette = useCommandPalette()
    
    palette.toggle()
    expect(palette.state.value.visible).toBe(true)

    palette.toggle()
    expect(palette.state.value.visible).toBe(false)
  })

  it('应该支持设置搜索关键词', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    palette.setQuery('新建')
    expect(palette.state.value.query).toBe('新建')
    expect(palette.state.value.selectedIndex).toBe(0)
  })

  it('应该支持模糊匹配搜索', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    // 搜索 "新建"
    palette.setQuery('新建')
    expect(palette.filteredCommands.value.length).toBe(1)
    expect(palette.filteredCommands.value[0].id).toBe('cmd1')

    // 搜索 "项目" - 应该匹配所有包含"项目"的命令
    palette.setQuery('项目')
    expect(palette.filteredCommands.value.length).toBe(3)

    // 搜索 "G代码"
    palette.setQuery('G代码')
    expect(palette.filteredCommands.value.length).toBe(1)
    expect(palette.filteredCommands.value[0].id).toBe('cmd4')
  })

  it('应该支持选择下一个命令', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    expect(palette.state.value.selectedIndex).toBe(0)
    
    palette.selectNext()
    expect(palette.state.value.selectedIndex).toBe(1)

    palette.selectNext()
    expect(palette.state.value.selectedIndex).toBe(2)
  })

  it('应该支持选择上一个命令', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    palette.selectNext()
    palette.selectNext()
    expect(palette.state.value.selectedIndex).toBe(2)

    palette.selectPrev()
    expect(palette.state.value.selectedIndex).toBe(1)
  })

  it('不应该超出选择范围', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    // 尝试选择上一个（已经在第一个）
    palette.selectPrev()
    expect(palette.state.value.selectedIndex).toBe(0)

    // 选择到最后
    palette.selectNext()
    palette.selectNext()
    palette.selectNext()
    expect(palette.state.value.selectedIndex).toBe(3)

    // 尝试再选择下一个（已经在最后一个）
    palette.selectNext()
    expect(palette.state.value.selectedIndex).toBe(3)
  })

  it('应该支持执行命令', async () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    await palette.executeCommand(mockCommands[0])

    expect(mockCommands[0].action).toHaveBeenCalled()
    expect(palette.state.value.visible).toBe(false)
  })

  it('应该支持执行选中的命令', async () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    palette.selectNext()
    await palette.executeSelected()

    expect(mockCommands[1].action).toHaveBeenCalled()
  })

  it('应该记录命令使用频率', async () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    await palette.executeCommand(mockCommands[0])
    expect(palette.usageData.value['cmd1']).toBeDefined()
    expect(palette.usageData.value['cmd1'].count).toBe(1)

    await palette.executeCommand(mockCommands[0])
    expect(palette.usageData.value['cmd1'].count).toBe(2)
  })

  it('应该根据使用频率智能排序', async () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    // 使用 cmd2 三次
    await palette.executeCommand(mockCommands[1])
    await palette.executeCommand(mockCommands[1])
    await palette.executeCommand(mockCommands[1])

    // 使用 cmd1 一次
    await palette.executeCommand(mockCommands[0])

    // 重新打开面板，检查排序
    palette.open()
    expect(palette.filteredCommands.value[0].id).toBe('cmd2')
    expect(palette.filteredCommands.value[1].id).toBe('cmd1')
  })

  it('应该保存和加载使用数据', async () => {
    const storageKey = 'test_command_usage'
    const palette = useCommandPalette({ storageKey })
    palette.registerCommands(mockCommands)
    palette.open()

    await palette.executeCommand(mockCommands[0])
    await palette.executeCommand(mockCommands[1])

    // 验证数据已保存
    const saved = localStorage.getItem(storageKey)
    expect(saved).toBeTruthy()

    // 创建新的实例，应该加载已保存的数据
    const palette2 = useCommandPalette({ storageKey })
    palette2.registerCommands(mockCommands)
    palette2.open()

    expect(palette2.usageData.value['cmd1']).toBeDefined()
    expect(palette2.usageData.value['cmd2']).toBeDefined()
  })

  it('应该支持清理使用数据', async () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    await palette.executeCommand(mockCommands[0])
    expect(palette.usageData.value['cmd1']).toBeDefined()

    palette.clearUsageData()
    expect(Object.keys(palette.usageData.value).length).toBe(0)
    expect(localStorage.getItem('command_palette_usage')).toBeNull()
  })

  it('应该按分类分组命令', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    const groups = palette.groupedCommands.value
    expect(groups['文件']).toBeDefined()
    expect(groups['文件'].length).toBe(3)
    expect(groups['工具路径']).toBeDefined()
    expect(groups['工具路径'].length).toBe(1)
  })

  it('应该过滤禁用的命令', () => {
    const palette = useCommandPalette()
    const cmdsWithDisabled = [
      ...mockCommands,
      { ...mockCommands[0], id: 'cmd5', disabled: true }
    ]
    palette.registerCommands(cmdsWithDisabled)
    palette.open()

    expect(palette.filteredCommands.value.length).toBe(4)
    expect(palette.filteredCommands.value.find(cmd => cmd.id === 'cmd5')).toBeUndefined()
  })

  it('应该正确处理空搜索', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    palette.setQuery('')
    expect(palette.filteredCommands.value.length).toBe(4)

    palette.setQuery('   ')
    expect(palette.filteredCommands.value.length).toBe(4)
  })

  it('应该正确处理无匹配结果', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    palette.setQuery('不存在的命令')
    expect(palette.filteredCommands.value.length).toBe(0)
  })

  it('应该支持模糊匹配算法', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    // "xj" 应该匹配 "新建" (模糊匹配)
    palette.setQuery('xj')
    expect(palette.filteredCommands.value.length).toBeGreaterThan(0)

    // "dcg" 应该匹配 "导出G代码" (拼音首字母: 导=d, 出=c, G=g)
    palette.setQuery('dcg')
    expect(palette.filteredCommands.value.length).toBeGreaterThan(0)
  })

  it('应该根据相关性排序搜索结果', () => {
    const palette = useCommandPalette()
    palette.registerCommands(mockCommands)
    palette.open()

    palette.setQuery('项目')
    const results = palette.filteredCommands.value
    
    // 所有结果都应该包含"项目"
    expect(results.length).toBe(3)
    results.forEach(cmd => {
      expect(cmd.name.includes('项目') || cmd.description?.includes('项目')).toBe(true)
    })
  })

  it('应该支持自定义配置', () => {
    const customConfig = {
      shortcut: 'Cmd+P',
      storageKey: 'custom_storage',
      maxHistory: 100
    }

    const palette = useCommandPalette(customConfig)
    expect(palette).toBeDefined()
  })

  it('应该正确处理命令执行错误', async () => {
    const palette = useCommandPalette()
    const errorCmd: Command = {
      id: 'error_cmd',
      name: '错误命令',
      action: () => {
        throw new Error('命令执行失败')
      }
    }

    palette.registerCommand(errorCmd)
    palette.open()

    // 应该捕获错误，不抛出异常
    await expect(palette.executeCommand(errorCmd)).resolves.not.toThrow()
  })

  it('应该支持异步命令执行', async () => {
    const palette = useCommandPalette()
    const asyncCmd: Command = {
      id: 'async_cmd',
      name: '异步命令',
      action: async () => {
        await new Promise(resolve => setTimeout(resolve, 100))
        return 'done'
      }
    }

    palette.registerCommand(asyncCmd)
    palette.open()

    await palette.executeCommand(asyncCmd)
    expect(palette.state.value.visible).toBe(false)
  })

  it('应该限制历史记录数量', async () => {
    const maxHistory = 5
    const palette = useCommandPalette({ maxHistory })
    
    // 注册10个命令
    const manyCommands = Array.from({ length: 10 }, (_, i) => ({
      id: `cmd${i}`,
      name: `命令${i}`,
      action: vi.fn()
    }))
    
    palette.registerCommands(manyCommands)
    palette.open()

    // 使用所有命令
    for (const cmd of manyCommands) {
      await palette.executeCommand(cmd)
    }

    // 验证只保存了最近的5个
    const saved = localStorage.getItem('command_palette_usage')
    expect(saved).toBeTruthy()
    const data = JSON.parse(saved!)
    expect(Object.keys(data).length).toBeLessThanOrEqual(maxHistory)
  })
})
