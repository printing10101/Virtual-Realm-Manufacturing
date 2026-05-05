<template>
  <div class="route-stats">
    <el-row :gutter="20">
      <el-col :span="8">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.callDistribution') }}</h3>
          </template>
          <div
            ref="pieChartRef"
            style="height: 300px;"
          />
        </el-card>
      </el-col>

      <el-col :span="16">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.upgradeRateTrend') }}</h3>
          </template>
          <div
            ref="lineChartRef"
            style="height: 300px;"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-row style="margin-top: 20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.statsSummary') }}</h3>
          </template>
          <el-descriptions
            :column="4"
            border
          >
            <el-descriptions-item :label="t('modelManagement.totalCalls')">
              {{ stats.total_calls || 0 }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.localCalls')">
              {{ stats.local_calls || 0 }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.cloudCalls')">
              {{ stats.cloud_calls || 0 }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.fallbackCalls')">
              {{ stats.fallback_calls || 0 }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.avgDuration')">
              {{ Math.round(stats.avg_duration_ms || 0) }}ms
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts/core'
import { PieChart, LineChart } from 'echarts/charts'
import {
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent
} from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import type { EChartsType } from 'echarts/core'

echarts.use([
  PieChart,
  LineChart,
  TitleComponent,
  TooltipComponent,
  LegendComponent,
  GridComponent,
  ToolboxComponent,
  CanvasRenderer
])

const { t } = useI18n()
const pieChartRef = ref<HTMLElement>()
const lineChartRef = ref<HTMLElement>()
let pieChart: EChartsType | null = null
let lineChart: EChartsType | null = null
let resizeHandler: (() => void) | null = null

const props = defineProps<{
  stats: {
    total_calls?: number
    local_calls?: number
    cloud_calls?: number
    fallback_calls?: number
    avg_duration_ms?: number
    route_history?: Array<{ decision: string; model: string; duration_ms: number; timestamp: string }>
  }
}>()

onMounted(() => {
  initCharts()
  updateCharts()
  resizeHandler = () => {
    pieChart?.resize()
    lineChart?.resize()
  }
  window.addEventListener('resize', resizeHandler)
})

onUnmounted(() => {
  if (resizeHandler) {
    window.removeEventListener('resize', resizeHandler)
    resizeHandler = null
  }
  if (pieChart) {
    pieChart.dispose()
    pieChart = null
  }
  if (lineChart) {
    lineChart.dispose()
    lineChart = null
  }
})

watch(() => props.stats, () => {
  updateCharts()
}, { deep: true })

function initCharts() {
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
  }
  if (lineChartRef.value) {
    lineChart = echarts.init(lineChartRef.value)
  }
}

function updateCharts() {
  updatePieChart()
  updateLineChart()
}

function updatePieChart() {
  if (!pieChart) return

  const localCount = props.stats.local_calls || 0
  const cloudCount = props.stats.cloud_calls || 0
  const fallbackCount = props.stats.fallback_calls || 0

  pieChart.setOption({
    tooltip: { trigger: 'item' },
    legend: { orient: 'vertical', left: 'left' },
    series: [{
      type: 'pie',
      radius: '50%',
      data: [
        { value: localCount, name: '本地调用' },
        { value: cloudCount, name: '云端调用' },
        { value: fallbackCount, name: 'Fallback' }
      ],
      emphasis: {
        itemStyle: {
          shadowBlur: 10,
          shadowOffsetX: 0,
          shadowColor: 'rgba(0, 0, 0, 0.5)'
        }
      }
    }]
  })
}

function updateLineChart() {
  if (!lineChart) return

  const history = props.stats.route_history || []
  const last50 = history.slice(-50)

  const timestamps = last50.map(h => {
    const date = new Date(h.timestamp)
    return `${date.getHours()}:${String(date.getMinutes()).padStart(2, '0')}`
  })
  const durations = last50.map(h => Math.round(h.duration_ms))
  
  let cloudCumulativeCount = 0
  const cloudCounts = last50.map(h => {
    if (h.decision === 'cloud') {
      cloudCumulativeCount++
    }
    return cloudCumulativeCount
  })

  lineChart.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: ['响应时间 (ms)', '云端调用累计次数'] },
    xAxis: {
      type: 'category',
      data: timestamps,
      axisLabel: { rotate: 45 }
    },
    yAxis: [
      { type: 'value', name: '响应时间' },
      { type: 'value', name: '云端调用次数' }
    ],
    series: [
      {
        name: '响应时间 (ms)',
        data: durations,
        type: 'line',
        smooth: true,
        itemStyle: { color: '#409eff' },
        yAxisIndex: 0
      },
      {
        name: '云端调用累计次数',
        data: cloudCounts,
        type: 'line',
        smooth: true,
        itemStyle: { color: '#f56c6c' },
        yAxisIndex: 1
      }
    ]
  })
}
</script>

<style scoped lang="scss">
.route-stats {
  h3 {
    margin: 0;
    font-size: 16px;
    color: #303133;
  }
}
</style>
