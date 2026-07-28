// Vitest setup file for frontend test utilities and mocks.

import { config } from '@vue/test-utils'
import { vi } from 'vitest'

// 全局 mock Tauri invoke（前端组件可能调用）
vi.mock('@tauri-apps/api/core', () => ({
  invoke: vi.fn(() => Promise.resolve({})),
}))

// 全局 mock window.matchMedia（Element Plus 依赖）
if (typeof window !== 'undefined' && !window.matchMedia) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: false,
    media: query,
    addListener: vi.fn(),
    removeListener: vi.fn(),
  }))
}

// Mock localStorage for happy-dom environment
const localStorageMock = (() => {
  let store: Record<string, string> = {}
  return {
    getItem: (key: string) => store[key] || null,
    setItem: (key: string, value: string) => { store[key] = value },
    removeItem: (key: string) => { delete store[key] },
    clear: () => { store = {} },
    get length() { return Object.keys(store).length },
    key: (index: number) => Object.keys(store)[index] || null
  }
})()

Object.defineProperty(globalThis, 'localStorage', {
  value: localStorageMock,
  writable: true
})

// Mock scrollIntoView for happy-dom environment
if (typeof Element !== 'undefined' && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = function(options?: ScrollIntoViewOptions) {
    // No-op in test environment
  }
}

// Mock Element Plus components globally
config.global.stubs = {
  ElDialog: {
    template: '<div class="el-dialog"><slot /></div>',
  },
  ElButton: {
    template: '<button class="el-button" @click="$emit(\'click\', $event)"><slot /></button>',
    props: ['type', 'loading', 'disabled', 'size', 'text', 'icon', 'circle'],
    emits: ['click'],
  },
  ElUpload: {
    template: '<div class="el-upload"><slot /><slot name="tip" /></div>',
    props: ['autoUpload', 'limit', 'accept', 'fileList', 'drag'],
  },
  ElIcon: {
    template: '<span class="el-icon"><slot /></span>',
  },
  ElProgress: {
    template: '<div class="el-progress"></div>',
    props: ['percentage', 'status', 'strokeWidth', 'indeterminate'],
  },
  ElAlert: {
    template: '<div class="el-alert"></div>',
    props: ['title', 'type', 'closable', 'showIcon'],
  },
  ElForm: {
    template: '<form class="el-form"><slot /></form>',
    props: ['labelWidth', 'size'],
  },
  ElFormItem: {
    template: '<div class="el-form-item"><slot /></div>',
    props: ['label'],
  },
  ElSelect: {
    template: '<select class="el-select"><slot /></select>',
    props: ['modelValue'],
  },
  ElOption: {
    template: '<option><slot /></option>',
    props: ['label', 'value'],
  },
  ElRadioGroup: {
    template: '<div class="el-radio-group"><slot /></div>',
    props: ['modelValue', 'size'],
  },
  ElRadio: {
    template: '<label class="el-radio"><slot /></label>',
    props: ['value'],
  },
  ElRadioButton: {
    template: '<label class="el-radio-button"><slot /></label>',
    props: ['value'],
  },
  ElTabs: {
    template: '<div class="el-tabs"><slot /></div>',
    props: ['modelValue'],
  },
  ElTabPane: {
    template: '<div class="el-tab-pane"><slot /></div>',
    props: ['label', 'name'],
  },
  ElTable: {
    template: '<table class="el-table"><slot /></table>',
    props: ['data', 'height', 'stripe', 'size'],
  },
  ElTableColumn: {
    template: '<th><slot /></th>',
    props: ['prop', 'label', 'width', 'minWidth'],
  },
  ElEmpty: {
    template: '<div class="el-empty"><slot /></div>',
    props: ['description', 'imageSize'],
  },
  ElResult: {
    template: '<div class="el-result"><slot name="extra" /></div>',
    props: ['icon', 'title', 'subTitle'],
  },
  ElDescriptions: {
    template: '<dl class="el-descriptions"><slot /></dl>',
    props: ['column', 'border', 'size'],
  },
  ElDescriptionsItem: {
    template: '<div class="el-descriptions-item"><slot /></div>',
    props: ['label'],
  },
  ElCheckbox: {
    template: '<label class="el-checkbox"><input type="checkbox" :checked="modelValue" @change="$emit(\'update:modelValue\', $event.target.checked)" /><span><slot /></span></label>',
    props: ['modelValue'],
    emits: ['update:modelValue', 'change'],
  },
  ElSlider: {
    template: '<div class="el-slider"><input type="range" :value="modelValue" @input="$emit(\'update:modelValue\', Number($event.target.value))" /></div>',
    props: ['modelValue', 'min', 'max', 'step', 'disabled'],
    emits: ['update:modelValue', 'input', 'change'],
  },
}
