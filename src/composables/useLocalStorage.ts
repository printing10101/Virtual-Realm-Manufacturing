/**
 * localStorage持久化状态管理
 * 消除各处重复的 localStorage.getItem/setItem + JSON.parse/stringify + try/catch 模式
 */

import { ref, Ref, watch } from 'vue'

export interface UseLocalStorageOptions<T> {
  /** 是否自动持久化（watch变化自动保存） */
  autoSave?: boolean
  /** 深度监听（配合autoSave） */
  deep?: boolean
}

/**
 * 创建与localStorage同步的响应式状态
 * @param key - localStorage键名
 * @param defaults - 默认值
 * @param options - 配置项
 * @returns { value, save, reset, clear }
 */
export function useLocalStorage<T>(
  key: string,
  defaults: T,
  options: UseLocalStorageOptions<T> = {}
): {
  value: Ref<T>
  save: () => void
  reset: () => void
  clear: () => void
} {
  const { autoSave = false, deep = true } = options

  // Load from storage
  function load(): T {
    try {
      const raw = localStorage.getItem(key)
      if (raw) {
        const parsed = JSON.parse(raw) as T
        // Merge with defaults to handle schema changes
        if (typeof defaults === 'object' && defaults !== null && !Array.isArray(defaults)) {
          return { ...defaults, ...parsed }
        }
        return parsed
      }
    } catch {
      // ignore parse errors
    }
    return defaults
  }

  const value = ref(load()) as Ref<T>

  function save() {
    try {
      localStorage.setItem(key, JSON.stringify(value.value))
    } catch {
      console.warn(`Failed to save to localStorage: ${key}`)
    }
  }

  function reset() {
    value.value = load()
  }

  function clear() {
    localStorage.removeItem(key)
    value.value = defaults
  }

  // Auto-save on change
  if (autoSave) {
    watch(value, save, { deep })
  }

  return { value, save, reset, clear }
}
