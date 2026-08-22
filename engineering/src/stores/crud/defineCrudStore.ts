/**
 * P3-2 前端自主化：Store 封装层 —— CRUD Store 工厂。
 *
 * 将 Pinia setup store 常见的「列表 + 详情 + 分页 + 加载 + 错误」样板
 * 抽为通用工厂，业务 store 只需提供 API 函数，减少重复代码并统一行为：
 *   - 列表加载（分页/筛选，复用 P3-1 的页码钳制语义）
 *   - 详情加载
 *   - 创建 / 更新 / 删除
 *   - loading / errorMessage 统一管理
 *   - 幂等（相同查询不重复请求）
 *
 * 用法：
 *   const useProductStore = defineCrudStore({
 *     id: 'product',
 *     list: (q) => productApi.list(q),
 *     get: (id) => productApi.get(id),
 *     create: (d) => productApi.create(d),
 *     update: (id, d) => productApi.update(id, d),
 *     remove: (id) => productApi.remove(id),
 *   })
 *   const store = useProductStore()
 *   await store.fetchList({ page: 1, size: 20 })
 *
 * 纯逻辑：不依赖 UI 组件，可单测。
 */

import { defineStore } from 'pinia'
import { computed, ref, type Ref } from 'vue'

export interface ListQuery {
  page?: number
  size?: number
  [key: string]: unknown
}

export interface ListResult<T> {
  items: T[]
  total: number
}

export interface CrudStoreOptions<T, Q extends ListQuery, C, U> {
  /** store id（全局唯一） */
  id: string
  /** 列表查询函数 */
  list: (query: Q) => Promise<ListResult<T>>
  /** 详情查询函数 */
  get?: (id: string | number) => Promise<T | null>
  /** 创建函数 */
  create?: (data: C) => Promise<T>
  /** 更新函数 */
  update?: (id: string | number, data: U) => Promise<T>
  /** 删除函数 */
  remove?: (id: string | number) => Promise<void>
  /** 行主键提取（列表操作用） */
  rowKey?: (row: T) => string | number
}

export interface CrudStore<T, Q extends ListQuery, C, U> {
  items: Ref<T[]>
  total: Ref<number>
  current: Ref<T | null>
  loading: Ref<boolean>
  saving: Ref<boolean>
  errorMessage: Ref<string>
  lastQuery: Ref<Q | null>
  isEmpty: import('vue').ComputedRef<boolean>
  fetchList: (query: Q) => Promise<void>
  fetchOne: (id: string | number) => Promise<T | null>
  createItem: (data: C) => Promise<T | null>
  updateItem: (id: string | number, data: U) => Promise<T | null>
  removeItem: (id: string | number) => Promise<boolean>
  reset: () => void
}

function isSameQuery(a: ListQuery | null, b: ListQuery | null): boolean {
  if (a === b) return true
  if (!a || !b) return false
  return JSON.stringify(a) === JSON.stringify(b)
}

/**
 * CRUD Store 工厂。
 */
export function defineCrudStore<T, Q extends ListQuery = ListQuery, C = Partial<T>, U = Partial<T>>(
  options: CrudStoreOptions<T, Q, C, U>,
) {
  return defineStore(options.id, (): CrudStore<T, Q, C, U> => {
    const items = ref<T[]>([]) as Ref<T[]>
    const total = ref(0)
    const current = ref<T | null>(null) as Ref<T | null>
    const loading = ref(false)
    const saving = ref(false)
    const errorMessage = ref('')
    const lastQuery = ref<Q | null>(null) as Ref<Q | null>

    const isEmpty = computed(() => items.value.length === 0 && !loading.value)

    function setError(e: unknown): void {
      errorMessage.value = e instanceof Error ? e.message : String(e)
    }

    async function fetchList(query: Q): Promise<void> {
      // 幂等：相同查询不重复请求
      if (isSameQuery(lastQuery.value, query) && !loading.value) {
        return
      }
      loading.value = true
      errorMessage.value = ''
      try {
        const result = await options.list(query)
        items.value = result.items
        total.value = result.total
        lastQuery.value = query
      } catch (e) {
        setError(e)
        items.value = []
      } finally {
        loading.value = false
      }
    }

    async function fetchOne(id: string | number): Promise<T | null> {
      if (!options.get) return null
      loading.value = true
      errorMessage.value = ''
      try {
        const result = await options.get(id)
        current.value = result
        return result
      } catch (e) {
        setError(e)
        current.value = null
        return null
      } finally {
        loading.value = false
      }
    }

    async function createItem(data: C): Promise<T | null> {
      if (!options.create) return null
      saving.value = true
      errorMessage.value = ''
      try {
        const result = await options.create(data)
        // 若当前列表已加载，把新行插入顶部
        if (lastQuery.value) {
          items.value = [result, ...items.value]
          total.value += 1
        }
        return result
      } catch (e) {
        setError(e)
        return null
      } finally {
        saving.value = false
      }
    }

    async function updateItem(id: string | number, data: U): Promise<T | null> {
      if (!options.update) return null
      saving.value = true
      errorMessage.value = ''
      try {
        const result = await options.update(id, data)
        const keyFn = options.rowKey
        if (keyFn) {
          const key = keyFn(result)
          const idx = items.value.findIndex((row) => keyFn(row) === key)
          if (idx >= 0) items.value[idx] = result
        } else {
          const idx = items.value.findIndex((row) => (row as { id?: unknown }).id === id)
          if (idx >= 0) items.value[idx] = result
        }
        if (current.value && keyFn && keyFn(current.value) === keyFn(result)) {
          current.value = result
        }
        return result
      } catch (e) {
        setError(e)
        return null
      } finally {
        saving.value = false
      }
    }

    async function removeItem(id: string | number): Promise<boolean> {
      if (!options.remove) return false
      saving.value = true
      errorMessage.value = ''
      try {
        await options.remove(id)
        const keyFn = options.rowKey
        items.value = keyFn
          ? items.value.filter((row) => keyFn(row) !== id)
          : items.value.filter((row) => (row as { id?: unknown }).id !== id)
        total.value = Math.max(0, total.value - 1)
        return true
      } catch (e) {
        setError(e)
        return false
      } finally {
        saving.value = false
      }
    }

    function reset(): void {
      items.value = []
      total.value = 0
      current.value = null
      loading.value = false
      saving.value = false
      errorMessage.value = ''
      lastQuery.value = null
    }

    return {
      items,
      total,
      current,
      loading,
      saving,
      errorMessage,
      lastQuery,
      isEmpty,
      fetchList,
      fetchOne,
      createItem,
      updateItem,
      removeItem,
      reset,
    }
  })
}

export type CrudStoreInstance<T, Q extends ListQuery, C, U> = ReturnType<
  ReturnType<typeof defineCrudStore<T, Q, C, U>>
>
