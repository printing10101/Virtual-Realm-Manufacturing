/**
 * 确认对话框执行
 * 消除 ElMessageBox.confirm → API call → success/error message → reload 重复模式
 */

import { ElMessage, ElMessageBox } from 'element-plus'

export interface ConfirmOptions {
  /** 确认对话框标题 */
  title?: string
  /** 确认对话框消息 */
  message: string
  /** 对话框类型 */
  type?: 'warning' | 'error' | 'info' | 'success'
  /** 确认按钮文本 */
  confirmText?: string
  /** 取消按钮文本 */
  cancelText?: string
}

/**
 * 显示确认对话框并在用户确认后执行异步操作
 * @param options - 确认对话框配置
 * @param action - 要执行的异步操作
 * @param onSuccess - 成功回调，接收操作返回值
 * @param onError - 错误回调（未提供时使用ElMessage.error）
 */
export async function confirmAndExecute<T = unknown>(
  options: ConfirmOptions,
  action: () => Promise<T>,
  onSuccess?: (result: T) => void,
  onError?: (error: unknown) => void
): Promise<void> {
  const {
    title = '确认',
    message,
    type = 'warning',
    confirmText = '确定',
    cancelText = '取消',
  } = options

  try {
    await ElMessageBox.confirm(message, title, {
      confirmButtonText: confirmText,
      cancelButtonText: cancelText,
      type,
    })

    const result = await action()
    if (onSuccess) {
      onSuccess(result)
    }
  } catch (e: unknown) {
    // User cancelled
    if (e !== 'cancel' && onError) {
      onError(e)
    }
  }
}

/**
 * 带成功消息提示的确认执行
 * @param options - 确认对话框配置
 * @param action - 要执行的异步操作
 * @param successMessage - 成功后显示的消息文本
 */
export async function confirmWithSuccessMessage(
  options: ConfirmOptions,
  action: () => Promise<unknown>,
  successMessage: string
): Promise<void> {
  return confirmAndExecute(
    options,
    action,
    () => { ElMessage.success(successMessage) }
  )
}
