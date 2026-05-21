/**
 * 统一的异步操作Loading管理
 * 消除 loading.value = true → try → finally { loading.value = false } 重复模式
 */

import { Ref, ref } from 'vue'

export interface AsyncOperationState {
  loading: Ref<boolean>
  error: Ref<string | null>
}

/**
 * 创建可复用的异步操作状态
 * @param initialLoading - 初始loading状态，默认false
 * @returns { loading, error, execute, reset } - execute用于执行异步函数并自动管理loading/error
 */
export function useAsyncOperation(initialLoading = false) {
  const loading = ref(initialLoading)
  const error = ref<string | null>(null)

  /**
   * 执行异步函数并自动管理loading/error状态
   * @param fn - 要执行的异步函数
   * @returns 异步函数的返回值，如果发生异常则返回undefined
   */
  async function execute<T>(fn: () => Promise<T>): Promise<T | undefined> {
    loading.value = true
    error.value = null
    try {
      return await fn()
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : '操作失败'
      error.value = message
      return undefined
    } finally {
      loading.value = false
    }
  }

  /**
   * 重置异步操作状态
   */
  function reset() {
    loading.value = false
    error.value = null
  }

  return { loading, error, execute, reset }
}

/**
 * 创建带loading管理的状态ref
 * 适用于需要loading+error+data完整状态管理的场景
 * @param fetchFn - 获取数据的异步函数
 * @param initialData - 初始数据值，默认null
 * @returns { data, loading, error, fetch, reset }
 */
export function useAsyncState<T>(fetchFn: () => Promise<T>, initialData: T | null = null) {
  const { loading, error, execute } = useAsyncOperation()
  const data = ref<T | null>(initialData) as Ref<T | null>

  /**
   * 执行数据获取并更新data
   * @returns 更新后的data值
   */
  async function fetch(): Promise<T | null> {
    const result = await execute(fetchFn)
    if (result !== undefined) {
      data.value = result
    }
    return data.value
  }

  /**
   * 重置所有状态到初始值
   */
  function reset() {
    data.value = initialData
    loading.value = false
    error.value = null
  }

  return { data, loading, error, fetch, reset }
}
