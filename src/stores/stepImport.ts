import { ref, computed } from 'vue'
import { defineStore } from 'pinia'
import axios from 'axios'
import type {
  StepImportResult,
  ImportHistoryEntry,
  ImportState,
  StlFileInfo,
} from '@/types'

export const useStepImportStore = defineStore('stepImport', () => {
  const importState = ref<ImportState>('idle')
  const uploadProgress = ref(0)
  const currentResult = ref<StepImportResult | null>(null)
  const errorMessage = ref('')
  const importHistory = ref<ImportHistoryEntry[]>([])
  const historyLoading = ref(false)
  const activeStlUrl = ref('')
  const activeStlFiles = ref<StlFileInfo[]>([])
  const selectedEntityIndex = ref(0)
  const showDialog = ref(false)

  const isIdle = computed(() => importState.value === 'idle')
  const isUploading = computed(() => importState.value === 'uploading')
  const isProcessing = computed(() => importState.value === 'processing')
  const isSuccess = computed(() => importState.value === 'success')
  const isError = computed(() => importState.value === 'error')
  const isActive = computed(() => importState.value === 'uploading' || importState.value === 'processing')

  const hasStlFiles = computed(() => activeStlFiles.value.length > 0)
  const modelInfo = computed(() => currentResult.value?.model_info ?? null)
  const entities = computed(() => currentResult.value?.entities ?? [])
  const warnings = computed(() => currentResult.value?.warnings ?? [])

  function reset() {
    importState.value = 'idle'
    uploadProgress.value = 0
    currentResult.value = null
    errorMessage.value = ''
    activeStlUrl.value = ''
    activeStlFiles.value = []
    selectedEntityIndex.value = 0
  }

  async function importStepFile(
    file: File,
    precision: string = 'medium',
    outputFormat: string = 'stl',
  ): Promise<boolean> {
    reset()
    importState.value = 'uploading'
    uploadProgress.value = 0

    const formData = new FormData()
    formData.append('file', file)
    formData.append('precision', precision)
    formData.append('output_format', outputFormat)
    formData.append('use_cache', 'true')

    try {
      const response = await axios.post<{ code: number; data: StepImportResult; message: string }>(
        '/api/import/step',
        formData,
        {
          headers: { 'Content-Type': 'multipart/form-data' },
          onUploadProgress: (progressEvent) => {
            if (progressEvent.total) {
              uploadProgress.value = Math.round((progressEvent.loaded * 100) / progressEvent.total)
            }
          },
          timeout: 120000,
        },
      )

      if (response.data.code === 0) {
        currentResult.value = response.data.data
        activeStlFiles.value = response.data.data.stl_files || []
        selectedEntityIndex.value = 0
        if (activeStlFiles.value.length > 0) {
          activeStlUrl.value = activeStlFiles.value[0].stl_url
        }
        importState.value = 'success'
        await fetchImportHistory()
        return true
      } else {
        errorMessage.value = response.data.message || '导入失败'
        importState.value = 'error'
        return false
      }
    } catch (err: any) {
      importState.value = 'error'
      if (err.response?.status === 413) {
        errorMessage.value = '文件过大，请选择小于50MB的STEP文件'
      } else if (err.code === 'ECONNABORTED') {
        errorMessage.value = '请求超时，文件可能过大或网络不稳定'
      } else if (err.response?.data?.message) {
        errorMessage.value = err.response.data.message
      } else {
        errorMessage.value = err.message || '网络错误，导入失败'
      }
      return false
    }
  }

  function selectEntity(index: number) {
    if (index >= 0 && index < activeStlFiles.value.length) {
      selectedEntityIndex.value = index
      activeStlUrl.value = activeStlFiles.value[index].stl_url
    }
  }

  async function fetchImportHistory() {
    historyLoading.value = true
    try {
      const response = await axios.get<{ code: number; data: { history: ImportHistoryEntry[]; total: number } }>(
        '/api/import/step/history',
        { params: { limit: 20 } },
      )
      if (response.data.code === 0) {
        importHistory.value = response.data.data.history || []
      }
    } catch {
      importHistory.value = []
    } finally {
      historyLoading.value = false
    }
  }

  async function deleteHistoryFile(fileName: string) {
    try {
      await axios.delete(`/api/import/step/history/${encodeURIComponent(fileName)}`)
      await fetchImportHistory()
    } catch {
      // silently fail
    }
  }

  async function clearCache() {
    try {
      await axios.delete('/api/import/step/cache')
    } catch {
      // silently fail
    }
  }

  return {
    importState,
    uploadProgress,
    currentResult,
    errorMessage,
    importHistory,
    historyLoading,
    activeStlUrl,
    activeStlFiles,
    selectedEntityIndex,
    showDialog,
    isIdle,
    isUploading,
    isProcessing,
    isSuccess,
    isError,
    isActive,
    hasStlFiles,
    modelInfo,
    entities,
    warnings,
    reset,
    importStepFile,
    selectEntity,
    fetchImportHistory,
    deleteHistoryFile,
    clearCache,
  }
})
