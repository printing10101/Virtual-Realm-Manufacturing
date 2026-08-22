// P3-2 CRUD Store 工厂测试（Pinia setup store，纯逻辑）
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

import { defineCrudStore } from '@/stores/crud/defineCrudStore'

interface Product {
  id: string | number
  name: string
}

function makeApi() {
  let seq = 1
  const rows: Product[] = [
    { id: '1', name: 'p1' },
    { id: '2', name: 'p2' },
  ]
  return {
    list: vi.fn(async (q: { page?: number; size?: number }) => ({
      items: rows.slice(0, q.size ?? 10),
      total: rows.length,
    })),
    get: vi.fn(async (id: string | number) => {
      const row = rows.find((r) => r.id === id)
      return row ?? null
    }),
    create: vi.fn(async (d: Partial<Product>) => {
      const row = { id: String(seq++), ...d } as Product
      rows.push(row)
      return row
    }),
    update: vi.fn(async (id: string | number, d: Partial<Product>) => {
      const row = rows.find((r) => r.id === id)!
      Object.assign(row, d)
      return row
    }),
    remove: vi.fn(async (id: string | number) => {
      const idx = rows.findIndex((r) => r.id === id)
      if (idx >= 0) rows.splice(idx, 1)
    }),
  }
}

describe('defineCrudStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('fetchList loads items and total', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number; size?: number }>({
      id: 'products-a',
      list: api.list,
      rowKey: (r) => r.id,
    })
    const store = useStore()
    await store.fetchList({ page: 1, size: 10 })
    expect(store.items).toHaveLength(2)
    expect(store.total).toBe(2)
    expect(store.isEmpty).toBe(false)
  })

  it('fetchList is idempotent for same query', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number; size?: number }>({
      id: 'products-b',
      list: api.list,
    })
    const store = useStore()
    await store.fetchList({ page: 1, size: 10 })
    const firstCallCount = api.list.mock.calls.length
    await store.fetchList({ page: 1, size: 10 })
    // 幂等：相同查询不重复调用 API
    expect(api.list.mock.calls.length).toBe(firstCallCount)
  })

  it('fetchList different query triggers reload', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number; size?: number }>({
      id: 'products-c',
      list: api.list,
    })
    const store = useStore()
    await store.fetchList({ page: 1, size: 10 })
    await store.fetchList({ page: 2, size: 10 })
    expect(api.list).toHaveBeenNthCalledWith(1, { page: 1, size: 10 })
    expect(api.list).toHaveBeenNthCalledWith(2, { page: 2, size: 10 })
  })

  it('fetchList failure sets error and clears items', async () => {
    const api = makeApi()
    api.list.mockRejectedValueOnce(new Error('list failed'))
    const useStore = defineCrudStore<Product, { page?: number; size?: number }>({
      id: 'products-d',
      list: api.list,
    })
    const store = useStore()
    await store.fetchList({ page: 1 })
    expect(store.errorMessage).toBe('list failed')
    expect(store.items).toEqual([])
  })

  it('createItem inserts row at top and increments total', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number }, Partial<Product>, Partial<Product>>({
      id: 'products-e',
      list: api.list,
      create: api.create,
      rowKey: (r) => r.id,
    })
    const store = useStore()
    await store.fetchList({ page: 1 })
    const created = await store.createItem({ name: 'p3' })
    expect(created?.name).toBe('p3')
    expect(store.items[0].name).toBe('p3')
    expect(store.total).toBe(3)
  })

  it('updateItem patches row in list', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number }, Partial<Product>, Partial<Product>>({
      id: 'products-f',
      list: api.list,
      update: api.update,
      rowKey: (r) => r.id,
    })
    const store = useStore()
    await store.fetchList({ page: 1 })
    await store.updateItem(1, { name: 'p1-renamed' })
    expect(store.items[0].name).toBe('p1-renamed')
  })

  it('removeItem filters row and decrements total', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number }, Partial<Product>, Partial<Product>>({
      id: 'products-g',
      list: api.list,
      remove: api.remove,
      rowKey: (r) => r.id,
    })
    const store = useStore()
    await store.fetchList({ page: 1 })
    const ok = await store.removeItem(1)
    expect(ok).toBe(true)
    expect(store.items).toHaveLength(1)
    expect(store.total).toBe(1)
  })

  it('fetchOne loads current', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number }, Partial<Product>, Partial<Product>>({
      id: 'products-h',
      list: api.list,
      get: api.get,
    })
    const store = useStore()
    const row = await store.fetchOne('2')
    expect(row?.name).toBe('p2')
    expect(store.current?.id).toBe('2')
  })

  it('reset clears all state', async () => {
    const api = makeApi()
    const useStore = defineCrudStore<Product, { page?: number }, Partial<Product>, Partial<Product>>({
      id: 'products-i',
      list: api.list,
    })
    const store = useStore()
    await store.fetchList({ page: 1 })
    store.reset()
    expect(store.items).toEqual([])
    expect(store.total).toBe(0)
    expect(store.errorMessage).toBe('')
  })
})
