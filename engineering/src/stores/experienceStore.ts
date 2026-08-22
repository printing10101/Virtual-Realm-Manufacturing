// 切削体验（数据飞轮）Store（P2-3 前端状态管理）
//
// 职责：
// - 封装 cuttingExperience API（查询/采集/统计）
// - 维护当前查询条件与结果列表
// - 维护聚合统计（仪表盘数据）
// - 提供实时采集入口（手工录入 → captureExperience）

import { defineStore } from 'pinia'
import { ref } from 'vue'
import {
  captureExperience,
  getExperienceStats,
  queryExperiences,
  type CuttingExperiencePayload,
  type CuttingExperienceRecord,
  type ExperienceQueryParams,
  type ExperienceStats,
} from '@/api/cuttingExperience'

export const useExperienceStore = defineStore('experience', () => {
  // ------------------------------------------------------------------
  // 状态
  // ------------------------------------------------------------------

  /** 查询结果列表 */
  const records = ref<CuttingExperienceRecord[]>([])
  /** 总记录数 */
  const total = ref(0)
  /** 当前查询条件 */
  const query = ref<ExperienceQueryParams>({ limit: 50, offset: 0 })
  /** 聚合统计 */
  const stats = ref<ExperienceStats | null>(null)
  /** 加载状态 */
  const loading = ref(false)
  /** 采集状态 */
  const capturing = ref(false)
  /** 最近错误消息 */
  const errorMessage = ref('')

  // ------------------------------------------------------------------
  // 动作
  // ------------------------------------------------------------------

  /** 刷新列表（用当前查询条件） */
  async function refreshList(): Promise<void> {
    loading.value = true
    errorMessage.value = ''
    try {
      const result = await queryExperiences(query.value)
      records.value = result.records
      total.value = result.total
    } catch (e) {
      errorMessage.value = e instanceof Error ? e.message : String(e)
    } finally {
      loading.value = false
    }
  }

  /** 按条件查询（更新条件并刷新） */
  async function fetchExperiences(params: ExperienceQueryParams): Promise<void> {
    query.value = { ...query.value, ...params }
    await refreshList()
  }

  /** 加载聚合统计 */
  async function fetchStats(machineId?: string, toolId?: string): Promise<void> {
    try {
      stats.value = await getExperienceStats({
        machine_id: machineId,
        tool_id: toolId,
      })
    } catch (e) {
      errorMessage.value = e instanceof Error ? e.message : String(e)
    }
  }

  /** 手工录入一条切削实测记录 */
  async function submitCapture(
    payload: CuttingExperiencePayload,
  ): Promise<CuttingExperienceRecord | null> {
    capturing.value = true
    errorMessage.value = ''
    try {
      const created = await captureExperience(payload)
      // 刷新列表与统计，保持面板一致
      await refreshList()
      await fetchStats()
      return created
    } catch (e) {
      errorMessage.value = e instanceof Error ? e.message : String(e)
      return null
    } finally {
      capturing.value = false
    }
  }

  /** 重置错误 */
  function clearError(): void {
    errorMessage.value = ''
  }

  return {
    // state
    records,
    total,
    query,
    stats,
    loading,
    capturing,
    errorMessage,
    // actions
    refreshList,
    fetchExperiences,
    fetchStats,
    submitCapture,
    clearError,
  }
})
