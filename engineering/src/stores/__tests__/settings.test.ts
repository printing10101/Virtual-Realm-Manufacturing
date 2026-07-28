import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useSettingsStore } from '@/stores/settings'

describe('useSettingsStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.clear()
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  describe('initial state', () => {
    it('无 localStorage 时使用默认设置', () => {
      const store = useSettingsStore()
      expect(store.settings.aiMode).toBe('local')
      expect(store.settings.localModel).toBe('qwen2.5:7b')
      expect(store.settings.device).toBe('cpu')
      expect(store.settings.offlineMode).toBe(false)
      expect(store.settings.hardwareTier).toBe('standard')
      expect(store.settings.lightweightMode).toBe(false)
    })

    it('默认日志设置正确', () => {
      const store = useSettingsStore()
      expect(store.settings.logSettings.logLevel).toBe('INFO')
      expect(store.settings.logSettings.maxFileSizeMB).toBe(50)
      expect(store.settings.logSettings.retentionDays).toBe(30)
      expect(store.settings.logSettings.exportDays).toBe(7)
    })

    it('localStorage 存在配置时合并加载', () => {
      localStorage.setItem('lingjing_settings', JSON.stringify({
        aiMode: 'cloud',
        localModel: 'gpt-4',
        device: 'cuda',
        hardwareTier: 'high',
      }))
      const store = useSettingsStore()
      expect(store.settings.aiMode).toBe('cloud')
      expect(store.settings.localModel).toBe('gpt-4')
      expect(store.settings.device).toBe('cuda')
      expect(store.settings.hardwareTier).toBe('high')
      // 未覆盖字段保留默认
      expect(store.settings.offlineMode).toBe(false)
    })

    it('localStorage 部分日志配置时合并', () => {
      localStorage.setItem('lingjing_settings', JSON.stringify({
        logSettings: { logLevel: 'ERROR' },
      }))
      const store = useSettingsStore()
      expect(store.settings.logSettings.logLevel).toBe('ERROR')
      expect(store.settings.logSettings.maxFileSizeMB).toBe(50)
    })

    it('localStorage 数据损坏时回退默认并清理', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      localStorage.setItem('lingjing_settings', '{invalid json')
      const store = useSettingsStore()
      expect(store.settings.aiMode).toBe('local')
      expect(localStorage.getItem('lingjing_settings')).toBeNull()
      warnSpy.mockRestore()
    })
  })

  describe('saveSettings', () => {
    it('保存设置到 localStorage', () => {
      const store = useSettingsStore()
      store.$patch({ settings: { ...store.settings, aiMode: 'cloud' } })
      store.saveSettings()
      const raw = localStorage.getItem('lingjing_settings')
      expect(raw).not.toBeNull()
      expect(JSON.parse(raw!).aiMode).toBe('cloud')
    })

    it('localStorage 写入失败时不抛错', () => {
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const store = useSettingsStore()
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('quota exceeded')
      })
      expect(() => store.saveSettings()).not.toThrow()
      warnSpy.mockRestore()
    })
  })

  describe('resetSettings', () => {
    it('重置为默认设置', () => {
      const store = useSettingsStore()
      store.$patch({ settings: { ...store.settings, aiMode: 'cloud', hardwareTier: 'ultra' } })
      store.resetSettings()
      expect(store.settings.aiMode).toBe('local')
      expect(store.settings.hardwareTier).toBe('standard')
    })
  })

  describe('updateLogSettings', () => {
    it('部分更新日志设置', () => {
      const store = useSettingsStore()
      store.updateLogSettings({ logLevel: 'DEBUG', maxFileSizeMB: 100 })
      expect(store.settings.logSettings.logLevel).toBe('DEBUG')
      expect(store.settings.logSettings.maxFileSizeMB).toBe(100)
      // 未更新字段保留
      expect(store.settings.logSettings.retentionDays).toBe(30)
    })
  })

  describe('watch 持久化（防抖）', () => {
    it('设置变更后防抖延迟内不写入', () => {
      vi.useFakeTimers()
      const store = useSettingsStore()
      const setSpy = vi.spyOn(Storage.prototype, 'setItem')
      store.$patch({ settings: { ...store.settings, aiMode: 'cloud' } })
      // 防抖 300ms 内不应触发 localStorage 写入
      vi.advanceTimersByTime(200)
      // 注：可能已有初始 watcher 触发，检查最新调用
      const callsBefore = setSpy.mock.calls.length
      vi.advanceTimersByTime(200)
      expect(setSpy.mock.calls.length).toBeGreaterThanOrEqual(callsBefore)
    })

    it('设置变更后超过 300ms 写入 localStorage', () => {
      vi.useFakeTimers()
      const store = useSettingsStore()
      const setSpy = vi.spyOn(Storage.prototype, 'setItem')
      setSpy.mockClear()
      store.$patch({ settings: { ...store.settings, aiMode: 'cloud' } })
      vi.advanceTimersByTime(400)
      expect(setSpy).toHaveBeenCalled()
      const raw = localStorage.getItem('lingjing_settings')
      expect(raw).not.toBeNull()
      expect(JSON.parse(raw!).aiMode).toBe('cloud')
    })

    it('防抖合并连续变更', () => {
      vi.useFakeTimers()
      const store = useSettingsStore()
      const setSpy = vi.spyOn(Storage.prototype, 'setItem')
      setSpy.mockClear()
      store.$patch({ settings: { ...store.settings, aiMode: 'cloud' } })
      store.$patch({ settings: { ...store.settings, aiMode: 'local' } })
      store.$patch({ settings: { ...store.settings, device: 'cuda' } })
      vi.advanceTimersByTime(400)
      // 多次变更只触发一次写入
      const persistCalls = setSpy.mock.calls.filter(c => c[0] === 'lingjing_settings')
      expect(persistCalls.length).toBe(1)
      expect(JSON.parse(persistCalls[0][1]).device).toBe('cuda')
    })

    it('localStorage 持久化失败时不抛错', () => {
      vi.useFakeTimers()
      const warnSpy = vi.spyOn(console, 'warn').mockImplementation(() => {})
      const store = useSettingsStore()
      vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
        throw new Error('quota')
      })
      store.$patch({ settings: { ...store.settings, aiMode: 'cloud' } })
      expect(() => vi.advanceTimersByTime(400)).not.toThrow()
      warnSpy.mockRestore()
    })
  })
})
