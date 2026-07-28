<!--
  可解释性可视化视图（ADR-016 阶段 7 p7-7）

  对应后端 `python/app/api/v1/explainability.py`。
  详见 `docs/adr/ADR-016-可解释性可视化.md`。

  功能：
    1. 解释记录列表（左侧，按类型过滤）+ 详情（右侧，含 payload）
    2. 4 类解释生成入口：
       - HIDDEN_STATE：隐状态投影（PCA/t-SNE/UMAP 降维）
       - GATE_DYNAMICS：LTC 门控动力学时序
       - COUNTERFACTUAL：反事实扰动敏感性
       - CONFIDENCE：MC dropout 置信度分布
    3. 解释对比：选两条记录生成 diff
    4. 工程约束：payload 大型数组以 JSON 存盘，需 include_payload=true 加载
-->
<template>
  <div class="explainability-page">
    <!-- ===== 页面头部 ===== -->
    <header class="page-header">
      <div class="page-header__title-block">
        <h1 class="page-header__title">{{ t('explainability.title') }}</h1>
        <p class="page-header__subtitle">{{ t('explainability.subtitle') }}</p>
      </div>
      <div class="page-header__actions">
        <el-dropdown @command="handleOpenGenerate" trigger="click">
          <el-button type="primary" :icon="MagicStick">
            {{ t('explainability.generateExplanation') }}
            <el-icon class="el-icon--right"><ArrowDown /></el-icon>
          </el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item :command="EXPLANATION_TYPE.HIDDEN_STATE">
                <el-tag :type="EXPLANATION_TYPE_TAG_TYPE[EXPLANATION_TYPE.HIDDEN_STATE]" size="small">
                  {{ EXPLANATION_TYPE_LABELS[EXPLANATION_TYPE.HIDDEN_STATE] }}
                </el-tag>
              </el-dropdown-item>
              <el-dropdown-item :command="EXPLANATION_TYPE.GATE_DYNAMICS">
                <el-tag :type="EXPLANATION_TYPE_TAG_TYPE[EXPLANATION_TYPE.GATE_DYNAMICS]" size="small">
                  {{ EXPLANATION_TYPE_LABELS[EXPLANATION_TYPE.GATE_DYNAMICS] }}
                </el-tag>
              </el-dropdown-item>
              <el-dropdown-item :command="EXPLANATION_TYPE.COUNTERFACTUAL">
                <el-tag :type="EXPLANATION_TYPE_TAG_TYPE[EXPLANATION_TYPE.COUNTERFACTUAL]" size="small">
                  {{ EXPLANATION_TYPE_LABELS[EXPLANATION_TYPE.COUNTERFACTUAL] }}
                </el-tag>
              </el-dropdown-item>
              <el-dropdown-item :command="EXPLANATION_TYPE.CONFIDENCE">
                <el-tag :type="EXPLANATION_TYPE_TAG_TYPE[EXPLANATION_TYPE.CONFIDENCE]" size="small">
                  {{ EXPLANATION_TYPE_LABELS[EXPLANATION_TYPE.CONFIDENCE] }}
                </el-tag>
              </el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
        <el-button :icon="Refresh" @click="handleRefresh" :loading="store.anyLoading">
          {{ t('common.refresh') }}
        </el-button>
      </div>
    </header>

    <!-- ===== 主体 ===== -->
    <div class="ex-main">
      <!-- 左侧：解释列表 -->
      <section class="ex-list-panel">
        <div class="ex-list-panel__header">
          <span class="ex-list-panel__title">{{ t('explainability.explanationList') }}</span>
          <el-select
            v-model="filterType"
            size="small"
            class="ex-list-panel__filter"
            @change="handleFilterChange"
          >
            <el-option :label="t('explainability.allTypes')" value="" />
            <el-option
              v-for="et in EXPLANATION_TYPE_VALUES"
              :key="et"
              :label="EXPLANATION_TYPE_LABELS[et]"
              :value="et"
            />
          </el-select>
        </div>
        <div v-loading="store.explanationsLoading" class="ex-list-panel__body">
          <el-empty
            v-if="!store.explanationsLoading && !store.hasExplanations"
            :description="t('explainability.emptyExplanations')"
          />
          <div
            v-for="exp in store.explanations"
            :key="exp.id"
            class="ex-card"
            :class="{ 'ex-card--active': store.currentExplanation?.id === exp.id }"
            @click="handleSelectExplanation(exp.id)"
          >
            <div class="ex-card__header">
              <el-tag :type="EXPLANATION_TYPE_TAG_TYPE[exp.explanation_type]" size="small">
                {{ EXPLANATION_TYPE_LABELS[exp.explanation_type] }}
              </el-tag>
              <span class="ex-card__id">{{ exp.id.slice(0, 12) }}…</span>
            </div>
            <div class="ex-card__meta">
              <span>{{ exp.model_uri }}</span>
            </div>
            <div class="ex-card__time">{{ formatDateTime(exp.created_at) }}</div>
          </div>
        </div>
        <el-pagination
          v-if="store.totalPages > 1"
          v-model:current-page="currentPage"
          small
          layout="prev, pager, next"
          :page-size="store.explanationPagination?.limit ?? 50"
          :total="store.explanationPagination?.total ?? 0"
          class="ex-list-panel__pager"
          @current-change="handlePageChange"
        />
      </section>

      <!-- 右侧：详情 + payload + 对比 -->
      <section class="ex-detail-panel">
        <!-- 详情卡片 -->
        <el-card v-loading="store.explanationLoading" class="ex-detail-card">
          <template #header>
            <div class="ex-detail-card__header">
              <span>{{ t('explainability.explanationDetail') }}</span>
              <div v-if="store.currentExplanation" class="ex-detail-card__actions">
                <el-button
                  link
                  type="primary"
                  :icon="Download"
                  @click="handleLoadPayload"
                  :loading="store.explanationLoading"
                >
                  {{ t('explainability.loadPayload') }}
                </el-button>
                <el-button
                  link
                  type="warning"
                  :icon="CopyDocument"
                  @click="handleAddToCompare"
                >
                  {{ t('explainability.addToCompare') }}
                </el-button>
                <el-button
                  link
                  type="danger"
                  :icon="Delete"
                  @click="handleDelete"
                  :loading="store.deleting"
                >
                  {{ t('common.delete') }}
                </el-button>
              </div>
            </div>
          </template>

          <el-empty
            v-if="!store.explanationLoading && !store.currentExplanation"
            :description="t('explainability.selectHint')"
          />

          <template v-else-if="store.currentExplanation">
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item :label="t('explainability.fields.id')">
                {{ store.currentExplanation.id }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.type')">
                <el-tag :type="EXPLANATION_TYPE_TAG_TYPE[store.currentExplanation.explanation_type]" size="small">
                  {{ EXPLANATION_TYPE_LABELS[store.currentExplanation.explanation_type] }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.modelUri')">
                {{ store.currentExplanation.model_uri }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.inputSignature')">
                <code>{{ store.currentExplanation.input_signature }}</code>
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.payloadSize')">
                {{ formatBytes(store.currentExplanation.payload_size_bytes) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.sourceSnapshot')">
                {{ store.currentExplanation.source_snapshot_id || '—' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.createdBy')">
                {{ store.currentExplanation.created_by || '—' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.createdAt')">
                {{ formatDateTime(store.currentExplanation.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.expiresAt')">
                {{ store.currentExplanation.expires_at ? formatDateTime(store.currentExplanation.expires_at) : '—' }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- payload 展示 -->
            <div v-if="currentPayload" class="ex-payload">
              <el-divider content-position="left">{{ t('explainability.payload') }}</el-divider>
              <component
                :is="getPayloadRenderer(store.currentExplanation.explanation_type)"
                :payload="currentPayload"
              />
            </div>
          </template>
        </el-card>

        <!-- 对比卡片 -->
        <el-card class="ex-compare-card">
          <template #header>
            <div class="ex-compare-card__header">
              <span>{{ t('explainability.comparison') }}</span>
              <el-tag v-if="compareSelection.length > 0" size="small">
                {{ compareSelection.length }} / 2
              </el-tag>
            </div>
          </template>

          <!-- 对比选择 -->
          <div class="ex-compare-selection">
            <div
              v-for="(id, idx) in compareSelection"
              :key="idx"
              class="ex-compare-item"
            >
              <span class="ex-compare-item__id">{{ id.slice(0, 16) }}…</span>
              <el-button link type="danger" :icon="Close" @click="handleRemoveFromCompare(idx)" />
            </div>
            <el-empty
              v-if="compareSelection.length === 0"
              :description="t('explainability.compareEmptyHint')"
              :image-size="40"
            />
          </div>

          <!-- 对比配置 -->
          <el-form :inline="true" class="ex-compare-form">
            <el-form-item :label="t('explainability.comparisonType')">
              <el-select v-model="compareForm.comparison_type" class="ex-compare-select">
                <el-option
                  v-for="ct in COMPARISON_TYPE_VALUES"
                  :key="ct"
                  :label="COMPARISON_TYPE_LABELS[ct]"
                  :value="ct"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :icon="Connection"
                :loading="store.comparing"
                :disabled="compareSelection.length !== 2"
                @click="handleCompare"
              >
                {{ t('explainability.runComparison') }}
              </el-button>
              <el-button @click="handleClearCompare">{{ t('common.clear') }}</el-button>
            </el-form-item>
          </el-form>

          <!-- 对比结果 -->
          <div v-if="store.lastComparisonResult" class="ex-compare-result">
            <el-divider content-position="left">{{ t('explainability.comparisonResult') }}</el-divider>
            <el-descriptions :column="1" border size="small">
              <el-descriptions-item :label="t('explainability.fields.id')">
                {{ store.lastComparisonResult.id }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.comparisonType')">
                <el-tag :type="COMPARISON_TYPE_TAG_TYPE[store.lastComparisonResult.comparison_type]" size="small">
                  {{ COMPARISON_TYPE_LABELS[store.lastComparisonResult.comparison_type] }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.baseExplanation')">
                {{ store.lastComparisonResult.base_explanation_id }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.comparedExplanation')">
                {{ store.lastComparisonResult.compared_explanation_id }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('explainability.fields.createdAt')">
                {{ formatDateTime(store.lastComparisonResult.created_at) }}
              </el-descriptions-item>
            </el-descriptions>
          </div>
        </el-card>
      </section>
    </div>

    <!-- ===== 生成对话框：隐状态投影 ===== -->
    <el-dialog
      v-model="generateDialogs.hidden_state"
      :title="t('explainability.generate.hiddenState')"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-width="120px" label-position="left">
        <el-form-item :label="t('explainability.fields.modelUri')">
          <el-input v-model="hiddenStateForm.model_uri" placeholder="model://LTC-ChatterPredictor/1.0.0" />
        </el-form-item>
        <el-form-item :label="t('explainability.projectionMethod')">
          <el-select v-model="hiddenStateForm.projection_method" class="ex-dialog-select">
            <el-option
              v-for="pm in PROJECTION_METHOD_VALUES"
              :key="pm"
              :label="PROJECTION_METHOD_LABELS[pm]"
              :value="pm"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('explainability.projectionDim')">
          <el-input-number v-model="hiddenStateForm.projection_dim" :min="2" :max="3" :step="1" />
        </el-form-item>
        <el-form-item :label="t('explainability.maxFrames')">
          <el-input-number v-model="hiddenStateForm.max_frames" :min="1" :max="10000" :step="100" />
        </el-form-item>
        <el-form-item :label="t('explainability.sourceSnapshotId')">
          <el-input v-model="hiddenStateForm.source_snapshot_id" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogs.hidden_state = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="store.generatingHiddenState"
          @click="handleGenerateHiddenState"
        >
          {{ t('common.generate') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 生成对话框：门控动力学 ===== -->
    <el-dialog
      v-model="generateDialogs.gate_dynamics"
      :title="t('explainability.generate.gateDynamics')"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-width="120px" label-position="left">
        <el-form-item :label="t('explainability.fields.modelUri')">
          <el-input v-model="gateDynamicsForm.model_uri" placeholder="model://LTC-ChatterPredictor/1.0.0" />
        </el-form-item>
        <el-form-item :label="t('explainability.anomalySigma')">
          <el-input-number v-model="gateDynamicsForm.anomaly_sigma" :min="1.0" :max="5.0" :step="0.1" />
        </el-form-item>
        <el-form-item :label="t('explainability.sourceSnapshotId')">
          <el-input v-model="gateDynamicsForm.source_snapshot_id" placeholder="可选" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogs.gate_dynamics = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="store.generatingGateDynamics"
          @click="handleGenerateGateDynamics"
        >
          {{ t('common.generate') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 生成对话框：反事实 ===== -->
    <el-dialog
      v-model="generateDialogs.counterfactual"
      :title="t('explainability.generate.counterfactual')"
      width="560px"
      :close-on-click-modal="false"
    >
      <el-form label-width="120px" label-position="left">
        <el-form-item :label="t('explainability.fields.modelUri')">
          <el-input v-model="counterfactualForm.model_uri" placeholder="model://LTC-ChatterPredictor/1.0.0" />
        </el-form-item>
        <el-form-item :label="t('explainability.perturbedFeature')">
          <el-input
            v-model="counterfactualForm.perturbed_feature"
            placeholder="如 spindle_speed"
          />
        </el-form-item>
        <el-form-item :label="t('explainability.perturbationStep')">
          <el-input-number v-model="counterfactualForm.perturbation_step" :min="0.01" :max="0.5" :step="0.01" />
        </el-form-item>
        <el-divider content-position="left">{{ t('explainability.baseInput') }}</el-divider>
        <div class="ex-base-input-grid">
          <el-form-item
            v-for="field in STATE_FIELD_VALUES"
            :key="field"
            :label="STATE_FIELD_LABELS[field].split(' ')[0]"
            label-width="100px"
          >
            <el-input-number
              v-model="counterfactualForm.base_input[field]"
              :step="0.1"
              controls-position="right"
              class="ex-base-input"
            />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogs.counterfactual = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="store.generatingCounterfactual"
          @click="handleGenerateCounterfactual"
        >
          {{ t('common.generate') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ===== 生成对话框：置信度 ===== -->
    <el-dialog
      v-model="generateDialogs.confidence"
      :title="t('explainability.generate.confidence')"
      width="500px"
      :close-on-click-modal="false"
    >
      <el-form label-width="120px" label-position="left">
        <el-form-item :label="t('explainability.fields.modelUri')">
          <el-input v-model="confidenceForm.model_uri" placeholder="model://LTC-ChatterPredictor/1.0.0" />
        </el-form-item>
        <el-form-item :label="t('explainability.sampleCount')">
          <el-input-number v-model="confidenceForm.sample_count" :min="5" :max="200" :step="5" />
        </el-form-item>
        <el-divider content-position="left">{{ t('explainability.inputData') }}</el-divider>
        <div class="ex-base-input-grid">
          <el-form-item
            v-for="field in STATE_FIELD_VALUES"
            :key="field"
            :label="STATE_FIELD_LABELS[field].split(' ')[0]"
            label-width="100px"
          >
            <el-input-number
              v-model="confidenceForm.input_data[field]"
              :step="0.1"
              controls-position="right"
              class="ex-base-input"
            />
          </el-form-item>
        </div>
      </el-form>
      <template #footer>
        <el-button @click="generateDialogs.confidence = false">{{ t('common.cancel') }}</el-button>
        <el-button
          type="primary"
          :loading="store.generatingConfidence"
          @click="handleGenerateConfidence"
        >
          {{ t('common.generate') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, shallowRef } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  MagicStick,
  ArrowDown,
  Download,
  Delete,
  CopyDocument,
  Connection,
  Close,
} from '@element-plus/icons-vue'
import { useExplainabilityStore } from '@/stores/explainability'
import {
  EXPLANATION_TYPE,
  EXPLANATION_TYPE_VALUES,
  EXPLANATION_TYPE_LABELS,
  EXPLANATION_TYPE_TAG_TYPE,
  PROJECTION_METHOD,
  PROJECTION_METHOD_VALUES,
  PROJECTION_METHOD_LABELS,
  DEFAULT_PROJECTION_METHOD,
  DEFAULT_PROJECTION_DIM,
  DEFAULT_MAX_FRAMES,
  DEFAULT_ANOMALY_SIGMA,
  DEFAULT_PERTURBATION_STEP,
  DEFAULT_SAMPLE_COUNT,
  COMPARISON_TYPE,
  COMPARISON_TYPE_VALUES,
  COMPARISON_TYPE_LABELS,
  COMPARISON_TYPE_TAG_TYPE,
  DEFAULT_COMPARISON_TYPE,
  type ExplanationType,
  type ComparisonType,
  type ExplanationPayload,
  type HiddenStateExplanation,
  type GateDynamicsExplanation,
  type CounterfactualExplanation,
  type ConfidenceExplanation,
  type GenerateHiddenStateRequest,
  type GenerateGateDynamicsRequest,
  type GenerateCounterfactualRequest,
  type GenerateConfidenceRequest,
  type CompareExplanationsRequest,
} from '@/contracts/explainability'
import { STATE_FIELD_VALUES, STATE_FIELD_LABELS } from '@/contracts/world_model'

const { t } = useI18n()
const store = useExplainabilityStore()

const currentPage = ref(1)
const filterType = ref<ExplanationType | ''>('')

/** 当前 payload（含完整内容） */
const currentPayload = shallowRef<ExplanationPayload | null>(null)

/** 对比选择（最多 2 个 explanation_id） */
const compareSelection = ref<string[]>([])

const generateDialogs = reactive({
  hidden_state: false,
  gate_dynamics: false,
  counterfactual: false,
  confidence: false,
})

const compareForm = reactive({
  comparison_type: DEFAULT_COMPARISON_TYPE as ComparisonType,
})

/** 隐状态投影表单 */
const hiddenStateForm = reactive({
  model_uri: 'model://LTC-ChatterPredictor/1.0.0',
  projection_method: DEFAULT_PROJECTION_METHOD,
  projection_dim: DEFAULT_PROJECTION_DIM,
  max_frames: DEFAULT_MAX_FRAMES,
  source_snapshot_id: '',
})

/** 门控动力学表单 */
const gateDynamicsForm = reactive({
  model_uri: 'model://LTC-ChatterPredictor/1.0.0',
  anomaly_sigma: DEFAULT_ANOMALY_SIGMA,
  source_snapshot_id: '',
})

/** 反事实表单 */
const counterfactualForm = reactive({
  model_uri: 'model://LTC-ChatterPredictor/1.0.0',
  perturbed_feature: 'spindle_speed',
  perturbation_step: DEFAULT_PERTURBATION_STEP,
  base_input: {
    spindle_speed: 8000,
    feed_rate: 1200,
    depth_of_cut: 1.5,
    width_of_cut: 6.0,
    tool_wear: 0.05,
    vibration_rms: 0.8,
    temperature: 45.0,
    chatter_probability: 0.1,
  } as Record<string, number>,
})

/** 置信度表单 */
const confidenceForm = reactive({
  model_uri: 'model://LTC-ChatterPredictor/1.0.0',
  sample_count: DEFAULT_SAMPLE_COUNT,
  input_data: {
    spindle_speed: 8000,
    feed_rate: 1200,
    depth_of_cut: 1.5,
    width_of_cut: 6.0,
    tool_wear: 0.05,
    vibration_rms: 0.8,
    temperature: 45.0,
    chatter_probability: 0.1,
  } as Record<string, number>,
})

/** payload 渲染器组件映射（简化为内联渲染函数） */
const payloadRenderers = {
  [EXPLANATION_TYPE.HIDDEN_STATE]: renderHiddenState,
  [EXPLANATION_TYPE.GATE_DYNAMICS]: renderGateDynamics,
  [EXPLANATION_TYPE.COUNTERFACTUAL]: renderCounterfactual,
  [EXPLANATION_TYPE.CONFIDENCE]: renderConfidence,
}

function getPayloadRenderer(type: ExplanationType) {
  return payloadRenderers[type] || renderRaw
}

function renderHiddenState(props: { payload: HiddenStateExplanation }) {
  return renderRaw({ payload: props.payload })
}

function renderGateDynamics(props: { payload: GateDynamicsExplanation }) {
  return renderRaw({ payload: props.payload })
}

function renderCounterfactual(props: { payload: CounterfactualExplanation }) {
  return renderRaw({ payload: props.payload })
}

function renderConfidence(props: { payload: ConfidenceExplanation }) {
  return renderRaw({ payload: props.payload })
}

/** 通用 JSON 渲染 */
function renderRaw(props: { payload: ExplanationPayload }) {
  return {
    template: '<pre class="ex-payload-json">{{ JSON.stringify(payload, null, 2) }}</pre>',
    setup() {
      return { payload: props.payload }
    },
  }
}

/** 格式化时间戳 */
function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

/** 格式化字节数 */
function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(2)} MB`
}

/** 加载解释列表 */
async function loadExplanations(): Promise<void> {
  const result = await store.fetchExplanations({
    limit: 50,
    offset: (currentPage.value - 1) * 50,
    explanation_type: filterType.value || undefined,
  })
  if (!result) {
    ElMessage.error(store.error || t('explainability.loadFailed'))
  }
}

/** 选择解释记录 */
async function handleSelectExplanation(id: string): Promise<void> {
  currentPayload.value = null
  const result = await store.fetchExplanation(id)
  if (!result) {
    ElMessage.error(store.error || t('explainability.loadFailed'))
  }
}

/** 加载完整 payload */
async function handleLoadPayload(): Promise<void> {
  if (!store.currentExplanation) return
  const result = await store.fetchExplanation(store.currentExplanation.id, {
    include_payload: true,
  })
  if (!result) {
    ElMessage.error(store.error || t('explainability.loadPayloadFailed'))
  } else if (result.payload) {
    currentPayload.value = result.payload
    ElMessage.success(t('explainability.payloadLoaded'))
  }
}

/** 删除解释记录 */
async function handleDelete(): Promise<void> {
  if (!store.currentExplanation) return
  try {
    await ElMessageBox.confirm(
      t('explainability.deleteConfirm'),
      t('common.delete'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  const result = await store.deleteExplanation(store.currentExplanation.id)
  if (!result) {
    ElMessage.error(store.error || t('explainability.deleteFailed'))
  } else {
    ElMessage.success(t('explainability.deleteSuccess'))
    currentPayload.value = null
    await loadExplanations()
  }
}

/** 添加到对比 */
function handleAddToCompare(): void {
  if (!store.currentExplanation) return
  const id = store.currentExplanation.id
  if (compareSelection.value.includes(id)) {
    ElMessage.warning(t('explainability.alreadyInCompare'))
    return
  }
  if (compareSelection.value.length >= 2) {
    ElMessage.warning(t('explainability.compareFull'))
    return
  }
  compareSelection.value.push(id)
  ElMessage.success(t('explainability.addedToCompare'))
}

/** 从对比移除 */
function handleRemoveFromCompare(idx: number): void {
  compareSelection.value.splice(idx, 1)
}

/** 清空对比 */
function handleClearCompare(): void {
  compareSelection.value = []
  store.clearLastResults()
}

/** 执行对比 */
async function handleCompare(): Promise<void> {
  if (compareSelection.value.length !== 2) return
  const request: CompareExplanationsRequest = {
    base_explanation_id: compareSelection.value[0],
    compared_explanation_id: compareSelection.value[1],
    comparison_type: compareForm.comparison_type,
  }
  const result = await store.compareExplanations(request)
  if (!result) {
    ElMessage.error(store.error || t('explainability.compareFailed'))
  } else {
    ElMessage.success(t('explainability.compareSuccess'))
  }
}

/** 打开生成对话框 */
function handleOpenGenerate(type: ExplanationType): void {
  generateDialogs[type] = true
}

/** 生成隐状态投影 */
async function handleGenerateHiddenState(): Promise<void> {
  const request: GenerateHiddenStateRequest = {
    model_uri: hiddenStateForm.model_uri,
    projection_method: hiddenStateForm.projection_method,
    projection_dim: hiddenStateForm.projection_dim,
    max_frames: hiddenStateForm.max_frames,
    source_snapshot_id: hiddenStateForm.source_snapshot_id || null,
  }
  const result = await store.generateHiddenStateExplanation(request)
  if (!result) {
    ElMessage.error(store.error || t('explainability.generateFailed'))
  } else {
    ElMessage.success(t('explainability.generateSuccess'))
    generateDialogs.hidden_state = false
    await loadExplanations()
  }
}

/** 生成门控动力学 */
async function handleGenerateGateDynamics(): Promise<void> {
  const request: GenerateGateDynamicsRequest = {
    model_uri: gateDynamicsForm.model_uri,
    anomaly_sigma: gateDynamicsForm.anomaly_sigma,
    source_snapshot_id: gateDynamicsForm.source_snapshot_id || null,
  }
  const result = await store.generateGateDynamicsExplanation(request)
  if (!result) {
    ElMessage.error(store.error || t('explainability.generateFailed'))
  } else {
    ElMessage.success(t('explainability.generateSuccess'))
    generateDialogs.gate_dynamics = false
    await loadExplanations()
  }
}

/** 生成反事实 */
async function handleGenerateCounterfactual(): Promise<void> {
  const request: GenerateCounterfactualRequest = {
    model_uri: counterfactualForm.model_uri,
    base_input: { ...counterfactualForm.base_input },
    perturbed_feature: counterfactualForm.perturbed_feature,
    perturbation_step: counterfactualForm.perturbation_step,
    source_snapshot_id: null,
  }
  const result = await store.generateCounterfactualExplanation(request)
  if (!result) {
    ElMessage.error(store.error || t('explainability.generateFailed'))
  } else {
    ElMessage.success(t('explainability.generateSuccess'))
    generateDialogs.counterfactual = false
    await loadExplanations()
  }
}

/** 生成置信度 */
async function handleGenerateConfidence(): Promise<void> {
  const request: GenerateConfidenceRequest = {
    model_uri: confidenceForm.model_uri,
    input_data: { ...confidenceForm.input_data },
    sample_count: confidenceForm.sample_count,
    source_snapshot_id: null,
  }
  const result = await store.generateConfidenceExplanation(request)
  if (!result) {
    ElMessage.error(store.error || t('explainability.generateFailed'))
  } else {
    ElMessage.success(t('explainability.generateSuccess'))
    generateDialogs.confidence = false
    await loadExplanations()
  }
}

/** 翻页 */
async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page
  await loadExplanations()
}

/** 类型过滤 */
async function handleFilterChange(): Promise<void> {
  currentPage.value = 1
  await loadExplanations()
}

/** 刷新 */
async function handleRefresh(): Promise<void> {
  currentPage.value = 1
  await loadExplanations()
}

onMounted(() => {
  void loadExplanations()
})
</script>

<style scoped>
.explainability-page {
  padding: 20px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ===== 页面头部 ===== */
.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.page-header__title {
  margin: 0;
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.page-header__subtitle {
  margin: 4px 0 0;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.page-header__actions {
  display: flex;
  gap: 8px;
}

/* ===== 主体布局 ===== */
.ex-main {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  align-items: start;
}

/* ===== 左侧列表 ===== */
.ex-list-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--radius-md);
  padding: 12px;
  max-height: calc(100vh - 140px);
}

.ex-list-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  gap: 8px;
}

.ex-list-panel__title {
  font-weight: 600;
  color: var(--el-text-color-primary);
  white-space: nowrap;
}

.ex-list-panel__filter {
  width: 140px;
}

.ex-list-panel__body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ex-list-panel__pager {
  margin-top: 8px;
  justify-content: center;
}

/* ===== 解释卡片 ===== */
.ex-card {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.ex-card:hover {
  border-color: var(--accent-primary);
  background: var(--accent-light);
}

.ex-card--active {
  border-color: var(--accent-primary);
  background: var(--accent-light);
  box-shadow: var(--shadow-ring);
}

.ex-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.ex-card__id {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

.ex-card__meta {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ex-card__time {
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

/* ===== 右侧详情 ===== */
.ex-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.ex-detail-card__header,
.ex-compare-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.ex-detail-card__actions {
  display: flex;
  gap: 4px;
}

/* ===== payload ===== */
.ex-payload {
  margin-top: 12px;
}

.ex-payload-json {
  margin: 0;
  padding: 12px;
  background: var(--el-fill-color-darker);
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--el-text-color-regular);
  max-height: 480px;
  overflow: auto;
  white-space: pre-wrap;
  word-break: break-all;
}

/* ===== 对比 ===== */
.ex-compare-selection {
  display: flex;
  flex-direction: column;
  gap: 6px;
  margin-bottom: 12px;
}

.ex-compare-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 6px 10px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--radius-xs);
  background: var(--el-fill-color-blank);
}

.ex-compare-item__id {
  font-family: var(--font-mono);
  font-size: 12px;
  color: var(--el-text-color-regular);
}

.ex-compare-form {
  margin-top: 8px;
}

.ex-compare-select {
  width: 200px;
}

.ex-compare-result {
  margin-top: 8px;
}

/* ===== 对话框表单 ===== */
.ex-dialog-select {
  width: 100%;
}

.ex-base-input-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 12px;
}

.ex-base-input {
  width: 100%;
}
</style>
