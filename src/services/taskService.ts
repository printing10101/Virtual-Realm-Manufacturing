import { ref, onUnmounted, type Ref } from 'vue'
import axios from 'axios'
import { DEFAULT_URLS } from '@/constants'

export type TaskStatus = 'pending' | 'running' | 'success' | 'failed' | 'cancelled'
export type TaskType = 'process_generation' | 'report_generation' | 'simulation_validation' | 'cad_generation' | 'workflow_execution'

export interface Task {
  task_id: string
  task_type: TaskType
  status: TaskStatus
  progress: number
  message: string
  result: Record<string, unknown> | null
  error: string | null
  params: Record<string, unknown> | null
  created_at: string
  updated_at: string
}

export interface TaskEvent {
  task_id: string
  event: 'progress' | 'status_change' | 'result' | 'error'
  progress?: number
  message?: string
  status?: TaskStatus
  result?: Record<string, unknown>
  error?: string
}

export interface TaskListResponse {
  tasks: Task[]
  total: number
  page: number
  page_size: number
}

class TaskService {
  private baseUrl: string

  constructor(baseUrl: string = DEFAULT_URLS.PYTHON_BACKEND) {
    this.baseUrl = baseUrl.replace(/\/$/, '')
  }

  async createTask(taskType: TaskType, params?: Record<string, unknown>, timeout?: number): Promise<{ task_id: string }> {
    const response = await axios.post(`${this.baseUrl}/api/v1/tasks`, {
      task_type: taskType,
      params: params || null,
      timeout: timeout || null
    })
    return response.data.data
  }

  async getTask(taskId: string): Promise<Task> {
    const response = await axios.get(`${this.baseUrl}/api/v1/tasks/${taskId}`)
    return response.data.data
  }

  async listTasks(
    status?: TaskStatus,
    taskType?: TaskType,
    page: number = 1,
    pageSize: number = 20
  ): Promise<TaskListResponse> {
    const params: Record<string, unknown> = { page, page_size: pageSize }
    if (status) params.status = status
    if (taskType) params.task_type = taskType

    const response = await axios.get(`${this.baseUrl}/api/v1/tasks`, { params })
    return response.data.data
  }

  async cancelTask(taskId: string): Promise<void> {
    await axios.delete(`${this.baseUrl}/api/v1/tasks/${taskId}`)
  }

  connectSSE(taskId: string, onEvent: (event: TaskEvent) => void): () => void {
    const url = `${this.baseUrl}/api/v1/tasks/${taskId}/stream`
    const eventSource = new EventSource(url)
    let closed = false

    eventSource.onmessage = (event: MessageEvent) => {
      if (closed) return
      try {
        const data: TaskEvent = JSON.parse(event.data)
        onEvent(data)

        if (data.event === 'result' || data.event === 'error' || 
            (data.event === 'status_change' && ['success', 'failed', 'cancelled'].includes(data.status || ''))) {
          eventSource.close()
        }
      } catch (e) {
        console.error('SSE parse error:', e)
      }
    }

    eventSource.onerror = () => {
      if (!closed) {
        eventSource.close()
      }
    }

    return () => {
      closed = true
      eventSource.close()
    }
  }

  connectSSERetry(taskId: string, onEvent: (event: TaskEvent) => void, maxBackoff: number = 30000): void {
    let backoff = 1000
    let disconnected = false

    const connect = () => {
      if (disconnected) return

      const cleanup = this.connectSSE(taskId, (event) => {
        backoff = 1000
        onEvent(event)

        if (event.event === 'result' || event.event === 'error') {
          disconnected = true
        }
      })

      const checkReconnect = setInterval(() => {
        if (disconnected) {
          clearInterval(checkReconnect)
          cleanup()
          return
        }
      }, 5000)

      const originalCleanup = cleanup
      return () => {
        clearInterval(checkReconnect)
        originalCleanup()
      }
    }

    const initialCleanup = connect()

    return
  }
}

export const taskService = new TaskService()

export function useTask(taskId: Ref<string> | string) {
  const task = ref<Task | null>(null)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const sseConnected = ref(false)
  let sseCleanup: (() => void) | null = null

  const idRef = typeof taskId === 'string' ? ref(taskId) : taskId

  async function fetchTask() {
    loading.value = true
    try {
      task.value = await taskService.getTask(idRef.value)
      error.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取任务失败'
    } finally {
      loading.value = false
    }
  }

  function connectSSE() {
    if (sseCleanup) {
      sseCleanup()
    }

    sseCleanup = taskService.connectSSE(idRef.value, (event) => {
      if (!task.value) {
        fetchTask()
        return
      }

      switch (event.event) {
        case 'progress':
          task.value.progress = event.progress ?? task.value.progress
          task.value.message = event.message ?? task.value.message
          task.value.updated_at = new Date().toISOString()
          break
        case 'status_change':
          task.value.status = event.status ?? task.value.status
          task.value.message = event.message ?? task.value.message
          task.value.updated_at = new Date().toISOString()
          break
        case 'result':
          task.value.status = 'success'
          task.value.progress = 100
          task.value.result = event.result ?? task.value.result
          task.value.updated_at = new Date().toISOString()
          break
        case 'error':
          task.value.status = 'failed'
          task.value.error = event.error ?? task.value.error
          task.value.updated_at = new Date().toISOString()
          break
      }
    })

    sseConnected.value = true
  }

  function disconnectSSE() {
    if (sseCleanup) {
      sseCleanup()
      sseCleanup = null
    }
    sseConnected.value = false
  }

  async function cancelTask() {
    try {
      await taskService.cancelTask(idRef.value)
      if (task.value) {
        task.value.status = 'cancelled'
      }
      disconnectSSE()
    } catch (e) {
      error.value = e instanceof Error ? e.message : '取消任务失败'
    }
  }

  onUnmounted(() => {
    disconnectSSE()
  })

  return {
    task,
    loading,
    error,
    sseConnected,
    fetchTask,
    connectSSE,
    disconnectSSE,
    cancelTask
  }
}

export function useTaskList() {
  const tasks = ref<Task[]>([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref<string | null>(null)
  const currentStatus = ref<TaskStatus | undefined>(undefined)
  const currentType = ref<TaskType | undefined>(undefined)
  const currentPage = ref(1)
  const pageSize = ref(20)
  let refreshTimer: ReturnType<typeof setInterval> | null = null

  async function fetchTasks() {
    loading.value = true
    try {
      const result = await taskService.listTasks(
        currentStatus.value,
        currentType.value,
        currentPage.value,
        pageSize.value
      )
      tasks.value = result.tasks
      total.value = result.total
      error.value = null
    } catch (e) {
      error.value = e instanceof Error ? e.message : '获取任务列表失败'
    } finally {
      loading.value = false
    }
  }

  function startAutoRefresh(intervalMs: number = 3000) {
    stopAutoRefresh()
    refreshTimer = setInterval(() => {
      fetchTasks()
    }, intervalMs)
  }

  function stopAutoRefresh() {
    if (refreshTimer) {
      clearInterval(refreshTimer)
      refreshTimer = null
    }
  }

  function setFilter(status?: TaskStatus, taskType?: TaskType) {
    currentStatus.value = status
    currentType.value = taskType
    currentPage.value = 1
    fetchTasks()
  }

  function setPage(page: number) {
    currentPage.value = page
    fetchTasks()
  }

  onUnmounted(() => {
    stopAutoRefresh()
  })

  return {
    tasks,
    total,
    loading,
    error,
    currentStatus,
    currentType,
    currentPage,
    pageSize,
    fetchTasks,
    startAutoRefresh,
    stopAutoRefresh,
    setFilter,
    setPage
  }
}
