/**
 * 请求批处理抽象基类
 * 
 * 提取 RequestMerger 和 RequestBatcher 的公共逻辑：
 * - 请求队列管理
 * - 定时刷新机制
 * - 去重逻辑
 * - 取消和销毁
 */

export interface BatchableRequest {
  id: string
  resolve: (value: any) => void
  reject: (reason: Error) => void
  timestamp: number
  priority?: number
}

export interface RequestBatcherConfig {
  windowMs?: number       // 批处理窗口时间（毫秒）
  maxBatchSize?: number   // 最大批次大小
  highPriorityThreshold?: number  // 高优先级阈值
}

export abstract class BaseRequestBatcher {
  protected queue: Map<string, BatchableRequest> = new Map()
  protected timer: ReturnType<typeof setTimeout> | null = null
  protected readonly windowMs: number
  protected readonly maxBatchSize: number
  protected readonly highPriorityThreshold: number

  constructor(config: RequestBatcherConfig = {}) {
    this.windowMs = config.windowMs ?? 50
    this.maxBatchSize = config.maxBatchSize ?? 10
    this.highPriorityThreshold = config.highPriorityThreshold ?? 100
  }

  /**
   * 将请求加入队列
   */
  enqueue(request: BatchableRequest): void {
    this.queue.set(request.id, request)

    if (this.shouldFlushImmediately(request)) {
      this.flush()
    } else if (this.queue.size >= this.maxBatchSize) {
      this.flush()
    } else if (!this.timer) {
      this.timer = setTimeout(() => this.flush(), this.windowMs)
    }
  }

  /**
   * 子类必须实现的批处理执行逻辑
   */
  protected abstract executeBatch(batch: BatchableRequest[]): Promise<void>

  /**
   * 执行单个请求（当批次只包含一个请求时）
   */
  protected abstract executeSingle(request: BatchableRequest): Promise<void>

  /**
   * 刷新队列，执行批处理
   */
  protected async flush(): Promise<void> {
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }

    if (this.queue.size === 0) return

    const batch = Array.from(this.queue.values())
    this.queue.clear()

    try {
      if (batch.length === 1) {
        await this.executeSingle(batch[0])
      } else {
        await this.executeBatch(batch)
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error)
      batch.forEach((req) => {
        req.reject(new Error(errorMessage))
      })
    }
  }

  /**
   * 取消所有待处理的请求
   */
  cancel(message: string = '请求已取消'): void {
    this.queue.forEach((req) => {
      req.reject(new Error(message))
    })
    this.queue.clear()
    if (this.timer) {
      clearTimeout(this.timer)
      this.timer = null
    }
  }

  /**
   * 销毁批处理器
   */
  destroy(): void {
    this.cancel()
  }

  /**
   * 获取队列大小
   */
  get queueSize(): number {
    return this.queue.size
  }

  /**
   * 检查是否应该立即刷新
   */
  private shouldFlushImmediately(request: BatchableRequest): boolean {
    const priority = request.priority ?? 0
    return priority >= this.highPriorityThreshold
  }
}
