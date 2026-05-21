/**
 * 工程管理 Pinia Store
 *
 * 管理加工工程的完整生命周期：新建、打开、保存、另存为。
 * 负责前端状态与后端 project.json 之间的双向同步。
 */
import { defineStore } from 'pinia'
import axios from 'axios'
import { extractErrorMessage } from '@/utils/errorUtils'
import type {
  ProjectManifest,
  ProjectMetadata,
  ProjectSummary,
  NewProjectRequest,
  SaveProjectRequest,
} from '@/types'

const API_BASE = '/api/projects'

function defaultManifest(name = '未命名工程'): ProjectManifest {
  return {
    version: '1.0',
    metadata: {
      name,
      created_at: new Date().toISOString(),
      modified_at: new Date().toISOString(),
      author: '',
      description: '',
    },
    resources: [],
    data: {
      stock_definition: {},
      tool_selection: [],
      process_steps: [],
      toolpath_config: {},
      postprocessor_config: {},
      simulation_config: {},
    },
    extensions: {},
  }
}

function emptySummary(): ProjectSummary {
  return { path: '', name: '', created_at: '', modified_at: '', resource_count: 0, file_size: 0 }
}

/**
 * 工程管理 Store
 * 管理加工工程的完整生命周期：新建、打开、保存、另存为。
 * 负责前端状态与后端 project.json 之间的双向同步。
 */
export const useProjectStore = defineStore('project', () => {
  /** 当前项目ID */
  const projectId = ref('')
  /** 工程清单 */
  const manifest = ref<ProjectManifest>(defaultManifest())
  /** 当前文件路径 */
  const currentFilePath = ref('')
  /** 是否已修改 */
  const isModified = ref(false)
  /** 加载状态 */
  const loading = ref(false)
  /** 错误信息 */
  const error = ref<string | null>(null)
  /** 项目列表 */
  const projectList = ref<ProjectSummary[]>([])
  /** 列表加载状态 */
  const listLoading = ref(false)

  const projectName = computed(() => manifest.value.metadata.name)
  const resourceCount = computed(() => manifest.value.resources.length)

  function markModified() { isModified.value = true }

  function _updateManifestMeta(meta: Partial<ProjectMetadata>) {
    manifest.value.metadata = { ...manifest.value.metadata, ...meta }
    manifest.value.metadata.modified_at = new Date().toISOString()
    isModified.value = true
  }

  async function createProject(request: NewProjectRequest): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const resp = await axios.post(`${API_BASE}/new`, request)
      if (resp.data.code === 0) {
        projectId.value = resp.data.data.project_id
        manifest.value = resp.data.data.manifest as ProjectManifest
        currentFilePath.value = ''
        isModified.value = true
        return true
      }
      error.value = resp.data.message || '创建工程失败'
      return false
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '创建工程失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function openProject(filePath?: string, uploadData?: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const resp = await axios.post(`${API_BASE}/open`, {
        file_path: filePath || undefined,
        upload_data: uploadData || undefined,
      })
      if (resp.data.code === 0) {
        manifest.value = resp.data.data.manifest as ProjectManifest
        currentFilePath.value = resp.data.data.file_path || filePath || ''
        isModified.value = false
        return true
      }
      error.value = resp.data.message || '打开工程失败'
      return false
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '打开工程失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function saveProject(outputName?: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const payload: SaveProjectRequest = {
        manifest: JSON.parse(JSON.stringify(manifest.value)),
        project_id: projectId.value,
        output_name: outputName || '',
      }
      const resp = await axios.post(`${API_BASE}/save`, payload)
      if (resp.data.code === 0) {
        currentFilePath.value = resp.data.data.file_path
        isModified.value = false
        return true
      }
      error.value = resp.data.message || '保存工程失败'
      return false
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '保存工程失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function saveAsProject(outputName: string): Promise<boolean> {
    loading.value = true
    error.value = null
    try {
      const payload: SaveProjectRequest = {
        manifest: JSON.parse(JSON.stringify(manifest.value)),
        project_id: projectId.value,
        output_name: outputName,
      }
      const resp = await axios.post(`${API_BASE}/save-as`, payload)
      if (resp.data.code === 0) {
        currentFilePath.value = resp.data.data.file_path
        manifest.value.metadata.name = outputName.replace('.vrm', '')
        isModified.value = false
        return true
      }
      error.value = resp.data.message || '另存为失败'
      return false
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '另存为失败')
      return false
    } finally {
      loading.value = false
    }
  }

  async function fetchProjectList(): Promise<void> {
    listLoading.value = true
    try {
      const resp = await axios.get(`${API_BASE}/list`)
      if (resp.data.code === 0) {
        projectList.value = resp.data.data.items as ProjectSummary[]
      }
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '获取工程列表失败')
    } finally {
      listLoading.value = false
    }
  }

  async function deleteProject(projectName: string): Promise<boolean> {
    try {
      const resp = await axios.delete(`${API_BASE}/${projectName}`)
      return resp.data.code === 0
    } catch {
      return false
    }
  }

  function downloadProject(projectName: string): void {
    const url = `${API_BASE}/download/${projectName}`
    const a = document.createElement('a')
    a.href = url
    a.download = projectName
    a.click()
  }

  function updateStockDefinition(data: Record<string, unknown>) {
    manifest.value.data.stock_definition = data
    markModified()
  }

  function updateToolSelection(tools: Array<Record<string, unknown>>) {
    manifest.value.data.tool_selection = tools
    markModified()
  }

  function updateProcessSteps(steps: Array<Record<string, unknown>>) {
    manifest.value.data.process_steps = steps
    markModified()
  }

  function updateToolpathConfig(config: Record<string, unknown>) {
    manifest.value.data.toolpath_config = config
    markModified()
  }

  function updatePostProcessorConfig(config: Record<string, unknown>) {
    manifest.value.data.postprocessor_config = config
    markModified()
  }

  function updateSimulationConfig(config: Record<string, unknown>) {
    manifest.value.data.simulation_config = config
    markModified()
  }

  function updateExtensions(ext: Record<string, unknown>) {
    manifest.value.extensions = ext
    markModified()
  }

  function resetProject() {
    projectId.value = ''
    manifest.value = defaultManifest()
    currentFilePath.value = ''
    isModified.value = false
    error.value = null
  }

  return {
    projectId,
    manifest,
    currentFilePath,
    isModified,
    loading,
    error,
    projectList,
    listLoading,
    projectName,
    resourceCount,
    markModified,
    createProject,
    openProject,
    saveProject,
    saveAsProject,
    fetchProjectList,
    deleteProject,
    downloadProject,
    updateStockDefinition,
    updateToolSelection,
    updateProcessSteps,
    updateToolpathConfig,
    updatePostProcessorConfig,
    updateSimulationConfig,
    updateExtensions,
    resetProject,
  }
})
