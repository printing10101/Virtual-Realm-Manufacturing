/**
 * API错误处理工具函数
 */

/**
 * 从API错误响应中提取用户友好的错误消息
 * 优先顺序: response.data.message > response.data.detail > error.message
 * @param error - axios错误对象或任意错误
 * @param fallback - 当无法提取时的回退消息
 * @returns 错误消息字符串
 */
export function extractErrorMessage(error: unknown, fallback = '操作失败'): string {
  if (!error) return fallback

  // Axios response errors
  const data = error.response?.data
  if (data) {
    if (data.message) return data.message
    if (data.detail) {
      if (typeof data.detail === 'string') return data.detail
      if (data.detail.message) return data.detail.message
    }
  }

  // Generic error
  if (typeof error === 'string') return error
  if (error.message) return error.message

  return fallback
}

/**
 * 判断是否为网络错误
 */
export function isNetworkError(error: unknown): boolean {
  if (!error) return false
  const err = error as Record<string, unknown>
  return (
    err.code === 'ERR_NETWORK' ||
    err.code === 'ECONNABORTED' ||
    err.message === 'Network Error' ||
    (typeof err.message === 'string' && err.message.includes('timeout')) ||
    (typeof err.message === 'string' && err.message.includes('Network Error'))
  )
}

/**
 * 格式化网络错误消息（带HTTP状态码）
 */
export function formatNetworkError(error: unknown): string {
  const err = error as Record<string, unknown>
  const response = err.response as Record<string, unknown> | undefined
  const status = response?.status as number | undefined
  if (status) {
    return `请求失败 (${status}): ${extractErrorMessage(error)}`
  }
  if (isNetworkError(error)) {
    return '网络连接错误，请检查网络后重试'
  }
  return extractErrorMessage(error)
}
