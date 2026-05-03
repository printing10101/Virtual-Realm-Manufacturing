import axios from 'axios'
import { DEFAULT_URLS, MODEL_CONSTANTS } from '@/constants'

export interface OllamaStatus {
  available: boolean
  version?: string
  base_url?: string
}

export interface OllamaModel {
  name: string
  size: string
}

export interface RecommendedModel {
  name: string
  size: string
  category: string
}

export interface GpuInfo {
  ollama_version: string
  gpu_count: number
  gpus: Array<{
    index: number
    name: string
    memory_total: string
    memory_free: string
  }>
}

export interface ModelPullProgress {
  status: string
  progress: number | null
}

async function getOllamaUrl(): Promise<string> {
  try {
    const { getSettings } = await import('@/services/settings')
    const settings = await getSettings()
    return settings.ollama_url
  } catch {
    return DEFAULT_URLS.OLLAMA
  }
}

export async function getOllamaStatus(): Promise<OllamaStatus> {
  const baseUrl = await getOllamaUrl()
  try {
    const response = await axios.get(`${baseUrl}/api/version`, { timeout: 5000 })
    return {
      available: true,
      version: response.data.version,
      base_url: baseUrl,
    }
  } catch {
    return {
      available: false,
      base_url: baseUrl,
    }
  }
}

export async function listModels(): Promise<{ models: OllamaModel[] }> {
  const baseUrl = await getOllamaUrl()
  try {
    const response = await axios.post(`${baseUrl}/api/tags`, {}, { timeout: 10000 })
    const models = (response.data.models || [])
      .filter((m: { name: string }) => m.name && !m.name.includes(':latest'))
      .map((m: { name: string; size: number }) => ({
        name: m.name,
        size: formatSize(m.size || 0),
      }))
    return { models }
  } catch (error: unknown) {
    throw new Error(`获取模型列表失败: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function pullModel(
  modelName: string,
  onProgress?: (progress: ModelPullProgress) => void
): Promise<void> {
  const baseUrl = await getOllamaUrl()

  let response: Response
  try {
    response = await fetch(`${baseUrl}/api/pull`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name: modelName, stream: true }),
      signal: AbortSignal.timeout(600000),
    })
  } catch (error) {
    if (error instanceof DOMException && error.name === 'TimeoutError') {
      throw new Error('下载模型超时，请检查网络连接')
    }
    throw new Error(`下载模型网络请求失败: ${error instanceof Error ? error.message : String(error)}`)
  }

  if (!response.ok) {
    let errorText: string
    try {
      errorText = await response.text()
    } catch {
      errorText = '无法读取错误响应'
    }
    throw new Error(`下载模型失败: HTTP ${response.status} - ${errorText}`)
  }

  if (!response.body) {
    throw new Error('服务器未返回响应体')
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''

  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        if (!line.trim()) continue
        try {
          const data = JSON.parse(line)
          if (data.status) {
            const progress = data.total ? data.completed / data.total : null
            onProgress?.({
              status: data.status,
              progress,
            })
          }
        } catch {}
      }
    }
  } catch (error) {
    throw new Error(`下载模型中断: ${error instanceof Error ? error.message : String(error)}`)
  } finally {
    reader?.cancel()
  }
}

export async function deleteModel(modelName: string): Promise<void> {
  const baseUrl = await getOllamaUrl()
  try {
    await axios.delete(`${baseUrl}/api/delete`, {
      data: { name: modelName },
      timeout: 10000,
    })
  } catch (error: unknown) {
    throw new Error(`删除模型失败: ${error instanceof Error ? error.message : String(error)}`)
  }
}

export async function getRecommendedModels(): Promise<{ models: RecommendedModel[] }> {
  const baseUrl = await getOllamaUrl()
  try {
    const response = await axios.get(`${baseUrl}/api/ps`, { timeout: 5000 })
    const runningModels = response.data.models || []
    return {
      models: MODEL_CONSTANTS.RECOMMENDED_MODELS.filter(
        m => !runningModels.some((r: { name: string }) => r.name === m.name)
      ),
    }
  } catch {
    return {
      models: [...MODEL_CONSTANTS.RECOMMENDED_MODELS],
    }
  }
}

export async function getGpuInfo(): Promise<GpuInfo> {
  const baseUrl = await getOllamaUrl()
  try {
    const [versionRes, psRes] = await Promise.all([
      axios.get(`${baseUrl}/api/version`, { timeout: 5000 }),
      axios.get(`${baseUrl}/api/ps`, { timeout: 5000 }),
    ])
    
    return {
      ollama_version: versionRes.data.version || 'unknown',
      gpu_count: psRes.data.gpu_info?.length || 0,
      gpus: (psRes.data.gpu_info || []).map((gpu: { name?: string; total_memory?: number; free_memory?: number }, index: number) => ({
        index,
        name: gpu.name || 'Unknown GPU',
        memory_total: formatMemory(gpu.total_memory || 0),
        memory_free: formatMemory(gpu.free_memory || 0),
      })),
    }
  } catch (error: unknown) {
    throw new Error(`获取GPU信息失败: ${error instanceof Error ? error.message : String(error)}`)
  }
}

function formatSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB', 'TB']
  const i = Math.floor(Math.log(bytes) / Math.log(1024))
  return `${(bytes / Math.pow(1024, i)).toFixed(1)} ${units[i]}`
}

function formatMemory(megabytes: number): string {
  if (!megabytes) return '0 MB'
  if (megabytes >= 1024) return `${(megabytes / 1024).toFixed(1)} GB`
  return `${megabytes} MB`
}
