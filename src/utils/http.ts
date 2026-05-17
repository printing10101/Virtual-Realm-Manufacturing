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
  (error) => {
    if (isNetworkError(error)) {
      ElMessage.error('网络连接错误，请检查网络状态后重试')
      return Promise.reject(error)
    }

    const response = error.response
    if (response) {
      const status = response.status
      const data = response.data || {}

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
