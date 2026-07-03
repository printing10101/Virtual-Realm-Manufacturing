import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export type UserRole = 'admin' | 'operator' | 'viewer'

interface UserInfo {
  id: string
  username: string
  role: UserRole
  permissions: string[]
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('auth_token'))
  // 刷新页面后从 localStorage 恢复用户信息，避免权限判断失真
  const _storedUser = localStorage.getItem('auth_user')
  const user = ref<UserInfo | null>(_storedUser ? JSON.parse(_storedUser) : null)

  const isAuthenticated = computed(() => !!token.value)
  const userRole = computed(() => user.value?.role ?? 'viewer')
  const permissions = computed(() => user.value?.permissions ?? [])

  function isAdmin() {
    return userRole.value === 'admin'
  }

  function hasPermission(perm: string) {
    return permissions.value.includes(perm)
  }

  async function login(username: string, password: string): Promise<{ success: boolean; error?: string }> {
    try {
      const res = await http.post(buildApiPath(API_CONFIG.AUTH, '/login'), { username, password })
      const data = res.data
      if (data.code === 0 && data.data) {
        token.value = data.data.access_token
        localStorage.setItem('auth_token', data.data.access_token)
        const userInfo: UserInfo = {
          id: data.data.user?.username ?? '',
          username: data.data.user?.username ?? username,
          role: (data.data.user?.role as UserRole) ?? 'viewer',
          permissions: data.data.user?.permissions ?? [],
        }
        user.value = userInfo
        localStorage.setItem('auth_user', JSON.stringify(userInfo))
        return { success: true }
      }
      return { success: false, error: data.message || '登录失败' }
    } catch (err) {
      const msg = (err as { response?: { data?: { message?: string } } })?.response?.data?.message
        || (err instanceof Error ? err.message : '网络错误，登录失败')
      return { success: false, error: msg }
    }
  }

  function logout() {
    token.value = null
    user.value = null
    localStorage.removeItem('auth_token')
    localStorage.removeItem('auth_user')
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
