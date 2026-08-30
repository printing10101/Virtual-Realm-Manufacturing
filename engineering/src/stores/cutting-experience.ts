/**
 * Cutting Experience Store (P3-2 数据飞轮数据采集)
 */
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import type { Ref } from 'vue'
import { extractErrorMessage } from '@/utils/error-handler'
import {
  getExperienceStats,
  queryExperiences as apiQueryExperiences,
  captureExperience as apiCaptureExperience,
  batchCaptureExperiences,
  deleteExperience as apiDeleteExperience,
  type CuttingExperiencePayload,
  type ExperienceStats,
  type MachiningType,
  type MachiningResult,
} from '@/api/cuttingExperience'

export interface LocalCuttingExperienceRecord {
  id: string
  machine_id: string
  tool_id: string
  program_name?: string
  material: string
  machining_type: string
  result: string
  anomalies?: unknown[]
  [key: string]: unknown
}

export const useCuttingExperienceStore = defineStore('cutting-experience', () => {
  const loading = ref(false)
  const error: Ref<string | null> = ref(null)
  const stats: Ref<ExperienceStats | null> = ref(null)
  const records = ref<LocalCuttingExperienceRecord[]>([])
  const total = ref(0)
  const filters = ref({
    machine_id: '',
    tool_id: '',
    material: '',
    machining_type: '',
    result: '',
    has_anomaly: null as null | boolean,
    start_time: '',
    end_time: '',
  })

  const hasError = computed(() => error.value !== null)
  
  const okRate = computed(() => {
    if (stats.value === null || stats.value === undefined) return null
    const rate = stats.value.ok_rate ?? 0
    return Array.isArray(rate) ? 0 : rate
  })

  const anomalyRate = computed(() => {
    if (stats.value === null || stats.value === undefined) return null
    const rate = stats.value.anomaly_rate ?? 0
    return Array.isArray(rate) ? 0 : rate
  })

  const hasStats = computed(() => stats.value !== null && stats.value !== undefined)

  async function fetchStats() {
    loading.value = true
    error.value = null
    try {
      const localFilters = filters.value
      const params: { machine_id?: string; tool_id?: string } = {}
      if (localFilters.machine_id) params.machine_id = localFilters.machine_id
      if (localFilters.tool_id) params.tool_id = localFilters.tool_id
      
      const data = await getExperienceStats(params)
      stats.value = data
    } catch (e) {
      error.value = extractErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function queryExperiences(page = 1) {
    loading.value = true
    error.value = null
    try {
      const localFilters = filters.value
      const params: {
        machine_id?: string
        tool_id?: string
        material?: string
        machining_type?: MachiningType
        result?: MachiningResult
        has_anomaly?: boolean
        start_time?: string
        end_time?: string
        limit?: number
        offset?: number
      } = {}
      
      if (localFilters.machine_id) params.machine_id = localFilters.machine_id
      if (localFilters.tool_id) params.tool_id = localFilters.tool_id
      if (localFilters.material) params.material = localFilters.material
      if (localFilters.machining_type) params.machining_type = localFilters.machining_type as MachiningType
      if (localFilters.result) params.result = localFilters.result as MachiningResult
      if (localFilters.has_anomaly !== null) params.has_anomaly = localFilters.has_anomaly
      if (localFilters.start_time) params.start_time = localFilters.start_time
      if (localFilters.end_time) params.end_time = localFilters.end_time
      if (localFilters.machine_id) params.machine_id = localFilters.machine_id
      if (localFilters.tool_id) params.tool_id = localFilters.tool_id
      
      params.limit = 20
      params.offset = (page - 1) * 20
      
      const apiData = await apiQueryExperiences(params)
      // Convert API records to local record format
      records.value = apiData.records.map((record) => ({
        id: record.id,
        machine_id: record.machine_id,
        tool_id: record.tool_id,
        program_name: record.program_number ?? undefined,
        material: record.material ?? '',
        machining_type: record.machining_type ?? '',
        result: record.results?.result ?? '',
        anomalies: record.anomalies,
      }))
      total.value = apiData.total
    } catch (e) {
      error.value = extractErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function captureExperience(payload: CuttingExperiencePayload) {
    loading.value = true
    error.value = null
    try {
      await apiCaptureExperience(payload)
      await fetchStats()
      await queryExperiences(1)
    } catch (e) {
      error.value = extractErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function batchExperiences(payloads: CuttingExperiencePayload[]) {
    loading.value = true
    error.value = null
    try {
      await batchCaptureExperiences(payloads)
      await fetchStats()
      await queryExperiences(1)
    } catch (e) {
      error.value = extractErrorMessage(e)
    } finally {
      loading.value = false
    }
  }

  async function deleteExperience(id: string) {
    error.value = null
    try {
      await apiDeleteExperience(id)
      await fetchStats()
      await queryExperiences(1)
    } catch (e) {
      error.value = extractErrorMessage(e)
    }
  }

  function clearError() {
    error.value = null
  }

  function refreshAll() {
    return Promise.all([fetchStats(), queryExperiences(1)])
  }

  return {
    loading,
    error,
    stats,
    okRate,
    anomalyRate,
    records,
    total,
    filters,
    hasError,
    hasStats,
    fetchStats,
    queryExperiences,
    captureExperience,
    batchExperiences,
    deleteExperience,
    clearError,
    refreshAll,
  }
})
