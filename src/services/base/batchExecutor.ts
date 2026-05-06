/**
 * 请求批处理基础抽象
 *
 * 提供请求批处理的通用逻辑：
 * - 请求队列管理
 * - 定时刷新机制
 * - 批量执行分发
 * - 取消和销毁支持
 *
 * 子类需实现具体的执行策略（如 axios、Tauri invoke 等）
 */

export interface QueuedRequestBase<TRequest, TResponse> {
  id: string
  request: TRequest
  resolve: (value: TResponse) => void
  reject: (reason: Error) => void
  timestamp: number
}

export interface BatchExecutorConfig {
  windowMs?: number
  maxBatchSize?: number
}

export abstract class BatchExecutorBase<TRequest, TResponse> {
  protected queue: Map<string, QueuedRequestBase<TRequest, TResponse>> = new Map()
  protected timer: ReturnType<typeof setTimeout> | null = null
  protected readonly windowMs: number
  protected readonly maxBatchSize: number

  constructor(config: BatchExecutorConfig = {}) {
    this.windowMs = config.windowMs ?? 50
    this.maxBatchSize = config.maxBatchSize ?? 10
  }

  enqueue(request: TRequest): Promise<TResponse> {
    const id = this.generateId()

    return new Promise((resolve, reject) => {
      const queued: QueuedRequestBase<TRequest, TResponse> = {
        id,
        request,
        resolve,
        reject,
        timestamp: Date.now(),
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
        item.reject(new Error('请求已取消'))
      })
      this.queue.clear()
    } else {
      const item = this.queue.get(requestId)
      if (item) {
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

  protected async flush(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }

    if (this.queue.size === 0) return

    const items = Array.from(this.queue.values())
    this.queue.clear()

    try {
      const results = await this.executeBatch(items.map(item => item.request))
      this.dispatchResults(results, items)
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      items.forEach((item) => {
        item.reject(new Error(errorMessage))
      })
    }
  }

  protected dispatchResults(
    results: TResponse[],
    items: QueuedRequestBase<TRequest, TResponse>[]
  ): void {
    items.forEach((item, index) => {
      const response = results[index]
      if (response === undefined) {
        item.reject(new Error('响应结果不匹配'))
      } else {
        item.resolve(response)
      }
    })
  }

  protected generateId(): string {
    return `req_${Date.now()}_${Math.random().toString(36).substring(2, 9)}`
  }

  /**
   * 子类必须实现的抽象方法
   * 执行一批请求并返回对应的响应数组
   */
  protected abstract executeBatch(requests: TRequest[]): Promise<TResponse[]>
}
