import { invoke } from '@tauri-apps/api/core'
import { DEFAULT_URLS, API_ENDPOINTS, POLLING_CONFIG } from '@/constants'
import { getRequestMerger, type ProxyRequest, type ProxyResponse } from '@/services/requestMerger'
import axios from 'axios'

export interface ApiResult<T> {
  code: number
  message: string
  data: T
}

export interface TaskStatus {
  status: string
  progress: number
  error_message?: string
}

export interface PollerCallbacks {
  onProgress: (data: TaskStatus) => void
  onComplete: (data: TaskStatus) => void
  onFailed: (data: TaskStatus) => void
  onError: (error: Error) => void
  intervalMs?: number
  timeoutMs?: number
}

export class ApiError extends Error {
  public code: number
  public originalMessage: string

  constructor(code: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.originalMessage = message
  }
}

const DEFAULT_TIMEOUT = 30000
let isTauriAvailable: boolean | null = null

export async function checkTauriAvailability(): Promise<boolean> {
  if (isTauriAvailable !== null) return isTauriAvailable

  try {
    await invoke('proxy_health_check', { url: 'http://localhost:1' })
    isTauriAvailable = true
  } catch {
    isTauriAvailable = false
  }

  return isTauriAvailable
}

export function resetTauriAvailability(): void {
  isTauriAvailable = null
}

export function buildApiUrl(endpoint: string, baseUrl: string = DEFAULT_URLS.PYTHON_BACKEND): string {
  return `${baseUrl.replace(/\/$/, '')}${endpoint}`
}

async function invokeProxyWithRetry(
  request: ProxyRequest,
  maxRetries = 2,
  baseDelay = 100
): Promise<ProxyResponse> {
  let lastError: Error | null = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      const merger = getRequestMerger()
      return await merger.enqueue(request)
    } catch (error) {
      lastError = error instanceof Error ? error : new Error(String(error))

      if (attempt < maxRetries) {
        const delay = baseDelay * Math.pow(2, attempt)
        await new Promise((resolve) => setTimeout(resolve, delay))
      }
    }
  }

  throw lastError || new Error('Proxy request failed')
}

async function directHttpRequest(
  url: string,
  method: string,
  body?: Record<string, any>,
  timeout = DEFAULT_TIMEOUT
): Promise<ProxyResponse> {
  const startTime = Date.now()

  try {
    const response = await axios({
      url,
      method: method.toLowerCase(),
      data: body,
      timeout,
      validateStatus: () => true,
    })

    return {
      status: response.status,
      headers: response.headers as Record<string, string>,
      body: response.data,
      duration_ms: Date.now() - startTime,
    }
  } catch (error: any) {
    if (error.response) {
      return {
        status: error.response.status,
        headers: error.response.headers || {},
        body: error.response.data || { error: error.message },
        duration_ms: Date.now() - startTime,
      }
    }
    throw new ApiError(-1, error.message || 'Network error')
  }
}

export async function apiRequest<T>(
  url: string,
  options?: {
    method?: string
    body?: Record<string, any>
    timeout?: number
    headers?: Record<string, string>
    useTauri?: boolean
    priority?: number
  }
): Promise<T> {
  const method = options?.method || 'GET'
  const timeout = options?.timeout || DEFAULT_TIMEOUT
  const shouldUseTauri = options?.useTauri ?? true

  if (shouldUseTauri) {
    const tauriAvailable = await checkTauriAvailability()

    if (tauriAvailable) {
      try {
        const proxyRequest: ProxyRequest = {
          method,
          url,
          headers: options?.headers,
          body: options?.body,
          timeout_ms: timeout,
        }

        const response = await invokeProxyWithRetry(
          proxyRequest,
          2,
          100
        )

        if (response.status >= 400) {
          throw new ApiError(response.status, `HTTP错误: ${response.status}`)
        }

        const result = response.body as ApiResult<T>

        if (result.code !== 0) {
          throw new ApiError(result.code, result.message)
        }

        return result.data
      } catch (error) {
        isTauriAvailable = false

        const fallbackUrl = url
        const response = await directHttpRequest(
          fallbackUrl,
          method,
          options?.body,
          timeout
        )

        if (response.status >= 400) {
          throw new ApiError(response.status, `HTTP错误: ${response.status}`)
        }

        const result = response.body as ApiResult<T>

        if (result.code !== 0) {
          throw new ApiError(result.code, result.message)
        }

        return result.data
      }
    }
  }

  const response = await directHttpRequest(
    url,
    method,
    options?.body,
    timeout
  )

  if (response.status >= 400) {
    throw new ApiError(response.status, `HTTP错误: ${response.status}`)
  }

  const result = response.body as ApiResult<T>

  if (result.code !== 0) {
    throw new ApiError(result.code, result.message)
  }

  return result.data
}

export async function apiStreamRequest(
  url: string,
  onChunk: (data: string) => void,
  options?: RequestInit
): Promise<void> {
  const response = await fetch(url, {
    ...options,
    headers: {
      Accept: 'text/event-stream',
      ...options?.headers,
    },
  })

  if (!response.ok) {
    throw new ApiError(
      response.status,
      `HTTP错误: ${response.status} ${response.statusText}`
    )
  }

  const reader = response.body?.getReader()
  if (!reader) {
    throw new ApiError(-1, '服务器响应格式错误')
  }

  const decoder = new TextDecoder()
  let buffer = ''

  try {
    // eslint-disable-next-line no-constant-condition
    while (true) {
      const { done, value } = await reader.read()
      if (done) break

      buffer += decoder.decode(value, { stream: true })
      const lines = buffer.split('\n')
      buffer = lines.pop() || ''

      for (const line of lines) {
        onChunk(line)
      }
    }
  } catch (error) {
    if (error instanceof ApiError) {
      throw error
    }
    throw new ApiError(-1, '流式请求中断')
  }
}

export function createTaskPoller(
  taskId: string,
  callbacks: PollerCallbacks,
  baseUrl?: string
): () => void {
  const {
    onProgress,
    onComplete,
    onFailed,
    onError,
    intervalMs = POLLING_CONFIG.INTERVAL_MS,
    timeoutMs = POLLING_CONFIG.TIMEOUT_MS,
  } = callbacks

  let isStopped = false

  const timeoutId = setTimeout(() => {
    if (!isStopped) {
      isStopped = true
      onError(new Error('任务超时'))
      clearInterval(intervalId)
    }
  }, timeoutMs)

  const intervalId = setInterval(async () => {
    if (isStopped) return

    try {
      const endpoint =
        typeof API_ENDPOINTS.CAD.TASK_STATUS === 'function'
          ? API_ENDPOINTS.CAD.TASK_STATUS(taskId)
          : `${API_ENDPOINTS.CAD.TASK_STATUS}/${taskId}`

      const response = await axios.get(buildApiUrl(endpoint, baseUrl))

      if (response.data.code === 0) {
        const data: TaskStatus = response.data.data
        onProgress(data)

        if (data.status === 'completed') {
          isStopped = true
          clearInterval(intervalId)
          clearTimeout(timeoutId)
          onComplete(data)
        } else if (data.status === 'failed') {
          isStopped = true
          clearInterval(intervalId)
          clearTimeout(timeoutId)
          onFailed(data)
        }
      }
    } catch (error) {
      onError(error as Error)
    }
  }, intervalMs)

  return () => {
    isStopped = true
    clearInterval(intervalId)
    clearTimeout(timeoutId)
  }
}
