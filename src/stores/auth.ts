import { defineStore } from 'pinia'
import { ref, computed } from 'vue'

export interface UserInfo {
  username: string
  role: string
  created_at: string
  last_login: string | null
}

interface LoginResponse {
  access_token: string
  refresh_token: string
  token_type: string
  user: UserInfo
}

interface RefreshResponse {
  access_token: string
  refresh_token: string
  token_type: string
}

const TOKEN_KEY = 'lingjing_access_token'
const REFRESH_KEY = 'lingjing_refresh_token'
const USER_KEY = 'lingjing_user'

function loadFromStorage<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key)
    return raw ? JSON.parse(raw) : null
  } catch {
    return null
  }
}

function saveToStorage(key: string, value: unknown) {
  localStorage.setItem(key, JSON.stringify(value))
}

function removeFromStorage(key: string) {
  localStorage.removeItem(key)
}

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref<string | null>(loadFromStorage(TOKEN_KEY))
  const refreshToken = ref<string | null>(loadFromStorage(REFRESH_KEY))
  const user = ref<UserInfo | null>(loadFromStorage(USER_KEY))

  const isAuthenticated = computed(() => !!accessToken.value && !!user.value)
  const isAdmin = computed(() => user.value?.role === 'admin')
  const currentUsername = computed(() => user.value?.username || '')

  let _refreshPromise: Promise<boolean> | null = null

  function setAuth(data: LoginResponse) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    user.value = data.user

    saveToStorage(TOKEN_KEY, data.access_token)
    saveToStorage(REFRESH_KEY, data.refresh_token)
    saveToStorage(USER_KEY, data.user)
  }

  function updateTokens(data: RefreshResponse) {
    accessToken.value = data.access_token
    refreshToken.value = data.refresh_token
    saveToStorage(TOKEN_KEY, data.access_token)
    saveToStorage(REFRESH_KEY, data.refresh_token)
  }

  function getAccessToken(): string | null {
    return accessToken.value
  }

  function getRefreshToken(): string | null {
    return refreshToken.value
  }

  async function tryRefreshToken(): Promise<boolean> {
    if (_refreshPromise) {
      return _refreshPromise
    }

    const stored = refreshToken.value
    if (!stored) return false

    _refreshPromise = (async () => {
      try {
        const { default: http } = await import('@/utils/http')
        const response = await http.post('/api/v1/auth/refresh', {
          refresh_token: stored,
        })

        if (response.data?.code === 0 && response.data?.data) {
          updateTokens(response.data.data)
          return true
        }
        return false
      } catch {
        return false
      } finally {
        _refreshPromise = null
      }
    })()

    return _refreshPromise
  }

  function logout() {
    const storedAccess = accessToken.value
    const storedRefresh = refreshToken.value

    accessToken.value = null
    refreshToken.value = null
    user.value = null

    removeFromStorage(TOKEN_KEY)
    removeFromStorage(REFRESH_KEY)
    removeFromStorage(USER_KEY)

    import('@/stores/permissions').then(({ usePermissionsStore }) => {
      usePermissionsStore().clear()
    }).catch(() => {})

    if (storedAccess || storedRefresh) {
      import('@/utils/http').then(({ default: http }) => {
        http.post('/api/v1/auth/logout', {
          access_token: storedAccess,
          refresh_token: storedRefresh,
        }).catch(() => {})
      })
    }
  }

  function loadFromCache() {
    accessToken.value = loadFromStorage(TOKEN_KEY)
    refreshToken.value = loadFromStorage(REFRESH_KEY)
    user.value = loadFromStorage(USER_KEY)
  }

  return {
    accessToken,
    refreshToken,
    user,
    isAuthenticated,
    isAdmin,
    currentUsername,
    setAuth,
    updateTokens,
    getAccessToken,
    getRefreshToken,
    tryRefreshToken,
    logout,
    loadFromCache,
  }
})