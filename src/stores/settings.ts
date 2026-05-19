import { defineStore } from 'pinia'
import { ref, watch } from 'vue'

export interface LogSettings {
  logLevel: 'DEBUG' | 'INFO' | 'WARN' | 'ERROR'
  maxFileSizeMB: number
  retentionDays: number
  exportDays: number
}

export interface AppSettings {
  aiMode: 'local' | 'cloud'
  localModel: string
  device: 'cpu' | 'cuda'
  offlineMode: boolean
  logSettings: LogSettings
}

const STORAGE_KEY = 'lingjing_settings'

function getDefaultLogSettings(): LogSettings {
  return {
    logLevel: 'INFO',
    maxFileSizeMB: 50,
    retentionDays: 30,
    exportDays: 7,
  }
}

function loadSettings(): AppSettings {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (raw) {
      const parsed = JSON.parse(raw)
      return {
        ...getDefaultSettings(),
        ...parsed,
        logSettings: {
          ...getDefaultLogSettings(),
          ...(parsed.logSettings || {}),
        },
      }
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
    logSettings: getDefaultLogSettings(),
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

  function updateLogSettings(partial: Partial<LogSettings>) {
    settings.value.logSettings = {
      ...settings.value.logSettings,
      ...partial,
    }
  }

  return { settings, saveSettings, resetSettings, updateLogSettings }
})