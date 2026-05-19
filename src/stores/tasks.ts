import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface TaskInfo {
  job_id: string
  task_type: string
  status: 'pending' | 'queued' | 'running' | 'completed' | 'failed' | 'cancelled'
  progress: number
  created_at: string
  duration_seconds?: number
  owner_id?: string
  error?: string
  params?: Record<string, any>
  result?: Record<string, any>
  progress_redis?: Record<string, any>
}

export interface TaskStats {
  total_tasks: number
  active_tasks: number
  queued_tasks: number
  completed_tasks: number
  failed_tasks: number
  max_concurrent: number
  available_slots: number
}

const API_BASE = import.meta.env.VITE_API_BASE_URL || ''

export const useTasksStore = defineStore('tasks', () => {
  const tasks = ref<TaskInfo[]>([])
  const currentTask = ref<TaskInfo | null>(null)
  const stats = ref<TaskStats>({
    total_tasks: 0,
    active_tasks: 0,
    queued_tasks: 0,
    completed_tasks: 0,
    failed_tasks: 0,
    max_concurrent: 3,
    available_slots: 3,
  })
  const loading = ref(false)
  const error = ref<string | null>(null)

  const activeTasks = computed(() =>
    tasks.value.filter(t => t.status === 'running' || t.status === 'queued')
  )

  const completedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'completed')
  )

  const failedTasks = computed(() =>
    tasks.value.filter(t => t.status === 'failed')
  )

  const cancelledTasks = computed(() =>
    tasks.value.filter(t => t.status === 'cancelled')
  )

  async function fetchTasks(params?: {
    task_type?: string
    status?: string
    owner_id?: string
    limit?: number
    offset?: number
  }) {
    loading.value = true
    error.value = null
    try {
      const searchParams = new URLSearchParams()
      if (params?.task_type) searchParams.set('task_type', params.task_type)
      if (params?.status) searchParams.set('status', params.status)
      if (params?.owner_id) searchParams.set('owner_id', params.owner_id)
      searchParams.set('limit', String(params?.limit ?? 50))
      searchParams.set('offset', String(params?.offset ?? 0))

      const response = await fetch(`${API_BASE}/api/v1/jobs?${searchParams}`)
      const json = await response.json()
      if (json.code === 0) {
        tasks.value = json.data.jobs || []
      } else {
        error.value = json.message || 'Failed to fetch tasks'
      }
    } catch (e: any) {
      error.value = e.message || 'Network error'
    } finally {
      loading.value = false
    }
  }

  async function fetchTask(jobId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}`)
      const json = await response.json()
      if (json.code === 0) {
        currentTask.value = json.data
        return json.data
      } else {
        error.value = json.message || 'Task not found'
        return null
      }
    } catch (e: any) {
      error.value = e.message || 'Network error'
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchTaskProgress(jobId: string) {
    try {
      const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/progress`)
      const json = await response.json()
      if (json.code === 0 && currentTask.value) {
        currentTask.value.progress = json.data.progress_db ?? currentTask.value.progress
        currentTask.value.progress_redis = {
          progress: json.data.progress_redis,
          message: json.data.message,
          metrics: json.data.metrics,
        }
      }
      return json
    } catch (e: any) {
      error.value = e.message || 'Network error'
      return null
    }
  }

  async function cancelTask(jobId: string) {
    loading.value = true
    error.value = null
    try {
      const response = await fetch(`${API_BASE}/api/v1/jobs/${jobId}/cancel`, {
        method: 'POST',
      })
      const json = await response.json()
      if (json.code === 0) {
        const idx = tasks.value.findIndex(t => t.job_id === jobId)
        if (idx !== -1) {
          tasks.value[idx] = { ...tasks.value[idx], status: 'cancelled' }
        }
        if (currentTask.value?.job_id === jobId) {
          currentTask.value = { ...currentTask.value, status: 'cancelled' }
        }
      } else {
        error.value = json.message || 'Failed to cancel task'
      }
      return json
    } catch (e: any) {
      error.value = e.message || 'Network error'
      return null
    } finally {
      loading.value = false
    }
  }

  async function fetchStats() {
    try {
      const response = await fetch(`${API_BASE}/api/v1/jobs/stats`)
      const json = await response.json()
      if (json.code === 0) {
        stats.value = json.data
      }
      return json
    } catch (e: any) {
      error.value = e.message || 'Network error'
      return null
    }
  }

  function updateTaskFromSSE(jobId: string, status: string, progress: number) {
    const idx = tasks.value.findIndex(t => t.job_id === jobId)
    if (idx !== -1) {
      tasks.value[idx] = {
        ...tasks.value[idx],
        status: status as TaskInfo['status'],
        progress,
      }
    }
    if (currentTask.value?.job_id === jobId) {
      currentTask.value = {
        ...currentTask.value,
        status: status as TaskInfo['status'],
        progress,
      }
    }
  }

  function reset() {
    tasks.value = []
    currentTask.value = null
    loading.value = false
    error.value = null
  }

  return {
    tasks,
    currentTask,
    stats,
    loading,
    error,
    activeTasks,
    completedTasks,
    failedTasks,
    cancelledTasks,
    fetchTasks,
    fetchTask,
    fetchTaskProgress,
    cancelTask,
    fetchStats,
    updateTaskFromSSE,
    reset,
  }
})