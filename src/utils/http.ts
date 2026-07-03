import axios, { type AxiosRequestConfig, type InternalAxiosRequestConfig } from 'axios'
import { ElMessage } from 'element-plus'
import {
  emitManufacturingError,
  type ErrorDialogPayload,
} from '@/composables/useErrorBus'
import { isNetworkError, shouldShowConflictDialog } from '@/utils/error-handler'

export type { ErrorDialogPayload }

/** 应用初始化阶段标记：首页加载后端健康检查完成前，抑制重复错误弹窗 */
let appInitializing = true
/** 用于外部设置初始化完成 */
export function setHttpReady() { appInitializing = false }

// =============================================================================
// 请求取消支持（AbortController 封装）
// =============================================================================

/**
 * 创建可取消的请求信号。
 *
 * 用法：
 * ```ts
 * const { signal, cancel } = createCancelToken()
 * http.get('/api/data', { signal })
 * // 页面卸载时：
 * cancel('组件卸载，取消请求')
 * ```
 */
export function createCancelToken() {
  const controller = new AbortController()
  return {
    signal: controller.signal,
    cancel: (reason?: string) => controller.abort(reason),
  }
}

// =============================================================================
// GET 请求自动重试（指数退避）
// =============================================================================

/** 可重试的 HTTP 状态码 */
const RETRYABLE_STATUS = new Set([408, 429, 500, 502, 503, 504])

/** 最大重试次数 */
const MAX_RETRIES = 2

/** 重试基础延迟（毫秒），实际延迟 = base * 2^attempt */
const RETRY_BASE_DELAY_MS = 500

/**
 * 判断错误是否可重试：网络错误或特定 5xx 状态码。
 */
function isRetryableError(error: unknown): boolean {
  if (isNetworkError(error)) return true
  const status = (error as { response?: { status?: number } })?.response?.status
  return typeof status === 'number' && RETRYABLE_STATUS.has(status)
}

/**
 * 计算重试延迟（指数退避 + 抖动）。
 */
function computeRetryDelay(attempt: number): number {
  const jitter = Math.random() * 200
  return RETRY_BASE_DELAY_MS * Math.pow(2, attempt) + jitter
}

// 扩展 AxiosRequestConfig 以支持自定义重试标记
declare module 'axios' {
  interface AxiosRequestConfig {
    /** 跳过自动重试（即使满足重试条件也不重试） */
    _skipRetry?: boolean
    /** 已重试次数（内部使用） */
    _retryCount?: number
  }
}

// =============================================================================
// Axios 实例
// =============================================================================

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

// 响应拦截器：业务错误码处理 + GET 自动重试
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
    // ===== GET 自动重试 =====
    const config = error.config as InternalAxiosRequestConfig | undefined
    if (
      config &&
      !config._skipRetry &&
      config.method?.toLowerCase() === 'get' &&
      isRetryableError(error)
    ) {
      const retryCount = config._retryCount ?? 0
      if (retryCount < MAX_RETRIES) {
        config._retryCount = retryCount + 1
        const delay = computeRetryDelay(retryCount)
        await new Promise((resolve) => setTimeout(resolve, delay))
        return http.request(config)
      }
    }

    // ===== 错误处理（原有逻辑） =====

    // 初始化阶段静默处理网络/服务器错误，避免批量弹出
    if (appInitializing && (isNetworkError(error) || !error.response || error.response?.status >= 500)) {
      return Promise.reject(error)
    }

    if (isNetworkError(error)) {
      // 重试耗尽后才提示
      const retryCount = config?._retryCount ?? 0
      if (retryCount >= MAX_RETRIES) {
        ElMessage.error(`网络连接错误，已重试 ${retryCount} 次仍失败，请检查网络状态`)
      } else {
        ElMessage.error('网络连接错误，请检查网络状态后重试')
      }
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
