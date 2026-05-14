/**
 * 灵境制造 — 集中类型定义
 *
 * 统一导出所有 Store / Composable / 通用类型，
 * 消除跨模块类型导入中的分散引用。
 */

export type {
  AgentSummary,
  CheckpointInfo,
  MemoryEntryInfo,
  AgentDetail,
} from '@/stores/agents'

export type {
  Plugin,
  PluginDetail,
} from '@/stores/plugin'

export type {
  AppSettings,
} from '@/stores/settings'

export type {
  VersionStatus,
} from '@/stores/version'

export type {
  SSEEvent,
  UseEventSourceOptions,
} from '@/composables/useEventSource'

/** 训练/推理任务状态 */
export type TaskStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled'

/** 插件类型 */
export type PluginType = 'adapter' | 'data_source' | 'tool' | 'enhancement'

/** 插件状态 */
export type PluginStatus = 'enabled' | 'disabled' | 'error' | 'installing' | 'uninstalling'

/** API 通用响应包装 */
export interface ApiResponse<T = unknown> {
  data: T
  message?: string
  status?: number
}

/** 分页参数 */
export interface Pagination {
  page: number
  pageSize: number
  total: number
}

/** 版本号三组 */
export interface SemVer {
  major: number
  minor: number
  patch: number
}
