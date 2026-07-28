import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RuleEditor from '@/views/RuleEditor.vue'

vi.mock('axios')

describe('RuleEditor.vue', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('should render the rule editor main view', () => {
    const wrapper = mount(RuleEditor, {
      global: {
        mocks: {
          $t: (key: string) => key,
        },
      },
    })
    expect(wrapper.exists()).toBe(true)
  })
})
