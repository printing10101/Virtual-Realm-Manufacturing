<template>
  <div class="workspace-page">
    <el-card>
      <template #header>
        <div class="header-with-actions">
          <span>{{ $t('workspace.header') }}</span>
          <el-tag
            type="info"
            size="small"
          >
            {{ $t('workspace.userSovereignty') }}
          </el-tag>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane
          :label="$t('workspace.predictTab')"
          name="predict"
        >
          <WorkspacePredictTab />
        </el-tab-pane>

        <el-tab-pane
          :label="$t('workspace.trainTab')"
          name="train"
        >
          <el-form
            :model="trainForm"
            label-width="140px"
          >
            <el-form-item :label="$t('workspace.modelName')">
              <el-input
                v-model="trainForm.modelName"
                :placeholder="$t('workspace.modelNamePlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="$t('workspace.dataPath')">
              <el-input
                v-model="trainForm.dataPath"
                :placeholder="$t('workspace.dataPathPlaceholder')"
              />
            </el-form-item>
            <el-divider content-position="left">
              {{ $t('workspace.hyperparams') }}
            </el-divider>
            <el-form-item :label="$t('workspace.learningRate')">
              <el-input-number
                v-model="trainForm.hyperparameters.learning_rate"
                :min="0.0001"
                :max="0.1"
                :step="0.001"
                :precision="4"
              />
            </el-form-item>
            <el-form-item :label="$t('workspace.epochs')">
              <el-input-number
                v-model="trainForm.hyperparameters.epochs"
                :min="1"
                :max="1000"
                :step="10"
              />
            </el-form-item>
            <el-form-item :label="$t('workspace.batchSize')">
              <el-input-number
                v-model="trainForm.hyperparameters.batch_size"
                :min="1"
                :max="256"
                :step="8"
              />
            </el-form-item>
            <el-form-item :label="$t('workspace.optimizer')">
              <el-select v-model="trainForm.hyperparameters.optimizer">
                <el-option
                  label="Adam"
                  value="adam"
                />
                <el-option
                  label="SGD"
                  value="sgd"
                />
                <el-option
                  label="RMSprop"
                  value="rmsprop"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="$t('workspace.device')">
              <el-select v-model="trainForm.device">
                <el-option
                  :label="$t('workspace.auto')"
                  value="auto"
                />
                <el-option
                  label="GPU (CUDA)"
                  value="cuda"
                />
                <el-option
                  :label="$t('workspace.cpu')"
                  value="cpu"
                />
              </el-select>
            </el-form-item>
            <el-form-item>
              <el-button
                type="warning"
                :loading="dryRunning"
                @click="handleDryRun"
              >
                {{ $t('workspace.previewPlan') }}
              </el-button>
              <el-button
                type="primary"
                :loading="training"
                :disabled="!trainPlanConfirmed"
                @click="handleTrain"
              >
                {{ $t('workspace.startTraining') }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <div
            v-if="dryRunResult"
            class="train-plan-section"
          >
            <h4>{{ $t('workspace.trainingPlanSummary') }}</h4>

            <el-alert
              :title="$t('workspace.trainingConfidence', { confidence: (dryRunResult.confidence * 100).toFixed(0) })"
              :type="getConfidenceAlertType(dryRunResult.confidence)"
              :closable="false"
              show-icon
              style="margin-bottom: 16px;"
            />

            <el-descriptions
              :column="2"
              border
            >
              <el-descriptions-item :label="$t('workspace.estDuration')">
                {{ dryRunResult.training_plan.estimated_duration_minutes.toFixed(1) }} {{ $t('common.minutes') }}
              </el-descriptions-item>
              <el-descriptions-item :label="$t('workspace.estMemory')">
                {{ dryRunResult.training_plan.estimated_memory_mb.toFixed(1) }} MB
              </el-descriptions-item>
              <el-descriptions-item :label="$t('workspace.datasetSamples')">
                {{ dryRunResult.training_plan.dataset_samples }}
              </el-descriptions-item>
              <el-descriptions-item :label="$t('workspace.trainValSplit')">
                {{ dryRunResult.training_plan.train_val_split.ratio }}
              </el-descriptions-item>
              <el-descriptions-item
                :label="$t('workspace.estGpuMemory')"
                :span="2"
              >
                {{ dryRunResult.training_plan.estimated_gpu_memory_mb ? `${dryRunResult.training_plan.estimated_gpu_memory_mb.toFixed(1)} MB` : 'N/A (CPU)' }}
              </el-descriptions-item>
            </el-descriptions>

            <div
              v-if="dryRunResult.training_plan.potential_risks.length > 0"
              class="risks-section"
            >
              <h5>{{ $t('workspace.potentialRisks') }}</h5>
              <el-alert
                v-for="(risk, idx) in dryRunResult.training_plan.potential_risks"
                :key="`risk-${idx}`"
                :title="risk"
                type="warning"
                :closable="false"
                show-icon
                style="margin-bottom: 8px;"
              />
            </div>

            <div
              v-if="dryRunResult.training_plan.recommendations.length > 0"
              class="recommendations-section"
            >
              <h5>{{ $t('workspace.trainingRecommendations') }}</h5>
              <ul>
                <li
                  v-for="(rec, idx) in dryRunResult.training_plan.recommendations"
                  :key="`rec-${idx}`"
                >
                  {{ rec }}
                </li>
              </ul>
            </div>

            <div class="reasoning-section">
              <h5>{{ $t('workspace.aiReasoningDesc') }}</h5>
              <p>{{ dryRunResult.reasoning }}</p>
            </div>

            <el-divider />

            <div class="confirm-section">
              <el-checkbox v-model="trainPlanConfirmed">
                {{ $t('workspace.confirmTraining') }}
              </el-checkbox>
            </div>
          </div>

          <div
            v-if="trainResult"
            class="train-result-section"
          >
            <h4>{{ $t('workspace.trainingMonitor') }}</h4>

            <div
              v-if="currentJobId"
              class="job-info"
            >
              <el-descriptions
                :column="2"
                border
                size="small"
              >
                <el-descriptions-item :label="$t('workspace.jobId')">
                  <el-tag
                    type="info"
                    size="small"
                    class="job-id-tag"
                  >
                    {{ currentJobId }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item :label="$t('common.status')">
                  <el-tag :type="getTaskStatusTagType(sse.currentStatus || 'queued')">
                    {{ getTaskStatusLabel(sse.currentStatus || 'queued') }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div
              v-if="sse.currentStatus === 'running' || (sse.progress ?? 0) > 0"
              class="progress-section"
            >
              <el-progress
                :percentage="Math.round(sse.progress ?? 0)"
                :stroke-width="20"
                :status="sse.currentStatus === 'completed' ? 'success' : sse.currentStatus === 'failed' ? 'exception' : undefined"
              />
              <div class="progress-info">
                <span
                  v-if="sse.lastProgressData?.message"
                  class="progress-message"
                >
                  {{ sse.lastProgressData.message }}
                </span>
                <span
                  v-if="sse.lastProgressData"
                  class="progress-metrics"
                >
                  Train Loss: {{ ((sse.lastProgressData.train_loss as number) ?? 0).toFixed(6) }} | 
                  Val Loss: {{ ((sse.lastProgressData.val_loss as number) ?? 0).toFixed(6) }}
                </span>
              </div>
            </div>

            <div
              v-if="lossHistory.length > 0"
              class="loss-curves"
            >
              <h5>Loss {{ $t('ruleEditor.result') }}</h5>
              <div class="chart-container">
                <canvas
                  ref="lossChartCanvas"
                  width="800"
                  height="300"
                />
              </div>
            </div>

            <div
              v-if="sse.currentStatus === 'running'"
              class="cancel-section"
            >
              <el-button
                type="danger"
                :loading="cancelling"
                @click="handleCancelTraining"
              >
                {{ $t('workspace.cancelTraining') }}
              </el-button>
            </div>

            <el-alert
              v-if="sse.currentStatus === 'completed'"
              :title="$t('workspace.trainingCompleted')"
              type="success"
              :closable="false"
              show-icon
              style="margin-top: 16px;"
            />

            <el-alert
              v-if="sse.currentStatus === 'failed'"
              :title="$t('workspace.trainingFailed') + ': ' + (sse.error || $t('common.unknownError'))"
              type="error"
              :closable="false"
              show-icon
              style="margin-top: 16px;"
            />

            <el-alert
              v-if="sse.currentStatus === 'cancelled'"
              :title="$t('workspace.trainingCancelled')"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top: 16px;"
            />

            <pre v-if="sse.currentStatus === 'completed' && sse.lastProgressData">{{ JSON.stringify(sse.lastProgressData, null, 2) }}</pre>
          </div>
        </el-tab-pane>

        <el-tab-pane
          :label="$t('workspace.modelsTab')"
          name="models"
        >
          <WorkspaceModelsTab />
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
// TODO(P1-3): 巨型组件拆分 — 本文件 1087 行，应拆分为子组件/composable：
//   - 工作区列表/网格 → WorkspaceGrid.vue
//   - 项目卡片 → ProjectCard.vue
//   - 创建/编辑弹窗 → ProjectDialog.vue
//   - 数据获取逻辑 → useWorkspace.ts
// 拆分时注意保持 props/emits 接口不变，逐模块迁移并验证。
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import http from '@/utils/http'
import WorkspacePredictTab from '@/components/workspace/WorkspacePredictTab.vue'
import WorkspaceModelsTab from '@/components/workspace/WorkspaceModelsTab.vue'
import { useEventSource } from '@/composables/useEventSource'
import { getTaskStatusTagType, getTaskStatusLabel } from '@/utils/statusHelpers'
import { API_CONFIG, buildApiPath } from '@/config/api'

const { t } = useI18n()
const activeTab = ref('predict')
const training = ref(false)
const dryRunning = ref(false)
const trainPlanConfirmed = ref(false)

interface DryRunResult {
  is_dry_run: boolean
  training_plan: {
    estimated_duration_minutes: number
    estimated_memory_mb: number
    estimated_gpu_memory_mb?: number
    dataset_samples: number
    train_val_split: { train: number; validation: number; ratio: string }
    potential_risks: string[]
    recommendations: string[]
  }
  confidence: number
  reasoning: string
}

interface TrainResult {
  job_id: string
  status: string
  message?: string
}

interface ModelInfo {
  name: string
  model_type: string
  version: string
  input_features?: string[]
}

const trainForm = reactive({
  modelName: '',
  dataPath: '',
  hyperparameters: {
    learning_rate: 0.001,
    epochs: 100,
    batch_size: 32,
    optimizer: 'adam',
  },
  device: 'auto',
})

const dryRunResult = ref<DryRunResult | null>(null)
const trainResult = ref<TrainResult | null>(null)
const modelList = ref<ModelInfo[]>([])

const currentJobId = ref<string | null>(null)
const sseJobId = ref('')
const sse = reactive(useEventSource(sseJobId, { autoReconnect: true, maxRetries: 10 }))
const cancelling = ref(false)
const lossChartCanvas = ref<HTMLCanvasElement | null>(null)

function connectToJob(jobId: string) {
  sseJobId.value = jobId
  sse.reset()
  sse.connect()
}

watch(() => sse.events?.length, () => {
  if (lossChartCanvas.value) {
    drawLossChart()
  }
})

function drawLossChart() {
  const canvas = lossChartCanvas.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = canvas.width
  const height = canvas.height
  const padding = 60

  const rootStyle = getComputedStyle(document.documentElement)
  const readColor = (varName: string, fallback: string): string =>
    rootStyle.getPropertyValue(varName).trim() || fallback

  const chartGridColor = readColor('--chart-grid', '#e0dbd4')
  const chartLabelColor = readColor('--chart-axis-label', '#6e6960')
  const chartTrainColor = readColor('--chart-series-train', '#8B7D6B')
  const chartValColor = readColor('--chart-series-val', '#D4A857')

  ctx.clearRect(0, 0, width, height)

  const allLosses = [...lossHistory.value, ...valLossHistory.value]
  if (allLosses.length === 0) return

  const maxLoss = Math.max(...allLosses)
  const minLoss = Math.min(...allLosses)
  const lossRange = maxLoss - minLoss || 1

  const epochs = Math.max(lossHistory.value.length, valLossHistory.value.length)

  ctx.strokeStyle = chartGridColor
  ctx.lineWidth = 1
  for (let i = 0; i <= 5; i++) {
    const y = padding + (i / 5) * (height - 2 * padding)
    ctx.beginPath()
    ctx.moveTo(padding, y)
    ctx.lineTo(width - padding, y)
    ctx.stroke()

    ctx.fillStyle = chartLabelColor
    ctx.font = '12px Arial'
    ctx.textAlign = 'right'
    const lossValue = maxLoss - (i / 5) * lossRange
    ctx.fillText(lossValue.toFixed(6), padding - 5, y + 4)
  }

  ctx.fillStyle = chartLabelColor
  ctx.font = '12px Arial'
  ctx.textAlign = 'center'
  ctx.fillText('Epoch', width / 2, height - 10)

  function drawLine(data: number[], color: string, label: string) {
    if (data.length === 0) return
    if (!ctx) return

    ctx.strokeStyle = color
    ctx.lineWidth = 2
    ctx.beginPath()

    for (let i = 0; i < data.length; i++) {
      const x = padding + (i / (epochs - 1 || 1)) * (width - 2 * padding)
      const y = padding + ((maxLoss - data[i]) / lossRange) * (height - 2 * padding)

      if (i === 0) {
        ctx.moveTo(x, y)
      } else {
        ctx.lineTo(x, y)
      }
    }
    ctx.stroke()

    ctx.fillStyle = color
    ctx.font = 'bold 12px Arial'
    ctx.textAlign = 'left'
    ctx.fillText(label, width - padding + 5, padding)
  }

  drawLine(lossHistory.value, chartTrainColor, 'Train Loss')
  drawLine(valLossHistory.value, chartValColor, 'Val Loss')
}

const lossHistory = computed(() => {
  const losses: number[] = []
  if (!sse.events) return losses
  for (const event of sse.events) {
    if (event.type === 'progress' && event.data.metrics?.train_loss !== undefined) {
      losses.push(event.data.metrics.train_loss as number)
    }
  }
  return losses
})

const valLossHistory = computed(() => {
  const losses: number[] = []
  if (!sse.events) return losses
  for (const event of sse.events) {
    if (event.type === 'progress' && event.data.metrics?.val_loss !== undefined) {
      losses.push(event.data.metrics.val_loss as number)
    }
  }
  return losses
})

async function handleDryRun() {
  if (!trainForm.modelName || !trainForm.dataPath) {
    ElMessage.warning(t('common.inputPlaceholder'))
    return
  }

  dryRunning.value = true
  dryRunResult.value = null
  trainPlanConfirmed.value = false

  try {
    const res = await http.post(buildApiPath(API_CONFIG.LNN, '/train/dry_run'), {
      model_name: trainForm.modelName,
      data_path: trainForm.dataPath,
      hyperparameters: trainForm.hyperparameters,
      device: trainForm.device,
    })

    dryRunResult.value = res.data.data as DryRunResult
    ElMessage.success(t('workspace.trainingPlanSummary'))
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(errorMsg || t('common.unknownError'))
  } finally {
    dryRunning.value = false
  }
}

async function handleTrain() {
  if (!trainPlanConfirmed.value) {
    ElMessage.warning(t('workspace.confirmTraining'))
    return
  }

  training.value = true
  trainResult.value = null

  try {
    const res = await http.post(buildApiPath(API_CONFIG.LNN, '/train'), {
      model_name: trainForm.modelName,
      data_path: trainForm.dataPath,
      hyperparameters: trainForm.hyperparameters,
      device: trainForm.device,
    })

    const jobId = res.data.data?.job_id
    if (!jobId) {
      ElMessage.error(t('workspace.jobId'))
      return
    }

    currentJobId.value = jobId
    connectToJob(jobId)

    trainResult.value = res.data.data
    ElMessage.success(t('workspace.trainingMonitor'))

    await recordAuditLog('lnn_train', dryRunResult.value, 'accept', 'success', trainForm)
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(errorMsg || t('common.unknownError'))
    await recordAuditLog('lnn_train', dryRunResult.value, 'reject', 'failed', trainForm)
  } finally {
    training.value = false
  }
}

async function handleCancelTraining() {
  if (!currentJobId.value) return

  try {
    await ElMessageBox.confirm(t('workspace.confirmCancelTraining'), t('workspace.confirmCancelTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })

    cancelling.value = true
    await http.post(buildApiPath(API_CONFIG.JOBS, `/${currentJobId.value}/cancel`))
    ElMessage.info(t('workspace.trainingCancelled'))
  } catch (e: unknown) {
    if (e !== 'cancel') {
      ElMessage.error(t('common.failed'))
    }
  } finally {
    cancelling.value = false
  }
}

async function recordAuditLog(
  aiModule: string,
  aiRecommendation: Record<string, unknown> | null,
  userDecision: string,
  operationStatus: string,
  finalExecution?: Record<string, unknown>,
) {
  try {
    await http.post(buildApiPath(API_CONFIG.USER_SOVEREIGNTY, '/audit-log/record'), null, {
      params: {
        ai_module: aiModule,
        ai_recommendation: JSON.stringify(aiRecommendation || {}),
        user_decision: userDecision,
        final_execution: JSON.stringify(finalExecution || {}),
        operation_status: operationStatus,
        confidence: dryRunResult.value?.confidence || null,
        reasoning: dryRunResult.value?.reasoning || null,
      },
    })
  } catch (e: unknown) {
    // 审计日志记录失败不应阻塞用户主流程，但需记录便于后续审计追溯
    console.warn('[Workspace] recordAuditLog failed:', e)
  }
}

function getConfidenceAlertType(confidence: number): 'success' | 'warning' | 'error' | 'info' {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.5) return 'warning'
  return 'error'
}

onMounted(async () => {
  try {
    const res = await http.get(buildApiPath(API_CONFIG.LNN, '/models'))
    modelList.value = res.data?.data?.models || []
  } catch {
    modelList.value = []
  }
})
</script>

<style scoped>
.workspace-page {
  max-width: 1200px;
  margin: 0 auto;
}

.header-with-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.result-section {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: 16px;
  border: 1px solid var(--border-light);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.prediction-value {
  margin: 16px 0;
  padding: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  border-left: 4px solid var(--accent-primary);
}

.prediction-value .label {
  font-weight: 600;
  color: var(--text-secondary);
  margin-right: 8px;
}

.prediction-value .value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

.reasoning-section {
  margin: 16px 0;
  padding: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  border-left: 4px solid var(--success);
}

.reasoning-section h5 {
  margin: 0 0 8px 0;
  color: var(--success);
  font-weight: 600;
}

.reasoning-section p {
  margin: 0;
  color: var(--text-secondary);
  line-height: 1.6;
}

.train-plan-section {
  margin-top: 16px;
}

.risks-section {
  margin: 16px 0;
}

.risks-section h5 {
  margin: 0 0 12px 0;
  color: var(--warning);
  font-weight: 600;
}

.recommendations-section {
  margin: 16px 0;
}

.recommendations-section h5 {
  margin: 0 0 12px 0;
  color: var(--success);
  font-weight: 600;
}

.recommendations-section ul {
  margin: 0;
  padding-left: 20px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.confirm-section {
  margin: 20px 0;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  text-align: center;
  border: 1px solid var(--border-light);
}

.confirm-section .el-checkbox {
  font-size: 16px;
  font-weight: 600;
}

.train-result-section {
  margin-top: 16px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.adjusted-result {
  margin-top: 16px;
  padding: 12px;
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-light);
}

.adjusted-result pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  color: var(--text-secondary);
}

pre {
  margin: 8px 0 0 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  color: var(--text-secondary);
}
</style>
