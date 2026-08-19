/**
 * 命令面板共享类型
 *
 * 原定义于 composables/useCommandPalette.ts（该 composable 为死代码——
 * CommandPalette.vue 自实现全部状态逻辑，仅引用 Command 类型），
 * 2026-08-20 迁移至此，删除死代码 composable。
 */

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
