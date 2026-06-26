import axios from 'axios'
import { ElMessage } from 'element-plus'
import {
  emitManufacturingError,
  type ErrorDialogPayload,
} from '@/composables/useErrorBus'
import { isNetworkError, shouldShowConflictDialog } from '@/utils/error-handler'

export type { ErrorDialogPayload }

const http = axios.create({
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器：自动携带 Authorization header
http.interceptors.request.use(
  (config) => {
    // 从 localStorage 恢复 token（兼容刷新页面后 token 丢失）
    const stored = localStorage.getItem('auth_token')
    const token = stored || ''
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
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
        emitManufacturingError(payload)
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

    if (response) {
      const status = response.status
      const data = response.data || {}

      if (status === 401) {
        // 桌面应用自动登录，401 不弹错误提示（避免初始化阶段干扰）
        return Promise.reject(error)
      }

      if (status === 500) {
        ElMessage.error('系统内部错误，请联系管理员')
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
        emitManufacturingError(payload)
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
