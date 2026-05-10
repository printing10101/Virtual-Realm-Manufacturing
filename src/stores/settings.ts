import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export interface AppSettings {
  aiMode: 'local' | 'cloud'
  localModel: string
  device: 'cpu' | 'cuda'
  offlineMode: boolean
}

const STORAGE_KEY = 'lingjing_settings'

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      return { ...getDefaultSettings(), ...JSON.parse(raw) }
    }
  } catch {
    // ignore parse errors
  }
  return getDefaultSettings()
}

function getDefaultSettings(): AppSettings {
  return {
    aiMode: 'local',
    localModel: 'qwen2.5:7b',
    device: 'cpu',
    offlineMode: false,
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings>(loadSettings())

  watch(settings, (val) => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(val))
  }, { deep: true })

  function saveSettings() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(settings.value))
  }

  function resetSettings() {
    settings.value = getDefaultSettings()
  }

  return { settings, saveSettings, resetSettings }
})