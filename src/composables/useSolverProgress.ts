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

export function useSolverProgress(taskId: string) {
  const phaseStates = ref<PhaseState[]>([])
  const performanceReport = ref<PerformanceReport | null>(null)
  const isActive = ref(false)
  const canTerminate = ref(false)
  const terminationReason = ref('')
  const eventSource = ref<EventSource | null>(null)

  function connect() {
    if (eventSource.value) {
      eventSource.value.close()
    }

    const baseUrl = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
    const url = `${baseUrl}/api/v1/tasks/${taskId}/solver-stream`

    eventSource.value = new EventSource(url)

    eventSource.value.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data)

        if (data.error) {
          console.error('Solver progress error:', data.error)
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
        console.error('Failed to parse solver progress event:', e)
      }
    }

    eventSource.value.onerror = (error) => {
      console.error('Solver progress SSE error:', error)
      eventSource.value?.close()
      eventSource.value = null
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

  function disconnect() {
    if (eventSource.value) {
      eventSource.value.close()
      eventSource.value = null
    }
  }

  onUnmounted(() => {
    disconnect()
  })

  return {
    phaseStates,
    performanceReport,
    isActive,
    canTerminate,
    terminationReason,
    connect,
    disconnect
  }
}
