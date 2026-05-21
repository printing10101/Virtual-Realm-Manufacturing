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
export function extractErrorMessage(error: any, fallback = '操作失败'): string {
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
export function isNetworkError(error: any): boolean {
  return (
    error?.code === 'ERR_NETWORK' ||
    error?.code === 'ECONNABORTED' ||
    error?.message === 'Network Error' ||
    error?.message?.includes('timeout') ||
    error?.message?.includes('Network Error')
  )
}

/**
 * 格式化网络错误消息（带HTTP状态码）
 */
export function formatNetworkError(error: any): string {
  const status = error.response?.status
  if (status) {
    return `请求失败 (${status}): ${extractErrorMessage(error)}`
  }
  if (isNetworkError(error)) {
    return '网络连接错误，请检查网络后重试'
  }
  return extractErrorMessage(error)
}
