import { ElMessage } from 'element-plus'

export enum AppErrorCode {
  NETWORK_ERROR = 'NETWORK_ERROR',
  FILE_NOT_FOUND = 'FILE_NOT_FOUND',
  PERMISSION_DENIED = 'PERMISSION_DENIED',
  AI_SERVICE_UNAVAILABLE = 'AI_SERVICE_UNAVAILABLE',
  CAD_GENERATION_FAILED = 'CAD_GENERATION_FAILED',
  INVALID_INPUT = 'INVALID_INPUT',
  UNKNOWN_ERROR = 'UNKNOWN_ERROR'
}

const ERROR_MESSAGES: Record<AppErrorCode, string> = {
  [AppErrorCode.NETWORK_ERROR]: '网络连接失败，请检查网络设置',
  [AppErrorCode.FILE_NOT_FOUND]: '文件未找到',
  [AppErrorCode.PERMISSION_DENIED]: '权限不足，无法执行此操作',
  [AppErrorCode.AI_SERVICE_UNAVAILABLE]: 'AI 服务不可用，请检查 Ollama 是否运行',
  [AppErrorCode.CAD_GENERATION_FAILED]: 'CAD 生成失败，请检查输入参数',
  [AppErrorCode.INVALID_INPUT]: '输入参数无效',
  [AppErrorCode.UNKNOWN_ERROR]: '操作失败，请重试'
}

export class AppError extends Error {
  public code: AppErrorCode
  public details?: Record<string, unknown>

  constructor(code: AppErrorCode, message?: string, details?: Record<string, unknown>) {
    super(message || ERROR_MESSAGES[code])
    this.name = 'AppError'
    this.code = code
    this.details = details
  }
}

export function createAppError(error: unknown): AppError {
  if (error instanceof AppError) {
    return error
  }

  if (error instanceof Error) {
    const msg = error.message.toLowerCase()
    
    if (msg.includes('network') || msg.includes('fetch') || msg.includes('connection')) {
      return new AppError(AppErrorCode.NETWORK_ERROR, error.message)
    }
    if (msg.includes('not found') || msg.includes('不存在')) {
      return new AppError(AppErrorCode.FILE_NOT_FOUND, error.message)
    }
    if (msg.includes('permission') || msg.includes('denied') || msg.includes('拒绝')) {
      return new AppError(AppErrorCode.PERMISSION_DENIED, error.message)
    }
    if (msg.includes('ollama') || msg.includes('ai') || msg.includes('model')) {
      return new AppError(AppErrorCode.AI_SERVICE_UNAVAILABLE, error.message)
    }
    if (msg.includes('cad') || msg.includes('3d') || msg.includes('model')) {
      return new AppError(AppErrorCode.CAD_GENERATION_FAILED, error.message)
    }
    
    return new AppError(AppErrorCode.UNKNOWN_ERROR, error.message)
  }

  return new AppError(AppErrorCode.UNKNOWN_ERROR, String(error))
}

export function handleError(error: unknown, showToast = true): AppError {
  const appError = createAppError(error)
  
  if (showToast) {
    ElMessage.error(appError.message)
  }
  
  console.error(`[AppError] ${appError.code}: ${appError.message}`, appError.details || appError.stack)
  
  return appError
}

export async function safeExecute<T>(
  fn: () => Promise<T>,
  errorHandler?: (error: AppError) => void
): Promise<T | null> {
  try {
    return await fn()
  } catch (error) {
    const appError = handleError(error)
    errorHandler?.(appError)
    return null
  }
}
