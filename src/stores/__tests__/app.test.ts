import { describe, it, expect, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useAppStore } from '@/stores/app'

describe('useAppStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  describe('initial state', () => {
    it('has light theme by default', () => {
      const store = useAppStore()
      expect(store.theme).toBe('light')
    })

    it('has sidebar expanded by default', () => {
      const store = useAppStore()
      expect(store.sidebarCollapsed).toBe(false)
    })

    it('has no current task by default', () => {
      const store = useAppStore()
      expect(store.currentTaskId).toBeNull()
    })
  })

  describe('setTheme', () => {
    it('switches theme to dark', () => {
      const store = useAppStore()
      store.setTheme('dark')
      expect(store.theme).toBe('dark')
    })

    it('switches theme back to light', () => {
      const store = useAppStore()
      store.setTheme('dark')
      store.setTheme('light')
      expect(store.theme).toBe('light')
    })
  })

  describe('toggleSidebar', () => {
    it('collapses sidebar on first toggle', () => {
      const store = useAppStore()
      store.toggleSidebar()
      expect(store.sidebarCollapsed).toBe(true)
    })

    it('expands sidebar on second toggle', () => {
      const store = useAppStore()
      store.toggleSidebar()
      store.toggleSidebar()
      expect(store.sidebarCollapsed).toBe(false)
    })
  })

  describe('setCurrentTask', () => {
    it('sets current task id', () => {
      const store = useAppStore()
      store.setCurrentTask('task-123')
      expect(store.currentTaskId).toBe('task-123')
    })

    it('clears current task id with null', () => {
      const store = useAppStore()
      store.setCurrentTask('task-123')
      store.setCurrentTask(null)
      expect(store.currentTaskId).toBeNull()
    })
  })
})
