/**
 * Server-Sent Events (SSE) 事件源管理
 * 提供连接、重连、事件处理等完整功能
 */

import { ref, onUnmounted, unref, type Ref } from 'vue'
import { API_CONFIG, buildApiPath } from '@/config/api'
import { resolveBackendUrl } from '@/utils/http'

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
  // 修复竞态：每次 connect/close/reset 递增 streamEpoch，
  // 异步事件回调与重连定时器执行时检查 epoch 是否仍为最新，
  // 否则丢弃事件 / 取消重连，避免：
  //   1. 快速切换 jobId（A → B）：A 的 in-flight 事件仍在事件循环队列中，
  //      reset 后被处理写入 events.value，造成 B 的事件列表中混入 A 的事件
  //   2. close → onerror 触发 scheduleReconnect，retryTimer 到期后建立幽灵连接
  let streamEpoch = 0

  /**
   * 获取EventSource连接URL
   * @returns SSE流地址
   */
  const getEventSourceUrl = (): string => {
    // 桌面模式：EventSource 不走 axios baseURL，必须显式解析为后端实际端口的完整 URL
    return resolveBackendUrl(buildApiPath(API_CONFIG.JOBS, `/${unref(jobId)}/stream`))
  }

  /**
   * 建立SSE连接
   */
  const connect = (): void => {
    // 修复：原实现 `if (!jobId) return` 仅检查 jobId 参数本身（对象 truthy），
    // 当 jobId 是 Ref<string> 且 ref.value 为 ''（空字符串）时仍会继续执行，
    // getEventSourceUrl 会构造 `/jobs//stream` 这种错误 URL，
    // 浏览器尝试连接 → 404 → onerror → 无限重连。
    // 现改为 unref 后检查实际值，空字符串直接返回。
    const id = unref(jobId)
    if (!id) return
    if (eventSource) {
      close()
    }

    // 递增 epoch 使前一个连接的 in-flight 事件回调失效
    streamEpoch += 1
    const currentEpoch = streamEpoch

    const url = getEventSourceUrl()
    eventSource = new EventSource(url)

    eventSource.onopen = (): void => {
      if (currentEpoch !== streamEpoch) return
      isConnected.value = true
      retryCount = 0
      // SSE 连接到事件流
    }

    eventSource.onerror = (): void => {
      if (currentEpoch !== streamEpoch) return
      isConnected.value = false
      // SSE 连接错误

      if (autoReconnect && !isDone.value && retryCount < maxRetries) {
        scheduleReconnect(currentEpoch)
      }
    }

    const eventTypes = ['queued', 'started', 'progress', 'complete', 'failed', 'cancelled', 'done'] as const
    const source = eventSource
    if (!source) {
      // eventSource 未初始化（理论上不会发生），记录后跳过避免运行时崩溃
      console.warn('[useEventSource] eventSource is null when registering listeners')
      return
    }
    eventTypes.forEach(eventType => {
      source.addEventListener(eventType, (event: MessageEvent) => {
        // 事件到达时若 epoch 已不匹配（已被新 connect / close 取代），直接丢弃
        if (currentEpoch !== streamEpoch) return
        try {
          const data = JSON.parse(event.data) as SSEEventData
          const sseEvent: SSEEvent = {
            type: eventType,
            data,
            timestamp: new Date(),
          }
          events.value.push(sseEvent)
          handleEvent(sseEvent, currentEpoch)
        } catch (e: unknown) {
          // SSE 事件解析失败通常为协议异常或非预期数据，记录便于排查但不应断开连接
          console.warn('[useEventSource] event parse failed for', eventType, e)
        }
      })
    })
  }

  /**
   * 处理接收到的SSE事件
   * @param event - SSE事件对象
   * @param epoch - 触发此次事件处理的 epoch（用于防御过期事件）
   */
  const handleEvent = (event: SSEEvent, epoch: number): void => {
    // 二次防御：handleEvent 可能在 close/reset 之后被调用（事件循环队列延迟）
    if (epoch !== streamEpoch) return
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
  const scheduleReconnect = (epoch: number): void => {
    retryCount++
    const delay = Math.min(baseDelay * Math.pow(2, retryCount - 1), maxDelay)
    // SSE 重连中: delay ms (attempt retryCount/maxRetries)

    retryTimer = window.setTimeout(() => {
      // 重连到期时若 epoch 已不匹配（已被新 connect / close 取代），放弃重连
      if (epoch !== streamEpoch) return
      connect()
    }, delay)
  }

  /**
   * 关闭SSE连接并清理定时器
   */
  const close = (): void => {
    // 递增 epoch 使任何 in-flight 事件回调立即失效
    streamEpoch += 1
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
    // 递增 epoch 使 in-flight 事件不再写入旧 events 数组
    streamEpoch += 1
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
