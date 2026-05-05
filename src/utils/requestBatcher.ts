import axios from 'axios'

export interface BatchSubRequest {
  id: string
  method: string
  path: string
  headers?: Record<string, string>
  body?: Record<string, any>
}

export interface BatchSubResponse {
  id: string
  status: number
  data: any
  error: { code: string; message: string } | null
}

export interface BatchRequest {
  requests: BatchSubRequest[]
}

export interface BatchResponse {
  results: BatchSubResponse[]
}

export interface QueuedRequest {
  id: string
  request: Omit<BatchSubRequest, 'id'>
  resolve: (value: BatchSubResponse) => void
  reject: (reason: Error) => void
  timestamp: number
  cancelled: boolean
}

export interface RequestBatcherConfig {
  windowMs?: number
  maxBatchSize?: number
  maxRetries?: number
  retryableStatuses?: number[]
  baseUrl?: string
}

export class RequestBatcher {
  private queue: Map<string, QueuedRequest> = new Map()
  private timer: ReturnType<typeof setTimeout> | null = null
  private readonly windowMs: number
  private readonly maxBatchSize: number
  private readonly maxRetries: number
  private readonly retryableStatuses: Set<number>
  private readonly baseUrl: string

  constructor(config: RequestBatcherConfig = {}) {
    this.windowMs = config.windowMs ?? 50
    this.maxBatchSize = config.maxBatchSize ?? 10
    this.maxRetries = config.maxRetries ?? 2
    this.retryableStatuses = new Set(config.retryableStatuses ?? [500, 502, 503, 504])
    this.baseUrl = config.baseUrl ?? ''
  }

  enqueue(request: Omit<BatchSubRequest, 'id'>): Promise<BatchSubResponse> {
    const id = this.generateId()

    return new Promise((resolve, reject) => {
      const queued: QueuedRequest = {
        id,
        request,
        resolve,
        reject,
        timestamp: Date.now(),
        cancelled: false,
      }

      this.queue.set(id, queued)

      if (!this.timer) {
        this.timer = setTimeout(() => this.flush(), this.windowMs)
      }

      if (this.queue.size >= this.maxBatchSize) {
        this.flush()
      }
    })
  }

  cancel(requestId: string): void {
    if (requestId === 'all') {
      this.queue.forEach((item) => {
        if (!item.cancelled) {
          item.cancelled = true
          item.reject(new Error('请求已取消'))
        }
      })
      this.queue.clear()
    } else {
      const item = this.queue.get(requestId)
      if (item && !item.cancelled) {
        item.cancelled = true
        item.reject(new Error('请求已取消'))
        this.queue.delete(requestId)
      }
    }

    if (this.queue.size === 0 && this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  }

  destroy(): void {
    this.cancel('all')
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  }

  private async flush(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }

    if (this.queue.size === 0) return

    const { uniqueRequests, dedupGroups } = this.deduplicateRequests()

    const batchRequest: BatchRequest = {
      requests: uniqueRequests.map((item) => ({
        id: item.id,
        method: item.request.method,
        path: item.request.path,
        headers: item.request.headers,
        body: item.request.body,
      })),
    }

    try {
      const result = await this.executeWithRetry(batchRequest)
      this.dispatchResults(result, uniqueRequests, dedupGroups)
    } catch (error) {
      let errorMessage: string
      if (error instanceof Error) {
        errorMessage = error.message
      } else if (typeof error === 'object' && error !== null && 'message' in error) {
        errorMessage = String((error as any).message)
      } else {
        errorMessage = String(error)
      }
      uniqueRequests.forEach((item) => {
        if (!item.cancelled) {
          item.reject(new Error(errorMessage))
        }
        const duplicates = dedupGroups.get(item.id) || []
        duplicates.forEach((dup) => {
          if (!dup.cancelled) {
            dup.reject(new Error(errorMessage))
          }
        })
      })
    }
  }

  private deduplicateRequests(): { uniqueRequests: QueuedRequest[]; dedupGroups: Map<string, QueuedRequest[]> } {
    const seen = new Map<string, string>()
    const uniqueRequests: QueuedRequest[] = []
    const dedupGroups = new Map<string, QueuedRequest[]>()

    this.queue.forEach((item) => {
      if (item.cancelled) return

      const key = `${item.request.method}:${item.request.path}:${JSON.stringify(item.request.body || '')}`
      const originalId = seen.get(key)

      if (!originalId) {
        seen.set(key, item.id)
        uniqueRequests.push(item)
        dedupGroups.set(item.id, [])
      } else {
        const group = dedupGroups.get(originalId)!
        group.push(item)
      }
    })

    this.queue.clear()
    return { uniqueRequests, dedupGroups }
  }

  private async executeWithRetry(batchRequest: BatchRequest, attempt: number = 0): Promise<BatchResponse> {
    try {
      const response = await axios.post(`${this.baseUrl}/api/batch/execute`, batchRequest, {
        timeout: 30000,
        validateStatus: () => true,
      })

      const responseData = response.data

      if (responseData && responseData.data && responseData.data.results) {
        return responseData.data
      }

      if (responseData && responseData.results) {
        return responseData
      }

      throw new Error('响应格式不正确')
    } catch (error: any) {
      if (attempt < this.maxRetries && this.shouldRetry(error)) {
        return this.executeWithRetry(batchRequest, attempt + 1)
      }

      if (error.response && error.response.data) {
        const respData = error.response.data
        if (respData.message) {
          throw new Error(respData.message)
        }
        if (respData.data && respData.results) {
          return respData.data
        }
      }

      throw error
    }
  }

  private shouldRetry(error: any): boolean {
    if (error.code === 'ECONNABORTED') return true
    if (error.code === 'ERR_NETWORK') return true

    const status = error.response?.status
    return status && this.retryableStatuses.has(status)
  }

  private dispatchResults(
    result: BatchResponse,
    uniqueRequests: QueuedRequest[],
    dedupGroups: Map<string, QueuedRequest[]>
  ): void {
    uniqueRequests.forEach((item, index) => {
      const response = result.results[index]
      if (!response) {
        const rejectError = new Error('响应结果不匹配')
        if (!item.cancelled) item.reject(rejectError)

        const duplicates = dedupGroups.get(item.id) || []
        duplicates.forEach((dup) => {
          if (!dup.cancelled) dup.reject(rejectError)
        })
        return
      }

      if (response.error) {
        const rejectError = new Error(response.error.message)
        if (!item.cancelled) item.reject(rejectError)

        const duplicates = dedupGroups.get(item.id) || []
        duplicates.forEach((dup) => {
          if (!dup.cancelled) dup.reject(rejectError)
        })
      } else {
        if (!item.cancelled) item.resolve(response)

        const duplicates = dedupGroups.get(item.id) || []
        duplicates.forEach((dup) => {
          if (!dup.cancelled) dup.resolve(response)
        })
      }
    })
  }

  private generateId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
  }
}

let batcherInstance: RequestBatcher | null = null

export function getRequestBatcher(config?: RequestBatcherConfig): RequestBatcher {
  if (!batcherInstance) {
    batcherInstance = new RequestBatcher(config)
  }
  return batcherInstance
}

export function destroyRequestBatcher(): void {
  if (batcherInstance) {
    batcherInstance.destroy()
    batcherInstance = null
  }
}
