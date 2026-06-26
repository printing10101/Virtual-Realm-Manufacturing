import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'

export type UserRole = 'admin' | 'operator' | 'viewer'

interface UserInfo {
  id: string
  username: string
  role: UserRole
  permissions: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'))
  const user = ref<UserInfo | null>(null)

  const isAuthenticated = computed(() => !!token.value)
  const userRole = computed(() => user.value?.role ?? 'viewer')
  const permissions = computed(() => user.value?.permissions ?? [])

  function isAdmin() {
    return userRole.value === 'admin'
  }

  function hasPermission(perm: string) {
    return permissions.value.includes(perm)
  }

  async function login(username: string, password: string) {
    try {
      const res = await http.post('/api/v1/auth/login', { username, password })
      const data = res.data
      if (data.code === 0 && data.data) {
        token.value = data.data.access_token
        localStorage.setItem('auth_token', data.data.access_token)
        user.value = {
          id: data.data.user?.username ?? '',
          username: data.data.user?.username ?? username,
          role: (data.data.user?.role as UserRole) ?? 'viewer',
          permissions: data.data.user?.permissions ?? [],
        }
        return true
      }
      return false
    } catch {
      return false
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('auth_token')
  }

  function setToken(t: string) {
    token.value = t
    localStorage.setItem('auth_token', t)
  }

  function setUser(info: UserInfo) {
    user.value = info
  }

  return {
    token,
    user,
    isAuthenticated,
    userRole,
    permissions,
    isAdmin,
    hasPermission,
    login,
    logout,
    setUser,
    setToken,
  }
})
