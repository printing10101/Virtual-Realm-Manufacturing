import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'

export const usePermissionsStore = defineStore('permissions', () => {
  const permissions = ref<string[]>([])
  const loaded = ref(false)
  const loading = ref(false)

  const hasPermission = (code: string): boolean => {
    return permissions.value.includes(code)
  }

  const hasAnyPermission = (...codes: string[]): boolean => {
    return codes.some((c) => permissions.value.includes(c))
  }

  const hasAllPermissions = (...codes: string[]): boolean => {
    return codes.every((c) => permissions.value.includes(c))
  }

  async function fetchPermissions(): Promise<string[]> {
    if (loading.value) return permissions.value

    loading.value = true
    try {
      const res = await http.get('/api/v1/users/me/permissions')
      if (res.data?.code === 0 && res.data?.data) {
        permissions.value = res.data.data.user_permissions || []
      }
      loaded.value = true
      return permissions.value
    } catch {
      return permissions.value
    } finally {
      loading.value = false
    }
  }

  function clear() {
    permissions.value = []
    loaded.value = false
    loading.value = false
  }

  return {
    permissions,
    loaded,
    loading,
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    fetchPermissions,
    clear,
  }
})