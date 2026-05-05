import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { RequestBatcher } from '@/utils/requestBatcher'
import axios from 'axios'

vi.mock('axios')

describe('RequestBatcher', () => {
  let batcher: RequestBatcher

  beforeEach(() => {
    vi.useFakeTimers()
    vi.clearAllMocks()
    batcher = new RequestBatcher({
      windowMs: 50,
      maxBatchSize: 10,
      baseUrl: 'http://localhost:8000',
    })
  })

  afterEach(async () => {
    await vi.advanceTimersByTimeAsync(10)
    batcher.destroy()
    await vi.advanceTimersByTimeAsync(10)
    vi.useRealTimers()
  })

  describe('基础请求合并', () => {
    it('应该在时间窗口内合并多个请求', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [
              { id: 'req-1', status: 200, data: { value: 1 }, error: null },
              { id: 'req-2', status: 200, data: { value: 2 }, error: null },
            ],
          },
        },
      })

      const promise1 = batcher.enqueue({
        method: 'GET',
        path: '/api/tasks/1',
      })

      const promise2 = batcher.enqueue({
        method: 'GET',
        path: '/api/tasks/2',
      })

      await vi.advanceTimersByTimeAsync(50)

      const [result1, result2] = await Promise.all([promise1, promise2])

      expect(mockAxiosPost).toHaveBeenCalledTimes(1)
      expect(result1.data).toEqual({ value: 1 })
      expect(result2.data).toEqual({ value: 2 })
    })

    it('应该为每个请求生成唯一标识符', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [
              { id: 'unique-1', status: 200, data: { msg: 'ok' }, error: null },
            ],
          },
        },
      })

      const promise = batcher.enqueue({
        method: 'GET',
        path: '/api/test',
      })

      await vi.advanceTimersByTimeAsync(50)
      const result = await promise

      expect(mockAxiosPost).toHaveBeenCalledWith(
        'http://localhost:8000/api/batch/execute',
        expect.objectContaining({
          requests: expect.arrayContaining([
            expect.objectContaining({ id: expect.any(String) }),
          ]),
        }),
        expect.any(Object)
      )
    })
  })

  describe('HTTP 方法支持', () => {
    it('应该支持 GET 请求', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [{ id: 'get-1', status: 200, data: { items: [] }, error: null }],
          },
        },
      })

      const promise = batcher.enqueue({
        method: 'GET',
        path: '/api/items',
      })

      await vi.advanceTimersByTimeAsync(50)
      const result = await promise

      const callArgs = mockAxiosPost.mock.calls[0]
      expect((callArgs[1] as any).requests[0].method).toBe('GET')
    })

    it('应该支持 POST 请求', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [{ id: 'post-1', status: 201, data: { created: true }, error: null }],
          },
        },
      })

      const promise = batcher.enqueue({
        method: 'POST',
        path: '/api/items',
        body: { name: 'test' },
      })

      await vi.advanceTimersByTimeAsync(50)
      const result = await promise

      const callArgs = mockAxiosPost.mock.calls[0]
      expect((callArgs[1] as any).requests[0].method).toBe('POST')
      expect((callArgs[1] as any).requests[0].body).toEqual({ name: 'test' })
    })

    it('应该支持 PUT 和 DELETE 请求', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [
              { id: 'put-1', status: 200, data: { updated: true }, error: null },
              { id: 'del-1', status: 204, data: null, error: null },
            ],
          },
        },
      })

      const promise1 = batcher.enqueue({
        method: 'PUT',
        path: '/api/items/1',
        body: { name: 'updated' },
      })

      const promise2 = batcher.enqueue({
        method: 'DELETE',
        path: '/api/items/2',
      })

      await vi.advanceTimersByTimeAsync(50)
      await Promise.all([promise1, promise2])

      const callArgs = mockAxiosPost.mock.calls[0]
      const methods = (callArgs[1] as any).requests.map((r: any) => r.method)
      expect(methods).toContain('PUT')
      expect(methods).toContain('DELETE')
    })
  })

  describe('请求去重', () => {
    it('应该在同一批次中去除重复请求', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [{ id: 'dedup-1', status: 200, data: { value: 1 }, error: null }],
          },
        },
      })

      const promise1 = batcher.enqueue({
        method: 'GET',
        path: '/api/tasks/1',
      })

      const promise2 = batcher.enqueue({
        method: 'GET',
        path: '/api/tasks/1',
      })

      await vi.advanceTimersByTimeAsync(50)
      const [result1, result2] = await Promise.all([promise1, promise2])

      expect(mockAxiosPost).toHaveBeenCalledTimes(1)
      const callArgs = mockAxiosPost.mock.calls[0]
      expect((callArgs[1] as any).requests).toHaveLength(1)
      expect(result1.data).toEqual({ value: 1 })
      expect(result2.data).toEqual({ value: 1 })
    })
  })

  describe('请求取消机制', () => {
    it('应该支持取消特定请求', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      
      const promise = batcher.enqueue({
        method: 'GET',
        path: '/api/test',
      })

      batcher.cancel('all')

      await vi.advanceTimersByTimeAsync(50)

      await expect(promise).rejects.toThrow('请求已取消')
      expect(mockAxiosPost).not.toHaveBeenCalled()
    })

    it('取消的请求不应被发送到服务器', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      
      batcher.enqueue({
        method: 'GET',
        path: '/api/test',
      })

      batcher.cancel('all')

      await vi.advanceTimersByTimeAsync(50)

      expect(mockAxiosPost).not.toHaveBeenCalled()
    })
  })

  describe('错误处理', () => {
    it('应该正确处理部分请求失败', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [
              { id: 'ok-1', status: 200, data: { success: true }, error: null },
              {
                id: 'fail-1',
                status: 404,
                data: null,
                error: { code: 'NOT_FOUND', message: '资源不存在' },
              },
            ],
          },
        },
      })

      const promise1 = batcher.enqueue({ method: 'GET', path: '/api/exist' })
      const promise2 = batcher.enqueue({ method: 'GET', path: '/api/missing' })

      await vi.advanceTimersByTimeAsync(50)

      const result1 = await promise1
      expect(result1.data).toEqual({ success: true })

      await expect(promise2).rejects.toThrow('资源不存在')
    })

    it('应该处理网络错误', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockRejectedValue(new Error('Network Error'))

      const promise = batcher.enqueue({ method: 'GET', path: '/api/test' })

      await vi.advanceTimersByTimeAsync(50)

      await expect(promise).rejects.toThrow('Network Error')
    })

    it('应该处理请求超时', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockRejectedValue({ code: 'ECONNABORTED', message: 'timeout' })

      const promise = batcher.enqueue({ method: 'GET', path: '/api/slow' })

      await vi.advanceTimersByTimeAsync(50)

      await expect(promise).rejects.toThrow('timeout')
    })
  })

  describe('自动刷新机制', () => {
    it('应该在达到最大批次大小时立即刷新', async () => {
      const batcher = new RequestBatcher({
        windowMs: 1000,
        maxBatchSize: 3,
        baseUrl: 'http://localhost:8000',
      })

      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [
              { id: 'req-0', status: 200, data: { index: 0 }, error: null },
              { id: 'req-1', status: 200, data: { index: 1 }, error: null },
              { id: 'req-2', status: 200, data: { index: 2 }, error: null },
            ],
          },
        },
      })

      batcher.enqueue({ method: 'GET', path: '/api/1' })
      batcher.enqueue({ method: 'GET', path: '/api/2' })
      batcher.enqueue({ method: 'GET', path: '/api/3' })

      await vi.advanceTimersByTimeAsync(10)

      expect(mockAxiosPost).toHaveBeenCalledTimes(1)

      batcher.destroy()
    })

    it('应该在时间窗口结束时刷新', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [{ id: 'timer-1', status: 200, data: {}, error: null }],
          },
        },
      })

      batcher.enqueue({ method: 'GET', path: '/api/test' })

      expect(mockAxiosPost).not.toHaveBeenCalled()

      await vi.advanceTimersByTimeAsync(50)

      expect(mockAxiosPost).toHaveBeenCalledTimes(1)
    })
  })

  describe('Promise 接口一致性', () => {
    it('应该返回与普通请求相同的 Promise 接口', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [{ id: 'p1', status: 200, data: { value: 42 }, error: null }],
          },
        },
      })

      const promise = batcher.enqueue({ method: 'GET', path: '/api/test' })

      expect(promise).toHaveProperty('then')
      expect(promise).toHaveProperty('catch')
      expect(promise).toHaveProperty('finally')

      await vi.advanceTimersByTimeAsync(50)
      const result = await promise

      expect(result.data).toEqual({ value: 42 })
    })
  })

  describe('重试机制', () => {
    it('应该对 5xx 错误进行自动重试', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost
        .mockRejectedValueOnce({ response: { status: 500 } })
        .mockResolvedValueOnce({
          data: {
            code: 0,
            message: 'success',
            data: {
              results: [{ id: 'retry-1', status: 200, data: { ok: true }, error: null }],
            },
          },
        })

      const promise = batcher.enqueue({ method: 'GET', path: '/api/test' })

      await vi.advanceTimersByTimeAsync(50)
      const result = await promise

      expect(mockAxiosPost).toHaveBeenCalledTimes(2)
      expect(result.data).toEqual({ ok: true })
    })

    it('不应该对 4xx 错误重试', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockResolvedValue({
        data: {
          code: 0,
          message: 'success',
          data: {
            results: [{ id: 'err-1', status: 403, data: null, error: { code: 'FORBIDDEN', message: '权限不足' } }],
          },
        },
      })

      const promise = batcher.enqueue({ method: 'GET', path: '/api/secret' })

      await vi.advanceTimersByTimeAsync(50)

      await expect(promise).rejects.toThrow('权限不足')
      expect(mockAxiosPost).toHaveBeenCalledTimes(1)
    })

    it('重试次数不应超过最大限制', async () => {
      const mockAxiosPost = vi.mocked(axios.post)
      mockAxiosPost.mockRejectedValue({ response: { status: 502 } })

      const batcher = new RequestBatcher({
        windowMs: 50,
        maxRetries: 2,
        baseUrl: 'http://localhost:8000',
      })

      const promise = batcher.enqueue({ method: 'GET', path: '/api/flaky' })

      await vi.advanceTimersByTimeAsync(50)

      await expect(promise).rejects.toThrow()
      expect(mockAxiosPost).toHaveBeenCalledTimes(3)

      batcher.destroy()
    })
  })
})
