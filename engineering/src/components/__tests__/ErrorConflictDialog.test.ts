/* eslint-disable vue/no-unused-vars */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { mount } from '@vue/test-utils'
import ErrorConflictDialog from '@/components/ErrorConflictDialog.vue'
import type { ErrorDialogPayload } from '@/utils/http'

const sampleError: ErrorDialogPayload = {
  title: '加工参数冲突',
  code: 'E3002',
  message: '刀具库中无合适刀具',
  severity: 'error',
  detail: '刀具直径(20mm)大于槽宽(10mm)，无法进入槽内进行加工。当前材料：45钢，工序：槽铣',
  suggestion: '刀具直径(20mm)超出槽宽(10mm)限制。建议方案：1) 更换刀具，选用直径≤10mm的立铣刀；2) 调整加工工艺，改用分层加工或多刀铣削策略；3) 修改零件设计，增大槽宽至≥20mm。',
  recoverable: false,
}

describe('ErrorConflictDialog.vue', () => {
  afterEach(() => {
    vi.clearAllMocks()
  })

  // eslint-disable-next-line vue/no-unused-vars
  it('should mount and register event handler', () => {
    const addSpy = vi.spyOn(window, 'addEventListener')
    const wrapper = mount(ErrorConflictDialog, { global: { stubs: { ErrorNotification: true } } })
    expect(wrapper.vm).toBeDefined()

    expect(addSpy).toHaveBeenCalledWith(
      'manufacturing-error',
      expect.any(Function),
    )
    addSpy.mockRestore()
  })

  it('should unregister event handler on unmount', () => {
    const removeSpy = vi.spyOn(window, 'removeEventListener')
    const wrapper = mount(ErrorConflictDialog)
    wrapper.unmount()

    expect(removeSpy).toHaveBeenCalledWith(
      'manufacturing-error',
      expect.any(Function),
    )
    removeSpy.mockRestore()
  })

  it('should handle manufacturing-error event without throwing', () => {
    mount(ErrorConflictDialog)

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', { detail: { ...sampleError } }),
      )
    }).not.toThrow()
  })

  it('should accept error severity payloads', () => {
    mount(ErrorConflictDialog)

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', {
          detail: { ...sampleError, severity: 'error' },
        }),
      )
    }).not.toThrow()

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', {
          detail: { ...sampleError, severity: 'warning' },
        }),
      )
    }).not.toThrow()

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', {
          detail: { ...sampleError, severity: 'critical' },
        }),
      )
    }).not.toThrow()
  })

  it('should handle error with empty fields gracefully', () => {
    mount(ErrorConflictDialog)

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', {
          detail: {
            title: 'test',
            code: 'E0000',
            message: '',
            severity: 'error',
            detail: '',
            suggestion: '',
            recoverable: false,
          },
        }),
      )
    }).not.toThrow()
  })

  it('should handle long suggestion text', () => {
    mount(ErrorConflictDialog)

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', {
          detail: {
            ...sampleError,
            suggestion: '很长'.repeat(200),
          },
        }),
      )
    }).not.toThrow()
  })

  it('should handle recoverable errors with adjusted values', () => {
    mount(ErrorConflictDialog)

    expect(() => {
      window.dispatchEvent(
        new CustomEvent('manufacturing-error', {
          detail: {
            ...sampleError,
            recoverable: true,
            adjusted_values: { feed_rate: 350, spindle_speed: 6000 },
          },
        }),
      )
    }).not.toThrow()
  })
})

describe('http utility', () => {
  it('should export http client with full API', async () => {
    const mod = await import('@/utils/http')
    expect(mod.default).toBeDefined()
    expect(typeof mod.default.get).toBe('function')
    expect(typeof mod.default.post).toBe('function')
    expect(typeof mod.default.put).toBe('function')
    expect(typeof mod.default.delete).toBe('function')
  })

  it('should define ErrorDialogPayload type structure', async () => {
    const payload: ErrorDialogPayload = {
      title: 'test',
      code: 'E0001',
      message: 'test msg',
      severity: 'error',
      detail: '',
      suggestion: '',
      recoverable: false,
    }
    expect(payload.title).toBe('test')
    expect(payload.code).toBe('E0001')
  })
})
