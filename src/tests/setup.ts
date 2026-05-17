// Vitest setup file for frontend test utilities and mocks.

import { config } from '@vue/test-utils'

// Mock Element Plus components globally
config.global.stubs = {
  ElDialog: {
    template: '<div class="el-dialog"><slot /></div>',
  },
  ElButton: {
    template: '<button class="el-button"><slot /></button>',
    props: ['type', 'loading', 'disabled', 'size', 'text'],
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
}
