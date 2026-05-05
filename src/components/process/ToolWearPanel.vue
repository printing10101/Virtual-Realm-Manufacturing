<template>
  <div class="tool-wear-panel">
    <div class="panel-header">
      <h3 class="panel-title">
        <svg
          viewBox="0 0 1024 1024"
          width="20"
          height="20"
          class="title-icon"
        >
          <path
            d="M896 192H128c-35.3 0-64 28.7-64 64v512c0 35.3 28.7 64 64 64h768c35.3 0 64-28.7 64-64V256c0-35.3-28.7-64-64-64zM128 128h768c70.7 0 128 57.3 128 128v512c0 70.7-57.3 128-128 128H128C57.3 896 0 838.7 0 768V256C0 185.3 57.3 128 128 128z"
            fill="#409EFF"
          />
          <path
            d="M512 320c-106 0-192 86-192 192s86 192 192 192 192-86 192-192-86-192-192-192zm0 320c-70.7 0-128-57.3-128-128s57.3-128 128-128 128 57.3 128 128-57.3 128-128 128z"
            fill="#409EFF"
          />
        </svg>
        刀具磨损预测
      </h3>
      <div class="header-actions">
        <button
          class="action-btn"
          :disabled="loading"
          @click="runPrediction"
        >
          <svg
            viewBox="0 0 1024 1024"
            width="16"
            height="16"
          >
            <path
              d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"
              fill="currentColor"
            />
            <path
              d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256z"
              fill="currentColor"
            />
          </svg>
          {{ loading ? '预测中...' : '开始预测' }}
        </button>
      </div>
    </div>

    <div class="panel-body">
      <div class="param-section">
        <h4 class="section-title">
          加工参数
        </h4>
        <div class="param-grid">
          <div class="param-item">
            <label>切削速度 (m/min)</label>
            <input
              v-model.number="params.cutting_speed"
              type="number"
              step="10"
              min="10"
              max="500"
            >
          </div>
          <div class="param-item">
            <label>进给量 (mm/rev)</label>
            <input
              v-model.number="params.feed_rate"
              type="number"
              step="0.01"
              min="0.01"
              max="1.0"
            >
          </div>
          <div class="param-item">
            <label>切削深度 (mm)</label>
            <input
              v-model.number="params.depth_of_cut"
              type="number"
              step="0.1"
              min="0.1"
              max="10"
            >
          </div>
          <div class="param-item">
            <label>材料类型</label>
            <select v-model="params.material_type">
              <option value="aluminum_6061">
                Aluminum 6061
              </option>
              <option value="aluminum_7075">
                Aluminum 7075
              </option>
              <option
                value="steel_45"
                selected
              >
                Steel 45#
              </option>
              <option value="steel_4140">
                Steel 4140
              </option>
              <option value="stainless_304">
                Stainless 304
              </option>
              <option value="stainless_316">
                Stainless 316
              </option>
              <option value="titanium_ti64">
                Titanium Ti-6Al-4V
              </option>
              <option value="inconel_718">
                Inconel 718
              </option>
              <option value="cast_iron">
                Cast Iron
              </option>
              <option value="brass">
                Brass
              </option>
            </select>
          </div>
          <div class="param-item">
            <label>刀具类型</label>
            <select v-model="params.tool_type">
              <option
                value="carbide"
                selected
              >
                硬质合金
              </option>
              <option value="coated_carbide">
                涂层硬质合金
              </option>
              <option value="cermet">
                金属陶瓷
              </option>
              <option value="ceramic">
                陶瓷
              </option>
              <option value="cbn">
                CBN
              </option>
              <option value="pcd">
                PCD
              </option>
              <option value="hss">
                高速钢
              </option>
            </select>
          </div>
          <div class="param-item">
            <label>当前磨损量 (mm)</label>
            <input
              v-model.number="params.current_wear"
              type="number"
              step="0.01"
              min="0"
              max="0.5"
            >
          </div>
        </div>
      </div>

      <div
        v-if="prediction"
        class="metrics-section"
      >
        <h4 class="section-title">
          寿命指标
        </h4>
        <div class="metrics-grid">
          <div class="metric-card">
            <div class="metric-label">
              总寿命
            </div>
            <div class="metric-value">
              {{ prediction.total_life.toFixed(1) }} min
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-label">
              剩余寿命
            </div>
            <div class="metric-value">
              {{ remainingLife.toFixed(1) }} min
            </div>
            <div class="metric-progress">
              <div
                class="progress-bar"
                :class="lifeStatusClass"
                :style="{ width: lifePercent + '%' }"
              />
              <span class="progress-text">{{ lifePercent.toFixed(0) }}%</span>
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-label">
              平均磨损率
            </div>
            <div class="metric-value">
              {{ prediction.wear_rate_avg.toFixed(5) }} mm/min
            </div>
          </div>
          <div class="metric-card">
            <div class="metric-label">
              预测置信度
            </div>
            <div class="metric-value">
              {{ (prediction.confidence * 100).toFixed(0) }}%
            </div>
          </div>
        </div>
      </div>

      <div
        v-if="prediction"
        class="warning-section"
      >
        <h4 class="section-title">
          预警状态
        </h4>
        <div
          class="warning-indicator"
          :class="warningClass"
        >
          <svg
            v-if="warningLevel === 'normal'"
            viewBox="0 0 1024 1024"
            width="24"
            height="24"
          >
            <path
              d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"
              fill="#67C23A"
            />
            <path
              d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256z"
              fill="#67C23A"
            />
          </svg>
          <svg
            v-else-if="warningLevel === 'warning'"
            viewBox="0 0 1024 1024"
            width="24"
            height="24"
          >
            <path
              d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"
              fill="#E6A23C"
            />
            <path
              d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256z"
              fill="#E6A23C"
            />
          </svg>
          <svg
            v-else
            viewBox="0 0 1024 1024"
            width="24"
            height="24"
          >
            <path
              d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z"
              fill="#F56C6C"
            />
            <path
              d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256z"
              fill="#F56C6C"
            />
          </svg>
          <span class="warning-text">{{ warningText }}</span>
        </div>
      </div>

      <div
        v-if="prediction && prediction.data_points.length > 0"
        class="chart-section"
      >
        <h4 class="section-title">
          磨损曲线
        </h4>
        <div
          ref="chartRef"
          class="wear-chart"
        />
      </div>

      <div
        v-if="suggestions && suggestions.suggestions.length > 0"
        class="suggestions-section"
      >
        <h4 class="section-title">
          参数调整建议
        </h4>
        <div class="suggestions-list">
          <div
            v-for="(suggestion, index) in suggestions.suggestions"
            :key="index"
            class="suggestion-card"
          >
            <div class="suggestion-header">
              <span class="suggestion-type">{{ formatParamType(suggestion.param_type) }}</span>
              <span
                class="suggestion-delta"
                :class="getDeltaClass(suggestion.adjustment_delta)"
              >
                {{ formatDelta(suggestion) }}
              </span>
            </div>
            <div class="suggestion-body">
              <div class="suggestion-values">
                <span class="value-label">当前值:</span>
                <span class="value-current">{{ suggestion.current_value }}</span>
                <span class="value-arrow">→</span>
                <span class="value-suggested">{{ suggestion.suggested_value }}</span>
              </div>
              <p class="suggestion-effect">
                {{ suggestion.expected_effect }}
              </p>
            </div>
          </div>
        </div>
      </div>

      <div class="calibration-section">
        <h4 class="section-title">
          实际磨损录入
        </h4>
        <div class="calibration-form">
          <div class="calib-item">
            <label>实测 VB 值 (mm)</label>
            <input
              v-model.number="measuredWear"
              type="number"
              step="0.01"
              min="0"
              max="0.5"
              placeholder="输入实测磨损量"
            >
          </div>
          <div class="calib-item">
            <label>已加工时间 (min)</label>
            <input
              v-model.number="elapsedTime"
              type="number"
              step="1"
              min="0"
              placeholder="输入加工时间"
            >
          </div>
          <button
            class="calib-btn"
            :disabled="!measuredWear || !elapsedTime || loading"
            @click="calibrate"
          >
            校准预测曲线
          </button>
          <div
            v-if="calibrationResult"
            class="calibration-result"
          >
            <p>预测偏差: <span :class="calibrationResult.deviation > 0 ? 'positive' : 'negative'">{{ calibrationResult.deviation.toFixed(4) }} mm</span></p>
            <p>偏差百分比: <span :class="Math.abs(calibrationResult.deviation_percent) > 20 ? 'critical' : 'acceptable'">{{ calibrationResult.deviation_percent.toFixed(2) }}%</span></p>
            <p>修正系数: {{ calibrationResult.correction_factor.toFixed(3) }}</p>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import {
  TooltipComponent,
  LegendComponent,
  GridComponent,
  MarkAreaComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { buildApiUrl } from '@/utils/api'
import axios from 'axios'

echarts.use([
  LineChart,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  MarkAreaComponent,
  CanvasRenderer
])

interface PredictionData {
  total_life: number
  time_to_threshold: number
  wear_rate_avg: number
  confidence: number
  data_points: {
    time: number
    vb: number
    wear_rate: number
    phase: string
  }[]
}

interface SuggestionItem {
  param_type: string
  current_value: number
  suggested_value: number
  adjustment_delta: number
  expected_effect: string
}

interface CalibrationResult {
  measured_wear: number
  predicted_wear_at_time: number
  deviation: number
  deviation_percent: number
  correction_factor: number
}

const params = ref({
  cutting_speed: 150,
  feed_rate: 0.2,
  depth_of_cut: 1.5,
  material_type: 'steel_45',
  tool_type: 'carbide',
  current_wear: 0.0
})

const loading = ref(false)
const prediction = ref<PredictionData | null>(null)
const suggestions = ref<{ suggestions: SuggestionItem[] } | null>(null)
const measuredWear = ref(0)
const elapsedTime = ref(0)
const calibrationResult = ref<CalibrationResult | null>(null)
const chartRef = ref<HTMLElement | null>(null)
let chart: echarts.ECharts | null = null
let chartRenderTimer: ReturnType<typeof setTimeout> | null = null
let resizeHandler: (() => void) | null = null

const remainingLife = computed(() => {
  if (!prediction.value) return 0
  return Math.max(0, prediction.value.total_life - prediction.value.time_to_threshold + prediction.value.time_to_threshold)
})

const lifePercent = computed(() => {
  if (!prediction.value || prediction.value.total_life === 0) return 0
  return Math.max(0, Math.min(100, ((prediction.value.total_life - (prediction.value.time_to_threshold || 0)) / prediction.value.total_life) * 100))
})

const lifeStatusClass = computed(() => {
  if (lifePercent.value > 50) return 'status-normal'
  if (lifePercent.value > 20) return 'status-warning'
  return 'status-critical'
})

const warningLevel = computed(() => {
  if (!prediction.value) return 'normal'
  if (lifePercent.value > 50) return 'normal'
  if (lifePercent.value > 20) return 'warning'
  return 'critical'
})

const warningText = computed(() => {
  switch (warningLevel.value) {
    case 'normal': return '正常 - 刀具寿命充足'
    case 'warning': return '警告 - 刀具寿命低于50%，建议关注'
    case 'critical': return '危急 - 刀具寿命低于20%，建议立即更换'
    default: return '未知'
  }
})

const warningClass = computed(() => {
  return `warning-${warningLevel.value}`
})

function formatParamType(type: string): string {
  const map: Record<string, string> = {
    cutting_speed: '切削速度',
    feed_rate: '进给量',
    depth_of_cut: '切削深度',
    coolant_flow: '冷却液流量',
    tool_inspection: '刀具检查'
  }
  return map[type] || type
}

function getDeltaClass(delta: number): string {
  if (delta < 0) return 'delta-negative'
  if (delta > 0) return 'delta-positive'
  return 'delta-neutral'
}

function formatDelta(s: SuggestionItem): string {
  if (s.param_type === 'tool_inspection') return '立即检查'
  return `${s.adjustment_delta > 0 ? '+' : ''}${s.adjustment_delta}%`
}

async function runPrediction() {
  loading.value = true
  try {
    const predictRes = await axios.post(buildApiUrl('/api/v1/wear/predict'), params.value)
    if (predictRes.data.code === 0) {
      prediction.value = predictRes.data.data
      renderChart()

      const life = prediction.value!.total_life - prediction.value!.time_to_threshold
      const suggestRes = await axios.post(buildApiUrl('/api/v1/wear/suggest'), {
        ...params.value,
        current_wear: params.value.current_wear,
        remaining_life: Math.max(0, life),
        coolant_flow: 10.0
      })
      if (suggestRes.data.code === 0) {
        suggestions.value = suggestRes.data.data
      }
    }
  } catch (e) {
    console.error('Prediction failed:', e)
  } finally {
    loading.value = false
  }
}

async function calibrate() {
  if (!measuredWear.value || !elapsedTime.value) return
  loading.value = true
  try {
    const res = await axios.post(buildApiUrl('/api/v1/wear/calibrate'), {
      measured_wear: measuredWear.value,
      elapsed_time: elapsedTime.value,
      ...params.value
    })
    if (res.data.code === 0) {
      calibrationResult.value = {
        measured_wear: res.data.data.measured_wear,
        predicted_wear_at_time: res.data.data.predicted_wear_at_time,
        deviation: res.data.data.deviation,
        deviation_percent: res.data.data.deviation_percent,
        correction_factor: res.data.data.correction_factor
      }
      if (res.data.data.calibrated_curve) {
        prediction.value = res.data.data.calibrated_curve
        renderChart()
      }
    }
  } catch (e) {
    console.error('Calibration failed:', e)
  } finally {
    loading.value = false
  }
}

function renderChart() {
  if (!chartRef.value || !prediction.value) return
  if (!chart) {
    chart = echarts.init(chartRef.value)
  }

  const dataPoints = prediction.value.data_points
  const threshold = 0.3

  const initialData = dataPoints.filter(d => d.phase === 'initial').map(d => [d.time, d.vb])
  const steadyData = dataPoints.filter(d => d.phase === 'steady').map(d => [d.time, d.vb])
  const acceleratedData = dataPoints.filter(d => d.phase === 'accelerated').map(d => [d.time, d.vb])

  const option: echarts.EChartsCoreOption = {
    tooltip: {
      trigger: 'axis',
      formatter: (p: any) => {
        if (p[0]) {
          return `时间: ${p[0].value[0]} min<br/>VB: ${p[0].value[1]} mm`
        }
        return ''
      }
    },
    legend: {
      data: ['初始磨损', '稳定磨损', '加速磨损', '更换阈值'],
      top: 10
    },
    grid: {
      left: '3%',
      right: '4%',
      bottom: '3%',
      containLabel: true
    },
    xAxis: {
      type: 'value',
      name: '时间 (min)',
      splitLine: { show: true, lineStyle: { type: 'dashed' } }
    },
    yAxis: {
      type: 'value',
      name: 'VB (mm)',
      min: 0,
      max: 0.4,
      splitLine: { show: true, lineStyle: { type: 'dashed' } }
    },
    series: [
      {
        name: '初始磨损',
        type: 'line',
        data: initialData,
        smooth: true,
        lineStyle: { width: 2, color: '#67C23A' },
        itemStyle: { color: '#67C23A' },
        symbol: 'none'
      },
      {
        name: '稳定磨损',
        type: 'line',
        data: steadyData,
        smooth: true,
        lineStyle: { width: 2, color: '#409EFF' },
        itemStyle: { color: '#409EFF' },
        symbol: 'none'
      },
      {
        name: '加速磨损',
        type: 'line',
        data: acceleratedData,
        smooth: true,
        lineStyle: { width: 2, color: '#E6A23C' },
        itemStyle: { color: '#E6A23C' },
        symbol: 'none'
      },
      {
        name: '更换阈值',
        type: 'line',
        data: [[0, threshold], [dataPoints[dataPoints.length - 1]?.time || 100, threshold]],
        lineStyle: { width: 2, color: '#F56C6C', type: 'dashed' },
        symbol: 'none',
        markArea: {
          silent: true,
          data: [
            [
              { yAxis: threshold, itemStyle: { color: 'rgba(245,108,108,0.1)' } },
              { yAxis: 0.4, itemStyle: { color: 'rgba(245,108,108,0.1)' } }
            ]
          ]
        }
      }
    ]
  }

  chart.setOption(option)
}

watch(() => prediction.value, () => {
  if (prediction.value) {
    if (chartRenderTimer) {
      clearTimeout(chartRenderTimer)
    }
    chartRenderTimer = setTimeout(renderChart, 100)
  }
})

onMounted(() => {
  resizeHandler = () => chart?.resize()
  window.addEventListener('resize', resizeHandler)
})

onBeforeUnmount(() => {
  if (chartRenderTimer) {
    clearTimeout(chartRenderTimer)
    chartRenderTimer = null
  }
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  if (chart) {
    chart.dispose()
    chart = null
  }
})
</script>

<style scoped>
.tool-wear-panel {
  background: #fff;
  border-radius: 8px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  border-bottom: 1px solid #ebeef5;
  background: #fafafa;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
  margin: 0;
}

.title-icon {
  flex-shrink: 0;
}

.action-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: #409EFF;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.action-btn:hover:not(:disabled) {
  background: #66b1ff;
}

.action-btn:disabled {
  background: #a0cfff;
  cursor: not-allowed;
}

.panel-body {
  padding: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.param-section {
  margin-bottom: 24px;
}

.param-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.param-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-item label {
  font-size: 12px;
  color: #909399;
}

.param-item input,
.param-item select {
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
  outline: none;
  transition: border-color 0.2s;
}

.param-item input:focus,
.param-item select:focus {
  border-color: #409EFF;
}

.metrics-section {
  margin-bottom: 24px;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  text-align: center;
}

.metric-label {
  font-size: 12px;
  color: #909399;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 20px;
  font-weight: 700;
  color: #303133;
}

.metric-progress {
  margin-top: 8px;
  height: 8px;
  background: #ebeef5;
  border-radius: 4px;
  overflow: hidden;
  position: relative;
}

.progress-bar {
  height: 100%;
  border-radius: 4px;
  transition: width 0.3s;
}

.progress-bar.status-normal {
  background: #67C23A;
}

.progress-bar.status-warning {
  background: #E6A23C;
}

.progress-bar.status-critical {
  background: #F56C6C;
}

.progress-text {
  position: absolute;
  top: -18px;
  right: 0;
  font-size: 11px;
  color: #606266;
}

.warning-section {
  margin-bottom: 24px;
}

.warning-indicator {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 12px 16px;
  border-radius: 8px;
  background: #f0f9eb;
}

.warning-indicator.warning-normal {
  background: #f0f9eb;
}

.warning-indicator.warning-warning {
  background: #fdf6ec;
}

.warning-indicator.warning-critical {
  background: #fef0f0;
}

.warning-text {
  font-size: 14px;
  font-weight: 500;
  color: #303133;
}

.chart-section {
  margin-bottom: 24px;
}

.wear-chart {
  height: 400px;
  border: 1px solid #ebeef5;
  border-radius: 8px;
  background: #fff;
}

.suggestions-section {
  margin-bottom: 24px;
}

.suggestions-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.suggestion-card {
  padding: 16px;
  background: #f5f7fa;
  border-radius: 8px;
  border-left: 4px solid #409EFF;
}

.suggestion-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.suggestion-type {
  font-weight: 600;
  color: #303133;
}

.suggestion-delta {
  padding: 2px 8px;
  border-radius: 4px;
  font-size: 12px;
  font-weight: 500;
}

.suggestion-delta.delta-negative {
  background: #fde2e2;
  color: #F56C6C;
}

.suggestion-delta.delta-positive {
  background: #e1f3d8;
  color: #67C23A;
}

.suggestion-delta.delta-neutral {
  background: #ebeef5;
  color: #909399;
}

.suggestion-values {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-size: 14px;
}

.value-label {
  color: #909399;
}

.value-current {
  color: #606266;
  font-weight: 500;
}

.value-arrow {
  color: #409EFF;
}

.value-suggested {
  color: #409EFF;
  font-weight: 600;
}

.suggestion-effect {
  margin: 0;
  font-size: 13px;
  color: #606266;
  line-height: 1.5;
}

.calibration-section {
  margin-bottom: 24px;
}

.calibration-form {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  align-items: flex-end;
}

.calib-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.calib-item label {
  font-size: 12px;
  color: #909399;
}

.calib-item input {
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 4px;
  font-size: 14px;
  outline: none;
  width: 150px;
}

.calib-item input:focus {
  border-color: #409EFF;
}

.calib-btn {
  padding: 8px 20px;
  background: #67C23A;
  color: #fff;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  transition: background 0.2s;
}

.calib-btn:hover:not(:disabled) {
  background: #85ce61;
}

.calib-btn:disabled {
  background: #b3e19d;
  cursor: not-allowed;
}

.calibration-result {
  margin-top: 12px;
  padding: 12px 16px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
  color: #606266;
}

.calibration-result p {
  margin: 4px 0;
}

.calibration-result .positive {
  color: #F56C6C;
  font-weight: 600;
}

.calibration-result .negative {
  color: #67C23A;
  font-weight: 600;
}

.calibration-result .critical {
  color: #F56C6C;
  font-weight: 600;
}

.calibration-result .acceptable {
  color: #67C23A;
  font-weight: 600;
}
</style>
