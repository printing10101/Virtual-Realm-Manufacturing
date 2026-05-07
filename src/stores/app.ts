import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useAppStore = defineStore('app', () => {
  const count = ref(0)
  const theme = ref('light')

  function increment() {
    count.value++
  }

  function setTheme(newTheme: string) {
    theme.value = newTheme
  }

  return { count, theme, increment, setTheme }
})
