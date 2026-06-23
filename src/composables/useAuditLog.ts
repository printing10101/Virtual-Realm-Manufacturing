import { ref, reactive, onMounted } from 'vue'
import http from '@/utils/http'
import { formatTimestamp } from '@/utils/formatters'
import {
  getAuditModuleName as getModuleName,
  getAuditDecisionLabel as getDecisionName,
  getAuditDecisionTagType as getDecisionType,
  getGenericStatusLabel as getStatusName,
  getGenericStatusTagType as getStatusType,
} from '@/utils/statusHelpers'

/** 审计日志记录 */
export interface AuditLogEntry {
  id?: string | number
  ai_module?: string
  user_decision?: string
  status?: string
  created_at?: number
  [key: string]: unknown
}

/** 审计日志查询响应 */
export interface AuditLogResponse {
  logs: AuditLogEntry[]
  total: number
}

/** 审计统计信息 */
export interface AuditLogStatistics {
  total_entries?: number
  avg_confidence?: number
  recent_24h?: number
  by_module?: Record<string, number>
  by_decision?: Record<string, number>
  total?: number
  [key: string]: unknown
}

/** 审计日志查询参数 */
export interface AuditLogQueryParams {
  limit: number
  offset: number
  ai_module?: string
  user_decision?: string
  start_time?: number
  end_time?: number
}

/** 审计日志导出参数 */
export interface AuditLogExportParams {
  format: string
  ai_module?: string
  start_time?: number
  end_time?: number
}

/** 清空日志响应 */
export interface ClearLogsResponse {
  cleared_entries: number
}

export interface AuditLogFilters {
  ai_module: string
  user_decision: string
  dateRange: [Date, Date] | null
}

export interface AuditLogPagination {
  page: number
  pageSize: number
  total: number
}

export interface UseAuditLogReturn {
  auditLogs: ReturnType<typeof ref<AuditLogEntry[]>>
  auditLogStatistics: ReturnType<typeof ref<AuditLogStatistics | null>>
  loadingLogs: ReturnType<typeof ref<boolean>>
  exporting: ReturnType<typeof ref<boolean>>
  clearing: ReturnType<typeof ref<boolean>>
  logSearchKeyword: ReturnType<typeof ref<string>>
  logDetailVisible: ReturnType<typeof ref<boolean>>
  selectedLog: ReturnType<typeof ref<AuditLogEntry | null>>
  logFilters: AuditLogFilters
  logPagination: AuditLogPagination
  loadAuditLogs: () => Promise<void>
  searchLogs: () => Promise<void>
  loadStatistics: () => Promise<void>
  exportLogs: () => Promise<void>
  clearLogs: () => Promise<void>
  viewLogDetail: (row: AuditLogEntry) => void
  formatTimestamp: (ts: number) => string
  getModuleName: (module: string) => string
  getDecisionName: (decision: string) => string
  getDecisionType: (decision: string) => import('@/utils/statusHelpers').TagType
  getStatusName: (status: string) => string
  getStatusType: (status: string) => import('@/utils/statusHelpers').TagType
}

export function useAuditLog(): UseAuditLogReturn {
  const auditLogs = ref<AuditLogEntry[]>([])
  const auditLogStatistics = ref<AuditLogStatistics | null>(null)
  const loadingLogs = ref(false)
  const exporting = ref(false)
  const clearing = ref(false)
  const logSearchKeyword = ref('')
  const logDetailVisible = ref(false)
  const selectedLog = ref<AuditLogEntry | null>(null)

  const logFilters = reactive<AuditLogFilters>({
    ai_module: '',
    user_decision: '',
    dateRange: null as [Date, Date] | null,
  })

  const logPagination = reactive<AuditLogPagination>({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  async function loadAuditLogs() {
    loadingLogs.value = true
    try {
      const params: AuditLogQueryParams = {
        limit: logPagination.pageSize,
        offset: (logPagination.page - 1) * logPagination.pageSize,
      }

      if (logFilters.ai_module) params.ai_module = logFilters.ai_module
      if (logFilters.user_decision) params.user_decision = logFilters.user_decision
      if (logFilters.dateRange) {
        params.start_time = logFilters.dateRange[0].getTime()
        params.end_time = logFilters.dateRange[1].getTime()
      }

      const res = await http.post<{ data: AuditLogResponse }>('/api/v1/user-sovereignty/audit-log/query', params)
      auditLogs.value = res.data.data.logs
      logPagination.total = res.data.data.total
    } catch (e: unknown) {
      console.warn('Failed to load audit logs:', e)
    } finally {
      loadingLogs.value = false
    }
  }

  async function searchLogs() {
    if (!logSearchKeyword.value) {
      loadAuditLogs()
      return
    }

    loadingLogs.value = true
    try {
      const res = await http.post<{ data: AuditLogResponse }>('/api/v1/user-sovereignty/audit-log/search', {
        keyword: logSearchKeyword.value,
        limit: 50,
      })
      auditLogs.value = res.data.data.logs
      logPagination.total = res.data.data.total
    } catch (e: unknown) {
      console.warn('Failed to search audit logs:', e)
    } finally {
      loadingLogs.value = false
    }
  }

  async function loadStatistics() {
    try {
      const res = await http.get<{ data: AuditLogStatistics }>('/api/v1/user-sovereignty/audit-log/statistics')
      auditLogStatistics.value = res.data.data
    } catch (e: unknown) {
      console.warn('Failed to load audit log statistics:', e)
    }
  }

  async function exportLogs() {
    exporting.value = true
    try {
      const params: AuditLogExportParams = { format: 'json' }
      if (logFilters.ai_module) params.ai_module = logFilters.ai_module
      if (logFilters.dateRange) {
        params.start_time = logFilters.dateRange[0].getTime()
        params.end_time = logFilters.dateRange[1].getTime()
      }

      const res = await http.post<{ data: { content: string } }>('/api/v1/user-sovereignty/audit-log/export', params)
      const blob = new Blob([res.data.data.content], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_log_${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('日志导出成功')
    } catch (e: unknown) {
      ElMessage.error('日志导出失败')
    } finally {
      exporting.value = false
    }
  }

  async function clearLogs() {
    try {
      await ElMessageBox.confirm('确定要清空所有操作日志吗？此操作不可恢复。', '警告', {
        confirmButtonText: '确定',
        cancelButtonText: '取消',
        type: 'warning',
      })

      const res = await http.delete<{ data: ClearLogsResponse }>('/api/v1/user-sovereignty/audit-log/clear')
      ElMessage.success(`已清空 ${res.data.data.cleared_entries} 条日志`)
      loadAuditLogs()
      loadStatistics()
    } catch (e: unknown) {
      // User cancelled or error
    }
  }

  function viewLogDetail(row: AuditLogEntry) {
    selectedLog.value = row
    logDetailVisible.value = true
  }

  onMounted(() => {
    loadAuditLogs()
    loadStatistics()
  })

  return {
    auditLogs,
    auditLogStatistics,
    loadingLogs,
    exporting,
    clearing,
    logSearchKeyword,
    logDetailVisible,
    selectedLog,
    logFilters,
    logPagination,
    loadAuditLogs,
    searchLogs,
    loadStatistics,
    exportLogs,
    clearLogs,
    viewLogDetail,
    formatTimestamp,
    getModuleName,
    getDecisionName,
    getDecisionType,
    getStatusName,
    getStatusType,
  }
}
