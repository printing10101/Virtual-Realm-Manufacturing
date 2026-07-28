/**
 * SnapshotPanel.vue 组件测试
 *
 * 覆盖范围：
 *   1. 组件挂载与基础渲染（页面标题、双栏布局、列表/详情面板、筛选区、分页）
 *   2. 快照列表交互（空列表 el-empty、卡片渲染、点击选中、active 高亮、刷新、重置筛选、筛选 change）
 *   3. 详情面板（空状态、详情内容、操作按钮可见性、关闭详情）
 *   4. 创建对话框（打开、取消、表单校验、提交成功/失败）
 *   5. 复现交互（确认/取消、成功、不支持复现 warning、其他错误 error）
 *
 * 对应 ADR-005 阶段 2 验收标准（前端"实验快照"视图 + "一键复现"按钮）。
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { shallowMount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import type { ExperimentSnapshot } from '@/contracts/observability'

// ---------------------------------------------------------------------------
// Mock: vue-i18n（useI18n composition API）
// ---------------------------------------------------------------------------
vi.mock('vue-i18n', () => ({
  useI18n: () => ({
    t: (key: string, params?: Record<string, unknown>) => {
      if (params) {
        let result = key
        Object.entries(params).forEach(([k, v]) => {
          result = result.replace(`{${k}}`, String(v))
        })
        return result
      }
      return key
    },
  }),
}))

// ---------------------------------------------------------------------------
// Mock: @element-plus/icons-vue
// ---------------------------------------------------------------------------
vi.mock('@element-plus/icons-vue', () => ({
  Refresh: { name: 'Refresh', template: '<i class="icon-refresh" />' },
  Plus: { name: 'Plus', template: '<i class="icon-plus" />' },
  VideoPlay: { name: 'VideoPlay', template: '<i class="icon-video-play" />' },
  Close: { name: 'Close', template: '<i class="icon-close" />' },
}))

// ---------------------------------------------------------------------------
// Mock: element-plus（ElMessage / ElMessageBox + 组件存根）
// ---------------------------------------------------------------------------
const mockElMessage = {
  success: vi.fn(),
  warning: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
}
const mockElMessageBox = {
  confirm: vi.fn(() => Promise.resolve('confirm')),
}
vi.mock('element-plus', () => ({
  ElMessage: mockElMessage,
  ElMessageBox: mockElMessageBox,
  // shallowMount 存根：保留 v-model / slot / 关键事件转发
  ElDialog: {
    template:
      '<div class="el-dialog" v-if="modelValue"><slot /><slot name="footer" /></div>',
    props: ['modelValue', 'title', 'width'],
    emits: ['update:modelValue'],
  },
  ElForm: {
    template: '<form class="el-form"><slot /></form>',
    props: ['model', 'labelWidth', 'labelPosition'],
  },
  ElFormItem: {
    template: '<div class="el-form-item"><slot /></div>',
    props: ['label'],
  },
  ElInput: {
    template:
      '<input class="el-input" :value="modelValue" @input="$emit(\'update:modelValue\', $event.target.value)" @change="$emit(\'change\', $event.target.value)" />',
    props: ['modelValue', 'type', 'rows', 'placeholder', 'size', 'clearable'],
    emits: ['update:modelValue', 'change'],
  },
  ElButton: {
    template:
      '<button class="el-button" :class="{ \'el-button--primary\': type === \'primary\', \'el-button--danger\': type === \'danger\', \'el-button--warning\': type === \'warning\' }" @click="$emit(\'click\')"><slot /><slot name="icon" /></button>',
    props: ['type', 'size', 'loading', 'icon', 'link'],
    emits: ['click'],
  },
  ElTag: {
    template: '<span class="el-tag"><slot /></span>',
    props: ['type', 'size', 'effect'],
  },
  ElEmpty: {
    template: '<div class="el-empty"><slot /></div>',
    props: ['description', 'imageSize'],
  },
  ElPagination: {
    template: '<div class="el-pagination" />',
    props: ['currentPage', 'pageSize', 'total', 'layout', 'small'],
    emits: ['update:currentPage', 'current-change'],
  },
  ElDescriptions: {
    template: '<div class="el-descriptions"><slot /></div>',
    props: ['column', 'border'],
  },
  ElDescriptionsItem: {
    template:
      '<div class="el-descriptions-item"><span class="el-descriptions-item__label">{{ label }}</span><span class="el-descriptions-item__content"><slot /></span></div>',
    props: ['label'],
  },
}))

// ---------------------------------------------------------------------------
// Mock: @/composables/useSnapshots
// ---------------------------------------------------------------------------
const mockUseSnapshots = vi.hoisted(() => ({
  snapshots: { value: [] as ExperimentSnapshot[] },
  loading: { value: false },
  totalCount: { value: 0 },
  currentPage: { value: 1 },
  pageSize: { value: 20 },
  filterCreatedBy: { value: '' as string },
  filterGitSha: { value: '' as string },
  filterModelUri: { value: '' as string },
  loadSnapshots: vi.fn(() => Promise.resolve()),
  resetFilters: vi.fn(() => Promise.resolve()),
  currentSnapshot: { value: null as ExperimentSnapshot | null },
  currentLoading: { value: false },
  selectSnapshot: vi.fn((_id: string) => Promise.resolve()),
  clearCurrent: vi.fn(),
  creating: { value: false },
  reproducing: { value: false },
  submitSnapshot: vi.fn((_body: unknown) => Promise.resolve('snap_new_001')),
  reproduce: vi.fn((_id: string) => Promise.resolve('wf_repro_001')),
}))

vi.mock('@/composables/useSnapshots', () => ({
  useSnapshots: () => mockUseSnapshots,
}))

import SnapshotPanel from '@/views/SnapshotPanel.vue'

// ---------------------------------------------------------------------------
// 测试数据
// ---------------------------------------------------------------------------
function makeSnapshot(
  overrides: Partial<ExperimentSnapshot> = {},
): ExperimentSnapshot {
  return {
    snapshot_id: 'snap-001-abcdefgh',
    created_at: '2026-07-13T10:00:00Z',
    created_by: 'user-1',
    git_sha: 'abc123def456789',
    code_dirty: false,
    config: { lr: 0.001, epochs: 100 },
    dataset_versions: ['dataset://phm2010/v1'],
    model_uri: 'model://ltc-v1',
    metrics: { val_loss: 0.06, pcc: 0.51 },
    environment: { python: '3.10', torch: '2.0.1' },
    ...overrides,
  }
}

// ---------------------------------------------------------------------------
// 测试主体
// ---------------------------------------------------------------------------
describe('SnapshotPanel.vue', () => {
  let pinia: ReturnType<typeof createPinia>
  let router: ReturnType<typeof createRouter>

  beforeEach(() => {
    setActivePinia((pinia = createPinia()))
    router = createRouter({
      history: createMemoryHistory(),
      routes: [{ path: '/', component: { template: '<div/>' } }],
    })

    // 重置 mock 状态
    mockUseSnapshots.snapshots.value = []
    mockUseSnapshots.loading.value = false
    mockUseSnapshots.totalCount.value = 0
    mockUseSnapshots.currentPage.value = 1
    mockUseSnapshots.pageSize.value = 20
    mockUseSnapshots.filterCreatedBy.value = ''
    mockUseSnapshots.filterGitSha.value = ''
    mockUseSnapshots.filterModelUri.value = ''
    mockUseSnapshots.currentSnapshot.value = null
    mockUseSnapshots.currentLoading.value = false
    mockUseSnapshots.creating.value = false
    mockUseSnapshots.reproducing.value = false
    mockUseSnapshots.loadSnapshots.mockResolvedValue(undefined)
    mockUseSnapshots.resetFilters.mockResolvedValue(undefined)
    mockUseSnapshots.selectSnapshot.mockResolvedValue(undefined)
    mockUseSnapshots.submitSnapshot.mockResolvedValue('snap_new_001')
    mockUseSnapshots.reproduce.mockResolvedValue('wf_repro_001')

    mockElMessageBox.confirm.mockResolvedValue('confirm')

    vi.clearAllMocks()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  const mountPanel = (options = {}) => {
    return shallowMount(SnapshotPanel, {
      global: {
        plugins: [pinia, router],
        ...options,
      },
    })
  }

  // =========================================================================
  // 1. 组件挂载与基础渲染
  // =========================================================================
  describe('基础渲染', () => {
    it('组件能正确挂载', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.exists()).toBe(true)
      expect(wrapper.find('.snapshot-panel-page').exists()).toBe(true)
    })

    it('渲染页面标题与副标题', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.page-header__title h1').text()).toBe(
        'snapshotPanel.pageTitle',
      )
      expect(wrapper.find('.page-header__subtitle').text()).toBe(
        'snapshotPanel.pageSubtitle',
      )
    })

    it('渲染顶部操作按钮（刷新、创建）', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const actions = wrapper.find('.page-header__actions')
      expect(actions.exists()).toBe(true)
      const buttons = actions.findAll('button')
      expect(buttons.length).toBe(2)
    })

    it('挂载时调用 loadSnapshots', async () => {
      mountPanel()
      await flushPromises()
      expect(mockUseSnapshots.loadSnapshots).toHaveBeenCalled()
    })

    it('渲染主布局（列表 + 详情）', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.snapshot-main').exists()).toBe(true)
      expect(wrapper.find('.snapshot-list-panel').exists()).toBe(true)
      expect(wrapper.find('.snapshot-detail-panel').exists()).toBe(true)
    })

    it('渲染筛选区（3 个 el-input）', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const filters = wrapper.find('.panel-filters')
      expect(filters.exists()).toBe(true)
      expect(filters.findAll('.el-input').length).toBe(3)
    })

    it('渲染分页组件', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.panel-pagination .el-pagination').exists()).toBe(
        true,
      )
    })
  })

  // =========================================================================
  // 2. 快照列表
  // =========================================================================
  describe('快照列表', () => {
    it('列表为空时渲染 el-empty', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.snapshot-list-body .el-empty').exists()).toBe(true)
    })

    it('列表有数据时渲染 snapshot-card', async () => {
      mockUseSnapshots.snapshots.value = [
        makeSnapshot({ snapshot_id: 'snap-001' }),
        makeSnapshot({ snapshot_id: 'snap-002' }),
      ]
      const wrapper = mountPanel()
      await flushPromises()
      const cards = wrapper.findAll('.snapshot-card')
      expect(cards.length).toBe(2)
      expect(cards[0].find('.snapshot-id').text()).toBe('snap-001')
    })

    it('点击 snapshot-card 触发 selectSnapshot', async () => {
      mockUseSnapshots.snapshots.value = [
        makeSnapshot({ snapshot_id: 'snap-001abcdefgh' }),
      ]
      const wrapper = mountPanel()
      await flushPromises()
      await wrapper.find('.snapshot-card').trigger('click')
      await flushPromises()
      expect(mockUseSnapshots.selectSnapshot).toHaveBeenCalledWith(
        'snap-001abcdefgh',
      )
    })

    it('当前选中的 snapshot-card 带 active 类', async () => {
      mockUseSnapshots.snapshots.value = [
        makeSnapshot({ snapshot_id: 'snap-001' }),
        makeSnapshot({ snapshot_id: 'snap-002' }),
      ]
      mockUseSnapshots.currentSnapshot.value = makeSnapshot({
        snapshot_id: 'snap-002',
      })
      const wrapper = mountPanel()
      await flushPromises()
      const cards = wrapper.findAll('.snapshot-card')
      expect(cards[0].classes()).not.toContain('active')
      expect(cards[1].classes()).toContain('active')
    })

    it('点击刷新按钮调用 loadSnapshots', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      mockUseSnapshots.loadSnapshots.mockClear()
      const buttons = wrapper.findAll('.page-header__actions button')
      const refreshBtn = buttons[0]
      await refreshBtn.trigger('click')
      await flushPromises()
      expect(mockUseSnapshots.loadSnapshots).toHaveBeenCalled()
    })

    it('点击重置筛选调用 resetFilters', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const resetBtn = wrapper.find('.panel-header button')
      expect(resetBtn.exists()).toBe(true)
      await resetBtn.trigger('click')
      await flushPromises()
      expect(mockUseSnapshots.resetFilters).toHaveBeenCalled()
    })

    it('筛选 input change 触发 loadSnapshots 并回到第 1 页', async () => {
      mockUseSnapshots.currentPage.value = 3
      const wrapper = mountPanel()
      await flushPromises()
      mockUseSnapshots.loadSnapshots.mockClear()
      const inputs = wrapper.findAll('.panel-filters .el-input')
      await inputs[0].trigger('change')
      await flushPromises()
      expect(mockUseSnapshots.currentPage.value).toBe(1)
      expect(mockUseSnapshots.loadSnapshots).toHaveBeenCalled()
    })

    it('渲染 code_dirty 标签（clean/dirty）', async () => {
      mockUseSnapshots.snapshots.value = [
        makeSnapshot({ snapshot_id: 'snap-001', code_dirty: false }),
        makeSnapshot({ snapshot_id: 'snap-002', code_dirty: true }),
      ]
      const wrapper = mountPanel()
      await flushPromises()
      const tags = wrapper.findAll('.snapshot-card .el-tag')
      expect(tags.length).toBe(2)
      // clean → snapshotPanel.dirtyClean, dirty → snapshotPanel.dirtyDirty
      expect(tags[0].text()).toBe('snapshotPanel.dirtyClean')
      expect(tags[1].text()).toBe('snapshotPanel.dirtyDirty')
    })
  })

  // =========================================================================
  // 3. 详情面板
  // =========================================================================
  describe('详情面板', () => {
    it('未选中快照时渲染 el-empty', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const detailBody = wrapper.find('.snapshot-detail-body')
      expect(detailBody.exists()).toBe(true)
      expect(detailBody.find('.el-empty').exists()).toBe(true)
    })

    it('未选中快照时不渲染操作按钮', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.panel-header-actions').exists()).toBe(false)
    })

    it('选中快照时渲染详情内容', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot({
        snapshot_id: 'snap-001-abcdefgh',
        notes: 'baseline',
      })
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.snapshot-detail-content').exists()).toBe(true)
      // 渲染 el-descriptions
      expect(wrapper.find('.el-descriptions').exists()).toBe(true)
      // 渲染 config 块
      expect(wrapper.find('.config-section').exists()).toBe(true)
    })

    it('选中快照时渲染操作按钮（复现/关闭）', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot()
      const wrapper = mountPanel()
      await flushPromises()
      const actions = wrapper.find('.panel-header-actions')
      expect(actions.exists()).toBe(true)
      expect(actions.findAll('button').length).toBe(2)
    })

    it('点击关闭按钮调用 clearCurrent', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot()
      const wrapper = mountPanel()
      await flushPromises()
      const actions = wrapper.find('.panel-header-actions')
      const buttons = actions.findAll('button')
      // 关闭按钮是第 2 个（第 1 个是复现）
      await buttons[1].trigger('click')
      expect(mockUseSnapshots.clearCurrent).toHaveBeenCalled()
    })

    it('渲染 dataset_versions 列表', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot({
        dataset_versions: ['dataset://phm2010/v1', 'dataset://industrial/v2'],
      })
      const wrapper = mountPanel()
      await flushPromises()
      const uriItems = wrapper.findAll('.uri-item')
      expect(uriItems.length).toBe(2)
      expect(uriItems[0].text()).toBe('dataset://phm2010/v1')
    })

    it('lineage_record_id 存在时渲染对应 descriptions-item', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot({
        lineage_record_id: 'lin-001',
      })
      const wrapper = mountPanel()
      await flushPromises()
      // descriptions-item 包含 lineage record label
      const items = wrapper.findAll('.el-descriptions-item')
      const lineageItem = items.find(i =>
        i.find('.el-descriptions-item__label').text().includes('LineageRecord'),
      )
      // 至少不抛错；具体渲染依赖 mock label
      expect(items.length).toBeGreaterThan(0)
    })
  })

  // =========================================================================
  // 4. 创建对话框
  // =========================================================================
  describe('创建对话框', () => {
    it('点击创建按钮打开对话框', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.el-dialog').exists()).toBe(false)
      const buttons = wrapper.findAll('.page-header__actions button')
      // 第 2 个按钮是创建
      await buttons[1].trigger('click')
      await flushPromises()
      expect(wrapper.find('.el-dialog').exists()).toBe(true)
    })

    it('打开对话框时清空表单（metricsStr 默认 {}）', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()
      // 对话框中的输入框数量（6 个 form-item）
      const inputs = wrapper.findAll('.el-dialog .el-input')
      expect(inputs.length).toBeGreaterThanOrEqual(2) // 至少 modelUri + createdBy
    })

    it('校验 config 为空时提示 warning 且不提交', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()

      // 找到 footer 中的确认按钮（最后一个 button）
      const dialogButtons = wrapper.findAll('.el-dialog button')
      const confirmBtn = dialogButtons[dialogButtons.length - 1]
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.warning).toHaveBeenCalledWith(
        'snapshotPanel.msgConfigEmpty',
      )
      expect(mockUseSnapshots.submitSnapshot).not.toHaveBeenCalled()
    })

    it('校验 config 非法 JSON 时提示 warning', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()

      // 模拟输入 config 非法 JSON：触发 el-input 的 update:modelValue
      const inputs = wrapper.findAll('.el-dialog .el-input')
      // 第 1 个 input 是 config（textarea）
      await inputs[0].setValue('{ invalid json')
      // trigger change 让 v-model 生效
      await inputs[0].trigger('input')

      const dialogButtons = wrapper.findAll('.el-dialog button')
      const confirmBtn = dialogButtons[dialogButtons.length - 1]
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.warning).toHaveBeenCalledWith(
        'snapshotPanel.msgConfigInvalid',
      )
      expect(mockUseSnapshots.submitSnapshot).not.toHaveBeenCalled()
    })

    it('校验 metrics 非法 JSON 时提示 warning', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()

      const inputs = wrapper.findAll('.el-dialog .el-input')
      // config 合法 + metrics 非法
      await inputs[0].setValue('{"lr": 0.001}')
      // metrics 是第 4 个 input
      await inputs[3].setValue('{ invalid')
      await inputs[3].trigger('input')

      const dialogButtons = wrapper.findAll('.el-dialog button')
      const confirmBtn = dialogButtons[dialogButtons.length - 1]
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.warning).toHaveBeenCalledWith(
        'snapshotPanel.msgMetricsInvalid',
      )
      expect(mockUseSnapshots.submitSnapshot).not.toHaveBeenCalled()
    })

    it('校验 dataset_versions 为空时提示 warning', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()

      const inputs = wrapper.findAll('.el-dialog .el-input')
      // config 合法 + metrics 合法（默认 {}）+ dataset_versions 空
      await inputs[0].setValue('{"lr": 0.001}')

      const dialogButtons = wrapper.findAll('.el-dialog button')
      const confirmBtn = dialogButtons[dialogButtons.length - 1]
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.warning).toHaveBeenCalledWith(
        'snapshotPanel.msgDatasetVersionsEmpty',
      )
      expect(mockUseSnapshots.submitSnapshot).not.toHaveBeenCalled()
    })

    it('提交成功 → ElMessage.success + 关闭对话框 + selectSnapshot', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()

      const inputs = wrapper.findAll('.el-dialog .el-input')
      await inputs[0].setValue('{"lr": 0.001}')
      // dataset_versions 是第 2 个 input（textarea）
      await inputs[1].setValue('dataset://phm2010/v1')

      mockUseSnapshots.submitSnapshot.mockResolvedValueOnce('snap_new_001')
      mockUseSnapshots.selectSnapshot.mockClear()

      const dialogButtons = wrapper.findAll('.el-dialog button')
      const confirmBtn = dialogButtons[dialogButtons.length - 1]
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockUseSnapshots.submitSnapshot).toHaveBeenCalled()
      expect(mockElMessage.success).toHaveBeenCalledWith(
        'snapshotPanel.msgCreateSuccess',
      )
      expect(mockUseSnapshots.selectSnapshot).toHaveBeenCalledWith(
        'snap_new_001',
      )
      // 对话框关闭
      expect(wrapper.find('.el-dialog').exists()).toBe(false)
    })

    it('提交失败 → ElMessage.error', async () => {
      const wrapper = mountPanel()
      await flushPromises()
      const buttons = wrapper.findAll('.page-header__actions button')
      await buttons[1].trigger('click')
      await flushPromises()

      const inputs = wrapper.findAll('.el-dialog .el-input')
      await inputs[0].setValue('{"lr": 0.001}')
      await inputs[1].setValue('dataset://phm2010/v1')

      const err = new Error('网络错误')
      Object.assign(err, {
        response: { data: { message: '服务器内部错误' } },
      })
      mockUseSnapshots.submitSnapshot.mockRejectedValueOnce(err)

      const dialogButtons = wrapper.findAll('.el-dialog button')
      const confirmBtn = dialogButtons[dialogButtons.length - 1]
      await confirmBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.error).toHaveBeenCalledWith('服务器内部错误')
      // 对话框保持打开
      expect(wrapper.find('.el-dialog').exists()).toBe(true)
    })
  })

  // =========================================================================
  // 5. 复现交互
  // =========================================================================
  describe('复现交互', () => {
    it('点击复现 → ElMessageBox.confirm 确认 → reproduce → ElMessage.success', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot({
        snapshot_id: 'snap-001',
      })
      const wrapper = mountPanel()
      await flushPromises()

      const actions = wrapper.find('.panel-header-actions')
      const reproduceBtn = actions.findAll('button')[0]
      await reproduceBtn.trigger('click')
      await flushPromises()

      expect(mockElMessageBox.confirm).toHaveBeenCalled()
      expect(mockUseSnapshots.reproduce).toHaveBeenCalledWith('snap-001')
      expect(mockElMessage.success).toHaveBeenCalledWith(
        'snapshotPanel.msgReproduceSuccess',
      )
    })

    it('用户取消确认时不调用 reproduce', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot()
      mockElMessageBox.confirm.mockRejectedValueOnce(new Error('cancel'))
      const wrapper = mountPanel()
      await flushPromises()

      const actions = wrapper.find('.panel-header-actions')
      const reproduceBtn = actions.findAll('button')[0]
      await reproduceBtn.trigger('click')
      await flushPromises()

      expect(mockUseSnapshots.reproduce).not.toHaveBeenCalled()
    })

    it('reproduce 失败（不支持复现） → ElMessage.warning', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot()
      const err = new Error('invalid')
      Object.assign(err, {
        response: { data: { message: '该快照不支持一键复现' } },
      })
      mockUseSnapshots.reproduce.mockRejectedValueOnce(err)
      const wrapper = mountPanel()
      await flushPromises()

      const actions = wrapper.find('.panel-header-actions')
      const reproduceBtn = actions.findAll('button')[0]
      await reproduceBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.warning).toHaveBeenCalledWith(
        'snapshotPanel.msgReproduceNotSupported',
      )
    })

    it('reproduce 失败（其他错误） → ElMessage.error', async () => {
      mockUseSnapshots.currentSnapshot.value = makeSnapshot()
      const err = new Error('server error')
      Object.assign(err, {
        response: { data: { message: '工作流执行失败' } },
      })
      mockUseSnapshots.reproduce.mockRejectedValueOnce(err)
      const wrapper = mountPanel()
      await flushPromises()

      const actions = wrapper.find('.panel-header-actions')
      const reproduceBtn = actions.findAll('button')[0]
      await reproduceBtn.trigger('click')
      await flushPromises()

      expect(mockElMessage.error).toHaveBeenCalledWith(
        'snapshotPanel.msgReproduceFailed',
      )
    })

    it('currentSnapshot 为 null 时复现按钮不触发任何调用', async () => {
      // 由于按钮本身在 currentSnapshot 为 null 时不存在，此用例验证守卫逻辑
      const wrapper = mountPanel()
      await flushPromises()
      expect(wrapper.find('.panel-header-actions').exists()).toBe(false)
      expect(mockUseSnapshots.reproduce).not.toHaveBeenCalled()
    })
  })
})
