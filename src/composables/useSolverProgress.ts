import { ref, onUnmounted } from 'vue'

interface PhaseState {
  phase: string
  state: 'waiting' | 'solving' | 'completed' | 'failed' | 'rollback' | 'terminated'
  parameters?: Record<string, number>
  metrics?: Record<string, number>
  duration_ms?: number
  validation?: {
    validation_passed: boolean
    error_rate: number
    warnings?: string[]
    violations?: Record<string, any>
  }
  error_message?: string
}

interface PerformanceReport {
  total_phases: number
  passed_phases: number
  failed_phases: number
  success_rate: number
  total_solver_time_ms: number
  total_validation_time_ms: number
  total_time_ms: number
  average_phase_time_ms: number
  strategy: string
}

interface SolverProgressState {
  task_id: string
  phase_states: PhaseState[]
  performance_report: PerformanceReport | null
  is_active: boolean
  can_terminate: boolean
  termination_reason: string
  updated_at: string
}

type ConnectionState = 'idle' | 'connecting' | 'connected' | 'reconnecting' | 'closed' | 'error'

interface UseSolverProgressOptions {
  maxRetries?: number
  retryDelay?: number
  connectionTimeout?: number
}

const activeConnections = new Map<string, EventSource>()

export function useSolverProgress(taskId: string, options: UseSolverProgressOptions = {}) {
  const {
    maxRetries = 3,
    retryDelay = 3000,
    connectionTimeout = 30000
  } = options

  const phaseStates = ref<PhaseState[]>([])
  const performanceReport = ref<PerformanceReport | null>(null)
  const isActive = ref(false)
  const canTerminate = ref(false)
  const terminationReason = ref('')
  const eventSource = ref<EventSource | null>(null)
  const connectionState = ref<ConnectionState>('idle')
  const retryCount = ref(0)
  let reconnectTimer: ReturnType<typeof setTimeout> | null = null
  let connectionTimeoutTimer: ReturnType<typeof setTimeout> | null = null
  let isDestroyed = false

  function log(level: 'info' | 'warn' | 'error', message: string, data?: Record<string, any>) {
    const timestamp = new Date().toISOString()
    const logData = { timestamp, taskId, connectionState: connectionState.value, retryCount: retryCount.value, ...data }
    console[level](`[SSE-${taskId}] ${message}`, logData)
  }

  function clearAllTimers() {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
    if (connectionTimeoutTimer) {
      clearTimeout(connectionTimeoutTimer)
      connectionTimeoutTimer = null
    }
  }

  function updatePhaseState(phaseData: PhaseState) {
    const existingIndex = phaseStates.value.findIndex(p => p.phase === phaseData.phase)
    if (existingIndex >= 0) {
      phaseStates.value[existingIndex] = { ...phaseStates.value[existingIndex], ...phaseData }
    } else {
      phaseStates.value.push(phaseData)
    }
  }

  function handleConnectionSuccess() {
    connectionState.value = 'connected'
    retryCount.value = 0
    log('info', 'SSE connection established')
  }

  function handleMessage(event: MessageEvent) {
    try {
      const data = JSON.parse(event.data)

      if (data.error) {
        log('error', 'Solver progress error', { error: data.error })
        return
      }

      const state: SolverProgressState = data.state
      if (state) {
        phaseStates.value = state.phase_states || []
        performanceReport.value = state.performance_report
        isActive.value = state.is_active
        canTerminate.value = state.can_terminate
        terminationReason.value = state.termination_reason || ''
      }

      if (data.event === 'solver_phase_update' && data.phase_data) {
        updatePhaseState(data.phase_data)
      }
    } catch (e) {
      log('error', 'Failed to parse solver progress event', { error: e })
    }
  }

  function handleError(error: Event) {
    log('warn', 'SSE connection error', { error })

    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }

    activeConnections.delete(taskId)

    if (isDestroyed || retryCount.value >= maxRetries) {
      connectionState.value = isDestroyed ? 'closed' : 'error'
      log(isDestroyed ? 'info' : 'error', isDestroyed ? 'Connection closed on destroy' : 'Max retries reached')
      return
    }

    connectionState.value = 'reconnecting'
    retryCount.value++

    reconnectTimer = setTimeout(() => {
      if (!isDestroyed) {
        log('info', `Attempting reconnect (${retryCount.value}/${maxRetries})`)
        createConnection()
      }
    }, retryDelay)
  }

  function createConnection() {
    if (isDestroyed) {
      log('warn', 'Cannot create connection: component destroyed')
      return
    }

    if (activeConnections.has(taskId)) {
      log('warn', 'Closing existing connection before creating new one')
      activeConnections.get(taskId)!.close()
      activeConnections.delete(taskId)
    }

    connectionState.value = 'connecting'
    clearAllTimers()

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const url = `${baseUrl}/api/v1/tasks/${taskId}/solver-stream`

    log('info', 'Creating SSE connection', { url })

    eventSource.value = new EventSource(url)
    activeConnections.set(taskId, eventSource.value)

    connectionTimeoutTimer = setTimeout(() => {
      if (connectionState.value === 'connecting') {
        log('warn', 'Connection timeout')
        eventSource.value?.close()
        eventSource.value = null
        activeConnections.delete(taskId)
        handleError(new Event('timeout'))
      }
    }, connectionTimeout)

    eventSource.value.onopen = () => {
      handleConnectionSuccess()
      clearAllTimers()
    }

    eventSource.value.onmessage = handleMessage
    eventSource.value.onerror = handleError
  }

  function connect() {
    if (eventSource.value) {
      log('info', 'Closing existing connection before reconnect')
      disconnect()
    }
    retryCount.value = 0
    createConnection()
  }

  function disconnect() {
    log('info', 'Disconnecting SSE connection')
    isDestroyed = true
    clearAllTimers()

    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }

    activeConnections.delete(taskId)
    connectionState.value = 'closed'
  }

  onUnmounted(() => {
    log('info', 'Component unmounting, cleaning up SSE connection')
    disconnect()
  })

  return {
    phaseStates,
    performanceReport,
    isActive,
    canTerminate,
    terminationReason,
    connectionState,
    retryCount,
    connect,
    disconnect
  }
}
