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
          <el-form
            :model="predictForm"
            label-width="120px"
          >
            <el-form-item :label="$t('workspace.modelName')">
              <el-select
                v-model="predictForm.modelName"
                :placeholder="$t('workspace.selectModel')"
              >
                <el-option
                  label="CFC-Fast"
                  value="CFC-Fast"
                />
                <el-option
                  label="LTC-TimeSeries"
                  value="LTC-TimeSeries"
                />
                <el-option
                  label="Hybrid-Multimodal"
                  value="Hybrid-Multimodal"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="$t('workspace.inputData')">
              <el-input
                v-model="predictForm.inputData"
                type="textarea"
                :rows="4"
                :placeholder="$t('workspace.inputDataPlaceholder')"
              />
            </el-form-item>
            <el-form-item :label="$t('workspace.returnConfidence')">
              <el-switch v-model="predictForm.returnConfidence" />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="predicting"
                @click="handlePredict"
              >
                {{ $t('workspace.startInference') }}
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <div
            v-if="predictResponse"
            class="result-section"
          >
            <div class="result-header">
              <h4>{{ $t('workspace.inferenceResult') }}</h4>
              <ConfidenceIndicator
                v-if="predictResponse.confidence !== undefined && predictResponse.confidence !== null"
                :confidence="predictResponse.confidence"
              />
            </div>

            <div class="prediction-value">
              <span class="label">{{ $t('workspace.predictedValue') }}</span>
              <span class="value">{{ formatPredictionValue(predictResponse.value) }}</span>
            </div>

            <div
              v-if="predictResponse.reasoning"
              class="reasoning-section"
            >
              <h5>{{ $t('workspace.aiReasoning') }}</h5>
              <p>{{ predictResponse.reasoning }}</p>
            </div>

            <AcceptModifyReject
              :ai-recommendation="getAIRecommendation()"
              :confidence="predictResponse.confidence"
              :reasoning="predictResponse.reasoning"
              :alternatives="predictResponse.alternatives"
              :allow-modify="true"
              @accept="handleAcceptPrediction"
              @modify="handleModifyPrediction"
              @reject="handleRejectPrediction"
            >
              <!-- eslint-disable-next-line vue/no-unused-vars -->
              <template #modify-form="{ recommendation }">
                <el-alert
                  :title="$t('workspace.adjustPrediction')"
                  type="info"
                  :closable="false"
                  show-icon
                />
                <el-form
                  :model="modifiedPrediction"
                  label-width="120px"
                  style="margin-top: 16px;"
                >
                  <el-form-item :label="$t('workspace.predictedValueField')">
                    <el-input-number
                      v-if="typeof modifiedPrediction.value === 'number'"
                      v-model="modifiedPrediction.value"
                      :step="0.01"
                      :precision="4"
                    />
                    <el-input
                      v-else
                      v-model="modifiedPrediction.value"
                    />
                  </el-form-item>
                  <el-form-item :label="$t('workspace.confidenceField')">
                    <el-slider
                      v-model="modifiedPrediction.confidence"
                      :min="0"
                      :max="1"
                      :step="0.01"
                      :format-tooltip="(val: number) => `${(val * 100).toFixed(0)}%`"
                    />
                  </el-form-item>
                </el-form>

                <div
                  v-if="showAdjustedResult"
                  class="adjusted-result"
                >
                  <h5>{{ $t('workspace.adjustedResult') }}</h5>
                  <pre>{{ JSON.stringify(modifiedPrediction, null, 2) }}</pre>
                </div>
              </template>
            </AcceptModifyReject>
          </div>
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
                :key="idx"
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
                  :key="idx"
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
          <el-table
            :data="modelList"
            style="width: 100%"
          >
            <el-table-column
              prop="name"
              :label="$t('workspace.modelListName')"
            />
            <el-table-column
              prop="model_type"
              :label="$t('workspace.modelListType')"
            />
            <el-table-column
              prop="version"
              :label="$t('workspace.modelListVersion')"
            />
            <el-table-column
              prop="input_features"
              :label="$t('workspace.modelListFeatures')"
            >
              <template #default="{ row }">
                {{ row.input_features?.join(', ') }}
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import http from '@/utils/http'
import { setLocale, type SupportedLocale } from '@/i18n'
import ConfidenceIndicator from '@/components/ConfidenceIndicator.vue'
import AcceptModifyReject from '@/components/AcceptModifyReject.vue'
import { useSettingsStore } from '@/stores/settings'
import { useEventSource } from '@/composables/useEventSource'
import { getTaskStatusTagType, getTaskStatusLabel } from '@/utils/statusHelpers'

const settingsStore = useSettingsStore()
const { t } = useI18n()
const activeTab = ref('predict')
const predicting = ref(false)
const training = ref(false)
const dryRunning = ref(false)
const trainPlanConfirmed = ref(false)

interface PredictResponse {
  value: number | number[]
  confidence?: number
  reasoning?: string
  inference_time: number
  alternatives?: Array<{
    plan_id: string
    parameters: Record<string, any>
    expected_outcome: string
    confidence: number
    reasoning: string
  }>
}

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

const predictForm = reactive({
  modelName: 'CFC-Fast',
  inputData: '',
  returnConfidence: true,
})

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

const predictResponse = ref<PredictResponse | null>(null)
const dryRunResult = ref<DryRunResult | null>(null)
const trainResult = ref<any>(null)
const modelList = ref<any[]>([])
const modifiedPrediction = ref<Record<string, any>>({})
const showAdjustedResult = ref(false)

const currentJobId = ref<string | null>(null)
const sseJobId = ref('')
const sse = reactive(useEventSource(sseJobId.value, { autoReconnect: true, maxRetries: 10 }))
const cancelling = ref(false)
const lossChartCanvas = ref<HTMLCanvasElement | null>(null)

function connectToJob(jobId: string) {
  sseJobId.value = jobId
  sse.reset()
  sse.connect()
}

watch(() => sse.events, () => {
  if (lossChartCanvas.value) {
    drawLossChart()
  }
}, { deep: true })

function drawLossChart() {
  const canvas = lossChartCanvas.value
  if (!canvas) return

  const ctx = canvas.getContext('2d')
  if (!ctx) return

  const width = canvas.width
  const height = canvas.height
  const padding = 60

  ctx.clearRect(0, 0, width, height)

  const allLosses = [...lossHistory.value, ...valLossHistory.value]
  if (allLosses.length === 0) return

  const maxLoss = Math.max(...allLosses)
  const minLoss = Math.min(...allLosses)
  const lossRange = maxLoss - minLoss || 1

  const epochs = Math.max(lossHistory.value.length, valLossHistory.value.length)

  ctx.strokeStyle = '#e0e0e0'
  ctx.lineWidth = 1
  for (let i = 0; i <= 5; i++) {
    const y = padding + (i / 5) * (height - 2 * padding)
    ctx.beginPath()
    ctx.moveTo(padding, y)
    ctx.lineTo(width - padding, y)
    ctx.stroke()

    ctx.fillStyle = '#606266'
    ctx.font = '12px Arial'
    ctx.textAlign = 'right'
    const lossValue = maxLoss - (i / 5) * lossRange
    ctx.fillText(lossValue.toFixed(6), padding - 5, y + 4)
  }

  ctx.fillStyle = '#606266'
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

  drawLine(lossHistory.value, 'var(--accent-primary)', 'Train Loss')
  drawLine(valLossHistory.value, 'var(--warning)', 'Val Loss')
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

async function handlePredict() {
  predicting.value = true
  predictResponse.value = null
  try {
    const inputArray = predictForm.inputData
      .split(',')
      .map(val => val.trim())
      .filter(val => val !== '')
      .map(Number)
      .filter(num => !isNaN(num))

    if (inputArray.length === 0) {
      ElMessage.error(t('common.inputPlaceholder'))
      predicting.value = false
      return
    }

    const res = await http.post('/api/v1/lnn/predict', {
      model_name: predictForm.modelName,
      input_data: inputArray,
      return_confidence: predictForm.returnConfidence,
    })

    predictResponse.value = res.data.data as PredictResponse
    ElMessage.success(t('workspace.inferenceResult'))

    await recordAuditLog('lnn_predict', predictResponse.value, 'auto_executed', 'success')
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || t('common.unknownError')
    ElMessage.error(errorMsg)
  } finally {
    predicting.value = false
  }
}

function getAIRecommendation(): Record<string, any> {
  if (!predictResponse.value) return {}
  return {
    value: predictResponse.value.value,
    confidence: predictResponse.value.confidence,
    inference_time: predictResponse.value.inference_time,
  }
}

function formatPredictionValue(value: number | number[]): string {
  if (Array.isArray(value)) {
    return `[${value.map(v => v.toFixed(4)).join(', ')}]`
  }
  return value.toFixed(4)
}

async function handleAcceptPrediction(recommendation: Record<string, any>) {
  await recordAuditLog('lnn_predict', predictResponse.value, 'accept', 'success', recommendation)
  ElMessage.success(t('settings.accept'))
}

async function handleModifyPrediction(modifiedParams: Record<string, any>) {
  modifiedPrediction.value = { ...modifiedParams }
  showAdjustedResult.value = true
  await recordAuditLog('lnn_predict', predictResponse.value, 'modify', 'success', modifiedParams)
  ElMessage.info(t('settings.modify'))
}

async function handleRejectPrediction(recommendation: Record<string, any>) {
  await recordAuditLog('lnn_predict', predictResponse.value, 'reject', 'cancelled', recommendation)
  predictResponse.value = null
}

async function handleDryRun() {
  if (!trainForm.modelName || !trainForm.dataPath) {
    ElMessage.warning(t('common.inputPlaceholder'))
    return
  }

  dryRunning.value = true
  dryRunResult.value = null
  trainPlanConfirmed.value = false

  try {
    const res = await http.post('/api/v1/lnn/train/dry_run', {
      model_name: trainForm.modelName,
      data_path: trainForm.dataPath,
      hyperparameters: trainForm.hyperparameters,
      device: trainForm.device,
    })

    dryRunResult.value = res.data.data as DryRunResult
    ElMessage.success(t('workspace.trainingPlanSummary'))
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || t('common.unknownError')
    ElMessage.error(errorMsg)
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
    const res = await http.post('/api/v1/lnn/train', {
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
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || t('common.unknownError')
    ElMessage.error(errorMsg)
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
    await http.post(`/api/v1/jobs/${currentJobId.value}/cancel`)
    ElMessage.info(t('workspace.trainingCancelled'))
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(t('common.failed'))
    }
  } finally {
    cancelling.value = false
  }
}

async function recordAuditLog(
  aiModule: string,
  aiRecommendation: any,
  userDecision: string,
  operationStatus: string,
  finalExecution?: any,
) {
  try {
    await http.post('/api/v1/user-sovereignty/audit-log/record', null, {
      params: {
        ai_module: aiModule,
        ai_recommendation: JSON.stringify(aiRecommendation || {}),
        user_decision: userDecision,
        final_execution: JSON.stringify(finalExecution || {}),
        operation_status: operationStatus,
        confidence: predictResponse.value?.confidence || dryRunResult.value?.confidence || null,
        reasoning: predictResponse.value?.reasoning || dryRunResult.value?.reasoning || null,
      },
    })
  } catch (e) {
    console.warn('Failed to record audit log:', e)
  }
}

function getConfidenceAlertType(confidence: number): 'success' | 'warning' | 'error' | 'info' {
  if (confidence >= 0.8) return 'success'
  if (confidence >= 0.5) return 'warning'
  return 'error'
}

onMounted(async () => {
  try {
    const res = await http.get('/api/v1/lnn/models')
    modelList.value = res.data?.data?.models || []
  } catch (e) {
    console.error('Failed to load model list:', e)
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
