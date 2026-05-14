import { ref, reactive, onMounted } from 'vue'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'

export function useAuditLog() {
  const auditLogs = ref<any[]>([])
  const auditLogStatistics = ref<any>(null)
  const loadingLogs = ref(false)
  const exporting = ref(false)
  const clearing = ref(false)
  const logSearchKeyword = ref('')
  const logDetailVisible = ref(false)
  const selectedLog = ref<any>(null)

  const logFilters = reactive({
    ai_module: '',
    user_decision: '',
    dateRange: null as [Date, Date] | null,
  })

  const logPagination = reactive({
    page: 1,
    pageSize: 20,
    total: 0,
  })

  async function loadAuditLogs() {
    loadingLogs.value = true
    try {
      const params: any = {
        limit: logPagination.pageSize,
        offset: (logPagination.page - 1) * logPagination.pageSize,
      }

      if (logFilters.ai_module) params.ai_module = logFilters.ai_module
      if (logFilters.user_decision) params.user_decision = logFilters.user_decision
      if (logFilters.dateRange) {
        params.start_time = logFilters.dateRange[0].getTime()
        params.end_time = logFilters.dateRange[1].getTime()
      }

      const res = await axios.post('/api/v1/user-sovereignty/audit-log/query', params)
      auditLogs.value = res.data.data.logs
      logPagination.total = res.data.data.total
    } catch (e) {
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
      const res = await axios.post('/api/v1/user-sovereignty/audit-log/search', {
        keyword: logSearchKeyword.value,
        limit: 50,
      })
      auditLogs.value = res.data.data.logs
      logPagination.total = res.data.data.total
    } catch (e) {
      console.warn('Failed to search audit logs:', e)
    } finally {
      loadingLogs.value = false
    }
  }

  async function loadStatistics() {
    try {
      const res = await axios.get('/api/v1/user-sovereignty/audit-log/statistics')
      auditLogStatistics.value = res.data.data
    } catch (e) {
      console.warn('Failed to load audit log statistics:', e)
    }
  }

  async function exportLogs() {
    exporting.value = true
    try {
      const params: any = { format: 'json' }
      if (logFilters.ai_module) params.ai_module = logFilters.ai_module
      if (logFilters.dateRange) {
        params.start_time = logFilters.dateRange[0].getTime()
        params.end_time = logFilters.dateRange[1].getTime()
      }

      const res = await axios.post('/api/v1/user-sovereignty/audit-log/export', params)
      const blob = new Blob([res.data.data.content], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `audit_log_${Date.now()}.json`
      a.click()
      URL.revokeObjectURL(url)
      ElMessage.success('日志导出成功')
    } catch (e) {
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

      const res = await axios.delete('/api/v1/user-sovereignty/audit-log/clear')
      ElMessage.success(`已清空 ${res.data.data.cleared_entries} 条日志`)
      loadAuditLogs()
      loadStatistics()
    } catch (e) {
      // User cancelled or error
    }
  }

  function viewLogDetail(row: any) {
    selectedLog.value = row
    logDetailVisible.value = true
  }

  function formatTimestamp(ts: number): string {
    return new Date(ts).toLocaleString('zh-CN')
  }

  function getModuleName(module: string): string {
    const names: Record<string, string> = {
      lnn_predict: 'LNN预测',
      lnn_train: 'LNN训练',
      process_optimize: '工艺优化',
      tool_wear_analyze: '刀具磨损分析',
      cad_generate: 'CAD生成',
    }
    return names[module] || module
  }

  function getDecisionName(decision: string): string {
    const names: Record<string, string> = {
      accept: '接受',
      modify: '修改',
      reject: '拒绝',
      auto_executed: '自动执行',
    }
    return names[decision] || decision
  }

  function getDecisionType(decision: string): 'success' | 'warning' | 'danger' | 'info' {
    if (decision === 'accept') return 'success'
    if (decision === 'modify') return 'warning'
    if (decision === 'reject') return 'danger'
    return 'info'
  }

  function getStatusName(status: string): string {
    const names: Record<string, string> = {
      success: '成功',
      failed: '失败',
      cancelled: '已取消',
      pending: '待处理',
    }
    return names[status] || status
  }

  function getStatusType(status: string): 'success' | 'danger' | 'info' | 'warning' {
    if (status === 'success') return 'success'
    if (status === 'failed') return 'danger'
    if (status === 'cancelled') return 'warning'
    return 'info'
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
