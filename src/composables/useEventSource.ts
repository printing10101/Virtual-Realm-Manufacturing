/**
 * Server-Sent Events (SSE) 事件源管理
 * 提供连接、重连、事件处理等完整功能
 */

import { ref, onUnmounted, unref, type Ref } from 'vue'
import { API_CONFIG, buildApiPath } from '@/config/api'

/** SSE事件负载数据结构 */
export interface SSEEventData {
  percent?: number
  metrics?: Record<string, unknown>
  error?: string
  status?: string
  [key: string]: unknown
}

export interface SSEEvent {
  type: 'queued' | 'started' | 'progress' | 'complete' | 'failed' | 'cancelled' | 'done'
  data: SSEEventData
  timestamp: Date
}

export interface UseEventSourceOptions {
  autoReconnect?: boolean
  maxRetries?: number
  baseDelay?: number
  maxDelay?: number
}

export interface UseEventSourceReturn {
  events: ReturnType<typeof ref<SSEEvent[]>>
  isConnected: ReturnType<typeof ref<boolean>>
  isDone: ReturnType<typeof ref<boolean>>
  currentStatus: ReturnType<typeof ref<string | null>>
  progress: ReturnType<typeof ref<number>>
  lastProgressData: ReturnType<typeof ref<Record<string, unknown> | null>>
  error: ReturnType<typeof ref<string | null>>
  connect: () => void
  close: () => void
  reset: () => void
}

export function useEventSource(jobId: string | Ref<string>, options: UseEventSourceOptions = {}): UseEventSourceReturn {
  const {
    autoReconnect = true,
    maxRetries = 10,
    baseDelay = 1000,
    maxDelay = 30000,
  } = options

  const events = ref<SSEEvent[]>([])
  const isConnected = ref(false)
  const isDone = ref(false)
  const currentStatus = ref<string | null>(null)
  const progress = ref(0)
  const lastProgressData = ref<Record<string, unknown> | null>(null)
  const error = ref<string | null>(null)

  let eventSource: EventSource | null = null
  let retryCount = 0
  let retryTimer: number | null = null

  /**
   * 获取EventSource连接URL
   * @returns SSE流地址
   */
  const getEventSourceUrl = (): string => {
    return buildApiPath(API_CONFIG.JOBS, `/${unref(jobId)}/stream`)
  }

  /**
   * 建立SSE连接
   */
  const connect = (): void => {
    if (!jobId) return
    if (eventSource) {
      close()
    }

    const url = getEventSourceUrl()
    eventSource = new EventSource(url)

    eventSource.onopen = (): void => {
      isConnected.value = true
      retryCount = 0
      // SSE 连接到事件流
    }

    eventSource.onerror = (): void => {
      isConnected.value = false
      // SSE 连接错误

      if (autoReconnect && !isDone.value && retryCount < maxRetries) {
        scheduleReconnect()
      }
    }

    const eventTypes = ['queued', 'started', 'progress', 'complete', 'failed', 'cancelled', 'done'] as const
    eventTypes.forEach(eventType => {
      eventSource!.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data) as SSEEventData
          const sseEvent: SSEEvent = {
            type: eventType,
            data,
            timestamp: new Date(),
          }
          events.value.push(sseEvent)
          handleEvent(sseEvent)
        } catch {
          // 静默处理
        }
      })
    })
  }

  /**
   * 处理接收到的SSE事件
   * @param event - SSE事件对象
   */
  const handleEvent = (event: SSEEvent): void => {
    switch (event.type) {
      case 'queued':
        currentStatus.value = 'queued'
        progress.value = 0
        break

      case 'started':
        currentStatus.value = 'running'
        progress.value = 5
        break

      case 'progress':
        currentStatus.value = 'running'
        progress.value = event.data.percent ?? 0
        lastProgressData.value = event.data.metrics ?? null
        break

      case 'complete':
        currentStatus.value = 'completed'
        progress.value = 100
        isDone.value = true
        close()
        break

      case 'failed':
        currentStatus.value = 'failed'
        error.value = event.data.error ?? 'Unknown error occurred'
        isDone.value = true
        close()
        break

      case 'cancelled':
        currentStatus.value = 'cancelled'
        isDone.value = true
        close()
        break

      case 'done':
        currentStatus.value = event.data.status ?? currentStatus.value
        isDone.value = true
        close()
        break
    }
  }

  /**
   * 安排重连（指数退避策略）
   */
  const scheduleReconnect = (): void => {
    retryCount++
    const delay = Math.min(baseDelay * Math.pow(2, retryCount - 1), maxDelay)
    // SSE 重连中: delay ms (attempt retryCount/maxRetries)

    retryTimer = window.setTimeout(() => {
      connect()
    }, delay)
  }

  /**
   * 关闭SSE连接并清理定时器
   */
  const close = (): void => {
    if (eventSource) {
      eventSource.close()
      eventSource = null
    }
    if (retryTimer !== null) {
      clearTimeout(retryTimer)
      retryTimer = null
    }
    isConnected.value = false
  }

  /**
   * 重置所有状态到初始值
   */
  const reset = (): void => {
    events.value = []
    currentStatus.value = null
    progress.value = 0
    lastProgressData.value = null
    error.value = null
    isDone.value = false
    retryCount = 0
  }

  onUnmounted(() => {
    close()
  })

  return {
    events,
    isConnected,
    isDone,
    currentStatus,
    progress,
    lastProgressData,
    error,
    connect,
    close,
    reset,
  }
}
