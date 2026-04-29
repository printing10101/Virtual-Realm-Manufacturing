import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import type { AppSettings } from '@/types/persistence'
import { getSettings, saveSettings } from '@/services/settings'

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings>({
    python_backend_url: 'http://localhost:8000',
    ollama_url: 'http://localhost:11434',
    default_model: 'qwen2.5-coder:7b',
    theme: 'light',
    auto_save: true,
    language: 'zh-CN'
  })
  const isLoaded = ref(false)

  const loadSettings = async () => {
    try {
      const loaded = await getSettings()
      settings.value = loaded
      isLoaded.value = true
    } catch (error) {
      console.error('Failed to load settings:', error)
      isLoaded.value = true
    }
  }

  const saveSettingsFn = async () => {
    try {
      await saveSettings(settings.value)
    } catch (error) {
      console.error('Failed to save settings:', error)
    }
  }

  const updateSetting = <K extends keyof AppSettings>(key: K, value: AppSettings[K]) => {
    settings.value[key] = value
  }

  watch(settings, () => {
    if (isLoaded.value && settings.value.auto_save) {
      saveSettingsFn()
    }
  }, { deep: true })

  return {
    settings,
    isLoaded,
    loadSettings,
    saveSettings: saveSettingsFn,
    updateSetting
  }
})
