<!--
  RL Agent 视图（ADR-017 阶段 8 p8-7）

  对应后端 `python/app/api/v1/rl_agent.py`。
  详见 `docs/adr/ADR-017-世界模型与RL模块.md`。

  功能：
    1. 策略版本列表（左侧）+ 版本详情（右侧顶部）
    2. 决策面板：输入 current_state + candidate_actions + optimization_target，
       调用 store.act()，展示推荐动作与候选评估
    3. 训练控制面板：启动/停止 PPO 训练，轮询训练状态与指标
    4. 工程约束：
       - v1 仅离线 RL，基于历史数据 + 仿真环境训练
       - SafetyShield 硬约束强制过滤违反安全约束的动作
       - 推荐动作仅供 CAM 验证层参考，物理执行需持证操作员 + 导师签字 + 保险
-->
<template>
  <div class="rl-agent-page">
    <!-- ===== 页面头部 ===== -->
    <header class="page-header">
      <div class="page-header__title-block">
        <h1 class="page-header__title">{{ t('rlAgent.title') }}</h1>
        <p class="page-header__subtitle">{{ t('rlAgent.subtitle') }}</p>
      </div>
      <div class="page-header__actions">
        <el-button :icon="Refresh" @click="handleRefresh" :loading="store.anyLoading">
          {{ t('common.refresh') }}
        </el-button>
      </div>
    </header>

    <!-- ===== 主体：左列表 + 右详情/决策/训练 ===== -->
    <div class="rl-main">
      <!-- 左侧：策略版本列表 -->
      <section class="rl-list-panel">
        <div class="rl-list-panel__header">
          <span class="rl-list-panel__title">{{ t('rlAgent.policyVersions') }}</span>
          <el-tag v-if="store.versionPagination" size="small" type="info">
            {{ store.versionPagination.total }}
          </el-tag>
        </div>
        <div v-loading="store.versionsLoading" class="rl-list-panel__body">
          <el-empty
            v-if="!store.versionsLoading && !store.hasVersions"
            :description="t('rlAgent.emptyVersions')"
          />
          <div
            v-for="version in store.versions"
            :key="version.version"
            class="rl-version-card"
            :class="{ 'rl-version-card--active': store.currentVersion?.version === version.version }"
            @click="handleSelectVersion(version.version)"
          >
            <div class="rl-version-card__header">
              <span class="rl-version-card__version">v{{ version.version }}</span>
              <el-tag v-if="version.is_active" type="success" size="small">
                {{ t('rlAgent.active') }}
              </el-tag>
            </div>
            <div class="rl-version-card__desc">{{ version.description || '—' }}</div>
            <div class="rl-version-card__meta">
              <el-tag size="small" :type="POLICY_ALGORITHM_TAG_TYPE[version.algorithm]">
                {{ POLICY_ALGORITHM_LABELS[version.algorithm] }}
              </el-tag>
              <span>eps: {{ version.training_episodes }}</span>
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
          class="rl-list-panel__pager"
          @current-change="handlePageChange"
        />
      </section>

      <!-- 右侧：版本详情 + 决策 + 训练 -->
      <section class="rl-detail-panel">
        <!-- 版本详情 -->
        <el-card v-loading="store.versionLoading" class="rl-detail-card">
          <template #header>
            <div class="rl-detail-card__header">
              <span>{{ t('rlAgent.versionDetail') }}</span>
              <el-button
                v-if="store.currentVersion"
                link
                type="primary"
                @click="handleUseActiveVersion"
              >
                {{ t('rlAgent.useForAction') }}
              </el-button>
            </div>
          </template>
          <el-empty
            v-if="!store.versionLoading && !store.currentVersion"
            :description="t('rlAgent.selectVersionHint')"
          />
          <el-descriptions v-else-if="store.currentVersion" :column="2" border>
            <el-descriptions-item :label="t('rlAgent.fields.version')">
              {{ store.currentVersion.version }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.modelUri')">
              {{ store.currentVersion.model_uri }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.algorithm')">
              <el-tag size="small" :type="POLICY_ALGORITHM_TAG_TYPE[store.currentVersion.algorithm]">
                {{ POLICY_ALGORITHM_LABELS[store.currentVersion.algorithm] }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.trainingEpisodes')">
              {{ store.currentVersion.training_episodes }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.trainingSteps')">
              {{ store.currentVersion.training_steps }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.meanReward')">
              {{ store.currentVersion.mean_reward.toFixed(4) }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.createdAt')">
              {{ formatDateTime(store.currentVersion.created_at) }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('rlAgent.fields.isActive')">
              <el-tag :type="store.currentVersion.is_active ? 'success' : 'info'" size="small">
                {{ store.currentVersion.is_active ? t('common.yes') : t('common.no') }}
              </el-tag>
            </el-descriptions-item>
          </el-descriptions>
        </el-card>

        <!-- 决策面板 -->
        <el-card class="rl-act-card">
          <template #header>
            <div class="rl-act-card__header">
              <span>{{ t('rlAgent.actionDecision') }}</span>
              <el-tag v-if="store.lastAction" size="small" type="success">
                {{ t('rlAgent.decisionReady') }}
              </el-tag>
            </div>
          </template>

          <el-form label-width="140px" label-position="left">
            <el-form-item :label="t('rlAgent.fields.modelUri')">
              <el-input v-model="actForm.model_uri" placeholder="model://rl_agent/1.0.0" />
            </el-form-item>
            <el-form-item :label="t('rlAgent.optimizationTarget')">
              <el-select v-model="actForm.optimization_target" class="rl-form-select">
                <el-option
                  v-for="target in OPTIMIZATION_TARGET_VALUES"
                  :key="target"
                  :label="OPTIMIZATION_TARGET_LABELS[target]"
                  :value="target"
                />
              </el-select>
            </el-form-item>

            <!-- 当前状态 -->
            <el-divider content-position="left">{{ t('rlAgent.currentState') }}</el-divider>
            <div class="rl-state-grid">
              <el-form-item
                v-for="field in STATE_FIELD_VALUES"
                :key="field"
                :label="STATE_FIELD_LABELS[field]"
                label-width="120px"
              >
                <el-input-number
                  v-model="actForm.current_state[field]"
                  :step="0.01"
                  controls-position="right"
                  class="rl-state-input"
                />
              </el-form-item>
            </div>

            <!-- 候选动作集 -->
            <el-divider content-position="left">{{ t('rlAgent.candidateActions') }}</el-divider>
            <div
              v-for="(action, idx) in actForm.candidate_actions"
              :key="idx"
              class="rl-action-row"
            >
              <div class="rl-action-row__header">
                <span>{{ t('rlAgent.actionIndex', { n: idx + 1 }) }}</span>
                <el-button
                  v-if="actForm.candidate_actions.length > 1"
                  link
                  type="danger"
                  :icon="Delete"
                  @click="handleRemoveAction(idx)"
                />
              </div>
              <div class="rl-action-row__grid">
                <el-form-item
                  v-for="field in ACTION_FIELD_VALUES"
                  :key="field"
                  :label="ACTION_FIELD_LABELS[field]"
                  label-width="110px"
                >
                  <el-input-number
                    v-model="action[field]"
                    :step="0.05"
                    :min="-1"
                    :max="1"
                    controls-position="right"
                    class="rl-state-input"
                  />
                </el-form-item>
              </div>
            </div>
            <el-button :icon="Plus" plain @click="handleAddAction">
              {{ t('rlAgent.addAction') }}
            </el-button>

            <el-form-item class="rl-act-buttons">
              <el-button
                type="primary"
                :loading="store.acting"
                :icon="Promotion"
                @click="handleAct"
              >
                {{ t('rlAgent.runDecision') }}
              </el-button>
              <el-button @click="handleResetActForm">{{ t('common.reset') }}</el-button>
            </el-form-item>
          </el-form>

          <!-- 决策结果 -->
          <div v-if="store.lastAction" class="rl-act-result">
            <el-divider content-position="left">{{ t('rlAgent.decisionResult') }}</el-divider>

            <!-- 推荐动作 -->
            <el-alert
              :title="t('rlAgent.recommendedAction')"
              type="success"
              :closable="false"
              show-icon
              class="rl-recommend-alert"
            >
              <template #default>
                <div class="rl-recommend-body">
                  <div class="rl-recommend-action">
                    <el-tag
                      v-for="(val, key) in store.lastAction.recommended_action.action"
                      :key="key"
                      class="rl-action-tag"
                      :type="Math.abs(val) > 0.5 ? 'warning' : 'info'"
                    >
                      {{ key }}: {{ val.toFixed(3) }}
                    </el-tag>
                  </div>
                  <div class="rl-recommend-reasoning">
                    {{ store.lastAction.recommended_action.reasoning }}
                  </div>
                </div>
              </template>
            </el-alert>

            <!-- 策略元信息 -->
            <el-descriptions :column="2" border size="small" class="rl-policy-info">
              <el-descriptions-item :label="t('rlAgent.policy.algorithm')">
                <el-tag size="small" :type="POLICY_ALGORITHM_TAG_TYPE[store.lastAction.policy_info.algorithm]">
                  {{ POLICY_ALGORITHM_LABELS[store.lastAction.policy_info.algorithm] }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('rlAgent.policy.version')">
                {{ store.lastAction.policy_info.policy_version }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('rlAgent.policy.episodes')">
                {{ store.lastAction.policy_info.training_episodes }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('rlAgent.policy.epsilon')">
                {{ store.lastAction.policy_info.exploration_rate.toFixed(4) }}
              </el-descriptions-item>
            </el-descriptions>

            <!-- 候选评估表格 -->
            <div class="rl-eval-section">
              <div class="rl-eval-section__title">{{ t('rlAgent.actionEvaluations') }}</div>
              <el-table
                :data="store.lastAction.action_evaluation"
                size="small"
                max-height="280"
                border
              >
                <el-table-column type="index" label="#" width="50" />
                <el-table-column label="expected_return" width="140">
                  <template #default="{ row }">
                    {{ row.expected_return.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="chatter_prob" width="120">
                  <template #default="{ row }">
                    <span :class="{ 'rl-metric--warn': row.predicted_chatter_prob > 0.3 }">
                      {{ row.predicted_chatter_prob.toFixed(4) }}
                    </span>
                  </template>
                </el-table-column>
                <el-table-column label="tool_wear" width="120">
                  <template #default="{ row }">
                    {{ row.predicted_tool_wear.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="q_value" width="120">
                  <template #default="{ row }">
                    {{ row.q_value.toFixed(4) }}
                  </template>
                </el-table-column>
                <el-table-column label="safety" width="100">
                  <template #default="{ row }">
                    <el-tag :type="row.safety_violation ? 'danger' : 'success'" size="small">
                      {{ row.safety_violation ? t('rlAgent.violation') : t('rlAgent.safe') }}
                    </el-tag>
                  </template>
                </el-table-column>
              </el-table>
            </div>

            <el-alert
              :title="t('rlAgent.safetyNotice')"
              type="warning"
              :closable="false"
              show-icon
              class="rl-safety-alert"
            />
          </div>
        </el-card>

        <!-- 训练控制面板 -->
        <el-card class="rl-training-card">
          <template #header>
            <div class="rl-training-card__header">
              <span>{{ t('rlAgent.trainingControl') }}</span>
              <el-tag
                v-if="store.trainingStatus"
                :type="TRAINING_STATUS_TAG_TYPE[store.trainingStatus.status]"
                size="small"
              >
                {{ TRAINING_STATUS_LABELS[store.trainingStatus.status] }}
              </el-tag>
            </div>
          </template>

          <!-- 训练状态展示 -->
          <div v-loading="store.trainingStatusLoading" class="rl-training-status">
            <el-empty
              v-if="!store.trainingStatusLoading && !store.trainingStatus"
              :description="t('rlAgent.noTrainingStatus')"
            />
            <template v-else-if="store.trainingStatus">
              <el-descriptions :column="2" border size="small">
                <el-descriptions-item :label="t('rlAgent.training.status')">
                  <el-tag :type="TRAINING_STATUS_TAG_TYPE[store.trainingStatus.status]" size="small">
                    {{ TRAINING_STATUS_LABELS[store.trainingStatus.status] }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item :label="t('rlAgent.training.progress')">
                  {{ store.trainingProgress.toFixed(1) }}%
                </el-descriptions-item>
                <el-descriptions-item :label="t('rlAgent.training.currentStep')">
                  {{ store.trainingStatus.current_step }} / {{ store.trainingStatus.max_steps }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('rlAgent.training.currentEpisode')">
                  {{ store.trainingStatus.current_episode }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('rlAgent.training.startedAt')">
                  {{ formatDateTime(store.trainingStatus.started_at) }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('rlAgent.training.finishedAt')">
                  {{ formatDateTime(store.trainingStatus.finished_at) }}
                </el-descriptions-item>
              </el-descriptions>

              <!-- 训练指标 -->
              <div v-if="store.trainingStatus.metrics" class="rl-training-metrics">
                <div class="rl-training-metrics__title">{{ t('rlAgent.training.metrics') }}</div>
                <div class="rl-metrics-grid">
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">policy_loss</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.policy_loss.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">value_loss</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.value_loss.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">entropy</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.entropy.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">approx_kl</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.approx_kl.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">clip_fraction</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.clip_fraction.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">mean_reward</span>
                    <span class="rl-metric-item__value rl-metric-item__value--highlight">
                      {{ store.trainingStatus.metrics.mean_reward.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">epsilon</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.epsilon.toFixed(4) }}
                    </span>
                  </div>
                  <div class="rl-metric-item">
                    <span class="rl-metric-item__label">elapsed</span>
                    <span class="rl-metric-item__value">
                      {{ store.trainingStatus.metrics.elapsed_seconds.toFixed(1) }}s
                    </span>
                  </div>
                </div>
              </div>

              <!-- 失败原因 -->
              <el-alert
                v-if="store.trainingStatus.error_message"
                :title="t('rlAgent.training.errorOccurred')"
                :description="store.trainingStatus.error_message"
                type="error"
                :closable="false"
                show-icon
                class="rl-training-error"
              />
            </template>
          </div>

          <!-- 训练控制按钮 -->
          <div class="rl-training-controls">
            <el-form :inline="true" class="rl-training-form">
              <el-form-item :label="t('rlAgent.training.maxSteps')">
                <el-input-number
                  v-model="trainingForm.max_steps"
                  :min="MIN_MAX_STEPS"
                  :max="MAX_MAX_STEPS"
                  :step="10000"
                  controls-position="right"
                />
              </el-form-item>
              <el-form-item :label="t('rlAgent.training.algorithm')">
                <el-select v-model="trainingForm.algorithm" class="rl-training-select">
                  <el-option
                    v-for="algo in POLICY_ALGORITHM_VALUES"
                    :key="algo"
                    :label="POLICY_ALGORITHM_LABELS[algo]"
                    :value="algo"
                    :disabled="algo !== POLICY_ALGORITHM.PPO"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('rlAgent.training.target')">
                <el-select v-model="trainingForm.optimization_target" class="rl-training-select">
                  <el-option
                    v-for="target in OPTIMIZATION_TARGET_VALUES"
                    :key="target"
                    :label="OPTIMIZATION_TARGET_LABELS[target]"
                    :value="target"
                  />
                </el-select>
              </el-form-item>
            </el-form>

            <div class="rl-training-buttons">
              <el-button
                type="primary"
                :icon="VideoPlay"
                :loading="store.startingTraining"
                :disabled="store.isTraining"
                @click="handleStartTraining"
              >
                {{ t('rlAgent.training.start') }}
              </el-button>
              <el-button
                type="danger"
                :icon="VideoPause"
                :loading="store.stoppingTraining"
                :disabled="!store.isTraining"
                @click="handleStopTraining"
              >
                {{ t('rlAgent.training.stop') }}
              </el-button>
              <el-button :icon="Refresh" @click="handleFetchTrainingStatus">
                {{ t('rlAgent.training.refresh') }}
              </el-button>
            </div>

            <el-alert
              :title="t('rlAgent.training.offlineNotice')"
              type="info"
              :closable="false"
              show-icon
              class="rl-training-notice"
            />
          </div>
        </el-card>
      </section>
    </div>
  </div>
</template>

<script setup lang="ts">
import { onMounted, reactive, ref, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  VideoPlay,
  VideoPause,
  Promotion,
  Plus,
  Delete,
} from '@element-plus/icons-vue'
import { useRlAgentStore } from '@/stores/rlAgent'
import {
  STATE_FIELD,
  STATE_FIELD_VALUES,
  STATE_FIELD_LABELS,
  ACTION_FIELD,
  ACTION_FIELD_VALUES,
  ACTION_FIELD_LABELS,
  OPTIMIZATION_TARGET,
  OPTIMIZATION_TARGET_VALUES,
  OPTIMIZATION_TARGET_LABELS,
  POLICY_ALGORITHM,
  POLICY_ALGORITHM_VALUES,
  POLICY_ALGORITHM_LABELS,
  POLICY_ALGORITHM_TAG_TYPE,
  TRAINING_STATUS_LABELS,
  TRAINING_STATUS_TAG_TYPE,
  DEFAULT_RL_AGENT_URI,
  DEFAULT_MAX_STEPS,
  MIN_MAX_STEPS,
  MAX_MAX_STEPS,
  DEFAULT_OPTIMIZATION_TARGET,
  DEFAULT_POLICY_ALGORITHM,
  type OptimizationTarget,
  type PolicyAlgorithm,
  type RLActRequest,
} from '@/contracts/rl_agent'

const { t } = useI18n()
const store = useRlAgentStore()

const currentPage = ref(1)
let trainingPollTimer: ReturnType<typeof setInterval> | null = null

/** 默认状态值 */
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

const defaultAction = (): Record<string, number> => ({
  [ACTION_FIELD.SPINDLE_SPEED_DELTA]: 0.0,
  [ACTION_FIELD.FEED_RATE_DELTA]: 0.0,
  [ACTION_FIELD.DEPTH_OF_CUT_DELTA]: 0.0,
  [ACTION_FIELD.WIDTH_OF_CUT_DELTA]: 0.0,
})

const actForm = reactive({
  model_uri: DEFAULT_RL_AGENT_URI,
  optimization_target: DEFAULT_OPTIMIZATION_TARGET as OptimizationTarget,
  current_state: { ...defaultStateValue },
  candidate_actions: [defaultAction(), { ...defaultAction() }] as Array<Record<string, number>>,
})

const trainingForm = reactive({
  max_steps: DEFAULT_MAX_STEPS,
  algorithm: DEFAULT_POLICY_ALGORITHM as PolicyAlgorithm,
  optimization_target: DEFAULT_OPTIMIZATION_TARGET as OptimizationTarget,
  seed: null as number | null,
})

/** 格式化时间戳 */
function formatDateTime(iso: string | null): string {
  if (!iso) return '—'
  try {
    return new Date(iso).toLocaleString('zh-CN')
  } catch {
    return iso
  }
}

/** 加载版本列表 */
async function loadVersions(): Promise<void> {
  const result = await store.fetchVersions({ limit: 50, offset: (currentPage.value - 1) * 50 })
  if (!result) {
    ElMessage.error(store.error || t('rlAgent.loadFailed'))
  }
}

/** 选择版本查看详情 */
async function handleSelectVersion(version: string): Promise<void> {
  const result = await store.fetchVersion(version)
  if (!result) {
    ElMessage.error(store.error || t('rlAgent.loadFailed'))
  }
}

/** 使用当前版本填充 model_uri */
function handleUseActiveVersion(): void {
  if (store.currentVersion) {
    actForm.model_uri = store.currentVersion.model_uri
    ElMessage.success(t('rlAgent.modelUriFilled'))
  }
}

async function handlePageChange(page: number): Promise<void> {
  currentPage.value = page
  await loadVersions()
}

async function handleRefresh(): Promise<void> {
  currentPage.value = 1
  await loadVersions()
  await handleFetchTrainingStatus()
}

/** 添加候选动作 */
function handleAddAction(): void {
  actForm.candidate_actions.push(defaultAction())
}

/** 移除候选动作 */
function handleRemoveAction(idx: number): void {
  if (actForm.candidate_actions.length > 1) {
    actForm.candidate_actions.splice(idx, 1)
  }
}

/** 执行决策 */
async function handleAct(): Promise<void> {
  const request: RLActRequest = {
    model_uri: actForm.model_uri,
    optimization_target: actForm.optimization_target,
    current_state: { ...actForm.current_state },
    candidate_actions: actForm.candidate_actions.map((a) => ({ ...a })),
    safety_constraints: null,
  }
  const result = await store.act(request)
  if (!result) {
    ElMessage.error(store.error || t('rlAgent.actFailed'))
  } else {
    ElMessage.success(t('rlAgent.actSuccess'))
  }
}

/** 重置决策表单 */
function handleResetActForm(): void {
  actForm.model_uri = DEFAULT_RL_AGENT_URI
  actForm.optimization_target = DEFAULT_OPTIMIZATION_TARGET
  actForm.current_state = { ...defaultStateValue }
  actForm.candidate_actions = [defaultAction(), { ...defaultAction() }]
  store.clearLastAction()
}

/** 启动训练 */
async function handleStartTraining(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('rlAgent.training.startConfirm', { steps: trainingForm.max_steps }),
      t('rlAgent.training.startTitle'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  const result = await store.startTraining({
    max_steps: trainingForm.max_steps,
    algorithm: trainingForm.algorithm,
    optimization_target: trainingForm.optimization_target,
    seed: trainingForm.seed,
  })
  if (!result) {
    ElMessage.error(store.error || t('rlAgent.training.startFailed'))
  } else {
    ElMessage.success(t('rlAgent.training.startSuccess'))
    startTrainingPolling()
  }
}

/** 停止训练 */
async function handleStopTraining(): Promise<void> {
  try {
    await ElMessageBox.confirm(
      t('rlAgent.training.stopConfirm'),
      t('rlAgent.training.stopTitle'),
      { type: 'warning' },
    )
  } catch {
    return
  }
  const result = await store.stopTraining()
  if (!result) {
    ElMessage.error(store.error || t('rlAgent.training.stopFailed'))
  } else {
    ElMessage.success(t('rlAgent.training.stopSuccess'))
    stopTrainingPolling()
  }
}

/** 拉取训练状态 */
async function handleFetchTrainingStatus(): Promise<void> {
  await store.fetchTrainingStatus()
}

/** 启动轮询 */
function startTrainingPolling(): void {
  stopTrainingPolling()
  trainingPollTimer = setInterval(async () => {
    await handleFetchTrainingStatus()
    if (store.isTrainingTerminal) {
      stopTrainingPolling()
    }
  }, 3000)
}

/** 停止轮询 */
function stopTrainingPolling(): void {
  if (trainingPollTimer) {
    clearInterval(trainingPollTimer)
    trainingPollTimer = null
  }
}

onMounted(() => {
  void loadVersions()
  void handleFetchTrainingStatus()
})

onUnmounted(() => {
  stopTrainingPolling()
})
</script>

<style scoped>
.rl-agent-page {
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
.rl-main {
  display: grid;
  grid-template-columns: 360px 1fr;
  gap: 16px;
  align-items: start;
}

/* ===== 左侧列表 ===== */
.rl-list-panel {
  display: flex;
  flex-direction: column;
  gap: 8px;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 8px;
  padding: 12px;
  max-height: calc(100vh - 140px);
}

.rl-list-panel__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.rl-list-panel__title {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.rl-list-panel__body {
  flex: 1;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rl-list-panel__pager {
  margin-top: 8px;
  justify-content: center;
}

/* ===== 版本卡片 ===== */
.rl-version-card {
  padding: 10px 12px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.2s;
}

.rl-version-card:hover {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.rl-version-card--active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
  box-shadow: 0 0 0 1px var(--el-color-primary) inset;
}

.rl-version-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.rl-version-card__version {
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.rl-version-card__desc {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rl-version-card__meta {
  display: flex;
  gap: 8px;
  align-items: center;
  font-size: 11px;
  color: var(--el-text-color-placeholder);
}

/* ===== 右侧详情 ===== */
.rl-detail-panel {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.rl-detail-card__header,
.rl-act-card__header,
.rl-training-card__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

/* ===== 决策表单 ===== */
.rl-form-select {
  width: 100%;
}

.rl-state-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 16px;
}

.rl-state-input {
  width: 100%;
}

.rl-action-row {
  padding: 12px;
  margin-bottom: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  background: var(--el-fill-color-blank);
}

.rl-action-row__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.rl-action-row__grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0 16px;
}

.rl-act-buttons {
  margin-top: 12px;
}

/* ===== 决策结果 ===== */
.rl-act-result {
  margin-top: 8px;
}

.rl-recommend-alert {
  margin-bottom: 12px;
}

.rl-recommend-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.rl-recommend-action {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.rl-action-tag {
  font-family: monospace;
}

.rl-recommend-reasoning {
  font-size: 13px;
  color: var(--el-text-color-regular);
  line-height: 1.5;
}

.rl-policy-info {
  margin: 12px 0;
}

.rl-eval-section {
  margin-top: 12px;
}

.rl-eval-section__title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.rl-metric--warn {
  color: var(--el-color-danger);
  font-weight: 600;
}

.rl-safety-alert {
  margin-top: 16px;
}

/* ===== 训练控制 ===== */
.rl-training-status {
  margin-bottom: 16px;
}

.rl-training-metrics {
  margin-top: 12px;
}

.rl-training-metrics__title {
  font-weight: 600;
  margin-bottom: 8px;
  color: var(--el-text-color-primary);
}

.rl-metrics-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
}

.rl-metric-item {
  display: flex;
  flex-direction: column;
  padding: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  background: var(--el-fill-color-blank);
}

.rl-metric-item__label {
  font-size: 11px;
  color: var(--el-text-color-secondary);
  margin-bottom: 4px;
}

.rl-metric-item__value {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  font-family: monospace;
}

.rl-metric-item__value--highlight {
  color: var(--el-color-success);
}

.rl-training-error {
  margin-top: 12px;
}

.rl-training-form {
  margin-bottom: 8px;
}

.rl-training-select {
  width: 160px;
}

.rl-training-buttons {
  display: flex;
  gap: 8px;
  margin: 12px 0;
}

.rl-training-notice {
  margin-top: 8px;
}
</style>
