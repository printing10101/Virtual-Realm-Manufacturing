import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const theme = ref<'light' | 'dark'>('light')
  const sidebarCollapsed = ref(false)
  const currentTaskId = ref<string | null>(null)

  function setTheme(newTheme: 'light' | 'dark') {
    theme.value = newTheme
  }

  function toggleSidebar() {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  function setCurrentTask(id: string | null) {
    currentTaskId.value = id
  }

  return { theme, sidebarCollapsed, currentTaskId, setTheme, toggleSidebar, setCurrentTask }
})
