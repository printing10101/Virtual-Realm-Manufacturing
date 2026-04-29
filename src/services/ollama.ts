const API_BASE = 'http://localhost:8765/api/ollama'

export interface OllamaStatus {
  available: boolean
  version: string | null
  base_url: string
}

export interface OllamaModel {
  name: string
  size: string
  digest: string
  modified_at: string
}

export interface RecommendedModel {
  name: string
  size: string
  category: string
}

export interface PullProgress {
  status: string
  progress: number | null
  completed?: number
  total?: number
}

export interface GpuInfo {
  ollama_version: string
  gpus: Array<{
    index: number
    name: string
    memory_total: string
    memory_free: string
  }>
  gpu_count: number
}

interface ApiResponse<T> {
  code: number
  message: string
  data: T
}

export async function getOllamaStatus(): Promise<OllamaStatus> {
  const response = await fetch(`${API_BASE}/status`)
  const result: ApiResponse<OllamaStatus> = await response.json()
  if (result.code === 0) {
    return result.data
  }
  throw new Error(result.message)
}

export async function listModels(): Promise<{models: OllamaModel[]; total: number}> {
  const response = await fetch(`${API_BASE}/models`)
  const result: ApiResponse<{models: OllamaModel[]; total: number}> = await response.json()
  if (result.code === 0) {
    return result.data
  }
  throw new Error(result.message)
}

export async function getRecommendedModels(): Promise<{models: RecommendedModel[]; total: number}> {
  const response = await fetch(`${API_BASE}/models/recommended`)
  const result: ApiResponse<{models: RecommendedModel[]; total: number}> = await response.json()
  if (result.code === 0) {
    return result.data
  }
  throw new Error(result.message)
}

export async function pullModel(
  modelName: string,
  onProgress: (progress: PullProgress) => void
): Promise<void> {
  const response = await fetch(`${API_BASE}/models/pull/${encodeURIComponent(modelName)}`, {
    method: 'POST',
  })

  if (!response.ok) {
    throw new Error(`Failed to pull model: ${response.statusText}`)
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('No response body')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6)
        try {
          const progress = JSON.parse(data) as PullProgress
          onProgress(progress)
        } catch {
        }
      }
    }
  }
}

export async function deleteModel(modelName: string): Promise<void> {
  const response = await fetch(`${API_BASE}/models/${encodeURIComponent(modelName)}`, {
    method: 'DELETE',
  })
  const result: ApiResponse<null> = await response.json()
  if (result.code === 0) {
    return
  }
  throw new Error(result.message)
}

export async function getModelInfo(modelName: string): Promise<Record<string, unknown>> {
  const response = await fetch(`${API_BASE}/models/${encodeURIComponent(modelName)}/info`)
  const result: ApiResponse<Record<string, unknown>> = await response.json()
  if (result.code === 0) {
    return result.data
  }
  throw new Error(result.message)
}

export async function getGpuInfo(): Promise<GpuInfo> {
  const response = await fetch(`${API_BASE}/gpu-info`)
  const result: ApiResponse<GpuInfo> = await response.json()
  if (result.code === 0) {
    return result.data
  }
  throw new Error(result.message)
}
