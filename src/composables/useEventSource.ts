import { ref, onUnmounted } from 'vue'

export interface SSEEvent {
  type: 'queued' | 'started' | 'progress' | 'complete' | 'failed' | 'cancelled' | 'done'
  data: Record<string, any>
  timestamp: Date
}

export interface UseEventSourceOptions {
  autoReconnect?: boolean
  maxRetries?: number
  baseDelay?: number
  maxDelay?: number
}

export function useEventSource(jobId: string, options: UseEventSourceOptions = {}) {
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
  const lastProgressData = ref<Record<string, any> | null>(null)
  const error = ref<string | null>(null)

  let eventSource: EventSource | null = null
  let retryCount = 0
  let retryTimer: number | null = null

  const getEventSourceUrl = () => {
    const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
    return `${baseUrl}/api/v1/jobs/${jobId}/stream`
  }

  const connect = () => {
    if (eventSource) {
      close()
    }

    const url = getEventSourceUrl()
    eventSource = new EventSource(url)

    eventSource.onopen = () => {
      isConnected.value = true
      retryCount = 0
      console.log('[SSE] Connected to event stream')
    }

    eventSource.onerror = () => {
      isConnected.value = false
      console.error('[SSE] Connection error')

      if (autoReconnect && !isDone.value && retryCount < maxRetries) {
        scheduleReconnect()
      }
    }

    const eventTypes = ['queued', 'started', 'progress', 'complete', 'failed', 'cancelled', 'done']
    eventTypes.forEach(eventType => {
      eventSource!.addEventListener(eventType, (event: MessageEvent) => {
        try {
          const data = JSON.parse(event.data)
          const sseEvent: SSEEvent = {
            type: eventType as SSEEvent['type'],
            data,
            timestamp: new Date(),
          }
          events.value.push(sseEvent)
          handleEvent(sseEvent)
        } catch (e) {
          console.error(`[SSE] Failed to parse ${eventType} event:`, e)
        }
      })
    })
  }

  const handleEvent = (event: SSEEvent) => {
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
        progress.value = event.data.percent || 0
        lastProgressData.value = event.data.metrics || null
        break

      case 'complete':
        currentStatus.value = 'completed'
        progress.value = 100
        isDone.value = true
        close()
        break

      case 'failed':
        currentStatus.value = 'failed'
        error.value = event.data.error || 'Unknown error occurred'
        isDone.value = true
        close()
        break

      case 'cancelled':
        currentStatus.value = 'cancelled'
        isDone.value = true
        close()
        break

      case 'done':
        currentStatus.value = event.data.status || currentStatus.value
        isDone.value = true
        close()
        break
    }
  }

  const scheduleReconnect = () => {
    retryCount++
    const delay = Math.min(baseDelay * Math.pow(2, retryCount - 1), maxDelay)
    console.log(`[SSE] Reconnecting in ${delay}ms (attempt ${retryCount}/${maxRetries})`)

    retryTimer = window.setTimeout(() => {
      connect()
    }, delay)
  }

  const close = () => {
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

  const reset = () => {
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
