export interface ApiResult<T> {
  code: number
  message: string
  data: T
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

export async function apiRequest<T>(
  url: string,
  options?: RequestInit & { timeout?: number }
): Promise<T> {
  const { timeout = DEFAULT_TIMEOUT, ...fetchOptions } = options || {}

  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeout)

  try {
    const response = await fetch(url, {
      ...fetchOptions,
      signal: controller.signal
    })

    clearTimeout(timeoutId)

    if (!response.ok) {
      throw new ApiError(
        response.status,
        `HTTP错误: ${response.status} ${response.statusText}`
      )
    }

    const result: ApiResult<T> = await response.json()

    if (result.code !== 0) {
      throw new ApiError(result.code, result.message)
    }

    return result.data
  } catch (error) {
    clearTimeout(timeoutId)

    if (error instanceof ApiError) {
      throw error
    }

    if (error instanceof DOMException && error.name === 'AbortError') {
      throw new ApiError(-1, '请求超时,请稍后重试')
    }

    if (error instanceof TypeError && error.message.includes('fetch')) {
      throw new ApiError(-1, '网络错误,请检查网络连接')
    }

    throw error
  }
}

export async function apiStreamRequest(
  url: string,
  onChunk: (data: string) => void,
  options?: RequestInit
): Promise<void> {
  const response = await fetch(url, {
    ...options,
    headers: {
      'Accept': 'text/event-stream',
      ...options?.headers
    }
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
