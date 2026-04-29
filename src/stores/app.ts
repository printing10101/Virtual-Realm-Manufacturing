import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const errorMessage = ref('')
  const statusMessage = ref('就绪')
  const currentTheme = ref<string>('light')
  const currentLanguage = ref<string>('zh-CN')
  const sidebarCollapsed = ref<boolean>(false)

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

  const toggleTheme = () => {
    currentTheme.value = currentTheme.value === 'light' ? 'dark' : 'light'
  }

  const setLanguage = (lang: string) => {
    currentLanguage.value = lang
  }

  const toggleSidebar = () => {
    sidebarCollapsed.value = !sidebarCollapsed.value
  }

  return {
    loading,
    errorMessage,
    statusMessage,
    currentTheme,
    currentLanguage,
    sidebarCollapsed,
    setLoading,
    setError,
    setStatus,
    clearError,
    toggleTheme,
    setLanguage,
    toggleSidebar
  }
}, {
  persist: true
})
