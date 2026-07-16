import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// Mock 依赖：使用 vi.hoisted 确保在 http.ts 导入前完成 mock 注册
const mocks = vi.hoisted(() => {
  return {
    // axios 实例上的方法将被替换
    request: vi.fn(),
    get: vi.fn(),
    post: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
    interceptors: {
      request: { use: vi.fn() },
      response: { use: vi.fn() },
    },
    create: vi.fn(() => ({
      request: mocks.request,
      get: mocks.get,
      post: mocks.post,
      put: mocks.put,
      delete: mocks.delete,
      interceptors: mocks.interceptors,
    })),
    // ElMessage 错误提示
    elMessage: {
      error: vi.fn(),
      success: vi.fn(),
      warning: vi.fn(),
      info: vi.fn(),
    },
    // 错误总线
    emitManufacturingError: vi.fn(),
    // 错误处理器
    isNetworkError: vi.fn(() => false),
    shouldShowConflictDialog: vi.fn(() => false),
  }
})

vi.mock('axios', () => ({
  default: {
    create: mocks.create,
  },
}))

vi.mock('element-plus', () => ({
  ElMessage: mocks.elMessage,
}))

vi.mock('@/composables/useErrorBus', () => ({
  emitManufacturingError: mocks.emitManufacturingError,
}))

vi.mock('@/utils/error-handler', () => ({
  isNetworkError: mocks.isNetworkError,
  shouldShowConflictDialog: mocks.shouldShowConflictDialog,
}))

// 导入被测模块（在所有 mock 注册之后）
import http, { createCancelToken, setHttpReady } from '@/utils/http'

describe('http', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  describe('createCancelToken', () => {
    it('返回 signal 与 cancel 函数', () => {
      const { signal, cancel } = createCancelToken()
      expect(signal).toBeInstanceOf(AbortSignal)
      expect(typeof cancel).toBe('function')
    })

    it('cancel 调用后 signal 变为 aborted 状态', () => {
      const { signal, cancel } = createCancelToken()
      expect(signal.aborted).toBe(false)
      cancel('取消请求')
      expect(signal.aborted).toBe(true)
    })

    it('cancel 支持不传 reason', () => {
      const { signal, cancel } = createCancelToken()
      cancel()
      expect(signal.aborted).toBe(true)
    })
  })

  describe('axios 实例创建', () => {
    it('调用 axios.create 创建实例', () => {
      expect(mocks.create).toHaveBeenCalledWith(
        expect.objectContaining({
          timeout: 30000,
          headers: { 'Content-Type': 'application/json' },
        }),
      )
    })

    it('注册请求与响应拦截器', () => {
      expect(mocks.interceptors.request.use).toHaveBeenCalled()
      expect(mocks.interceptors.response.use).toHaveBeenCalled()
    })

    it('导出默认 http 实例包含常用方法', () => {
      expect(typeof http.get).toBe('function')
      expect(typeof http.post).toBe('function')
      expect(typeof http.put).toBe('function')
      expect(typeof http.delete).toBe('function')
      expect(typeof http.request).toBe('function')
    })
  })

  describe('setHttpReady', () => {
    it('可正常调用不影响后续逻辑', () => {
      expect(() => setHttpReady()).not.toThrow()
    })
  })
})
