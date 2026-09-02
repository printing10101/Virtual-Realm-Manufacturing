<template>
  <!-- 图表区域 -->
  <div class="content-card">
    <div class="content-card__header">
      <span class="content-card__title">{{ t('productionReport.chartTitle') }}</span>
      <el-radio-group
        :model-value="chartType"
        size="small"
        @change="onChartTypeChange"
      >
        <el-radio-button value="bar">
          {{ t('productionReport.chartTypeBar') }}
        </el-radio-button>
        <el-radio-button value="line">
          {{ t('productionReport.chartTypeLine') }}
        </el-radio-button>
      </el-radio-group>
    </div>
    <div style="padding: 20px;">
      <div
        ref="chartEl"
        class="trend-chart"
        v-loading="statsLoading"
      />
      <el-empty
        v-if="!statsLoading && trendData.length === 0"
        :description="t('productionReport.emptyTrendData')"
        :image-size="60"
      />
    </div>
  </div>

  <!-- 生产趋势明细表 -->
  <div class="content-card">
    <div class="content-card__header">
      <span class="content-card__title">{{ t('productionReport.trendDetailTitle') }}</span>
    </div>
    <div class="content-card__body">
      <el-table
        v-loading="statsLoading"
        :data="trendData"
        style="width: 100%"
        :empty-text="t('productionReport.emptyTrendData')"
        stripe
      >
        <el-table-column
          prop="date"
          :label="t('productionReport.colDate')"
          width="140"
        />
        <el-table-column
          prop="planOutput"
          :label="t('productionReport.colPlanOutput')"
          width="120"
        />
        <el-table-column
          prop="actualOutput"
          :label="t('productionReport.colActualOutput')"
          width="120"
        >
          <template #default="{ row }">
            <span :class="{ 'text-warning': row.actualOutput < row.planOutput }">
              {{ row.actualOutput }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="yieldRate"
          :label="t('productionReport.colYieldRate')"
          width="110"
        >
          <template #default="{ row }">
            <span :class="{ 'text-danger': parseFloat(row.yieldRate) < 98 }">
              {{ row.yieldRate }}
            </span>
          </template>
        </el-table-column>
        <el-table-column
          prop="utilization"
          :label="t('productionReport.colUtilization')"
          width="110"
        />
        <el-table-column
          :label="t('productionReport.colAchievementRate')"
          width="140"
        >
          <template #default="{ row }">
            <el-progress
              :percentage="Math.min(row.achievementRate, 100)"
              :stroke-width="8"
              :color="row.achievementRate >= 95 ? 'var(--success)' : row.achievementRate >= 85 ? 'var(--warning)' : 'var(--error)'"
            />
          </template>
        </el-table-column>
      </el-table>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'

const { t } = useI18n()

interface TrendRow {
  date: string
  planOutput: number
  actualOutput: number
  yieldRate: string
  utilization: string
  achievementRate: number
}

const props = defineProps<{
  chartType: string
  statsLoading: boolean
  trendData: TrendRow[]
}>()

const emit = defineEmits<{
  'update:chart-type': [value: string]
}>()

function onChartTypeChange(value: string | number | boolean | undefined) {
  emit('update:chart-type', String(value || 'bar'))
}

// 趋势图表
const chartEl = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

/** 渲染生产趋势图表。 */
function renderChart() {
  if (!chartEl.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }
  const dates = props.trendData.map((r) => r.date)
  const planOutputs = props.trendData.map((r) => r.planOutput)
  const actualOutputs = props.trendData.map((r) => r.actualOutput)
  const yieldRates = props.trendData.map((r) => parseFloat(r.yieldRate))
  const utilizations = props.trendData.map((r) => parseFloat(r.utilization))

  const isBar = props.chartType === 'bar'
  const series = isBar
    ? [
        { name: t('productionReport.colPlanOutput'), type: 'bar', barGap: '10%', data: planOutputs, itemStyle: { color: '#a69c84' } },
        { name: t('productionReport.colActualOutput'), type: 'bar', data: actualOutputs, itemStyle: { color: '#007aff' } },
      ]
    : [
        { name: t('productionReport.colPlanOutput'), type: 'line', smooth: true, data: planOutputs, itemStyle: { color: '#a69c84' } },
        { name: t('productionReport.colActualOutput'), type: 'line', smooth: true, data: actualOutputs, itemStyle: { color: '#007aff' } },
      ]

  chartInstance.setOption({
    tooltip: { trigger: 'axis' },
    legend: { data: [t('productionReport.colPlanOutput'), t('productionReport.colActualOutput'), t('productionReport.colYieldRate'), t('productionReport.colUtilization')] },
    grid: { left: 50, right: 50, top: 40, bottom: 40 },
    xAxis: { type: 'category', data: dates },
    yAxis: [
      { type: 'value', name: t('productionReport.colQtyShort') },
      { type: 'value', name: '%', max: 100, splitLine: { show: false } },
    ],
    series: [
      ...series,
      { name: t('productionReport.colYieldRate'), type: 'line', smooth: true, yAxisIndex: 1, data: yieldRates, itemStyle: { color: '#34c759' } },
      { name: t('productionReport.colUtilization'), type: 'line', smooth: true, yAxisIndex: 1, data: utilizations, itemStyle: { color: '#ff9500' } },
    ],
  })
}

/** 图表自适应容器宽度。 */
function resizeChart() {
  chartInstance?.resize()
}

// 趋势数据或图表类型变化时重新渲染
watch(
  () => [props.trendData, props.chartType],
  () => {
    renderChart()
  },
  { deep: true }
)

onMounted(() => {
  setTimeout(() => renderChart(), 0)
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  window.removeEventListener('resize', resizeChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.trend-chart {
  width: 100%;
  height: 340px;
}

.text-warning {
  color: var(--warning);
  font-weight: 500;
}

.text-danger {
  color: var(--error);
  font-weight: 500;
}
</style>
