import { invoke } from '@tauri-apps/api/core'

export interface ProxyRequest {
  method: string
  url: string
  headers?: Record<string, string>
  body?: Record<string, any>
  timeout_ms?: number
}

export interface ProxyResponse {
  status: number
  headers: Record<string, string>
  body: any
  duration_ms: number
}

export interface ProxyError {
  code: string
  message: string
  status?: number
}

export interface BatchResponse {
  responses: Array<{ Ok: ProxyResponse } | { Err: ProxyError }>
  total_duration_ms: number
}

export interface QueuedRequest {
  id: string
  request: ProxyRequest
  resolve: (value: ProxyResponse) => void
  reject: (reason: Error) => void
  timestamp: number
  priority: number
}

export class RequestMerger {
  private queue: QueuedRequest[] = []
  private timer: ReturnType<typeof setTimeout> | null = null
  private readonly windowMs: number
  private readonly maxBatchSize: number
  private readonly highPriorityThreshold: number

  constructor(windowMs = 75, maxBatchSize = 10, highPriorityThreshold = 100) {
    this.windowMs = windowMs
    this.maxBatchSize = maxBatchSize
    this.highPriorityThreshold = highPriorityThreshold
  }

  enqueue(request: ProxyRequest, priority: number = 0): Promise<ProxyResponse> {
    return new Promise((resolve, reject) => {
      const queued: QueuedRequest = {
        id: `${Date.now()}-${Math.random().toString(36).substr(2, 9)}`,
        request,
        resolve,
        reject,
        timestamp: Date.now(),
        priority,
      }

      this.queue.push(queued)
      this.queue.sort((a, b) => b.priority - a.priority)

      if (priority >= this.highPriorityThreshold) {
        this.flush()
      } else if (this.queue.length >= this.maxBatchSize) {
        this.flush()
      } else if (!this.timer) {
        this.timer = setTimeout(() => this.flush(), this.windowMs)
      }
    })
  }

  private async flush(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }

    if (this.queue.length === 0) return

    const batch = [...this.queue]
    this.queue = []

    if (batch.length === 1) {
      const item = batch[0]
      try {
        const response = await invoke<ProxyResponse>('proxy_http_request', {
          request: item.request,
        })
        item.resolve(response)
      } catch (error) {
        item.reject(error instanceof Error ? error : new Error(String(error)))
      }
      return
    }

    try {
      const result = await invoke<BatchResponse>('proxy_batch_request', {
        batch: { requests: batch.map((b) => b.request) },
      })

      result.responses.forEach((res, index) => {
        if (index < batch.length) {
          if ('Ok' in res) {
            batch[index].resolve(res.Ok)
          } else {
            batch[index].reject(new Error(res.Err.message))
          }
        }
      })
    } catch (error) {
      batch.forEach((item) => {
        item.reject(error instanceof Error ? error : new Error(String(error)))
      })
    }
  }

  clear(): void {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
    this.queue.forEach((item) => {
      item.reject(new Error('Request cancelled'))
    })
    this.queue = []
  }
}

let mergerInstance: RequestMerger | null = null

export function getRequestMerger(): RequestMerger {
  if (!mergerInstance) {
    mergerInstance = new RequestMerger()
  }
  return mergerInstance
}

export function destroyRequestMerger(): void {
  if (mergerInstance) {
    mergerInstance.clear()
    mergerInstance = null
  }
}
