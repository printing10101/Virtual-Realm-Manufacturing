<template>
  <div class="validation-view">
    <h1 class="page-title">
      <el-icon><DataAnalysis /></el-icon>
      仿真验证
    </h1>

    <el-row :gutter="20">
      <el-col :span="8">
        <el-card
          shadow="hover"
          class="left-panel"
        >
          <template #header>
            <div class="card-header">
              <span>
                <el-icon><FolderOpened /></el-icon>
                数据集管理
              </span>
            </div>
          </template>

          <div class="dataset-list">
            <div
              v-for="ds in datasets"
              :key="ds.name"
              class="dataset-item"
              :class="{ active: selectedDatasets.includes(ds.name) }"
              @click="toggleDataset(ds.name)"
            >
              <div class="dataset-info">
                <div class="dataset-name">
                  {{ ds.name }}
                </div>
                <div class="dataset-meta">
                  <el-tag size="small">
                    {{ ds.samples }} 样本
                  </el-tag>
                  <el-tag
                    size="small"
                    type="info"
                  >
                    {{ ds.source }}
                  </el-tag>
                </div>
              </div>
            </div>
          </div>

          <el-divider />

          <div class="import-section">
            <el-upload
              action="/api/v1/validation/datasets/import"
              :data="uploadData"
              :on-success="handleImportSuccess"
              :on-error="handleImportError"
              :before-upload="beforeUpload"
              accept=".csv"
              :show-file-list="false"
            >
              <el-button
                type="primary"
                :icon="Upload"
              >
                导入自定义数据集
              </el-button>
            </el-upload>
            <el-input
              v-model="importName"
              placeholder="数据集名称"
              size="small"
              class="import-name-input"
            />
          </div>
        </el-card>

        <el-card
          shadow="hover"
          class="config-panel"
          style="margin-top: 20px"
        >
          <template #header>
            <div class="card-header">
              <span>
                <el-icon><Setting /></el-icon>
                验证配置
              </span>
            </div>
          </template>

          <el-form
            label-position="top"
            size="small"
          >
            <el-form-item label="验证类型">
              <el-select
                v-model="validationType"
                style="width: 100%"
              >
                <el-option
                  label="在线公式验证"
                  value="online"
                />
                <el-option
                  label="离线数据集验证"
                  value="offline"
                />
                <el-option
                  label="综合验证"
                  value="comprehensive"
                />
              </el-select>
            </el-form-item>

            <el-form-item label="切削速度 (m/min)">
              <el-input-number
                v-model="params.v_c"
                :min="10"
                :max="1000"
                :step="10"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="进给量 (mm/rev)">
              <el-input-number
                v-model="params.f"
                :min="0.01"
                :max="5"
                :step="0.05"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="切削深度 (mm)">
              <el-input-number
                v-model="params.a_p"
                :min="0.1"
                :max="50"
                :step="0.5"
                style="width: 100%"
              />
            </el-form-item>

            <el-form-item label="材料">
              <el-select
                v-model="params.material"
                style="width: 100%"
              >
                <el-option
                  label="45钢"
                  value="45钢"
                />
                <el-option
                  label="不锈钢304"
                  value="不锈钢304"
                />
                <el-option
                  label="铝合金6061"
                  value="铝合金6061"
                />
                <el-option
                  label="钛合金TC4"
                  value="钛合金TC4"
                />
              </el-select>
            </el-form-item>

            <el-divider />

            <el-form-item label="误差阈值配置">
              <el-row :gutter="10">
                <el-col :span="8">
                  <el-input-number
                    v-model="thresholds.cutting_force"
                    :min="1"
                    :max="50"
                    :step="1"
                    size="small"
                    style="width: 100%"
                  />
                  <div class="threshold-label">
                    切削力 %
                  </div>
                </el-col>
                <el-col :span="8">
                  <el-input-number
                    v-model="thresholds.tool_life"
                    :min="1"
                    :max="50"
                    :step="1"
                    size="small"
                    style="width: 100%"
                  />
                  <div class="threshold-label">
                    刀具寿命 %
                  </div>
                </el-col>
                <el-col :span="8">
                  <el-input-number
                    v-model="thresholds.surface_roughness"
                    :min="1"
                    :max="50"
                    :step="1"
                    size="small"
                    style="width: 100%"
                  />
                  <div class="threshold-label">
                    粗糙度 %
                  </div>
                </el-col>
              </el-row>
            </el-form-item>

            <el-button
              type="success"
              :icon="VideoPlay"
              style="width: 100%; margin-top: 10px"
              :loading="validating"
              @click="runValidation"
            >
              开始验证
            </el-button>
          </el-form>
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card
          shadow="hover"
          class="results-panel"
        >
          <template #header>
            <div class="card-header">
              <span>
                <el-icon><TrendCharts /></el-icon>
                验证结果
              </span>
              <el-button
                v-if="validationResult"
                type="primary"
                :icon="Download"
                @click="exportReport"
              >
                导出报告
              </el-button>
            </div>
          </template>

          <el-empty
            v-if="!validationResult"
            description="运行验证后显示结果"
          />

          <template v-if="validationResult">
            <div class="metrics-cards">
              <el-card
                shadow="hover"
                class="metric-card"
                :class="metricStatus('mape')"
              >
                <div class="metric-label">
                  MAPE
                </div>
                <div class="metric-value">
                  {{ validationResult.overall_mape?.toFixed(2) || 0 }}%
                </div>
                <div class="metric-desc">
                  平均绝对百分比误差
                </div>
              </el-card>

              <el-card
                shadow="hover"
                class="metric-card"
                :class="metricStatus('rmse')"
              >
                <div class="metric-label">
                  RMSE
                </div>
                <div class="metric-value">
                  {{ validationResult.overall_rmse?.toFixed(4) || 0 }}
                </div>
                <div class="metric-desc">
                  均方根误差
                </div>
              </el-card>

              <el-card
                shadow="hover"
                class="metric-card"
                :class="metricStatus('r2')"
              >
                <div class="metric-label">
                  R²
                </div>
                <div class="metric-value">
                  {{ validationResult.overall_r_squared?.toFixed(4) || 0 }}
                </div>
                <div class="metric-desc">
                  决定系数
                </div>
              </el-card>

              <el-card
                shadow="hover"
                class="metric-card"
              >
                <div class="metric-label">
                  样本统计
                </div>
                <div class="metric-value">
                  {{ validationResult.total_samples || 0 }}
                </div>
                <div class="metric-desc">
                  <span style="color: #67c23a">通过: {{ validationResult.pass_count || 0 }}</span>
                  /
                  <span style="color: #f56c6c">失败: {{ validationResult.fail_count || 0 }}</span>
                </div>
              </el-card>
            </div>

            <el-row
              :gutter="20"
              style="margin-top: 20px"
            >
              <el-col :span="12">
                <div
                  ref="scatterChart"
                  class="chart-container"
                />
              </el-col>
              <el-col :span="12">
                <div
                  ref="histogramChart"
                  class="chart-container"
                />
              </el-col>
            </el-row>

            <el-table
              v-if="validationResult.details && validationResult.details.length > 0"
              :data="validationResult.details"
              style="width: 100%; margin-top: 20px"
              border
              stripe
              size="small"
            >
              <el-table-column
                prop="metric_name"
                label="指标"
                width="120"
              />
              <el-table-column
                prop="predicted_value"
                label="预测值"
                width="100"
              />
              <el-table-column
                prop="actual_value"
                label="实际值"
                width="100"
              />
              <el-table-column
                prop="error"
                label="误差"
                width="100"
                :formatter="formatError"
              />
              <el-table-column
                prop="error_percent"
                label="误差%"
                width="100"
                :formatter="formatPercent"
              />
              <el-table-column
                prop="status"
                label="状态"
                width="80"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="row.status === 'PASS' ? 'success' : 'danger'"
                    size="small"
                  >
                    {{ row.status }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="threshold"
                label="阈值"
                width="100"
              />
            </el-table>
          </template>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onUnmounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { DataAnalysis, FolderOpened, Setting, Upload, VideoPlay, Download, TrendCharts } from '@element-plus/icons-vue'
import * as echarts from 'echarts'
import axios from 'axios'

interface Dataset {
  name: string
  samples: number
  source: string
  description: string
}

interface ValidationParam {
  v_c: number
  f: number
  a_p: number
  material: string
}

interface ValidationResult {
  overall_mape: number
  overall_rmse: number
  overall_r_squared: number
  total_samples: number
  pass_count: number
  fail_count: number
  details?: Array<{
    metric_name: string
    predicted_value: number
    actual_value: number
    error: number
    error_percent: number
    status: string
    threshold: number
  }>
}

const datasets = ref<Dataset[]>([])
const selectedDatasets = ref<string[]>([])
const validationType = ref('comprehensive')
const validating = ref(false)
const validationResult = ref<ValidationResult | null>(null)
const importName = ref('')

const params = reactive<ValidationParam>({
  v_c: 150,
  f: 0.2,
  a_p: 2.0,
  material: '45钢'
})

const thresholds = reactive({
  cutting_force: 15,
  tool_life: 20,
  surface_roughness: 25
})

const scatterChart = ref<HTMLDivElement>()
const histogramChart = ref<HTMLDivElement>()

let scatterInstance: echarts.ECharts | null = null
let histogramInstance: echarts.ECharts | null = null
let pollTimer: ReturnType<typeof setTimeout> | null = null
let resizeHandler: (() => void) | null = null

onMounted(async () => {
  await loadDatasets()
  resizeHandler = () => {
    scatterInstance?.resize()
    histogramInstance?.resize()
  }
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (pollTimer) {
    clearTimeout(pollTimer)
    pollTimer = null
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  if (scatterInstance) {
    scatterInstance.dispose()
    scatterInstance = null
  }
  if (histogramInstance) {
    histogramInstance.dispose()
    histogramInstance = null
  }
})

async function loadDatasets() {
  try {
    const res = await axios.get('/api/v1/validation/datasets')
    if (res.data.success) {
      datasets.value = res.data.data.datasets
      selectedDatasets.value = datasets.value.map(d => d.name)
    }
  } catch (err) {
    console.error('Failed to load datasets:', err)
  }
}

function toggleDataset(name: string) {
  const idx = selectedDatasets.value.indexOf(name)
  if (idx === -1) {
    selectedDatasets.value.push(name)
  } else {
    selectedDatasets.value.splice(idx, 1)
  }
}

const uploadData = reactive({ name: '' })

function beforeUpload(file: File) {
  if (!importName.value) {
    ElMessage.error('请先输入数据集名称')
    return false
  }
  uploadData.name = importName.value
  return true
}

function handleImportSuccess(res: any) {
  if (res.success) {
    ElMessage.success(`数据集导入成功: ${res.data.name} (${res.data.samples} 样本)`)
    importName.value = ''
    loadDatasets()
  } else {
    ElMessage.error(res.message || '导入失败')
  }
}

function handleImportError() {
  ElMessage.error('数据集导入失败')
}

async function runValidation() {
  if (selectedDatasets.value.length === 0) {
    ElMessage.warning('请至少选择一个数据集')
    return
  }

  validating.value = true
  validationResult.value = null

  try {
    const taskId = `validation_${Date.now()}`

    await axios.post('/api/v1/tasks', {
      task_id: taskId,
      task_type: 'validation',
      params: {}
    })

    await axios.post('/api/v1/validation/run', {
      task_id: taskId,
      validation_type: validationType.value,
      datasets: selectedDatasets.value,
      params: { ...params },
      thresholds: { ...thresholds }
    })

    await pollResults(taskId)
  } catch (err: any) {
    ElMessage.error(err.response?.data?.message || '验证失败')
  } finally {
    validating.value = false
  }
}

async function pollResults(taskId: string) {
  const maxAttempts = 60
  let attempts = 0

  const poll = async () => {
    attempts++
    if (attempts > maxAttempts) {
      ElMessage.warning('验证超时')
      return
    }

    try {
      const res = await axios.get(`/api/v1/validation/results/${taskId}`)
      if (res.data.success) {
        validationResult.value = res.data.data
        await nextTick()
        renderCharts()
        ElMessage.success('验证完成')
      } else {
        pollTimer = setTimeout(poll, 1000)
      }
    } catch {
      pollTimer = setTimeout(poll, 1000)
    }
  }

  pollTimer = setTimeout(poll, 1000)
}

function renderCharts() {
  if (!validationResult.value?.details) return

  const details = validationResult.value.details

  const predicted = details.map(d => d.predicted_value)
  const actual = details.map(d => d.actual_value)

  if (scatterInstance) {
    scatterInstance.dispose()
  }

  if (scatterChart.value) {
    scatterInstance = echarts.init(scatterChart.value)

    const maxValue = Math.max(...predicted, ...actual)

    scatterInstance.setOption({
      title: { text: '预测值 vs 实际值', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: {
        trigger: 'item',
        formatter: (p: any) => `预测: ${p.data[0].toFixed(2)}<br/>实际: ${p.data[1].toFixed(2)}`
      },
      xAxis: { name: '预测值', type: 'value' },
      yAxis: { name: '实际值', type: 'value' },
      series: [
        {
          type: 'scatter',
          data: predicted.map((p, i) => [p, actual[i]]),
          itemStyle: { color: '#409eff' },
          symbolSize: 8
        },
        {
          type: 'line',
          data: [[0, 0], [maxValue, maxValue]],
          lineStyle: { type: 'dashed', color: '#f56c6c' },
          symbol: 'none'
        }
      ]
    })
  }

  if (histogramInstance) {
    histogramInstance.dispose()
  }

  if (histogramChart.value) {
    histogramInstance = echarts.init(histogramChart.value)

    const errors = details.map(d => Math.abs(d.error_percent))
    const bins = [0, 5, 10, 15, 20, 25, 30, 50, 100]
    const counts = new Array(bins.length - 1).fill(0)

    errors.forEach(e => {
      for (let i = 0; i < bins.length - 1; i++) {
        if (e >= bins[i] && e < bins[i + 1]) {
          counts[i]++
          break
        }
      }
    })

    histogramInstance.setOption({
      title: { text: '误差分布', left: 'center', textStyle: { fontSize: 14 } },
      tooltip: { trigger: 'axis' },
      xAxis: { type: 'category', data: bins.slice(0, -1).map((b, i) => `${b}-${bins[i+1]}%`) },
      yAxis: { type: 'value', name: '频次' },
      series: [{
        type: 'bar',
        data: counts,
        itemStyle: { color: '#67c23a' }
      }]
    })
  }
}

function metricStatus(metric: string) {
  if (!validationResult.value) return ''

  if (metric === 'mape') {
    const v = validationResult.value.overall_mape
    if (v < 10) return 'good'
    if (v < 20) return 'warning'
    return 'danger'
  }

  if (metric === 'r2') {
    const v = validationResult.value.overall_r_squared
    if (v > 0.9) return 'good'
    if (v > 0.7) return 'warning'
    return 'danger'
  }

  return ''
}

function formatError(row: any) {
  return row.error?.toFixed(4)
}

function formatPercent(row: any) {
  return row.error_percent?.toFixed(2) + '%'
}

async function exportReport() {
  const taskId = `validation_${Date.now()}`
  window.open(`/api/v1/validation/results/${taskId}/export`, '_blank')
  ElMessage.success('报告导出中...')
}
</script>

<style scoped lang="scss">
.validation-view {
  padding: 20px;

  .page-title {
    font-size: 24px;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    gap: 10px;
  }

  .left-panel {
    .dataset-list {
      max-height: 300px;
      overflow-y: auto;

      .dataset-item {
        padding: 10px;
        border-radius: 4px;
        cursor: pointer;
        margin-bottom: 5px;
        transition: all 0.2s;

        &:hover {
          background: #f5f7fa;
        }

        &.active {
          background: #ecf5ff;
          border: 1px solid #409eff;
        }

        .dataset-info {
          .dataset-name {
            font-weight: 500;
            margin-bottom: 5px;
          }

          .dataset-meta {
            display: flex;
            gap: 5px;
          }
        }
      }
    }

    .import-section {
      display: flex;
      flex-direction: column;
      gap: 10px;

      .import-name-input {
        width: 100%;
      }
    }
  }

  .config-panel {
    .threshold-label {
      font-size: 12px;
      color: #909399;
      text-align: center;
      margin-top: 4px;
    }
  }

  .results-panel {
    .metrics-cards {
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 15px;

      .metric-card {
        text-align: center;
        padding: 15px;

        .metric-label {
          font-size: 14px;
          color: #909399;
          margin-bottom: 8px;
        }

        .metric-value {
          font-size: 28px;
          font-weight: bold;
          color: #303133;
          margin-bottom: 4px;
        }

        .metric-desc {
          font-size: 12px;
          color: #c0c4cc;
        }

        &.good .metric-value {
          color: #67c23a;
        }

        &.warning .metric-value {
          color: #e6a23c;
        }

        &.danger .metric-value {
          color: #f56c6c;
        }
      }
    }

    .chart-container {
      height: 350px;
      border: 1px solid #ebeef5;
      border-radius: 4px;
    }
  }
}
</style>
