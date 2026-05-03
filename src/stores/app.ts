import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { Task } from '@/services/taskService'

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const errorMessage = ref('')
  const statusMessage = ref('就绪')
  const sidebarCollapsed = ref<boolean>(false)
  const taskPanelVisible = ref<boolean>(false)
  const selectedTask = ref<Task | null>(null)
  const taskStatusFilter = ref('')
  const taskTypeFilter = ref('')

  const setLoading = (value: boolean) => {
    loading.value = value
  }

  const setError = (message: string) => {
    errorMessage.value = message
    statusMessage.value = message
  }

  const setStatus = (message: string) => {
    statusMessage.value = message
    errorMessage.value = ''
  }

  const clearError = () => {
    errorMessage.value = ''
  }

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  const toggleTaskPanel = () => {
    taskPanelVisible.value = !taskPanelVisible.value
  }

  return {
    loading,
    errorMessage,
    statusMessage,
    sidebarCollapsed,
    taskPanelVisible,
    selectedTask,
    taskStatusFilter,
    taskTypeFilter,
    setLoading,
    setError,
    setStatus,
    clearError,
    toggleSidebar,
    toggleTaskPanel
  }
})
