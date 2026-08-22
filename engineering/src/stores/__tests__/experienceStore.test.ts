// experienceStore 测试（P2-3 前端）
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'

import { useExperienceStore } from '@/stores/experienceStore'
import * as api from '@/api/cuttingExperience'

vi.mock('@/api/cuttingExperience', () => ({
  captureExperience: vi.fn(),
  getExperienceStats: vi.fn(),
  queryExperiences: vi.fn(),
}))

const mockedQuery = vi.mocked(api.queryExperiences)
const mockedCapture = vi.mocked(api.captureExperience)
const mockedStats = vi.mocked(api.getExperienceStats)

describe('experienceStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('refreshList loads records and total', async () => {
    mockedQuery.mockResolvedValue({
      records: [{ id: 'exp_1', machine_id: 'VM-001' }],
      total: 1,
      limit: 50,
      offset: 0,
    } as never)

    const store = useExperienceStore()
    await store.refreshList()

    expect(store.records.length).toBe(1)
    expect(store.total).toBe(1)
    expect(store.loading).toBe(false)
  })

  it('refreshList sets errorMessage on failure', async () => {
    mockedQuery.mockRejectedValue(new Error('network down'))

    const store = useExperienceStore()
    await store.refreshList()

    expect(store.errorMessage).toBe('network down')
    expect(store.records.length).toBe(0)
  })

  it('fetchExperiences merges params and refreshes', async () => {
    mockedQuery.mockResolvedValue({
      records: [],
      total: 0,
      limit: 50,
      offset: 0,
    } as never)

    const store = useExperienceStore()
    await store.fetchExperiences({ machine_id: 'VM-002', limit: 10 })

    expect(store.query.machine_id).toBe('VM-002')
    expect(store.query.limit).toBe(10)
    expect(mockedQuery).toHaveBeenCalledTimes(1)
  })

  it('submitCapture posts payload and refreshes list', async () => {
    mockedCapture.mockResolvedValue({
      id: 'exp_new',
      machine_id: 'VM-001',
    } as never)
    mockedQuery.mockResolvedValue({
      records: [{ id: 'exp_new' }],
      total: 1,
      limit: 50,
      offset: 0,
    } as never)
    mockedStats.mockResolvedValue({ total_records: 1 } as never)

    const store = useExperienceStore()
    const created = await store.submitCapture({
      machine_id: 'VM-001',
      tool_id: 'T-1',
      parameters: { depth_of_cut_mm: 1, feed_mm_per_rev: 0.1, spindle_rpm: 5000 },
      results: { cycle_time_s: 30, result: 'ok' },
    })

    expect(created?.id).toBe('exp_new')
    expect(store.records.length).toBe(1)
    expect(mockedStats).toHaveBeenCalled()
  })

  it('clearError resets errorMessage', async () => {
    mockedQuery.mockRejectedValue(new Error('boom'))
    const store = useExperienceStore()
    await store.refreshList()
    expect(store.errorMessage).toBe('boom')
    store.clearError()
    expect(store.errorMessage).toBe('')
  })
})
