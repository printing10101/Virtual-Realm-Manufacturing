// cuttingExperience API 客户端测试（P2-3 前端）
import { describe, it, expect, vi, beforeEach } from 'vitest'

import http from '@/utils/http'
import {
  captureExperience,
  queryExperiences,
  getExperienceStats,
} from '@/api/cuttingExperience'

vi.mock('@/utils/http', () => ({
  default: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}))

const mockedGet = vi.mocked(http.get)
const mockedPost = vi.mocked(http.post)

describe('cuttingExperience API', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('captureExperience posts to /capture and unwraps data', async () => {
    mockedPost.mockResolvedValue({
      data: {
        data: {
          id: 'exp_abc',
          machine_id: 'VM-001',
          tool_id: 'T-12',
          parameters: { depth_of_cut_mm: 2.0 },
        },
      },
    } as never)

    const result = await captureExperience({
      machine_id: 'VM-001',
      tool_id: 'T-12',
      parameters: { depth_of_cut_mm: 2.0, feed_mm_per_rev: 0.2, spindle_rpm: 8000 },
      results: { cycle_time_s: 60, result: 'ok' },
    })

    expect(mockedPost).toHaveBeenCalledWith(
      expect.stringContaining('/experience/capture'),
      expect.objectContaining({ machine_id: 'VM-001' }),
    )
    expect(result.id).toBe('exp_abc')
  })

  it('queryExperiences passes params and unwraps records', async () => {
    mockedGet.mockResolvedValue({
      data: {
        data: {
          records: [{ id: 'exp_1', machine_id: 'VM-001' }],
          total: 1,
          limit: 50,
          offset: 0,
        },
      },
    } as never)

    const result = await queryExperiences({ machine_id: 'VM-001', limit: 50 })
    expect(mockedGet).toHaveBeenCalledWith(
      expect.stringContaining('/experience'),
      expect.objectContaining({ params: expect.objectContaining({ machine_id: 'VM-001' }) }),
    )
    expect(result.total).toBe(1)
    expect(result.records[0].id).toBe('exp_1')
  })

  it('getExperienceStats returns stats object', async () => {
    mockedGet.mockResolvedValue({
      data: {
        data: { total_records: 5, ok_rate: 0.8 },
      },
    } as never)

    const stats = await getExperienceStats({ machine_id: 'VM-001' })
    expect(stats.total_records).toBe(5)
    expect(stats.ok_rate).toBe(0.8)
  })
})
