<template>
  <div class="process-planning-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div>
        <h2>{{ $t('processPlanning.pageTitle') }}</h2>
        <p class="subtitle">{{ $t('processPlanning.subtitle') }}</p>
      </div>
      <el-tag
        :type="statusTagType"
        size="default"
        effect="light"
        class="status-tag"
      >
        <el-icon
          v-if="requestState === 'loading'"
          class="is-loading"
        >
          <Loading />
        </el-icon>
        {{ statusText }}
      </el-tag>
    </div>

    <!-- 主体三栏布局：左（特征） / 中（工序+3D） / 右（G代码） -->
    <el-container class="main-container">
      <!-- 左侧：特征面板 -->
      <el-aside
        :width="isMobile ? '100%' : '320px'"
        class="left-panel"
      >
        <el-card
          shadow="never"
          class="panel-card"
        >
          <template #header>
            <div class="panel-header">
              <span class="panel-title">
                <el-icon><Grid /></el-icon>
                {{ $t('processPlanning.featurePanel.title') }}
              </span>
            </div>
          </template>

          <!-- 工件参数 -->
          <el-form
            :model="partInfo"
            label-position="top"
            size="small"
            class="part-form"
          >
            <div class="form-section">
              <div class="section-label">
                {{ $t('processPlanning.featurePanel.partInfo') }}
              </div>
              <el-form-item :label="$t('processPlanning.featurePanel.material')">
                <el-select
                  v-model="partInfo.material"
                  :placeholder="$t('processPlanning.featurePanel.selectMaterial')"
                  style="width: 100%"
                >
                  <el-option
                    v-for="m in materialOptions"
                    :key="m"
                    :label="m"
                    :value="m"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="$t('processPlanning.featurePanel.partSize')">
                <el-input-number
                  v-model="partInfo.width"
                  :min="1"
                  :step="1"
                  controls-position="right"
                  size="small"
                />
                <span class="size-sep">×</span>
                <el-input-number
                  v-model="partInfo.length"
                  :min="1"
                  :step="1"
                  controls-position="right"
                  size="small"
                />
                <span class="size-sep">×</span>
                <el-input-number
                  v-model="partInfo.height"
                  :min="1"
                  :step="1"
                  controls-position="right"
                  size="small"
                />
              </el-form-item>
            </div>
          </el-form>

          <el-divider />

          <!-- 特征列表 -->
          <div class="form-section">
            <div class="section-label">
              {{ $t('processPlanning.featurePanel.features') }}
            </div>
            <el-checkbox-group
              v-model="selectedFeatureIds"
              class="feature-group"
              @change="handleFeatureSelectionChange"
            >
              <el-checkbox
                v-for="feature in featureList"
                :key="feature.id"
                :value="feature.id"
                class="feature-item"
                border
              >
                <div class="feature-item-content">
                  <el-icon
                    :size="16"
                    class="feature-icon"
                  >
                    <component :is="feature.icon" />
                  </el-icon>
                  <span class="feature-name">{{ getFeatureName(feature) }}</span>
                  <el-tag
                    size="small"
                    effect="plain"
                    class="feature-count"
                  >
                    ×{{ feature.count }}
                  </el-tag>
                </div>
              </el-checkbox>
            </el-checkbox-group>
            <el-empty
              v-if="featureList.length === 0"
              :description="$t('processPlanning.featurePanel.noFeature')"
              :image-size="60"
            />
          </div>
        </el-card>
      </el-aside>

      <!-- 中间：工序树 + 3D预览 -->
      <el-main class="center-panel">
        <el-tabs
          v-model="centerTab"
          class="center-tabs"
        >
          <!-- 工序树 -->
          <el-tab-pane
            :label="$t('processPlanning.operationTree.title')"
            name="operations"
          >
            <div class="tree-toolbar">
              <el-button-group>
                <el-button
                  size="small"
                  :disabled="!operationTreeData.length"
                  @click="expandAll"
                >
                  <el-icon><Expand /></el-icon>
                  {{ $t('processPlanning.operationTree.expandAll') }}
                </el-button>
                <el-button
                  size="small"
                  :disabled="!operationTreeData.length"
                  @click="collapseAll"
                >
                  <el-icon><Fold /></el-icon>
                  {{ $t('processPlanning.operationTree.collapseAll') }}
                </el-button>
              </el-button-group>
              <span
                v-if="operationTreeData.length"
                class="op-summary"
              >
                {{ operationTreeData.length }} {{ $t('processPlanning.operationTree.stepLabel') }}
              </span>
            </div>
            <div
              v-loading="requestState === 'loading'"
              class="tree-container"
            >
              <el-empty
                v-if="operationTreeData.length === 0 && requestState !== 'loading'"
                :description="$t('processPlanning.operationTree.empty')"
              />
              <el-tree
                v-else
                ref="operationTreeRef"
                :data="operationTreeData"
                :props="treeProps"
                node-key="id"
                :default-expand-all="false"
                :expand-on-click-node="false"
                class="operation-tree"
              >
                <template #default="{ node, data }">
                  <div class="tree-node">
                    <div class="tree-node-main">
                      <span class="node-label">{{ data.label }}</span>
                      <el-tag
                        v-if="data.type"
                        size="small"
                        effect="plain"
                        :type="tagTypeForOperation(data.type)"
                      >
                        {{ data.type }}
                      </el-tag>
                    </div>
                    <div
                      v-if="data.tool || data.params || data.estTime"
                      class="tree-node-meta"
                    >
                      <span
                        v-if="data.tool"
                        class="meta-item"
                      >
                        <el-icon><Cpu /></el-icon>
                        {{ $t('processPlanning.operationTree.toolLabel') }}: {{ data.tool }}
                      </span>
                      <span
                        v-if="data.params"
                        class="meta-item"
                      >
                        <el-icon><SetUp /></el-icon>
                        {{ data.params }}
                      </span>
                      <span
                        v-if="data.estTime"
                        class="meta-item"
                      >
                        <el-icon><Timer /></el-icon>
                        {{ data.estTime }}
                      </span>
                    </div>
                  </div>
                </template>
              </el-tree>
            </div>
          </el-tab-pane>

          <!-- 3D预览 -->
          <el-tab-pane
            :label="$t('processPlanning.threeViewer.title')"
            name="viewer"
          >
            <div class="viewer-container">
              <ThreeViewer
                v-if="centerTab === 'viewer'"
                :model-url="modelUrl"
                :auto-rotate="true"
                :enable-grid="true"
                background-color="#10141a"
                class="three-viewer"
                @model-loaded="onViewerModelLoaded"
              />
              <div
                v-else
                class="viewer-placeholder"
              >
                <el-empty :description="$t('processPlanning.threeViewer.noModel')" />
              </div>
            </div>
          </el-tab-pane>
        </el-tabs>
      </el-main>

      <!-- 右侧：G代码预览 -->
      <el-aside
        :width="isMobile ? '100%' : '420px'"
        class="right-panel"
      >
        <el-card
          shadow="never"
          class="panel-card"
        >
          <template #header>
            <div class="panel-header">
              <span class="panel-title">
                <el-icon><DocumentCopy /></el-icon>
                {{ $t('processPlanning.gcodePreview.title') }}
              </span>
              <el-button
                v-if="gcodeText"
                size="small"
                type="primary"
                text
                @click="exportGcode"
              >
                <el-icon><Download /></el-icon>
                {{ $t('processPlanning.gcodePreview.download') }}
              </el-button>
            </div>
          </template>

          <el-alert
            v-if="gcodeText"
            :title="$t('processPlanning.gcodePreview.editableHint')"
            type="info"
            :closable="false"
            show-icon
            class="gcode-hint"
          />
          <el-empty
            v-if="!gcodeText"
            :description="$t('processPlanning.gcodePreview.empty')"
            :image-size="60"
          />
          <div
            v-else
            class="gcode-editor"
          >
            <div class="gcode-line-numbers">
              <div
                v-for="line in gcodeLineNumbers"
                :key="'ln-' + line"
                class="ln"
              >
                {{ line }}
              </div>
            </div>
            <textarea
              v-model="gcodeText"
              class="gcode-textarea"
              spellcheck="false"
              @scroll="syncLineScroll"
            />
          </div>
        </el-card>
      </el-aside>
    </el-container>

    <!-- 底部操作按钮组 -->
    <div class="action-bar">
      <div class="action-bar-left">
        <el-button
          type="primary"
          :loading="requestState === 'loading'"
          :disabled="!selectedFeatureIds.length"
          @click="replanProcess"
        >
          <el-icon><Refresh /></el-icon>
          {{ requestState === 'loading' ? $t('processPlanning.actions.replanning') : $t('processPlanning.actions.replan') }}
        </el-button>
        <el-button
          type="success"
          :disabled="!gcodeText"
          @click="exportGcode"
        >
          <el-icon><Download /></el-icon>
          {{ $t('processPlanning.actions.export') }}
        </el-button>
        <el-button
          type="warning"
          :loading="simulating"
          :disabled="!gcodeText"
          @click="runSimulation"
        >
          <el-icon><VideoPlay /></el-icon>
          {{ simulating ? $t('processPlanning.threeViewer.simulating') : $t('processPlanning.actions.simulate') }}
        </el-button>
      </div>
      <div class="action-bar-right">
        <span
          v-if="lastResponseMeta"
          class="meta-info"
        >
          {{ lastResponseMeta }}
        </span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 工艺规划页面
 *
 * 提供"特征选择 → 工序规划 → G代码生成 → 仿真"的全流程可视化操作。
 * 通过调用后端 /api/process_planning/plan 接口获取工序与G代码。
 */
import { computed, nextTick, onBeforeUnmount, onMounted, reactive, ref, watch, type Component } from 'vue'
import { ElMessage, ElNotification } from 'element-plus'
import type { CheckboxValueType } from 'element-plus'
import {
  Loading,
  Grid,
  Aim,
  Coin,
  Crop,
  Document,
  Expand,
  Fold,
  Cpu,
  SetUp,
  Timer,
  DocumentCopy,
  Download,
  Refresh,
  VideoPlay,
} from '@element-plus/icons-vue'
import http from '@/utils/http'
import { triggerFileDownload } from '@/utils/download'
import { useProjectStore } from '@/stores/project'
import ThreeViewer from '@/components/ThreeViewer.vue'

// ========================= 类型定义 =========================
/** 加工特征类型 */
type FeatureType = 'hole' | 'boss' | 'cavity' | 'plane'

/** 加工特征 */
interface MachiningFeature {
  id: string
  name?: string
  /** i18n 键名（推荐使用，名称统一从翻译资源中读取） */
  nameKey?: string
  type: FeatureType
  count: number
  icon: Component
}

/** 工序树节点 */
interface OperationNode {
  id: string
  label: string
  type?: string
  tool?: string
  params?: string
  estTime?: string
  children?: OperationNode[]
}

/** 后端规划响应 */
interface PlanResponse {
  success?: boolean
  summary?: string
  total_duration_ms?: number
  operation_plan?: {
    operations?: Array<{
      id?: string | number
      name?: string
      operation_type?: string
      tool?: string
      parameters?: Record<string, unknown>
      estimated_time_min?: number
      children?: Array<{
        id?: string | number
        name?: string
        operation_type?: string
        tool?: string
        parameters?: Record<string, unknown>
        estimated_time_min?: number
      }>
    }>
  }
  gcode?: {
    program_text?: string
    program_number?: string
    controller_type?: string
    total_lines?: number
    estimated_cycle_time_min?: number
  }
  stages?: Array<{ name: string; status: string; duration_ms?: number }>
}

type RequestState = 'idle' | 'loading' | 'success' | 'error'

// ========================= 状态管理 =========================
const projectStore = useProjectStore()

// 工件参数
const partInfo = reactive({
  material: 'Aluminum 6061',
  width: 100,
  length: 80,
  height: 20,
})

// 可选材料（演示用，实际可由后端数据驱动）
const materialOptions = [
  'Aluminum 6061',
  'Aluminum 7075',
  'Steel 45#',
  'Stainless Steel 304',
  'Brass H62',
  'Engineering Plastic',
]

// 特征列表（来自工程或后端特征识别）
// 名称使用 i18n key，便于在 zh-CN / en 之间切换
const featureList = ref<MachiningFeature[]>([
  { id: 'hole-1', nameKey: 'processPlanning.features.hole8Through', type: 'hole', count: 4, icon: Aim },
  { id: 'hole-2', nameKey: 'processPlanning.features.hole6Counterbore', type: 'hole', count: 2, icon: Aim },
  { id: 'boss-1', nameKey: 'processPlanning.features.rectBoss', type: 'boss', count: 1, icon: Coin },
  { id: 'cavity-1', nameKey: 'processPlanning.features.squareCavity', type: 'cavity', count: 1, icon: Crop },
  { id: 'plane-1', nameKey: 'processPlanning.features.topFaceFinish', type: 'plane', count: 1, icon: Document },
])

/** 解析特征显示名称（优先 i18n key，回退原始 name 字段） */
function getFeatureName(feature: MachiningFeature): string {
  if (feature.nameKey) return t(feature.nameKey)
  return feature.name || feature.id
}

// 选中的特征 ID
const selectedFeatureIds = ref<string[]>([])

// 中间标签页（工序/3D）
const centerTab = ref<'operations' | 'viewer'>('operations')

// 工序树数据
const operationTreeData = ref<OperationNode[]>([])
const operationTreeRef = ref()

// G代码
const gcodeText = ref('')
const gcodeLineNumbers = computed(() => {
  if (!gcodeText.value) return []
  const lines = gcodeText.value.split('\n').length
  return Array.from({ length: lines }, (_, i) => i + 1)
})

// 请求状态
const requestState = ref<RequestState>('idle')
const statusText = computed(() => {
  switch (requestState.value) {
    case 'loading':
      return t('processPlanning.status.loading')
    case 'success':
      return t('processPlanning.status.success')
    case 'error':
      return t('processPlanning.status.error')
    default:
      return t('processPlanning.status.idle')
  }
})
const statusTagType = computed(() => {
  switch (requestState.value) {
    case 'loading': return 'warning'
    case 'success': return 'success'
    case 'error': return 'danger'
    default: return 'info'
  }
})

// 仿真状态
const simulating = ref(false)
let simulationTimeoutId: number | null = null

// 3D模型地址（来自工程）
const modelUrl = computed(() => {
  // 优先取工程中导入的模型资源
  const resources = projectStore.manifest?.resources || []
  const modelResource = resources.find((r: { type: string }) => r.type === 'model') as { path?: string } | undefined
  if (!modelResource?.path) return ''
  // 资源路径通常是相对路径，需要拼接静态访问前缀
  const base = (import.meta.env.VITE_API_BASE_URL as string | undefined) || '/api'
  return modelResource.path.startsWith('http')
    ? modelResource.path
    : `${base.replace(/\/+$/, '')}/${modelResource.path.replace(/^\/+/, '')}`
})

// 树节点默认配置
const treeProps = {
  children: 'children',
  label: 'label',
}

// 响应式（屏幕尺寸）
const isMobile = ref(false)
function checkScreenSize() {
  isMobile.value = window.innerWidth < 1024
}
onMounted(() => {
  checkScreenSize()
  window.addEventListener('resize', checkScreenSize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', checkScreenSize)
  if (simulationTimeoutId !== null) {
    clearTimeout(simulationTimeoutId)
    simulationTimeoutId = null
  }
})

// 最后一次响应的元信息
const lastResponseMeta = ref('')

// i18n 辅助
import { useI18n } from 'vue-i18n'
const { t } = useI18n()

// ========================= 业务方法 =========================

/**
 * 根据工序类型获取 tag 配色
 * 优先匹配英文 operation_type（drill / mill / finish / rough），
 * 兼容可能传入的中文（孔 / 铣 / 精 / 粗）。
 */
function tagTypeForOperation(type: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  const lower = (type || '').toLowerCase()
  if (lower.includes('drill') || lower.includes('孔')) return 'primary'
  if (lower.includes('mill') || lower.includes('铣')) return 'success'
  if (lower.includes('finish') || lower.includes('精')) return 'warning'
  if (lower.includes('rough') || lower.includes('粗')) return 'info'
  return 'info'
}

/**
 * 选区变化时记录（用于状态提示/重置）
 */
function handleFeatureSelectionChange(values: CheckboxValueType[]) {
  if (values.length === 0) {
    // 清空时仅记录，不强制清空已生成的工序/G代码
    return
  }
  // 任意变化都重置成功状态
  if (requestState.value === 'success') {
    requestState.value = 'idle'
  }
}

/**
 * 重新规划：调用后端 API
 */
async function replanProcess() {
  if (selectedFeatureIds.value.length === 0) {
    ElMessage.warning(t('processPlanning.status.noSelection'))
    return
  }

  requestState.value = 'loading'
  lastResponseMeta.value = ''

  const selectedFeatures = featureList.value.filter(f =>
    selectedFeatureIds.value.includes(f.id),
  )

  const payload = {
    workpiece: {
      material: partInfo.material,
      dimensions: {
        width: partInfo.width,
        length: partInfo.length,
        height: partInfo.height,
      },
    },
    features: selectedFeatures.map(f => ({
      id: f.id,
      type: f.type,
      name: f.name,
      count: f.count,
    })),
    controller_type: 'fanuc_0i',
    safe_z: 50.0,
  }

  try {
    const response = await http.post<PlanResponse>('/api/process_planning/plan', payload)
    const data = response.data || ({} as PlanResponse)
    handlePlanResponse(data)
    requestState.value = 'success'
    ElNotification.success({
      title: t('processPlanning.messages.replanSuccess'),
      message: data.summary || t('processPlanning.status.success'),
    })
  } catch {
    requestState.value = 'error'
    // 错误已被 http 拦截器处理（弹 ElMessage / ErrorConflictDialog）
    // 静默处理，避免重复弹窗
  }
}

/**
 * 处理后端返回数据：转换为工序树 + G代码
 */
function handlePlanResponse(data: PlanResponse) {
  // ---- 1) 转换工序树 ----
  const operations = data.operation_plan?.operations || []
  operationTreeData.value = operations.map((op, idx) => {
    const id = String(op.id ?? `op-${idx + 1}`)
    const label = op.name || `${t('processPlanning.operationTree.stepLabel')} ${idx + 1}`
    const params = op.parameters
      ? Object.entries(op.parameters)
          .map(([k, v]) => `${k}=${v}`)
          .join(', ')
      : ''
    const estTime = op.estimated_time_min != null
      ? `${op.estimated_time_min.toFixed(2)} ${t('common.minutes')}`
      : ''
    const children: OperationNode[] = (op.children || []).map((sub, sIdx) => ({
      id: `${id}-${sIdx + 1}`,
      label: sub.name || `${t('processPlanning.operationTree.stepLabel')} ${idx + 1}.${sIdx + 1}`,
      type: sub.operation_type,
      tool: sub.tool,
      params: sub.parameters
        ? Object.entries(sub.parameters).map(([k, v]) => `${k}=${v}`).join(', ')
        : '',
      estTime: sub.estimated_time_min != null
        ? `${sub.estimated_time_min.toFixed(2)} ${t('common.minutes')}`
        : '',
    }))
    return {
      id,
      label,
      type: op.operation_type,
      tool: op.tool,
      params,
      estTime,
      children: children.length ? children : undefined,
    }
  })

  // ---- 2) 解析 G代码 ----
  gcodeText.value = data.gcode?.program_text || ''

  // ---- 3) 元信息 ----
  if (data.gcode?.total_lines) {
    lastResponseMeta.value = `${data.gcode.total_lines} lines · ${data.gcode.controller_type || ''}`
  } else if (data.total_duration_ms) {
    lastResponseMeta.value = `${(data.total_duration_ms / 1000).toFixed(2)}s`
  }
}

/**
 * 展开/折叠所有节点
 */
function expandAll() {
  if (!operationTreeRef.value) return
  const allNodes = operationTreeRef.value.store.nodesMap || {}
  Object.values(allNodes).forEach((node: { expand: () => void }) => {
    node.expand()
  })
}
function collapseAll() {
  if (!operationTreeRef.value) return
  const allNodes = operationTreeRef.value.store.nodesMap || {}
  Object.values(allNodes).forEach((node: { collapse: () => void }) => {
    node.collapse()
  })
}

/**
 * G代码行号同步滚动
 */
function syncLineScroll(e: Event) {
  const ta = e.target as HTMLTextAreaElement
  const lineContainer = ta.previousElementSibling as HTMLElement | null
  if (lineContainer) {
    lineContainer.scrollTop = ta.scrollTop
  }
}

/**
 * 导出 G 代码
 */
function exportGcode() {
  if (!gcodeText.value) {
    ElMessage.warning(t('processPlanning.messages.noGcode'))
    return
  }
  const filename = `process_${Date.now()}.nc`
  triggerFileDownload(
    new Blob([gcodeText.value], { type: 'text/plain;charset=utf-8' }),
    filename,
  )
  ElMessage.success(t('processPlanning.messages.exportSuccess'))
}

/**
 * 仿真验证：切到 3D 视图并触发仿真
 */
function runSimulation() {
  if (!gcodeText.value) {
    ElMessage.warning(t('processPlanning.messages.noGcode'))
    return
  }
  simulating.value = true
  centerTab.value = 'viewer'
  // ThreeViewer 已经在挂载时显示工件；此处仅作状态展示
  ElMessage.success(t('processPlanning.messages.simulateSuccess'))
  nextTick(() => {
    simulationTimeoutId = window.setTimeout(() => {
      simulating.value = false
      simulationTimeoutId = null
    }, 1500)
  })
}

/**
 * ThreeViewer 模型加载回调
 */
function onViewerModelLoaded(_model: unknown) {
  // 模型加载完成，静默处理
}

// 监听工序树数据变化：自动展开第一层
watch(operationTreeData, (val) => {
  if (val.length && operationTreeRef.value) {
    nextTick(() => {
      val.forEach(op => {
        const node = operationTreeRef.value?.getNode(op.id)
        if (node) node.expand()
      })
    })
  }
})
</script>

<style lang="scss" scoped>
.process-planning-page {
  display: flex;
  flex-direction: column;
  height: calc(100vh - 120px);
  min-height: 600px;
}

.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 16px;

  h2 {
    margin: 0 0 4px 0;
    font-size: 1.5rem;
    color: var(--text-primary);
  }
  .subtitle {
    margin: 0;
    color: var(--text-secondary);
    font-size: 13px;
  }
  .status-tag {
    font-weight: 500;
  }
}

.main-container {
  flex: 1;
  min-height: 0;
  background: transparent;
}

.left-panel,
.right-panel {
  height: 100%;
  padding: 0 8px;
}

.center-panel {
  padding: 0 8px;
  height: 100%;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.panel-card {
  height: 100%;
  display: flex;
  flex-direction: column;
  :deep(.el-card__body) {
    flex: 1;
    overflow-y: auto;
    padding: 14px;
  }
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.panel-title {
  display: flex;
  align-items: center;
  gap: 6px;
  font-weight: 600;
  font-size: 14px;
  color: var(--text-primary);
}

.part-form {
  .size-sep {
    margin: 0 4px;
    color: var(--text-tertiary);
  }
  :deep(.el-form-item) {
    margin-bottom: 10px;
  }
  :deep(.el-form-item__label) {
    font-size: 12px;
    color: var(--text-secondary);
    padding-bottom: 2px;
  }
}

.form-section {
  .section-label {
    font-size: 12px;
    font-weight: 600;
    color: var(--text-secondary);
    margin-bottom: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }
}

.feature-group {
  display: flex;
  flex-direction: column;
  gap: 6px;

  :deep(.el-checkbox) {
    margin-right: 0;
    width: 100%;
    padding: 8px 10px;
  }
  :deep(.el-checkbox__label) {
    width: 100%;
  }
}
.feature-item-content {
  display: flex;
  align-items: center;
  gap: 8px;
  width: 100%;
}
.feature-icon {
  color: var(--accent-primary);
}
.feature-name {
  flex: 1;
  font-size: 13px;
  color: var(--text-primary);
}
.feature-count {
  flex-shrink: 0;
}

.center-tabs {
  height: 100%;
  display: flex;
  flex-direction: column;
  :deep(.el-tabs__header) {
    margin-bottom: 8px;
  }
  :deep(.el-tabs__content) {
    flex: 1;
    overflow: hidden;
  }
  :deep(.el-tab-pane) {
    height: 100%;
  }
}

.tree-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}
.op-summary {
  font-size: 12px;
  color: var(--text-secondary);
}

.tree-container {
  height: calc(100% - 40px);
  overflow-y: auto;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 8px;
}

.operation-tree {
  background: transparent;
  :deep(.el-tree-node__content) {
    height: auto;
    padding: 6px 0;
  }
}

.tree-node {
  display: flex;
  flex-direction: column;
  gap: 4px;
  width: 100%;
  font-size: 13px;
}
.tree-node-main {
  display: flex;
  align-items: center;
  gap: 8px;
  .node-label {
    font-weight: 500;
    color: var(--text-primary);
  }
}
.tree-node-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  font-size: 12px;
  color: var(--text-secondary);
  padding-left: 4px;
  .meta-item {
    display: inline-flex;
    align-items: center;
    gap: 4px;
  }
}

.viewer-container {
  height: 100%;
  display: flex;
  flex-direction: column;
  background: #0b0d11;
  border-radius: var(--radius-sm);
  overflow: hidden;
}
.three-viewer {
  flex: 1;
  min-height: 360px;
}
.viewer-placeholder {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-secondary);
}

.gcode-hint {
  margin-bottom: 10px;
}

.gcode-editor {
  display: flex;
  height: 100%;
  min-height: 360px;
  border: 1px solid var(--border-medium);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: #1e1e1e;
}
.gcode-line-numbers {
  flex-shrink: 0;
  width: 48px;
  background: #252526;
  color: #858585;
  font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  padding: 8px 0;
  text-align: right;
  user-select: none;
  overflow: hidden;
  .ln {
    padding: 0 8px;
  }
}
.gcode-textarea {
  flex: 1;
  background: #1e1e1e;
  color: #d4d4d4;
  border: none;
  outline: none;
  resize: none;
  font-family: 'Cascadia Code', 'Fira Code', Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
  padding: 8px 12px;
  white-space: pre;
  overflow: auto;
  &::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  &::-webkit-scrollbar-thumb {
    background: #424242;
    border-radius: 4px;
  }
}

.action-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 12px;
  padding: 12px 16px;
  background: var(--bg-card);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-sm);
  .action-bar-left {
    display: flex;
    gap: 10px;
  }
  .action-bar-right {
    font-size: 12px;
    color: var(--text-secondary);
  }
  .meta-info {
    font-family: monospace;
  }
}

/* 响应式 */
@media (max-width: 1024px) {
  .process-planning-page {
    height: auto;
    min-height: auto;
  }
  .main-container {
    flex-direction: column;
  }
  .left-panel,
  .right-panel,
  .center-panel {
    width: 100% !important;
    margin-bottom: 12px;
  }
  .panel-card {
    height: auto;
  }
  .gcode-editor {
    min-height: 240px;
  }
}
</style>
