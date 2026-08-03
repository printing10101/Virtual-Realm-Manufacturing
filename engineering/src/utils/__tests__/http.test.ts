import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

/** axios 实例形状（mock 用）。 */
interface HttpAxiosLike {
  request: ReturnType<typeof vi.fn>
  get: ReturnType<typeof vi.fn>
  post: ReturnType<typeof vi.fn>
  put: ReturnType<typeof vi.fn>
  delete: ReturnType<typeof vi.fn>
  interceptors: {
    request: { use: ReturnType<typeof vi.fn> }
    response: { use: ReturnType<typeof vi.fn> }
  }
}

/** hoisted mock 集合类型（消除自引用导致的隐式 any）。 */
interface HttpMocks extends HttpAxiosLike {
  create: (...args: unknown[]) => HttpAxiosLike
  elMessage: {
    error: ReturnType<typeof vi.fn>
    success: ReturnType<typeof vi.fn>
    warning: ReturnType<typeof vi.fn>
    info: ReturnType<typeof vi.fn>
  }
  emitManufacturingError: ReturnType<typeof vi.fn>
  isNetworkError: ReturnType<typeof vi.fn>
  shouldShowConflictDialog: ReturnType<typeof vi.fn>
}

// Mock 依赖：使用 vi.hoisted 确保在 http.ts 导入前完成 mock 注册
const mocks = vi.hoisted<HttpMocks>(() => {
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
    create: vi.fn((() => ({
      request: mocks.request,
      get: mocks.get,
      post: mocks.post,
      put: mocks.put,
      delete: mocks.delete,
      interceptors: mocks.interceptors,
    })) as (...args: unknown[]) => HttpAxiosLike),
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
    isNetworkError: vi.fn(() => false) as unknown as ReturnType<typeof vi.fn>,
    shouldShowConflictDialog: vi.fn(() => false) as unknown as ReturnType<typeof vi.fn>,
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
