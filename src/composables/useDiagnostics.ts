/**
 * 诊断信息收集 Composable
 * 
 * 提供 Vue 组件级别的诊断信息收集和管理功能：
 * - 响应式的诊断信息状态
 * - 错误上下文收集
 * - 诊断文本生成和复制
 * - 与组件生命周期集成
 * 
 * 用法示例：
 * ```vue
 * <script setup>
 * import { useDiagnostics } from '@/composables/useDiagnostics'
 * 
 * const { 
 *   diagnosticContext, 
 *   collectError, 
 *   copyDiagnostic,
 *   hasDiagnostic 
 * } = useDiagnostics()
 * 
 * // 当发生错误时收集诊断信息
 * function handleError(error) {
 *   collectError(error)
 * }
 * 
 * // 用户点击复制诊断信息
 * async function handleCopy() {
 *   const success = await copyDiagnostic()
 *   if (success) {
 *     // 显示成功提示
 *   }
 * }
 * </script>
 * ```
 */

import { ref, computed, readonly, onBeforeUnmount, type Ref, type ComputedRef } from 'vue'
import {
  type StandardError,
  type DiagnosticContext,
  buildErrorFromResponse,
  buildErrorFromAxiosError,
  buildErrorFromError,
  collectDiagnosticContext,
  generateDiagnosticText,
  copyDiagnosticText,
} from '@/utils/error-handler'

// ============================================================
// 类型定义
// ============================================================

export interface UseDiagnosticsOptions {
  /** 组件名称，用于标识诊断信息来源 */
  componentName?: string
  /** 是否自动收集全局错误 */
  autoCollectGlobalErrors?: boolean
  /** 最大保留的诊断信息数量 */
  maxHistorySize?: number
}

export interface DiagnosticHistoryEntry {
  /** 唯一标识 */
  id: string
  /** 诊断上下文 */
  context: DiagnosticContext
  /** 收集时间 */
  collectedAt: string
  /** 组件来源 */
  component?: string
}

export interface UseDiagnosticsReturn {
  /** 当前诊断上下文（只读） */
  diagnosticContext: Readonly<Ref<DiagnosticContext | null>>
  /** 诊断历史列表（只读） */
  diagnosticHistory: Readonly<Ref<DiagnosticHistoryEntry[]>>
  /** 是否有诊断信息 */
  hasDiagnostic: ComputedRef<boolean>
  /** 收集错误信息 */
  collectError: (error: any, extra?: Record<string, any>) => string
  /** 从 API 响应收集错误 */
  collectFromResponse: (response: any, extra?: Record<string, any>) => string
  /** 从 Axios 错误收集 */
  collectFromAxiosError: (error: any, extra?: Record<string, any>) => string
  /** 从普通 Error 收集 */
  collectFromError: (error: Error, code?: number, message?: string, extra?: Record<string, any>) => string
  /** 复制当前诊断信息 */
  copyDiagnostic: (extra?: Record<string, any>) => Promise<boolean>
  /** 复制指定的历史诊断信息 */
  copyHistoryEntry: (id: string) => Promise<boolean>
  /** 清空当前诊断信息 */
  clearDiagnostic: () => void
  /** 清空所有历史记录 */
  clearHistory: () => void
  /** 生成当前诊断文本 */
  generateText: (extra?: Record<string, any>) => string
}

// ============================================================
// Composable 实现
// ============================================================

let historyIdCounter = 0

/**
 * 诊断信息收集 composable
 */
export function useDiagnostics(options: UseDiagnosticsOptions = {}): UseDiagnosticsReturn {
  const {
    componentName,
    autoCollectGlobalErrors = false,
    maxHistorySize = 10,
  } = options

  // 当前诊断上下文
  const currentContext = ref<DiagnosticContext | null>(null)
  
  // 诊断历史记录
  const history = ref<DiagnosticHistoryEntry[]>([])

  // 是否有诊断信息
  const hasDiagnostic = computed(() => currentContext.value !== null)

  /**
   * 添加历史记录
   */
  function addToHistory(context: DiagnosticContext): string {
    const id = `diag-${++historyIdCounter}-${Date.now()}`
    const entry: DiagnosticHistoryEntry = {
      id,
      context,
      collectedAt: new Date().toISOString(),
      component: componentName,
    }
    
    history.value.unshift(entry)
    
    // 限制历史记录数量
    if (history.value.length > maxHistorySize) {
      history.value = history.value.slice(0, maxHistorySize)
    }
    
    return id
  }

  /**
   * 收集标准化错误
   */
  function collectStandardError(error: StandardError, extra?: Record<string, any>): string {
    const context = collectDiagnosticContext(error, extra)
    currentContext.value = context
    const id = addToHistory(context)
    return id
  }

  /**
   * 收集任意错误
   */
  function collectError(error: any, extra?: Record<string, any>): string {
    let standardError: StandardError
    
    if (error && typeof error === 'object' && 'code' in error && 'errorCode' in error) {
      // 已经是 StandardError
      standardError = error as StandardError
    } else if (error?.response) {
      // Axios 错误
      standardError = buildErrorFromAxiosError(error)
    } else if (error instanceof Error) {
      // 普通 Error
      standardError = buildErrorFromError(error)
    } else {
      // 其他
      standardError = buildErrorFromError(new Error(String(error)))
    }
    
    return collectStandardError(standardError, extra)
  }

  /**
   * 从 API 响应收集错误
   */
  function collectFromResponse(response: any, extra?: Record<string, any>): string {
    const standardError = buildErrorFromResponse(response)
    return collectStandardError(standardError, extra)
  }

  /**
   * 从 Axios 错误收集
   */
  function collectFromAxiosError(error: any, extra?: Record<string, any>): string {
    const standardError = buildErrorFromAxiosError(error)
    return collectStandardError(standardError, extra)
  }

  /**
   * 从普通 Error 收集
   */
  function collectFromError(
    error: Error, 
    code?: number, 
    message?: string, 
    extra?: Record<string, any>
  ): string {
    const standardError = buildErrorFromError(error, code, message)
    return collectStandardError(standardError, extra)
  }

  /**
   * 复制当前诊断信息
   */
  async function copyDiagnostic(extra?: Record<string, any>): Promise<boolean> {
    if (!currentContext.value) {
      return false
    }
    
    // 如果有额外信息，合并到上下文中
    let context = currentContext.value
    if (extra && Object.keys(extra).length > 0) {
      context = {
        ...context,
        extra: { ...context.extra, ...extra },
      }
    }
    
    return copyDiagnosticText(context)
  }

  /**
   * 复制指定的历史诊断信息
   */
  async function copyHistoryEntry(id: string): Promise<boolean> {
    const entry = history.value.find(h => h.id === id)
    if (!entry) {
      return false
    }
    return copyDiagnosticText(entry.context)
  }

  /**
   * 清空当前诊断信息
   */
  function clearDiagnostic(): void {
    currentContext.value = null
  }

  /**
   * 清空所有历史记录
   */
  function clearHistory(): void {
    history.value = []
  }

  /**
   * 生成当前诊断文本
   */
  function generateText(extra?: Record<string, any>): string {
    if (!currentContext.value) {
      return ''
    }
    
    let context = currentContext.value
    if (extra && Object.keys(extra).length > 0) {
      context = {
        ...context,
        extra: { ...context.extra, ...extra },
      }
    }
    
    return generateDiagnosticText(context)
  }

  // 自动收集全局错误
  if (autoCollectGlobalErrors && typeof window !== 'undefined') {
    const handler = (event: PromiseRejectionEvent | ErrorEvent) => {
      const error = 'reason' in event ? event.reason : event.error
      collectError(error, { source: 'global' })
    }
    
    window.addEventListener('unhandledrejection', handler as EventListener)
    window.addEventListener('error', handler as EventListener)
    
    // 组件卸载时清理全局错误监听器
    onBeforeUnmount(() => {
      window.removeEventListener('unhandledrejection', handler as EventListener)
      window.removeEventListener('error', handler as EventListener)
    })
  }

  return {
    diagnosticContext: readonly(currentContext) as Readonly<Ref<DiagnosticContext | null>>,
    diagnosticHistory: readonly(history) as Readonly<Ref<DiagnosticHistoryEntry[]>>,
    hasDiagnostic,
    collectError,
    collectFromResponse,
    collectFromAxiosError,
    collectFromError,
    copyDiagnostic: copyDiagnostic,
    copyHistoryEntry,
    clearDiagnostic,
    clearHistory,
    generateText,
  }
}

/**
 * 简化版：仅用于复制诊断信息的 composable
 * 
 * 适用于只需要在错误展示界面提供"复制诊断信息"按钮的场景
 */
export function useDiagnosticCopy(error: Ref<StandardError | null>) {
  const isCopying = ref(false)
  const copySuccess = ref(false)

  async function copy(): Promise<boolean> {
    if (!error.value) {
      return false
    }

    isCopying.value = true
    copySuccess.value = false

    try {
      const context = collectDiagnosticContext(error.value)
      const success = await copyDiagnosticText(context)
      copySuccess.value = success
      
      // 2秒后重置成功状态
      if (success) {
        setTimeout(() => {
          copySuccess.value = false
        }, 2000)
      }
      
      return success
    } finally {
      isCopying.value = false
    }
  }

  return {
    isCopying: readonly(isCopying),
    copySuccess: readonly(copySuccess),
    copy,
  }
}
