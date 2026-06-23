import { defineStore } from 'pinia'
import http from '@/utils/http'
import { ref, computed } from 'vue'
import type {
  ProcessRule,
  RuleGroup,
  RuleListResponse,
  RuleGroupListResponse,
  RuleStats,
  RuleImportResponse,
  RuleCreateRequest,
  RuleUpdateRequest,
  RuleGroupCreateRequest,
  RuleGroupUpdateRequest,
} from '@/types'
import { ElMessage } from 'element-plus'
import { extractErrorMessage } from '@/utils/errorUtils'

/**
 * 工艺规则管理 Store
 * 管理工艺规则的增删改查、分组管理、导入导出和数据库备份。
 */
export const useRuleStore = defineStore('rules', () => {
  /** 规则列表 */
  const rules = ref<ProcessRule[]>([])
  /** 分组列表 */
  const groups = ref<RuleGroup[]>([])
  /** 当前选中的规则 */
  const currentRule = ref<ProcessRule | null>(null)
  /** 规则统计信息 */
  const stats = ref<RuleStats | null>(null)
  /** 加载状态 */
  const loading = ref(false)
  /** 创建/编辑对话框显示状态 */
  const showDialog = ref(false)
  /** 正在编辑的规则 */
  const editingRule = ref<ProcessRule | null>(null)
  /** 分组对话框显示状态 */
  const showGroupDialog = ref(false)
  /** 正在编辑的分组 */
  const editingGroup = ref<RuleGroup | null>(null)

  const totalRules = ref(0)
  const currentPage = ref(1)
  const pageSize = ref(20)
  const totalPages = ref(0)

  const activeRules = computed(() => rules.value.filter((r) => r.status === 'active'))
  const draftRules = computed(() => rules.value.filter((r) => r.status === 'draft'))

  async function fetchRules(params?: {
    group_id?: number
    status?: string
    keyword?: string
    sort_by?: string
    sort_order?: string
    page?: number
    page_size?: number
  }) {
    loading.value = true
    try {
      const response = await http.get('/api/rules/list', { params })
      const data: RuleListResponse = response.data.data
      rules.value = data.rules
      totalRules.value = data.total
      currentPage.value = data.page
      pageSize.value = data.page_size
      totalPages.value = data.total_pages
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '获取规则列表失败'))
    } finally {
      loading.value = false
    }
  }

  async function fetchGroups() {
    try {
      const response = await http.get('/api/rules/groups/list')
      const data: RuleGroupListResponse = response.data.data
      groups.value = data.groups
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '获取规则分组失败'))
    }
  }

  async function fetchStats() {
    try {
      const response = await http.get('/api/rules/stats')
      stats.value = response.data.data
    } catch (e: unknown) {
      console.error('获取规则统计失败:', e)
    }
  }

  async function createRule(rule: RuleCreateRequest) {
    try {
      const response = await http.post('/api/rules/create', rule)
      ElMessage.success(response.data.message || '规则创建成功')
      await fetchRules()
      await fetchStats()
      return response.data.data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '创建规则失败'))
      throw e
    }
  }

  async function updateRule(ruleId: number, rule: RuleUpdateRequest) {
    try {
      const response = await http.put(`/api/rules/update/${ruleId}`, rule)
      ElMessage.success(response.data.message || '规则更新成功')
      await fetchRules()
      await fetchStats()
      return response.data.data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '更新规则失败'))
      throw e
    }
  }

  async function deleteRule(ruleId: number) {
    try {
      const response = await http.delete(`/api/rules/delete/${ruleId}`)
      ElMessage.success(response.data.message || '规则删除成功')
      await fetchRules()
      await fetchStats()
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '删除规则失败'))
      throw e
    }
  }

  async function getRule(ruleId: number) {
    try {
      const response = await http.get(`/api/rules/detail/${ruleId}`)
      currentRule.value = response.data.data
      return response.data.data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '获取规则详情失败'))
      throw e
    }
  }

  async function createGroup(group: RuleGroupCreateRequest) {
    try {
      const response = await http.post('/api/rules/groups/create', group)
      ElMessage.success(response.data.message || '分组创建成功')
      await fetchGroups()
      await fetchStats()
      return response.data.data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '创建分组失败'))
      throw e
    }
  }

  async function updateGroup(groupId: number, group: RuleGroupUpdateRequest) {
    try {
      const response = await http.put(`/api/rules/groups/update/${groupId}`, group)
      ElMessage.success(response.data.message || '分组更新成功')
      await fetchGroups()
      return response.data.data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '更新分组失败'))
      throw e
    }
  }

  async function deleteGroup(groupId: number) {
    try {
      const response = await http.delete(`/api/rules/groups/delete/${groupId}`)
      ElMessage.success(response.data.message || '分组删除成功')
      await fetchGroups()
      await fetchStats()
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '删除分组失败'))
      throw e
    }
  }

  async function exportRules() {
    try {
      const response = await http.get('/api/rules/export', {
        responseType: 'blob',
      })
      const url = window.URL.createObjectURL(new Blob([response.data]))
      const link = document.createElement('a')
      link.href = url
      const disposition = response.headers['content-disposition']
      let filename = 'rules_export.json'
      if (disposition) {
        const match = disposition.match(/filename="?([^"]+)"?/)
        if (match) filename = match[1]
      }
      link.setAttribute('download', filename)
      document.body.appendChild(link)
      link.click()
      link.remove()
      window.URL.revokeObjectURL(url)
      ElMessage.success('规则导出成功')
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '规则导出失败'))
      throw e
    }
  }

  async function importRules(file: File) {
    try {
      const formData = new FormData()
      formData.append('file', file)
      const response = await http.post('/api/rules/import', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
      })
      const data: RuleImportResponse = response.data.data
      ElMessage.success(
        response.data.message || `导入成功: ${data.imported_rules} 条规则, ${data.imported_groups} 个分组`
      )
      await fetchRules()
      await fetchGroups()
      await fetchStats()
      return data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '规则导入失败'))
      throw e
    }
  }

  async function backupDatabase() {
    try {
      const response = await http.post('/api/rules/backup')
      ElMessage.success(response.data.message || '数据库备份成功')
      return response.data.data
    } catch (e: unknown) {
      ElMessage.error(extractErrorMessage(e, '数据库备份失败'))
      throw e
    }
  }

  function openCreateDialog() {
    editingRule.value = null
    showDialog.value = true
  }

  function openEditDialog(rule: ProcessRule) {
    editingRule.value = { ...rule }
    showDialog.value = true
  }

  function openCreateGroupDialog() {
    editingGroup.value = null
    showGroupDialog.value = true
  }

  function openEditGroupDialog(group: RuleGroup) {
    editingGroup.value = { ...group }
    showGroupDialog.value = true
  }

  function refreshAll() {
    fetchRules()
    fetchGroups()
    fetchStats()
  }

  return {
    rules,
    groups,
    currentRule,
    stats,
    loading,
    showDialog,
    editingRule,
    showGroupDialog,
    editingGroup,
    totalRules,
    currentPage,
    pageSize,
    totalPages,
    activeRules,
    draftRules,
    fetchRules,
    fetchGroups,
    fetchStats,
    createRule,
    updateRule,
    deleteRule,
    getRule,
    createGroup,
    updateGroup,
    deleteGroup,
    exportRules,
    importRules,
    backupDatabase,
    openCreateDialog,
    openEditDialog,
    openCreateGroupDialog,
    openEditGroupDialog,
    refreshAll,
  }
})
