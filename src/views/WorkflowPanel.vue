<template>
  <div class="workflow-panel-page">
    <!-- ===== Page Header ===== -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('workflowPanel.pageTitle') }}</h1>
        <span class="page-header__subtitle">
          {{ t('workflowPanel.pageSubtitle') }}
        </span>
      </div>
      <div class="page-header__actions">
        <el-button
          size="small"
          :icon="Refresh"
          :loading="loading"
          @click="handleRefresh"
        >
          {{ t('workflowPanel.btnRefresh') }}
        </el-button>
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="openSubmitDialog"
        >
          {{ t('workflowPanel.btnSubmit') }}
        </el-button>
        <el-button
          v-if="canCancel"
          size="small"
          :icon="CircleClose"
          @click="handleCancelCurrent"
        >
          {{ t('workflowPanel.btnCancel') }}
        </el-button>
        <el-button
          v-if="canResume"
          size="small"
          type="warning"
          :icon="VideoPlay"
          @click="openResumeDialog"
        >
          {{ t('workflowPanel.btnResume') }}
        </el-button>
        <el-button
          v-if="currentRunId"
          size="small"
          type="danger"
          :icon="Delete"
          @click="handleDeleteCurrent"
        >
          {{ t('workflowPanel.btnDelete') }}
        </el-button>
      </div>
    </div>

    <!-- ===== Main Layout: List | DAG + Events ===== -->
    <div class="workflow-main">
      <!-- ===== Left: Workflow List ===== -->
      <div class="workflow-list-panel">
        <div class="panel-header">
          <span class="panel-title">{{ t('workflowPanel.listTitle') }}</span>
          <div class="panel-filter">
            <el-select
              v-model="statusFilter"
              size="small"
              :placeholder="t('workflowPanel.filterStatusPlaceholder')"
              clearable
              style="width: 120px"
              @change="handleFilterChange"
            >
              <el-option
                v-for="opt in statusOptions"
                :key="opt.value"
                :label="opt.label"
                :value="opt.value"
              />
            </el-select>
          </div>
        </div>

        <div
          v-loading="loading"
          class="workflow-list-body"
        >
          <el-empty
            v-if="!loading && workflows.length === 0"
            :description="t('workflowPanel.emptyNoWorkflows')"
            :image-size="60"
          />
          <div
            v-for="wf in workflows"
            :key="wf.id"
            class="workflow-card"
            :class="{ active: wf.id === currentRunId }"
            @click="handleSelectWorkflow(wf.id)"
          >
            <div class="workflow-card-header">
              <span class="workflow-name">{{ wf.name }}</span>
              <el-tag
                :type="statusTagType(wf.status)"
                size="small"
                effect="light"
              >
                {{ statusLabel(wf.status) }}
              </el-tag>
            </div>
            <div class="workflow-card-meta">
              <span class="meta-item mono">{{ wf.id.slice(0, 12) }}…</span>
              <span class="meta-item">v{{ wf.version }}</span>
            </div>
            <div class="workflow-card-footer">
              <span class="meta-item">
                {{ t('workflowPanel.nodesCount') }}: {{ wf.spec?.nodes?.length ?? 0 }}
              </span>
              <span
                v-if="wf.created_at"
                class="meta-item"
              >
                {{ formatTime(wf.created_at) }}
              </span>
            </div>
          </div>
        </div>

        <div class="workflow-list-footer">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="totalCount"
            layout="prev, pager, next"
            small
            @current-change="handlePageChange"
          />
        </div>
      </div>

      <!-- ===== Right: DAG Visualization + Event Log ===== -->
      <div class="workflow-detail-panel">
        <!-- DAG Visualization -->
        <div class="dag-section">
          <div class="panel-header">
            <span class="panel-title">{{ t('workflowPanel.dagTitle') }}</span>
            <div
              v-if="currentRunId"
              class="dag-status"
            >
              <el-tag
                :type="statusTagType(currentDisplayStatus)"
                size="small"
              >
                {{ statusLabel(currentDisplayStatus) }}
              </el-tag>
              <span
                class="stream-indicator"
                :class="{ connected: stream.isConnected.value, done: stream.isDone.value }"
              >
                {{ streamStatusText }}
              </span>
            </div>
          </div>

          <div class="dag-canvas-wrapper">
            <el-empty
              v-if="!currentSpec"
              :description="t('workflowPanel.emptyNoSelection')"
              :image-size="80"
            />
            <svg
              v-else
              :viewBox="`0 0 ${dagLayout.width} ${dagLayout.height}`"
              class="dag-svg"
              preserveAspectRatio="xMidYMid meet"
            >
              <!-- Edges -->
              <path
                v-for="(edge, idx) in dagLayout.edges"
                :key="`edge-${idx}`"
                :d="edge.path"
                :class="['dag-edge', { active: isEdgeActive(edge) }]"
                fill="none"
              />
              <!-- Nodes -->
              <g
                v-for="node in dagLayout.nodes"
                :key="node.node_id"
                :transform="`translate(${node.x}, ${node.y})`"
                class="dag-node-group"
                @click="selectedNodeId = node.node_id"
              >
                <rect
                  :width="nodeWidth"
                  :height="nodeHeight"
                  :rx="6"
                  :class="['dag-node-rect', `status-${getNodeStatus(node.node_id)}`]"
                />
                <text
                  :x="nodeWidth / 2"
                  :y="22"
                  text-anchor="middle"
                  class="dag-node-title"
                >
                  {{ node.node_id }}
                </text>
                <text
                  :x="nodeWidth / 2"
                  :y="42"
                  text-anchor="middle"
                  class="dag-node-type"
                >
                  {{ node.task_type }}
                </text>
                <text
                  :x="nodeWidth / 2"
                  :y="62"
                  text-anchor="middle"
                  class="dag-node-status"
                >
                  {{ statusLabel(getNodeStatus(node.node_id)) }}
                </text>
              </g>
            </svg>
          </div>
        </div>

        <!-- Event Log -->
        <div class="event-log-section">
          <div class="panel-header">
            <span class="panel-title">{{ t('workflowPanel.eventLogTitle') }}</span>
            <el-button
              v-if="stream.events.value.length > 0"
              text
              size="small"
              @click="stream.reset"
            >
              {{ t('workflowPanel.btnClearEvents') }}
            </el-button>
          </div>
          <div
            ref="eventLogEl"
            class="event-log-body"
          >
            <div
              v-if="stream.events.value.length === 0"
              class="event-log-empty"
            >
              {{ t('workflowPanel.emptyNoEvents') }}
            </div>
            <div
              v-for="(ev, idx) in stream.events.value"
              :key="idx"
              class="event-log-entry"
              :class="`event-${ev.event_type}`"
            >
              <span class="event-time">{{ formatEventTime(ev.timestamp) }}</span>
              <span class="event-type">{{ ev.event_type }}</span>
              <span
                v-if="ev.node_id"
                class="event-node"
              >[{{ ev.node_id }}]</span>
              <span
                v-if="getEventMessage(ev)"
                class="event-msg"
              >{{ getEventMessage(ev) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== Submit / Resume Dialog ===== -->
    <el-dialog
      v-model="submitDialogVisible"
      :title="submitDialogTitle"
      width="720px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="submitFormRef"
        :model="submitForm"
        label-width="100px"
      >
        <el-form-item :label="t('workflowPanel.formTemplateName')">
          <el-select
            v-model="submitForm.templateName"
            :placeholder="t('workflowPanel.formTemplatePlaceholder')"
            clearable
            style="width: 100%"
            @change="handleTemplateSelect"
          >
            <el-option
              v-for="tpl in builtinTemplates"
              :key="tpl.name"
              :label="`${tpl.name} (v${tpl.version})`"
              :value="tpl.name"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('workflowPanel.formSpec')">
          <el-input
            v-model="submitForm.specYaml"
            type="textarea"
            :rows="14"
            :placeholder="t('workflowPanel.formSpecPlaceholder')"
            class="spec-editor"
          />
        </el-form-item>
        <el-form-item :label="t('workflowPanel.formOwnerId')">
          <el-input
            v-model="submitForm.ownerId"
            :placeholder="t('workflowPanel.formOwnerPlaceholder')"
            clearable
          />
        </el-form-item>
      </el-form>

      <template #footer>
        <el-button @click="submitDialogVisible = false">
          {{ t('workflowPanel.btnCancelDialog') }}
        </el-button>
        <el-button
          :loading="validating"
          @click="handleValidate"
        >
          {{ t('workflowPanel.btnValidate') }}
        </el-button>
        <el-button
          type="primary"
          :loading="submitting"
          @click="handleSubmit"
        >
          {{ submitConfirmButtonText }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Plus,
  CircleClose,
  VideoPlay,
  Delete,
} from '@element-plus/icons-vue'
import { useWorkflow } from '@/composables/useWorkflow'
import type { WorkflowSpec, TaskStatus, WorkflowEvent } from '@/contracts/task'

const { t } = useI18n()

// ---------------------------------------------------------------------------
// useWorkflow composable 接入
// ---------------------------------------------------------------------------
const {
  workflows,
  loading,
  totalCount,
  currentPage,
  pageSize,
  statusFilter,
  loadWorkflows,
  removeWorkflow,
  currentRunId,
  currentStatus,
  submitWorkflow,
  resumeCurrentWorkflow,
  cancelCurrent,
  refreshCurrentStatus,
  selectWorkflow,
  stream,
  validate,
} = useWorkflow()

// ---------------------------------------------------------------------------
// 状态枚举
// ---------------------------------------------------------------------------
const statusOptions = [
  { value: 'pending', label: t('workflowPanel.statusPending') },
  { value: 'queued', label: t('workflowPanel.statusQueued') },
  { value: 'running', label: t('workflowPanel.statusRunning') },
  { value: 'completed', label: t('workflowPanel.statusCompleted') },
  { value: 'failed', label: t('workflowPanel.statusFailed') },
  { value: 'cancelled', label: t('workflowPanel.statusCancelled') },
  { value: 'skipped', label: t('workflowPanel.statusSkipped') },
]

function statusTagType(s?: string | null) {
  switch (s) {
    case 'completed': return 'success'
    case 'failed': return 'danger'
    case 'cancelled': return 'info'
    case 'running': return 'primary'
    case 'queued':
    case 'pending': return 'warning'
    case 'skipped': return 'info'
    default: return 'info'
  }
}

function statusLabel(s?: string | null): string {
  const map: Record<string, string> = {
    pending: t('workflowPanel.statusPending'),
    queued: t('workflowPanel.statusQueued'),
    running: t('workflowPanel.statusRunning'),
    completed: t('workflowPanel.statusCompleted'),
    failed: t('workflowPanel.statusFailed'),
    cancelled: t('workflowPanel.statusCancelled'),
    skipped: t('workflowPanel.statusSkipped'),
  }
  return map[s || ''] ?? s ?? '-'
}

// ---------------------------------------------------------------------------
// 内置模板（与后端 python/app/workflow/templates/builtin/*.yaml 对应）
// 提供下拉选择，用户选择后填充 spec 编辑器
// ---------------------------------------------------------------------------
const builtinTemplates = ref<Array<{ name: string; version: string; spec: WorkflowSpec }>>([])

const SAMPLE_TOOL_WEAR_SPEC: WorkflowSpec = {
  name: '刀具磨损预测流水线',
  version: '1.0.0',
  nodes: [
    { node_id: 'load_dataset', task_type: 'dataset_loader', params: { loader_type: 'phm2010' }, inputs: {}, retry: 0, timeout_seconds: 600 },
    { node_id: 'train_model', task_type: 'ltc_trainer', params: { model_type: 'ltc', epochs: 50 }, inputs: { train_split: '${load_dataset.train_split}' }, retry: 1, timeout_seconds: 7200 },
    { node_id: 'evaluate_model', task_type: 'model_evaluator', params: { metrics: ['mae', 'r2'] }, inputs: { test_split: '${load_dataset.test_split}', trained_model: '${train_model.model_artifact}' }, retry: 0, timeout_seconds: 1800 },
    { node_id: 'generate_report', task_type: 'report_generator', params: { template: 'tool_wear_evaluation.md' }, inputs: { metrics: '${evaluate_model.metrics_artifact}' }, retry: 0, timeout_seconds: 600 },
  ],
  edges: [
    { upstream: 'load_dataset', downstream: 'train_model' },
    { upstream: 'train_model', downstream: 'evaluate_model' },
    { upstream: 'evaluate_model', downstream: 'generate_report' },
  ],
  inputs: {},
  outputs: { wear_report: '${generate_report.report_artifact}' },
  metadata: { max_concurrent: 2, tags: ['tool_wear', 'ltc'] },
}

function initBuiltinTemplates() {
  builtinTemplates.value = [
    { name: SAMPLE_TOOL_WEAR_SPEC.name, version: SAMPLE_TOOL_WEAR_SPEC.version, spec: SAMPLE_TOOL_WEAR_SPEC },
  ]
}

// ---------------------------------------------------------------------------
// 当前选中的工作流 spec（用于 DAG 可视化）
// ---------------------------------------------------------------------------
const currentSpec = computed<WorkflowSpec | null>(() => {
  if (!currentRunId.value) return null
  // 优先从列表中取 spec（完整结构），否则从 currentStatus 取
  const wf = workflows.value.find(w => w.id === currentRunId.value)
  if (wf?.spec) return wf.spec
  return null
})

const currentDisplayStatus = computed<string>(() => {
  // 优先采用 SSE 实时状态，其次持久化状态
  if (stream.currentStatus.value) return stream.currentStatus.value
  if (currentStatus.value?.status) return currentStatus.value.status
  const wf = workflows.value.find(w => w.id === currentRunId.value)
  return wf?.status ?? 'pending'
})

const canCancel = computed(() => {
  const s = currentDisplayStatus.value
  return currentRunId.value && (s === 'running' || s === 'queued' || s === 'pending')
})

const canResume = computed(() => {
  const s = currentDisplayStatus.value
  return currentRunId.value && (s === 'failed' || s === 'cancelled')
})

const streamStatusText = computed(() => {
  if (stream.isDone.value) return t('workflowPanel.streamDone')
  if (stream.isConnected.value) return t('workflowPanel.streamConnected')
  if (stream.error.value) return t('workflowPanel.streamError')
  return t('workflowPanel.streamIdle')
})

// ---------------------------------------------------------------------------
// 节点状态：合并 SSE nodeStatuses + 持久化 node_statuses
// ---------------------------------------------------------------------------
function getNodeStatus(nodeId: string): TaskStatus {
  // SSE 优先
  const sseStatus = stream.nodeStatuses.value[nodeId]
  if (sseStatus) return sseStatus
  // 持久化兜底
  const persisted = currentStatus.value?.node_statuses?.[nodeId]
  if (persisted) return persisted
  return 'pending'
}

// ---------------------------------------------------------------------------
// DAG 分层布局（自实现，避免引入 dagre 依赖）
// 算法：Kahn 拓扑排序 + 按入度分层
// ---------------------------------------------------------------------------
const nodeWidth = 160
const nodeHeight = 76
const layerGapX = 220
const padding = 40

interface LayoutNode {
  node_id: string
  task_type: string
  x: number
  y: number
  layer: number
}

interface LayoutEdge {
  path: string
  upstream: string
  downstream: string
}

const dagLayout = computed(() => {
  const spec = currentSpec.value
  if (!spec || spec.nodes.length === 0) {
    return { nodes: [] as LayoutNode[], edges: [] as LayoutEdge[], width: 0, height: 0 }
  }

  // 构建邻接表 + 入度
  const adj = new Map<string, string[]>()
  const inDegree = new Map<string, number>()
  spec.nodes.forEach(n => {
    adj.set(n.node_id, [])
    inDegree.set(n.node_id, 0)
  })
  spec.edges.forEach(e => {
    adj.get(e.upstream)?.push(e.downstream)
    inDegree.set(e.downstream, (inDegree.get(e.downstream) ?? 0) + 1)
  })

  // Kahn 分层：BFS，每层为当前入度为 0 的节点集合
  const layers: string[][] = []
  const remaining = new Map(inDegree)
  const visited = new Set<string>()

  while (visited.size < spec.nodes.length) {
    const layer = spec.nodes
      .map(n => n.node_id)
      .filter(id => !visited.has(id) && (remaining.get(id) ?? 0) === 0)
    if (layer.length === 0) {
      // 检测到环（理论上 validate 已拦截），把剩余节点强行放入最后一层避免死循环
      const leftover = spec.nodes.map(n => n.node_id).filter(id => !visited.has(id))
      layers.push(leftover)
      leftover.forEach(id => visited.add(id))
      break
    }
    layers.push(layer)
    layer.forEach(id => {
      visited.add(id)
      adj.get(id)?.forEach(down => {
        remaining.set(down, (remaining.get(down) ?? 1) - 1)
      })
    })
  }

  // 计算坐标：每层水平排列，层间垂直间距
  const nodeMap = new Map(spec.nodes.map(n => [n.node_id, n]))
  const layoutNodes: LayoutNode[] = []
  const maxLayerSize = Math.max(...layers.map(l => l.length), 1)

  layers.forEach((layer, layerIdx) => {
    const layerHeight = layer.length * nodeHeight + (layer.length - 1) * 20
    const startY = (maxLayerSize * (nodeHeight + 20) - layerHeight) / 2 + padding
    layer.forEach((nodeId, idx) => {
      const node = nodeMap.get(nodeId)
      layoutNodes.push({
        node_id: nodeId,
        task_type: node?.task_type ?? '',
        x: padding + layerIdx * layerGapX,
        y: startY + idx * (nodeHeight + 20),
        layer: layerIdx,
      })
    })
  })

  const totalWidth = padding * 2 + layers.length * layerGapX
  const totalHeight = padding * 2 + maxLayerSize * (nodeHeight + 20)

  // 计算边路径（贝塞尔曲线连接 downstream 节点底部 → upstream 节点顶部）
  const nodePos = new Map(layoutNodes.map(n => [n.node_id, n]))
  const layoutEdges: LayoutEdge[] = spec.edges.map(e => {
    const u = nodePos.get(e.upstream)
    const d = nodePos.get(e.downstream)
    if (!u || !d) return { path: '', upstream: e.upstream, downstream: e.downstream }
    const x1 = u.x + nodeWidth / 2
    const y1 = u.y + nodeHeight
    const x2 = d.x + nodeWidth / 2
    const y2 = d.y
    const midY = (y1 + y2) / 2
    return {
      path: `M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`,
      upstream: e.upstream,
      downstream: e.downstream,
    }
  }).filter(e => e.path !== '')

  return { nodes: layoutNodes, edges: layoutEdges, width: totalWidth, height: totalHeight }
})

function isEdgeActive(edge: LayoutEdge): boolean {
  // 当 upstream 节点 completed 且 downstream 节点已启动时高亮
  const u = getNodeStatus(edge.upstream)
  const d = getNodeStatus(edge.downstream)
  return u === 'completed' && d !== 'pending'
}

// ---------------------------------------------------------------------------
// 事件日志：自动滚动到底部
// ---------------------------------------------------------------------------
const eventLogEl = ref<HTMLElement | null>(null)

watch(
  () => stream.events.value.length,
  async () => {
    await nextTick()
    if (eventLogEl.value) {
      eventLogEl.value.scrollTop = eventLogEl.value.scrollHeight
    }
  },
)

function getEventMessage(ev: WorkflowEvent): string {
  const payload = ev.payload as Record<string, unknown>
  if (typeof payload?.error === 'string') return payload.error
  if (typeof payload?.message === 'string') return payload.message
  if (typeof payload?.progress === 'number') return `${Math.round(payload.progress * 100)}%`
  return ''
}

function formatEventTime(ts: number): string {
  if (!ts) return '--:--:--'
  const d = new Date(ts * 1000)
  return d.toLocaleTimeString('zh-CN', { hour12: false })
}

function formatTime(s: string | null): string {
  if (!s) return '-'
  try {
    const d = new Date(s)
    return d.toLocaleString('zh-CN', { hour12: false })
  } catch {
    return s
  }
}

// ---------------------------------------------------------------------------
// 列表交互
// ---------------------------------------------------------------------------
function handleRefresh() {
  loadWorkflows()
  if (currentRunId.value) refreshCurrentStatus()
}

function handleFilterChange() {
  currentPage.value = 1
  loadWorkflows()
}

function handlePageChange() {
  loadWorkflows()
}

async function handleSelectWorkflow(id: string) {
  try {
    await selectWorkflow(id)
  } catch (e) {
    console.warn('[WorkflowPanel] selectWorkflow failed:', e)
  }
}

async function handleCancelCurrent() {
  if (!currentRunId.value) return
  try {
    await ElMessageBox.confirm(
      t('workflowPanel.confirmCancel'),
      t('workflowPanel.warning'),
      { type: 'warning' },
    )
  } catch {
    return // 用户取消
  }
  try {
    await cancelCurrent()
    ElMessage.success(t('workflowPanel.msgCancelSuccess'))
  } catch (e) {
    console.warn('[WorkflowPanel] cancel failed:', e)
  }
}

async function handleDeleteCurrent() {
  if (!currentRunId.value) return
  try {
    await ElMessageBox.confirm(
      t('workflowPanel.confirmDelete'),
      t('workflowPanel.warning'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  try {
    await removeWorkflow(currentRunId.value)
    ElMessage.success(t('workflowPanel.msgDeleteSuccess'))
  } catch (e) {
    console.warn('[WorkflowPanel] delete failed:', e)
  }
}

// ---------------------------------------------------------------------------
// 提交 / 续跑对话框
// ---------------------------------------------------------------------------
const submitDialogVisible = ref(false)
const submitMode = ref<'submit' | 'resume'>('submit')
const submitFormRef = ref()
const submitForm = ref({
  templateName: '',
  specYaml: '',
  ownerId: '',
})
const validating = ref(false)
const submitting = ref(false)
const selectedNodeId = ref<string>('')

const submitDialogTitle = computed(() =>
  submitMode.value === 'submit'
    ? t('workflowPanel.dialogSubmitTitle')
    : t('workflowPanel.dialogResumeTitle'),
)

const submitConfirmButtonText = computed(() =>
  submitMode.value === 'submit'
    ? t('workflowPanel.btnSubmitConfirm')
    : t('workflowPanel.btnResumeConfirm'),
)

function openSubmitDialog() {
  submitMode.value = 'submit'
  submitForm.value = { templateName: '', specYaml: '', ownerId: '' }
  submitDialogVisible.value = true
}

function openResumeDialog() {
  if (!currentRunId.value) return
  submitMode.value = 'resume'
  // 续跑时预填当前 spec
  const wf = workflows.value.find(w => w.id === currentRunId.value)
  if (wf?.spec) {
    submitForm.value = {
      templateName: '',
      specYaml: JSON.stringify(wf.spec, null, 2),
      ownerId: wf.owner_id ?? '',
    }
  } else {
    submitForm.value = { templateName: '', specYaml: '', ownerId: '' }
  }
  submitDialogVisible.value = true
}

function handleTemplateSelect(name: string) {
  if (!name) return
  const tpl = builtinTemplates.value.find(t => t.name === name)
  if (tpl) {
    submitForm.value.specYaml = JSON.stringify(tpl.spec, null, 2)
  }
}

function parseSpec(): WorkflowSpec | null {
  const text = submitForm.value.specYaml.trim()
  if (!text) {
    ElMessage.warning(t('workflowPanel.msgSpecEmpty'))
    return null
  }
  try {
    // 后端模板是 YAML，前端为简化依赖使用 JSON 解析；
    // 用户也可粘贴 YAML（需后端 /validate 端点解析，此处先尝试 JSON）
    const obj = JSON.parse(text) as WorkflowSpec
    if (!obj.name || !obj.nodes || !obj.edges) {
      ElMessage.error(t('workflowPanel.msgSpecInvalid'))
      return null
    }
    return obj
  } catch {
    // JSON 解析失败时尝试 YAML 简单解析（key: value 形式）
    ElMessage.error(t('workflowPanel.msgSpecParseError'))
    return null
  }
}

async function handleValidate() {
  const spec = parseSpec()
  if (!spec) return
  validating.value = true
  try {
    const result = await validate(spec)
    if (result.valid) {
      ElMessage.success(
        t('workflowPanel.msgValidateSuccess')
          .replace('{nodes}', String(result.node_count))
          .replace('{edges}', String(result.edge_count)),
      )
    } else {
      ElMessage.warning(t('workflowPanel.msgValidateFailed'))
    }
  } catch (e) {
    console.warn('[WorkflowPanel] validate failed:', e)
  } finally {
    validating.value = false
  }
}

async function handleSubmit() {
  const spec = parseSpec()
  if (!spec) return
  submitting.value = true
  try {
    if (submitMode.value === 'submit') {
      const runId = await submitWorkflow({
        spec,
        owner_id: submitForm.value.ownerId || undefined,
      })
      ElMessage.success(t('workflowPanel.msgSubmitSuccess').replace('{id}', runId.slice(0, 12)))
      submitDialogVisible.value = false
      await loadWorkflows()
    } else {
      // 续跑：基于当前 run_id
      if (!currentRunId.value) {
        ElMessage.warning(t('workflowPanel.msgNoCurrentRun'))
        return
      }
      const newRunId = await resumeCurrentWorkflow(currentRunId.value, {
        spec,
        owner_id: submitForm.value.ownerId || undefined,
      })
      ElMessage.success(t('workflowPanel.msgResumeSuccess').replace('{id}', newRunId.slice(0, 12)))
      submitDialogVisible.value = false
      await loadWorkflows()
    }
  } catch (e) {
    console.warn('[WorkflowPanel] submit/resume failed:', e)
  } finally {
    submitting.value = false
  }
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------
onMounted(() => {
  initBuiltinTemplates()
  loadWorkflows()
})

// 监听 SSE 终态：自动刷新列表与持久化状态
watch(
  () => stream.isDone.value,
  (done) => {
    if (done) {
      void loadWorkflows()
      if (currentRunId.value) void refreshCurrentStatus()
    }
  },
)
</script>

<style scoped>
.workflow-panel-page {
  padding: 16px;
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 12px;
  overflow: hidden;
}

/* ===== Page Header ===== */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  flex-shrink: 0;
}
.page-header__title h1 {
  margin: 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.page-header__subtitle {
  display: block;
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}
.page-header__actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

/* ===== Main Layout ===== */
.workflow-main {
  flex: 1;
  display: grid;
  grid-template-columns: 320px 1fr;
  gap: 12px;
  min-height: 0;
}

/* ===== List Panel ===== */
.workflow-list-panel {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  overflow: hidden;
}
.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}
.panel-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}
.workflow-list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}
.workflow-card {
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  padding: 8px 10px;
  margin-bottom: 6px;
  cursor: pointer;
  transition: all 0.2s;
}
.workflow-card:hover {
  border-color: var(--el-color-primary-light-5);
  background: var(--el-fill-color-light);
}
.workflow-card.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}
.workflow-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 6px;
}
.workflow-name {
  font-size: 13px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.workflow-card-meta,
.workflow-card-footer {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.meta-item {
  font-size: 11px;
  color: var(--el-text-color-secondary);
}
.mono {
  font-family: 'Consolas', 'Monaco', monospace;
}
.workflow-list-footer {
  padding: 6px 8px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  justify-content: center;
}

/* ===== Detail Panel ===== */
.workflow-detail-panel {
  display: grid;
  grid-template-rows: 1fr 200px;
  gap: 12px;
  min-height: 0;
}

/* ===== DAG Section ===== */
.dag-section {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  overflow: hidden;
}
.dag-status {
  display: flex;
  align-items: center;
  gap: 8px;
}
.stream-indicator {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: 3px;
  background: var(--el-fill-color);
  color: var(--el-text-color-secondary);
}
.stream-indicator.connected {
  background: var(--el-color-success-light-9);
  color: var(--el-color-success);
}
.stream-indicator.done {
  background: var(--el-fill-color-dark);
  color: var(--el-text-color-regular);
}
.dag-canvas-wrapper {
  flex: 1;
  overflow: auto;
  padding: 16px;
  display: flex;
  align-items: center;
  justify-content: center;
}
.dag-svg {
  width: 100%;
  height: 100%;
  min-height: 300px;
}
.dag-edge {
  stroke: var(--el-border-color);
  stroke-width: 1.5;
  fill: none;
  transition: stroke 0.3s;
}
.dag-edge.active {
  stroke: var(--el-color-primary);
  stroke-width: 2;
}
.dag-node-group {
  cursor: pointer;
}
.dag-node-rect {
  stroke-width: 1.5;
  stroke: var(--el-border-color);
  fill: var(--el-bg-color);
  transition: fill 0.3s, stroke 0.3s;
}
.dag-node-rect.status-pending {
  fill: var(--el-fill-color-light);
  stroke: var(--el-border-color);
}
.dag-node-rect.status-running {
  fill: var(--el-color-primary-light-8);
  stroke: var(--el-color-primary);
}
.dag-node-rect.status-completed {
  fill: var(--el-color-success-light-9);
  stroke: var(--el-color-success);
}
.dag-node-rect.status-failed {
  fill: var(--el-color-danger-light-9);
  stroke: var(--el-color-danger);
}
.dag-node-rect.status-skipped,
.dag-node-rect.status-cancelled {
  fill: var(--el-fill-color-dark);
  stroke: var(--el-text-color-disabled);
}
.dag-node-title {
  font-size: 12px;
  font-weight: 600;
  fill: var(--el-text-color-primary);
}
.dag-node-type {
  font-size: 10px;
  fill: var(--el-text-color-secondary);
}
.dag-node-status {
  font-size: 10px;
  font-weight: 500;
  fill: var(--el-text-color-regular);
}

/* ===== Event Log ===== */
.event-log-section {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-light);
  border-radius: 6px;
  overflow: hidden;
}
.event-log-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px 12px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  background: var(--el-fill-color-blank);
}
.event-log-empty {
  color: var(--el-text-color-secondary);
  text-align: center;
  padding: 20px 0;
}
.event-log-entry {
  padding: 3px 0;
  border-bottom: 1px dashed var(--el-border-color-lighter);
  display: flex;
  gap: 8px;
  align-items: baseline;
}
.event-time {
  color: var(--el-text-color-secondary);
  flex-shrink: 0;
}
.event-type {
  font-weight: 600;
  flex-shrink: 0;
  min-width: 110px;
}
.event-node {
  color: var(--el-color-primary);
  flex-shrink: 0;
}
.event-msg {
  color: var(--el-text-color-regular);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.event-node_started .event-type { color: var(--el-color-primary); }
.event-node_completed .event-type { color: var(--el-color-success); }
.event-node_failed .event-type { color: var(--el-color-danger); }
.event-node_skipped .event-type { color: var(--el-text-color-secondary); }
.event-workflow_completed .event-type { color: var(--el-color-success); }
.event-workflow_failed .event-type { color: var(--el-color-danger); }

/* ===== Spec Editor ===== */
:deep(.spec-editor .el-textarea__inner) {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}
</style>
