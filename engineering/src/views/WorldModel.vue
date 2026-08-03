<!--
  世界模型视图（ADR-017 阶段 8 p8-7）

  对应后端 `python/app/api/v1/world_model.py`。
  详见 `docs/adr/ADR-017-世界模型与RL模块.md`。

  功能：
    1. 世界模型版本列表（左侧）+ 版本详情（右侧顶部）
    2. 轨迹预测面板：输入 current_state + candidate_action + horizon，
       调用 store.predict()，展示预测轨迹与汇总指标
    3. 工程约束：v1 仅离线预测，结果供 RL agent 训练参考，
       不直接接 CNC 控制器（物理执行需持证操作员 + 导师签字 + 保险）
-->
<template>
  <div class="world-model-page">
    <!-- ===== 页面头部 ===== -->
    <header class="page-header">
      <div class="page-header__title-block">
        <h1 class="page-header__title">{{ t('worldModel.title') }}</h1>
        <p class="page-header__subtitle">{{ t('worldModel.subtitle') }}</p>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" @click="handleRefresh" :loading="store.anyLoading">
          {{ t('common.refresh') }}
        </el-button>
      </div>
    </header>

    <!-- ===== 主体：左列表 + 右详情/预测 ===== -->
    <div class="wm-main">
      <!-- 左侧：版本列表 -->
      <section class="wm-list-panel">
        <div class="wm-list-panel__header">
          <span class="wm-list-panel__title">{{ t('worldModel.versionList') }}</span>
          <el-tag v-if="store.versionPagination" size="small" type="info">
            {{ store.versionPagination.total }}
          </el-tag>
        </div>
        <div v-loading="store.versionsLoading" class="wm-list-panel__body">
          <el-empty
            v-if="!store.versionsLoading && !store.hasVersions"
            :description="t('worldModel.emptyVersions')"
          />
          <div
            v-for="version in store.versions"
            :key="version.version"
            class="wm-version-card"
            :class="{ 'wm-version-card--active': store.currentVersion?.version === version.version }"
            @click="handleSelectVersion(version.version)"
          >
            <div class="wm-version-card__header">
              <span class="wm-version-card__version">v{{ version.version }}</span>
              <el-tag v-if="version.is_active" type="success" size="small">
                {{ t('worldModel.active') }}
              </el-tag>
            </div>
            <div class="wm-version-card__desc">{{ version.description || '—' }}</div>
            <div class="wm-version-card__meta">
              <span>horizon: {{ version.prediction_horizon }}</span>
              <span>samples: {{ version.training_data_size }}</span>
            </div>
          </div>
        </div>
        <el-pagination
          v-if="store.totalPages > 1"
          v-model:current-page="currentPage"
          small
          layout="prev, pager, next"
          :page-size="store.versionPagination?.limit ?? 50"
          :total="store.versionPagination?.total ?? 0"
          class="wm-list-panel__pager"
          @current-change="handlePageChange"
        />
      </section>

      <!-- 右侧：版本详情 + 预测面板 -->
      <section class="wm-detail-panel">
        <!-- 版本详情 -->
        <el-card v-loading="store.versionLoading" class="wm-detail-card">
          <template #header>
            <div class="wm-detail-card__header">
              <span>{{ t('worldModel.versionDetail') }}</span>
              <el-button
                v-if="store.currentVersion"
                link
                type="primary"
                @click="handleUseActiveVersion"
              >
                {{ t('worldModel.useForPrediction') }}
              </el-button>
            </div>
          </template>
          <el-empty
            v-if="!store.versionLoading && !store.currentVersion"
            :description="t('worldModel.selectVersionHint')"
          />
          <el-descriptions
            v-else-if="store.currentVersion"
            :column="1"
            border
          >
            <el-descriptions-item :label="t('worldModel.fields.version')">
              {{ store.currentVersion.version }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('worldModel.fields.modelUri')">
              {{ store.currentVersion.model_uri }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('worldModel.fields.algorithm')">
              {{ store.currentVersion.description || '—' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('worldModel.fields.trainingDataSize')">
              {{ store.currentVersion.training_data_size }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('worldModel.fields.predictionHorizon')">
              {{ store.currentVersion.prediction_horizon }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('worldModel.fields.createdAt')">
              {{ formatDateTime(store.currentVersion.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('worldModel.fields.isActive')">
              <el-tag :type="store.currentVersion.is_active ? 'success' : 'info'" size="small">
                {{ store.currentVersion.is_active ? t('common.yes') : t('common.no') }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 预测面板 -->
        <el-card class="wm-predict-card">
          <template #header>
            <div class="wm-predict-card__header">
              <span>{{ t('worldModel.trajectoryPrediction') }}</span>
              <el-tag v-if="store.lastPrediction" size="small" type="success">
                {{ t('worldModel.predictionReady') }}
              </el-tag>
            </div>
          </template>

          <!-- 预测表单 -->
          <el-form label-width="140px" label-position="left">
            <el-form-item :label="t('worldModel.fields.modelUri')">
              <el-input v-model="predictForm.model_uri" placeholder="model://world_model/1.0.0" />
            </el-form-item>
            <el-form-item :label="t('worldModel.horizon')">
              <el-input-number
                v-model="predictForm.horizon"
                :min="MIN_HORIZON"
                :max="MAX_HORIZON"
                :step="1"
              />
              <span class="wm-form-hint">{{ t('worldModel.horizonHint') }}</span>
            </el-form-item>

            <!-- 当前状态输入 -->
            <el-divider content-position="left">{{ t('worldModel.currentState') }}</el-divider>
            <div class="wm-state-grid">
              <el-form-item
                v-for="field in STATE_FIELD_VALUES"
                :key="field"
                :label="STATE_FIELD_LABELS[field]"
                label-width="120px"
              >
                <el-input-number
                  v-model="predictForm.current_state[field]"
                  :step="0.01"
                  controls-position="right"
                  class="wm-state-input"
                />
              </el-form-item>
            </div>

            <!-- 候选动作输入 -->
            <el-divider content-position="left">{{ t('worldModel.candidateAction') }}</el-divider>
            <div class="wm-state-grid">
              <el-form-item
                v-for="field in ACTION_FIELD_VALUES"
                :key="field"
                :label="ACTION_FIELD_LABELS[field]"
                label-width="120px"
              >
                <el-input-number
                  v-model="predictForm.candidate_action[field]"
                  :step="0.05"
                  :min="-1"
                  :max="1"
                  controls-position="right"
                  class="wm-state-input"
                />
              </el-form-item>
            </div>

            <el-form-item>
              <el-button
                type="primary"
                :loading="store.predicting"
                :icon="VideoPlay"
                @click="handlePredict"
              >
                {{ t('worldModel.runPrediction') }}
              </el-button>
              <el-button @click="handleResetForm">{{ t('common.reset') }}</el-button>
            </el-form-item>
          </el-form>

          <!-- 预测结果 -->
          <div v-if="store.lastPrediction" class="wm-predict-result">
            <el-divider content-position="left">{{ t('worldModel.predictionResult') }}</el-divider>

            <!-- 汇总指标 -->
            <el-descriptions :column="2" border size="small">
              <el-descriptions-item :label="t('worldModel.metrics.meanChatter')">
                <span :class="{ 'wm-metric--warn': store.lastPredictionMaxChatter > 0.3 }">
                  {{ store.lastPrediction.trajectory_metrics.mean_chatter_probability.toFixed(4) }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('worldModel.metrics.maxChatter')">
                <span :class="{ 'wm-metric--warn': store.lastPredictionMaxChatter > 0.5 }">
                  {{ store.lastPrediction.trajectory_metrics.max_chatter_probability.toFixed(4) }}
                </span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('worldModel.metrics.cumulativeWear')">
                {{ store.lastPrediction.trajectory_metrics.cumulative_tool_wear.toFixed(4) }} mm
              </el-descriptions-item>
              <el-descriptions-item :label="t('worldModel.metrics.finalRoughness')">
                {{ store.lastPrediction.trajectory_metrics.final_surface_roughness.toFixed(4) }} μm
              </el-descriptions-item>
            </el-descriptions>

            <!-- 模型信息 -->
            <el-descriptions :column="2" border size="small" class="wm-model-info">
              <el-descriptions-item :label="t('worldModel.modelInfo.version')">
                {{ store.lastPrediction.model_info.world_model_version }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('worldModel.modelInfo.uncertainty')">
                {{ store.lastPrediction.model_info.uncertainty_estimate.toFixed(4) }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- 轨迹表格 -->
            <div class="wm-trajectory-section">
              <div class="wm-trajectory-section__title">
                {{ t('worldModel.trajectorySteps') }}（{{ store.lastPredictionStepCount }}）
              </div>
              <el-table
                :data="store.lastPrediction.predicted_trajectory"
                size="small"
                max-height="320"
                border
              >
                <el-table-column prop="step" label="step" width="60" />
                <el-table-column label="chatter_prob" width="120">
                  <template #default="{ row }">
                    <span :class="{ 'wm-metric--warn': row.chatter_probability > 0.3 }">
                      {{ row.chatter_probability.toFixed(4) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="tool_wear_inc" width="120">
                  <template #default="{ row }">
                    {{ row.tool_wear_increment.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="Ra (μm)" width="100">
                  <template #default="{ row }">
                    {{ row.surface_roughness.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="confidence" width="100">
                  <template #default="{ row }">
                    {{ row.confidence.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="predicted_state">
                  <template #default="{ row }">
                    <pre class="wm-json-inline">{{ formatStateBrief(row.predicted_state) }}</pre>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <!-- 安全提示 -->
            <el-alert
              :title="t('worldModel.safetyNotice')"
              type="warning"
              :closable="false"
              show-icon
              class="wm-safety-alert"
            />
          </div>
        </el-card>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Refresh, VideoPlay } from '@element-plus/icons-vue'
import { useWorldModelStore } from '@/stores/worldModel'
import {
  STATE_FIELD,
  STATE_FIELD_VALUES,
  STATE_FIELD_LABELS,
  ACTION_FIELD,
  ACTION_FIELD_VALUES,
  ACTION_FIELD_LABELS,
  DEFAULT_HORIZON,
  MIN_HORIZON,
  MAX_HORIZON,
  DEFAULT_WORLD_MODEL_URI,
  type WorldModelPredictRequest,
} from '@/contracts/world_model'

const { t } = useI18n()
const store = useWorldModelStore()

const currentPage = ref(1)

/** 默认状态值（典型 6061-T6 粗加工场景） */
const defaultStateValue: Record<string, number> = {
  [STATE_FIELD.SPINDLE_SPEED]: 8000,
  [STATE_FIELD.FEED_RATE]: 1200,
  [STATE_FIELD.DEPTH_OF_CUT]: 1.5,
  [STATE_FIELD.WIDTH_OF_CUT]: 6.0,
  [STATE_FIELD.TOOL_WEAR]: 0.05,
  [STATE_FIELD.VIBRATION_RMS]: 0.8,
  [STATE_FIELD.TEMPERATURE]: 45.0,
  [STATE_FIELD.CHATTER_PROBABILITY]: 0.1,
}

const defaultActionValue: Record<string, number> = {
  [ACTION_FIELD.SPINDLE_SPEED_DELTA]: 0.0,
  [ACTION_FIELD.FEED_RATE_DELTA]: 0.0,
  [ACTION_FIELD.DEPTH_OF_CUT_DELTA]: 0.0,
  [ACTION_FIELD.WIDTH_OF_CUT_DELTA]: 0.0,
}

const predictForm = reactive<{
  model_uri: string
  horizon: number
  current_state: Record<string, number>
  candidate_action: Record<string, number>
}>({
  model_uri: DEFAULT_WORLD_MODEL_URI,
  horizon: DEFAULT_HORIZON,
  current_state: { ...defaultStateValue },
  candidate_action: { ...defaultActionValue },
})

/** 格式化时间戳 */
function formatDateTime(iso: string): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

/** 简要展示 state 字典 */
function formatStateBrief(state: Record<string, number>): string {
  const keys = [STATE_FIELD.CHATTER_PROBABILITY, STATE_FIELD.TOOL_WEAR, STATE_FIELD.VIBRATION_RMS]
  return keys
    .map((k) => `${STATE_FIELD_LABELS[k].split(' ')[0]}=${state[k]?.toFixed(3) ?? '—'}`)
    .join(', ')
}

/** 加载版本列表 */
async function loadVersions(): Promise<void> {
  const result = await store.fetchVersions({ limit: 50, offset: (currentPage.value - 1) * 50 })
  if (!result) {
    ElMessage.error(store.error || t('worldModel.loadFailed'))
  }
}

/** 选择版本查看详情 */
async function handleSelectVersion(version: string): Promise<void> {
  const result = await store.fetchVersion(version)
  if (!result) {
    ElMessage.error(store.error || t('worldModel.loadFailed'))
  }
}

/** 使用当前版本填充预测表单 model_uri */
function handleUseActiveVersion(): void {
  if (store.currentVersion) {
    predictForm.model_uri = store.currentVersion.model_uri
    ElMessage.success(t('worldModel.modelUriFilled'))
  }
}

/** 翻页 */
async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page
  await loadVersions()
}

/** 刷新 */
async function handleRefresh(): Promise<void> {
  currentPage.value = 1
  await loadVersions()
}

/** 执行预测 */
async function handlePredict(): Promise<void> {
  const request: WorldModelPredictRequest = {
    model_uri: predictForm.model_uri,
    horizon: predictForm.horizon,
    current_state: { ...predictForm.current_state },
    candidate_action: { ...predictForm.candidate_action },
  }
  const result = await store.predict(request)
  if (!result) {
    ElMessage.error(store.error || t('worldModel.predictFailed'))
  } else {
    ElMessage.success(t('worldModel.predictSuccess'))
  }
}

/** 重置表单 */
function handleResetForm(): void {
  predictForm.model_uri = DEFAULT_WORLD_MODEL_URI
  predictForm.horizon = DEFAULT_HORIZON
  predictForm.current_state = { ...defaultStateValue }
  predictForm.candidate_action = { ...defaultActionValue }
  store.clearLastPrediction()
}

onMounted(() => {
  void loadVersions()
})
</script>

<style scoped>
.world-model-page {
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

/* ===== 主体布局 ===== */
.wm-main {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  align-items: start;
}

/* ===== 左侧列表 ===== */
.wm-list-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--radius-md);
  padding: 12px;
  max-height: calc(100vh - 140px);
}

.wm-list-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.wm-list-panel__title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.wm-list-panel__body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.wm-list-panel__pager {
  margin-top: 8px;
  justify-content: center;
}

/* ===== 版本卡片 ===== */
.wm-version-card {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: all 0.2s;
}

.wm-version-card:hover {
  border-color: var(--accent-primary);
  background: var(--accent-light);
}

.wm-version-card--active {
  border-color: var(--accent-primary);
  background: var(--accent-light);
  box-shadow: var(--shadow-ring);
}

.wm-version-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.wm-version-card__version {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.wm-version-card__desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.wm-version-card__meta {
  display: flex;
  gap: 12px;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

/* ===== 右侧详情 ===== */
.wm-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.wm-detail-card__header,
.wm-predict-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ===== 预测表单 ===== */
.wm-form-hint {
  margin-left: 8px;
  font-size: 12px;
  color: var(--el-text-color-secondary);
}

.wm-state-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 16px;
}

.wm-state-input {
  width: 100%;
}

/* ===== 预测结果 ===== */
.wm-predict-result {
  margin-top: 8px;
}

.wm-model-info {
  margin-top: 12px;
}

.wm-trajectory-section {
  margin-top: 16px;
}

.wm-trajectory-section__title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.wm-json-inline {
  margin: 0;
  font-size: 11px;
  color: var(--el-text-color-secondary);
  white-space: pre-wrap;
}

.wm-metric--warn {
  color: var(--state-error);
  font-weight: 600;
}

.wm-safety-alert {
  margin-top: 16px;
}
</style>
