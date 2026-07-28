import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { mount } from '@vue/test-utils'
import StepImportDialog from '@/components/step_import/StepImportDialog.vue'

vi.mock('axios')

describe('StepImportDialog.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should render dialog when visible', () => {
    const wrapper = mount(StepImportDialog, {
      global: {
        mocks: {
          $t: (key: string) => key,
        },
      },
    })
    expect(wrapper.find('.el-dialog').exists()).toBe(true)
  })

  it('should display upload area when no file selected', () => {
    const wrapper = mount(StepImportDialog, {
      global: {
        mocks: {
          $t: (key: string) => key,
        },
      },
    })
    expect(wrapper.find('.el-upload').exists()).toBe(true)
  })

  it('should accept only .step and .stp file types', () => {
    const wrapper = mount(StepImportDialog, {
      global: {
        mocks: {
          $t: (key: string) => key,
        },
      },
    })
    const upload = wrapper.find('.el-upload')
    expect(upload.attributes('accept')).toContain('.step')
    expect(upload.attributes('accept')).toContain('.stp')
  })
})
