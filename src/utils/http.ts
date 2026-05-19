import axios from 'axios'
import { ElMessage } from 'element-plus'

function isNetworkError(err: any): boolean {
  return (
    err.code === 'ERR_NETWORK' ||
    err.code === 'ECONNABORTED' ||
    err.message === 'Network Error' ||
    err.message?.includes('timeout') ||
    err.message?.includes('Network Error')
  )
}

function shouldShowConflictDialog(data: any): boolean {
  return (
    data?.severity &&
    data?.error_code &&
    data?.suggestion
  )
}

interface ErrorDialogPayload {
  title: string
  code: string
  message: string
  severity: string
  detail: string
  suggestion: string
  recoverable: boolean
  adjusted_values?: Record<string, any>
}

const http = axios.create({
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

let isRefreshing = false
let failedQueue: Array<{
  resolve: (token: string) => void
  reject: (err: any) => void
}> = []

function processQueue(error: any, token: string | null = null) {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error)
    } else if (token) {
      prom.resolve(token)
    }
  })
  failedQueue = []
}

let _authStorePromise: Promise<any> | null = null

async function getAuthStore(): Promise<any> {
  if (!_authStorePromise) {
    _authStorePromise = import('@/stores/auth').then(m => m.useAuthStore())
  }
  return _authStorePromise
}

http.interceptors.request.use(
  async (config) => {
    try {
      const store = await getAuthStore()
      if (store) {
        const token = store.getAccessToken()
        if (token) {
          config.headers.Authorization = `Bearer ${token}`
        }
      }
    } catch {}
    return config
  },
  (error) => Promise.reject(error),
)

http.interceptors.response.use(
  (response) => {
    const data = response.data
    if (data && typeof data.code === 'number' && data.code !== 0) {
      if (shouldShowConflictDialog(data)) {
        const payload: ErrorDialogPayload = {
          title: data.message || '加工参数冲突',
          code: data.error_code || data.code,
          message: data.message || '操作异常',
          severity: data.severity || 'error',
          detail: data.detail || '',
          suggestion: data.suggestion || '',
          recoverable: data.recoverable || false,
          adjusted_values: data.adjusted_values,
        }
        window.dispatchEvent(
          new CustomEvent('manufacturing-error', { detail: payload }),
        )
      } else {
        ElMessage.error(data.message || '操作失败')
      }
      return Promise.reject(new Error(data.message || '操作失败'))
    }
    return response
  },
  async (error) => {
    if (isNetworkError(error)) {
      ElMessage.error('网络连接错误，请检查网络状态后重试')
      return Promise.reject(error)
    }

    const response = error.response
    const originalRequest = error.config

    if (response?.status === 401 && !originalRequest._retry) {
      const isAuthEndpoint = originalRequest.url?.includes('/api/v1/auth/')
      if (isAuthEndpoint) {
        try {
          const store = await getAuthStore()
          if (store) store.logout()
        } catch {}
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject })
        }).then((token) => {
          originalRequest.headers.Authorization = `Bearer ${token}`
          return http(originalRequest)
        })
      }

      originalRequest._retry = true
      isRefreshing = true

      let store: any = null
      try {
        store = await getAuthStore()
      } catch {}
      if (!store) {
        isRefreshing = false
        return Promise.reject(error)
      }

      try {
        const refreshed = await store.tryRefreshToken()
        if (refreshed) {
          const newToken = store.getAccessToken()
          processQueue(null, newToken)
          originalRequest.headers.Authorization = `Bearer ${newToken}`
          return http(originalRequest)
        } else {
          processQueue(error)
          store.logout()
          window.location.href = '/login'
          return Promise.reject(error)
        }
      } catch (refreshError) {
        processQueue(refreshError)
        store.logout()
        window.location.href = '/login'
        return Promise.reject(refreshError)
      } finally {
        isRefreshing = false
      }
    }

    if (response) {
      const status = response.status
      const data = response.data || {}

      if (status === 401) {
        ElMessage.error('登录已过期，请重新登录')
        const store = getAuthStore()
        if (store) store.logout()
        window.location.href = '/login'
        return Promise.reject(error)
      }

      if (status === 403) {
        ElMessage.error('权限不足，无法执行该操作')
        return Promise.reject(error)
      }

      if (status === 500) {
        ElMessage.error('系统内部错误，请联系管理员')
        if (import.meta.env.DEV) {
          console.warn('[DEV] Server 500 - error_id:', data?.detail?.error_id)
        }
        return Promise.reject(error)
      }

      if (shouldShowConflictDialog(data)) {
        const payload: ErrorDialogPayload = {
          title: data.message || '加工参数冲突',
          code: data.error_code || data.code,
          message: data.message || '操作异常',
          severity: data.severity || 'error',
          detail: data.detail || '',
          suggestion: data.suggestion || '',
          recoverable: data.recoverable || false,
          adjusted_values: data.adjusted_values,
        }
        window.dispatchEvent(
          new CustomEvent('manufacturing-error', { detail: payload }),
        )
        return Promise.reject(error)
      }

      const msg = data.message || `请求失败 (${status})`
      ElMessage.error(msg)
    } else {
      ElMessage.error('网络连接错误，请检查网络状态后重试')
    }
    return Promise.reject(error)
  },
)

export default http
export type { ErrorDialogPayload }