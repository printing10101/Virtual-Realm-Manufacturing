<template>
  <div class="workspace-page">
    <el-card>
      <template #header>
        <div class="header-with-actions">
          <span>工作区 - LNN模型推理</span>
          <el-tag
            type="info"
            size="small"
          >
            用户主权模式
          </el-tag>
        </div>
      </template>
      <el-tabs v-model="activeTab">
        <el-tab-pane
          label="预测推理"
          name="predict"
        >
          <el-form
            :model="predictForm"
            label-width="120px"
          >
            <el-form-item label="模型名称">
              <el-select
                v-model="predictForm.modelName"
                placeholder="选择模型"
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
            <el-form-item label="输入数据">
              <el-input
                v-model="predictForm.inputData"
                type="textarea"
                :rows="4"
                placeholder="输入数值数据，逗号分隔"
              />
            </el-form-item>
            <el-form-item label="返回置信度">
              <el-switch v-model="predictForm.returnConfidence" />
            </el-form-item>
            <el-form-item>
              <el-button
                type="primary"
                :loading="predicting"
                @click="handlePredict"
              >
                开始推理
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <div
            v-if="predictResponse"
            class="result-section"
          >
            <div class="result-header">
              <h4>推理结果</h4>
              <ConfidenceIndicator
                v-if="predictResponse.confidence !== undefined && predictResponse.confidence !== null"
                :confidence="predictResponse.confidence"
              />
            </div>

            <div class="prediction-value">
              <span class="label">预测值:</span>
              <span class="value">{{ formatPredictionValue(predictResponse.value) }}</span>
            </div>

            <div
              v-if="predictResponse.reasoning"
              class="reasoning-section"
            >
              <h5>AI推理过程</h5>
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
                  title="您可以在此调整预测参数"
                  type="info"
                  :closable="false"
                  show-icon
                />
                <el-form
                  :model="modifiedPrediction"
                  label-width="120px"
                  style="margin-top: 16px;"
                >
                  <el-form-item label="预测值">
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
                  <el-form-item label="置信度">
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
                  <h5>调整后结果</h5>
                  <pre>{{ JSON.stringify(modifiedPrediction, null, 2) }}</pre>
                </div>
              </template>
            </AcceptModifyReject>
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="模型训练"
          name="train"
        >
          <el-form
            :model="trainForm"
            label-width="140px"
          >
            <el-form-item label="模型名称">
              <el-input
                v-model="trainForm.modelName"
                placeholder="输入模型名称"
              />
            </el-form-item>
            <el-form-item label="数据路径">
              <el-input
                v-model="trainForm.dataPath"
                placeholder="输入训练数据路径"
              />
            </el-form-item>
            <el-divider content-position="left">
              超参数配置
            </el-divider>
            <el-form-item label="学习率">
              <el-input-number
                v-model="trainForm.hyperparameters.learning_rate"
                :min="0.0001"
                :max="0.1"
                :step="0.001"
                :precision="4"
              />
            </el-form-item>
            <el-form-item label="训练轮数">
              <el-input-number
                v-model="trainForm.hyperparameters.epochs"
                :min="1"
                :max="1000"
                :step="10"
              />
            </el-form-item>
            <el-form-item label="批次大小">
              <el-input-number
                v-model="trainForm.hyperparameters.batch_size"
                :min="1"
                :max="256"
                :step="8"
              />
            </el-form-item>
            <el-form-item label="优化器">
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
            <el-form-item label="设备">
              <el-select v-model="trainForm.device">
                <el-option
                  label="自动"
                  value="auto"
                />
                <el-option
                  label="GPU (CUDA)"
                  value="cuda"
                />
                <el-option
                  label="CPU"
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
                预览训练计划
              </el-button>
              <el-button
                type="primary"
                :loading="training"
                :disabled="!trainPlanConfirmed"
                @click="handleTrain"
              >
                开始训练
              </el-button>
            </el-form-item>
          </el-form>

          <el-divider />

          <div
            v-if="dryRunResult"
            class="train-plan-section"
          >
            <h4>训练计划概要</h4>

            <el-alert
              :title="`训练成功置信度: ${(dryRunResult.confidence * 100).toFixed(0)}%`"
              :type="getConfidenceAlertType(dryRunResult.confidence)"
              :closable="false"
              show-icon
              style="margin-bottom: 16px;"
            />

            <el-descriptions
              :column="2"
              border
            >
              <el-descriptions-item label="预估训练时长">
                {{ dryRunResult.training_plan.estimated_duration_minutes.toFixed(1) }} 分钟
              </el-descriptions-item>
              <el-descriptions-item label="预估内存占用">
                {{ dryRunResult.training_plan.estimated_memory_mb.toFixed(1) }} MB
              </el-descriptions-item>
              <el-descriptions-item label="数据集样本数">
                {{ dryRunResult.training_plan.dataset_samples }}
              </el-descriptions-item>
              <el-descriptions-item label="训练/验证集划分">
                {{ dryRunResult.training_plan.train_val_split.ratio }}
              </el-descriptions-item>
              <el-descriptions-item
                label="预估GPU显存"
                :span="2"
              >
                {{ dryRunResult.training_plan.estimated_gpu_memory_mb ? `${dryRunResult.training_plan.estimated_gpu_memory_mb.toFixed(1)} MB` : 'N/A (CPU模式)' }}
              </el-descriptions-item>
            </el-descriptions>

            <div
              v-if="dryRunResult.training_plan.potential_risks.length > 0"
              class="risks-section"
            >
              <h5>潜在风险</h5>
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
              <h5>训练建议</h5>
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
              <h5>AI推理说明</h5>
              <p>{{ dryRunResult.reasoning }}</p>
            </div>

            <el-divider />

            <div class="confirm-section">
              <el-checkbox v-model="trainPlanConfirmed">
                我已审阅训练计划，确认开始训练
              </el-checkbox>
            </div>
          </div>

          <div
            v-if="trainResult"
            class="train-result-section"
          >
            <h4>训练监控</h4>

            <div
              v-if="currentJobId"
              class="job-info"
            >
              <el-descriptions
                :column="2"
                border
                size="small"
              >
                <el-descriptions-item label="任务ID">
                  <el-tag
                    type="info"
                    size="small"
                    class="job-id-tag"
                  >
                    {{ currentJobId }}
                  </el-tag>
                </el-descriptions-item>
                <el-descriptions-item label="状态">
                  <el-tag :type="getTaskStatusTagType(sse.currentStatus)">
                    {{ getTaskStatusLabel(sse.currentStatus) }}
                  </el-tag>
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <div
              v-if="sse.currentStatus === 'running' || sse.progress > 0"
              class="progress-section"
            >
              <el-progress
                :percentage="Math.round(sse.progress)"
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
                  Train Loss: {{ sse.lastProgressData.train_loss?.toFixed(6) }} | 
                  Val Loss: {{ sse.lastProgressData.val_loss?.toFixed(6) }}
                </span>
              </div>
            </div>

            <div
              v-if="lossHistory.length > 0"
              class="loss-curves"
            >
              <h5>Loss曲线</h5>
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
                取消训练
              </el-button>
            </div>

            <el-alert
              v-if="sse.currentStatus === 'completed'"
              title="训练已完成"
              type="success"
              :closable="false"
              show-icon
              style="margin-top: 16px;"
            />

            <el-alert
              v-if="sse.currentStatus === 'failed'"
              :title="`训练失败: ${sse.error || '未知错误'}`"
              type="error"
              :closable="false"
              show-icon
              style="margin-top: 16px;"
            />

            <el-alert
              v-if="sse.currentStatus === 'cancelled'"
              title="训练已取消"
              type="warning"
              :closable="false"
              show-icon
              style="margin-top: 16px;"
            />

            <pre v-if="sse.currentStatus === 'completed' && sse.lastProgressData">{{ JSON.stringify(sse.lastProgressData, null, 2) }}</pre>
          </div>
        </el-tab-pane>

        <el-tab-pane
          label="模型列表"
          name="models"
        >
          <el-table
            :data="modelList"
            style="width: 100%"
          >
            <el-table-column
              prop="name"
              label="名称"
            />
            <el-table-column
              prop="model_type"
              label="类型"
            />
            <el-table-column
              prop="version"
              label="版本"
            />
            <el-table-column
              prop="input_features"
              label="输入特征"
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
import axios from 'axios'
import { setLocale, type SupportedLocale } from '@/i18n'
import ConfidenceIndicator from '@/components/ConfidenceIndicator.vue'
import AcceptModifyReject from '@/components/AcceptModifyReject.vue'
import { useSettingsStore } from '@/stores/settings'
import { useEventSource } from '@/composables/useEventSource'
import { getTaskStatusTagType, getTaskStatusLabel } from '@/utils/statusHelpers'

const settingsStore = useSettingsStore()
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
const sse = useEventSource(sseJobId.value, { autoReconnect: true, maxRetries: 10 })
const cancelling = ref(false)
const lossChartCanvas = ref<HTMLCanvasElement | null>(null)

function connectToJob(jobId: string) {
  sseJobId.value = jobId
  sse.reset()
  sse.connect()
}

watch(sse.events, () => {
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

  drawLine(lossHistory.value, '#409eff', 'Train Loss')
  drawLine(valLossHistory.value, '#e6a23c', 'Val Loss')
}

const lossHistory = computed(() => {
  const losses: number[] = []
  for (const event of sse.events.value) {
    if (event.type === 'progress' && event.data.metrics?.train_loss !== undefined) {
      losses.push(event.data.metrics.train_loss)
    }
  }
  return losses
})

const valLossHistory = computed(() => {
  const losses: number[] = []
  for (const event of sse.events.value) {
    if (event.type === 'progress' && event.data.metrics?.val_loss !== undefined) {
      losses.push(event.data.metrics.val_loss)
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
      ElMessage.error('请输入有效的数值数据')
      predicting.value = false
      return
    }

    const res = await axios.post('/api/v1/lnn/predict', {
      model_name: predictForm.modelName,
      input_data: inputArray,
      return_confidence: predictForm.returnConfidence,
    })

    predictResponse.value = res.data.data as PredictResponse
    ElMessage.success('推理完成')

    await recordAuditLog('lnn_predict', predictResponse.value, 'auto_executed', 'success')
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || '推理请求失败'
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
  ElMessage.success('已接受AI预测结果')
}

async function handleModifyPrediction(modifiedParams: Record<string, any>) {
  modifiedPrediction.value = { ...modifiedParams }
  showAdjustedResult.value = true
  await recordAuditLog('lnn_predict', predictResponse.value, 'modify', 'success', modifiedParams)
  ElMessage.info('已应用您的修改')
}

async function handleRejectPrediction(recommendation: Record<string, any>) {
  await recordAuditLog('lnn_predict', predictResponse.value, 'reject', 'cancelled', recommendation)
  predictResponse.value = null
}

async function handleDryRun() {
  if (!trainForm.modelName || !trainForm.dataPath) {
    ElMessage.warning('请填写模型名称和数据路径')
    return
  }

  dryRunning.value = true
  dryRunResult.value = null
  trainPlanConfirmed.value = false

  try {
    const res = await axios.post('/api/v1/lnn/train/dry_run', {
      model_name: trainForm.modelName,
      data_path: trainForm.dataPath,
      hyperparameters: trainForm.hyperparameters,
      device: trainForm.device,
    })

    dryRunResult.value = res.data.data as DryRunResult
    ElMessage.success('训练计划已生成，请审阅')
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || '训练计划生成失败'
    ElMessage.error(errorMsg)
  } finally {
    dryRunning.value = false
  }
}

async function handleTrain() {
  if (!trainPlanConfirmed.value) {
    ElMessage.warning('请先审阅并确认训练计划')
    return
  }

  training.value = true
  trainResult.value = null

  try {
    const res = await axios.post('/api/v1/lnn/train', {
      model_name: trainForm.modelName,
      data_path: trainForm.dataPath,
      hyperparameters: trainForm.hyperparameters,
      device: trainForm.device,
    })

    const jobId = res.data.data?.job_id
    if (!jobId) {
      ElMessage.error('未获取到任务ID')
      return
    }

    currentJobId.value = jobId
    connectToJob(jobId)

    trainResult.value = res.data.data
    ElMessage.success('训练任务已启动，正在监控进度...')

    await recordAuditLog('lnn_train', dryRunResult.value, 'accept', 'success', trainForm)
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || '训练启动失败'
    ElMessage.error(errorMsg)
    await recordAuditLog('lnn_train', dryRunResult.value, 'reject', 'failed', trainForm)
  } finally {
    training.value = false
  }
}

async function handleCancelTraining() {
  if (!currentJobId.value) return

  try {
    await ElMessageBox.confirm('确定要取消当前训练任务吗？', '确认取消', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    cancelling.value = true
    await axios.post(`/api/v1/jobs/${currentJobId.value}/cancel`)
    ElMessage.info('训练任务已取消')
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('取消失败')
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
    await axios.post('/api/v1/user-sovereignty/audit-log/record', null, {
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
    const res = await axios.get('/api/v1/lnn/models')
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
  background: #f5f7fa;
  border-radius: 4px;
  padding: 16px;
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
  background: #fff;
  border-radius: 4px;
  border-left: 4px solid #409eff;
}

.prediction-value .label {
  font-weight: 600;
  color: #606266;
  margin-right: 8px;
}

.prediction-value .value {
  font-size: 18px;
  font-weight: 700;
  color: #303133;
}

.reasoning-section {
  margin: 16px 0;
  padding: 12px;
  background: #fff;
  border-radius: 4px;
  border-left: 4px solid #67c23a;
}

.reasoning-section h5 {
  margin: 0 0 8px 0;
  color: #67c23a;
}

.reasoning-section p {
  margin: 0;
  color: #606266;
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
  color: #e6a23c;
}

.recommendations-section {
  margin: 16px 0;
}

.recommendations-section h5 {
  margin: 0 0 12px 0;
  color: #67c23a;
}

.recommendations-section ul {
  margin: 0;
  padding-left: 20px;
  color: #606266;
  line-height: 1.8;
}

.confirm-section {
  margin: 20px 0;
  padding: 16px;
  background: #ecf5ff;
  border-radius: 4px;
  text-align: center;
}

.confirm-section .el-checkbox {
  font-size: 16px;
  font-weight: 600;
}

.train-result-section {
  margin-top: 16px;
  padding: 16px;
  background: #f5f7fa;
  border-radius: 4px;
}

.adjusted-result {
  margin-top: 16px;
  padding: 12px;
  background: #fff;
  border-radius: 4px;
}

.adjusted-result pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}

pre {
  margin: 8px 0 0 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}
</style>
