/**
 * 命令面板可组合函数
 * 提供类似 VSCode 的命令面板功能，支持快捷键唤起、搜索、分类展示
 */

import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'

/** 命令类型 */
export interface Command {
  /** 唯一标识 */
  id: string
  /** 命令名称 */
  name: string
  /** 命令描述 */
  description?: string
  /** 命令分类 */
  category?: string
  /** 图标 */
  icon?: string
  /** 快捷键 */
  shortcut?: string
  /** 执行函数 */
  action: () => void | Promise<void>
  /** 是否禁用 */
  disabled?: boolean
  /** 使用次数（用于智能排序） */
  usageCount?: number
  /** 最后使用时间 */
  lastUsed?: number
}

/** 命令面板配置 */
export interface CommandPaletteConfig {
  /** 快捷键，默认 'Cmd+K' / 'Ctrl+K' */
  shortcut?: string
  /** 存储键名，用于记忆使用频率 */
  storageKey?: string
  /** 最大历史记录数 */
  maxHistory?: number
}

/** 命令面板状态 */
export interface CommandPaletteState {
  /** 是否可见 */
  visible: boolean
  /** 搜索关键词 */
  query: string
  /** 当前选中索引 */
  selectedIndex: number
}

const DEFAULT_CONFIG: CommandPaletteConfig = {
  shortcut: 'Cmd+K',
  storageKey: 'command_palette_usage',
  maxHistory: 50
}

export function useCommandPalette(config: CommandPaletteConfig = {}) {
  const mergedConfig = { ...DEFAULT_CONFIG, ...config }

  // 状态
  const commands = ref<Command[]>([])
  const state = ref<CommandPaletteState>({
    visible: false,
    query: '',
    selectedIndex: 0
  })

  // 使用频率记录
  const usageData = ref<Record<string, { count: number; lastUsed: number }>>({})

  // 计算属性：过滤和排序后的命令
  const filteredCommands = computed(() => {
    const query = state.value.query.toLowerCase().trim()
    
    let result = commands.value.filter(cmd => !cmd.disabled)

    // 搜索过滤（支持模糊匹配）
    if (query) {
      result = result.filter(cmd => {
        const searchText = `${cmd.name} ${cmd.description || ''} ${cmd.category || ''}`.toLowerCase()
        return fuzzyMatch(searchText, query)
      })
    }

    // 智能排序：结合使用频率和相关性
    result.sort((a, b) => {
      const aUsage = usageData.value[a.id]?.count || 0
      const bUsage = usageData.value[b.id]?.count || 0
      const aLastUsed = usageData.value[a.id]?.lastUsed || 0
      const bLastUsed = usageData.value[b.id]?.lastUsed || 0

      // 如果有搜索词，优先按相关性排序
      if (query) {
        const aScore = calculateRelevanceScore(a, query)
        const bScore = calculateRelevanceScore(b, query)
        if (aScore !== bScore) {
          return bScore - aScore
        }
      }

      // 否则按使用频率排序
      if (aUsage !== bUsage) {
        return bUsage - aUsage
      }

      // 使用次数相同，按最后使用时间排序
      if (aLastUsed !== bLastUsed) {
        return bLastUsed - aLastUsed
      }

      // 默认按名称排序
      return a.name.localeCompare(b.name)
    })

    return result
  })

  // 按分类分组的命令
  const groupedCommands = computed(() => {
    const groups: Record<string, Command[]> = {}
    
    filteredCommands.value.forEach(cmd => {
      const category = cmd.category || '其他'
      if (!groups[category]) {
        groups[category] = []
      }
      groups[category].push(cmd)
    })

    return groups
  })

  // 方法
  function open() {
    state.value.visible = true
    state.value.query = ''
    state.value.selectedIndex = 0
    loadUsageData()
  }

  function close() {
    state.value.visible = false
    state.value.query = ''
    state.value.selectedIndex = 0
  }

  function toggle() {
    if (state.value.visible) {
      close()
    } else {
      open()
    }
  }

  function setQuery(query: string) {
    state.value.query = query
    state.value.selectedIndex = 0
  }

  function selectNext() {
    if (state.value.selectedIndex < filteredCommands.value.length - 1) {
      state.value.selectedIndex++
    }
  }

  function selectPrev() {
    if (state.value.selectedIndex > 0) {
      state.value.selectedIndex--
    }
  }

  async function executeCommand(command: Command) {
    try {
      await command.action()
      recordUsage(command.id)
      close()
    } catch (e: unknown) {
      // 命令执行失败属于用户主动操作，必须给出反馈，否则用户会误以为已执行
      console.warn('[useCommandPalette] executeCommand failed:', command.id, e)
      ElMessage.error(`命令执行失败：${command.name}`)
    }
  }

  async function executeSelected() {
    const cmd = filteredCommands.value[state.value.selectedIndex]
    if (cmd) {
      await executeCommand(cmd)
    }
  }

  function registerCommand(command: Command) {
    const existingIndex = commands.value.findIndex(cmd => cmd.id === command.id)
    if (existingIndex >= 0) {
      commands.value[existingIndex] = command
    } else {
      commands.value.push(command)
    }
  }

  function registerCommands(newCommands: Command[]) {
    newCommands.forEach(cmd => registerCommand(cmd))
  }

  function unregisterCommand(commandId: string) {
    const index = commands.value.findIndex(cmd => cmd.id === commandId)
    if (index >= 0) {
      commands.value.splice(index, 1)
    }
  }

  function recordUsage(commandId: string) {
    const now = Date.now()
    if (!usageData.value[commandId]) {
      usageData.value[commandId] = { count: 0, lastUsed: 0 }
    }
    usageData.value[commandId].count++
    usageData.value[commandId].lastUsed = now
    saveUsageData()
  }

  function saveUsageData() {
    try {
      // 只保存最近使用的命令
      const sortedEntries = Object.entries(usageData.value)
        .sort((a, b) => b[1].lastUsed - a[1].lastUsed)
        .slice(0, mergedConfig.maxHistory)
      
      const dataToSave = Object.fromEntries(sortedEntries)
      localStorage.setItem(mergedConfig.storageKey!, JSON.stringify(dataToSave))
    } catch (e: unknown) {
      // localStorage 写入失败（如配额超限、隐私模式）不影响核心功能，记录便于排查
      console.warn('[useCommandPalette] saveUsageData failed:', e)
    }
  }

  function loadUsageData() {
    try {
      const raw = localStorage.getItem(mergedConfig.storageKey!)
      if (raw) {
        usageData.value = JSON.parse(raw)
      }
    } catch (e: unknown) {
      // localStorage 读取失败（数据损坏）时清空避免反复报错，记录便于排查
      console.warn('[useCommandPalette] loadUsageData failed, reset usage data:', e)
      try { localStorage.removeItem(mergedConfig.storageKey!) } catch { /* 二次失败忽略 */ }
      usageData.value = {}
    }
  }

  function clearUsageData() {
    usageData.value = {}
    localStorage.removeItem(mergedConfig.storageKey!)
  }

  // 常用汉字拼音首字母映射表
  const pinyinMap: Record<string, string> = {
    '新': 'x', '建': 'j', '项': 'x', '目': 'm', '打': 'd', '开': 'k',
    '保': 'b', '存': 'c', '当': 'd', '前': 'q', '工': 'g', '程': 'c',
    '导': 'd', '出': 'c', '代': 'd', '码': 'm', '文': 'w', '件': 'j',
    '路': 'l', '径': 'j', '创': 'c', '一': 'y', '个': 'g', '的': 'd',
    '已': 'y', '有': 'y', '关': 'g', '命': 'm', '令': 'l', '面': 'm',
    '板': 'b', '搜': 's', '索': 's', '闭': 'b', '切': 'q',
    '换': 'h', '设': 's', '置': 'z', '帮': 'b', '助': 'z',
    '于': 'y', '我': 'w', '们': 'm', '你': 'n', '他': 't', '她': 't',
    '它': 't', '是': 's', '在': 'z', '不': 'b', '中': 'z', '大': 'd',
    '来': 'l', '上': 's', '国': 'g', '到': 'd', '说': 's',
    '为': 'w', '子': 'z', '和': 'h', '地': 'd',
    '会': 'h', '也': 'y', '对': 'd', '这': 'z', '经': 'j',
    '两': 'l', '样': 'y', '看': 'k', '着': 'z', '都': 'd', '然': 'r',
    '没': 'm', '日': 'r', '起': 'q', '还': 'h', '发': 'f',
    '成': 'c', '事': 's', '只': 'z', '作': 'z', '想': 'x',
    '把': 'b', '自': 'z', '那': 'n', '进': 'j', '好': 'h', '多': 'd',
    '里': 'l', '如': 'r', '果': 'g', '最': 'z', '什': 's', '么': 'm',
    '时': 's', '候': 'h', '用': 'y', '做': 'z', '去': 'q', '能': 'n',
    '让': 'r', '所': 's', '从': 'c', '而': 'e', '得': 'd', '过': 'g',
    '行': 'x', '实': 's', '现': 'x', '功': 'g', '模': 'm',
    '式': 's', '系': 'x', '统': 't', '数': 's', '据': 'j', '库': 'k',
    '表': 'b', '格': 'g', '图': 't', '形': 'x', '参': 'c', '配': 'p',
    '输': 's', '入': 'r', '值': 'z', '返': 'f', '回': 'h', '结': 'j',
    '错': 'c', '误': 'w', '提': 't', '示': 's', '信': 'x',
    '息': 'x', '志': 'z', '记': 'j', '录': 'l', '查': 'c',
    '询': 'x', '编': 'b', '辑': 'j', '修': 'x', '改': 'g', '删': 's',
    '除': 'c', '添': 't', '加': 'j', '复': 'f', '制': 'z', '粘': 'n',
    '贴': 't', '剪': 'j', '移': 'y', '动': 'd', '排': 'p', '序': 'x',
    '升': 's', '降': 'j', '滤': 'l', '分': 'f', '组': 'z',
    '计': 'j', '析': 'x', '报': 'b', '告': 'g',
    '印': 'y', '预': 'y', '览': 'l', '全': 'q', '屏': 'p',
    '缩': 's', '放': 'f', '旋': 'x', '转': 'z', '平': 'p', '视': 's',
    '角': 'j', '渲': 'x', '染': 'r',
    '载': 'z', '卸': 'x', '刷': 's',
    '重': 'c', '清': 'q', '空': 'k', '缓': 'h', '冲': 'c',
    '夹': 'j',
    '包': 'b', '压': 'y', '解': 'j', '安': 'a',
    '装': 'z', '更': 'g',
    '级': 'j', '补': 'b', '丁': 'd',
    '题': 't', '检': 'j', '测': 'c', '试': 's', '调': 'd',
    '运': 'y', '停': 't', '止': 'z', '暂': 'z',
    '继': 'j', '续': 'x', '跳': 't',
    '步': 'b', '下': 'x',
    '完': 'w', '取': 'q', '消': 'x', '确': 'q', '定': 'd',
    '否': 'f', '通': 't', '失': 's', '败': 'b',
    '正': 'z', '等': 'd', '待': 'd',
    '警': 'j',
    '详': 'x', '情': 'q',
    '选': 'x', '默': 'm', '认': 'r',
    '高': 'g', '首': 's',
    '语': 'y', '言': 'y', '主': 'z', '外': 'w',
    '观': 'g', '字': 'z', '体': 't', '颜': 'y', '色': 's',
    '标': 'b', '准': 'z', '义': 'y'
  }

  // 获取字符串的拼音首字母
  function getPinyinInitials(text: string): string {
    let initials = ''
    for (let i = 0; i < text.length; i++) {
      const char = text[i]
      if (pinyinMap[char]) {
        initials += pinyinMap[char]
      } else if (/[a-zA-Z]/.test(char)) {
        initials += char.toLowerCase()
      }
    }
    return initials
  }

  // 模糊匹配算法（支持拼音首字母匹配）
  function fuzzyMatch(text: string, query: string): boolean {
    const lowerText = text.toLowerCase()
    const lowerQuery = query.toLowerCase()
    
    // 1. 直接字符匹配
    if (fuzzyMatchBasic(lowerText, lowerQuery)) {
      return true
    }
    
    // 2. 拼音首字母匹配
    const textInitials = getPinyinInitials(text)
    if (fuzzyMatchBasic(textInitials, lowerQuery)) {
      return true
    }
    
    return false
  }

  // 基础模糊匹配
  function fuzzyMatchBasic(text: string, query: string): boolean {
    let queryIndex = 0
    let textIndex = 0

    while (queryIndex < query.length && textIndex < text.length) {
      if (query[queryIndex] === text[textIndex]) {
        queryIndex++
      }
      textIndex++
    }

    return queryIndex === query.length
  }

  // 计算相关性分数
  function calculateRelevanceScore(command: Command, query: string): number {
    let score = 0
    const name = command.name.toLowerCase()
    const description = (command.description || '').toLowerCase()
    const category = (command.category || '').toLowerCase()

    // 名称完全匹配
    if (name === query) {
      score += 100
    } else if (name.startsWith(query)) {
      score += 50
    } else if (name.includes(query)) {
      score += 25
    }

    // 描述匹配
    if (description.includes(query)) {
      score += 10
    }

    // 分类匹配
    if (category.includes(query)) {
      score += 5
    }

    return score
  }

  // 键盘事件处理
  function handleKeydown(event: KeyboardEvent) {
    // 检查是否按下快捷键
    const isMac = navigator.platform.toUpperCase().indexOf('MAC') >= 0
    const shortcutKey = isMac ? event.metaKey : event.ctrlKey
    
    if (shortcutKey && event.key.toLowerCase() === 'k') {
      event.preventDefault()
      toggle()
      return
    }

    // 如果面板未打开，不处理其他键盘事件
    if (!state.value.visible) return

    switch (event.key) {
      case 'Escape':
        event.preventDefault()
        close()
        break
      case 'ArrowDown':
        event.preventDefault()
        selectNext()
        break
      case 'ArrowUp':
        event.preventDefault()
        selectPrev()
        break
      case 'Enter':
        event.preventDefault()
        executeSelected()
        break
    }
  }

  // 生命周期
  onMounted(() => {
    document.addEventListener('keydown', handleKeydown)
    loadUsageData()
  })

  onUnmounted(() => {
    document.removeEventListener('keydown', handleKeydown)
  })

  return {
    // 状态
    commands,
    state,
    filteredCommands,
    groupedCommands,
    usageData,

    // 方法
    open,
    close,
    toggle,
    setQuery,
    selectNext,
    selectPrev,
    executeCommand,
    executeSelected,
    registerCommand,
    registerCommands,
    unregisterCommand,
    recordUsage,
    clearUsageData
  }
}
