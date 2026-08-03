<template>
  <div class="production-report-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('productionReport.pageTitle') }}</h1>
        <p class="subtitle">
          {{ t('productionReport.pageSubtitle') }}
        </p>
      </div>
      <div class="page-header__actions">
        <el-button
          type="primary"
          size="small"
          :icon="Download"
          @click="handleExport"
        >
          {{ t('productionReport.btnExport') }}
        </el-button>
      </div>
    </div>

    <!-- 时间范围选择 -->
    <div class="filter-bar">
      <el-radio-group
        v-model="timeRange"
        size="small"
        @change="handleTimeRangeChange"
      >
        <el-radio-button value="today">
          {{ t('productionReport.rangeToday') }}
        </el-radio-button>
        <el-radio-button value="week">
          {{ t('productionReport.rangeWeek') }}
        </el-radio-button>
        <el-radio-button value="month">
          {{ t('productionReport.rangeMonth') }}
        </el-radio-button>
        <el-radio-button value="custom">
          {{ t('productionReport.rangeCustom') }}
        </el-radio-button>
      </el-radio-group>
      <el-date-picker
        v-if="timeRange === 'custom'"
        v-model="customDateRange"
        type="daterange"
        :range-separator="t('productionReport.dateRangeSeparator')"
        :start-placeholder="t('productionReport.startDatePlaceholder')"
        :end-placeholder="t('productionReport.endDatePlaceholder')"
        size="small"
        @change="handleTimeRangeChange"
      />
    </div>

    <!-- 生产汇总卡片 -->
    <div
      v-loading="dashboardLoading"
      class="summary-row"
    >
      <template v-if="summaryCards.length > 0">
        <el-card
          v-for="item in summaryCards"
          :key="item.label"
          shadow="hover"
          class="summary-card"
        >
          <div class="summary-card__header">
            <span class="summary-card__label">{{ item.label }}</span>
            <el-icon
              :size="16"
              class="summary-card__trend"
              :class="item.trendClass"
            >
              <component :is="item.trendIcon" />
            </el-icon>
          </div>
          <span class="summary-card__value">{{ item.value }}</span>
          <span class="summary-card__unit">{{ item.unit }}</span>
        </el-card>
      </template>
      <el-empty
        v-else
        :description="t('productionReport.loadFailed')"
        :image-size="60"
      />
    </div>

    <!-- 图表区域（占位） -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('productionReport.chartTitle') }}</span>
        <el-radio-group
          v-model="chartType"
          size="small"
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

    <!-- 最新生产记录 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('productionReport.recordsTitle') }}</span>
      </div>
      <div class="content-card__body">
        <el-table
          v-loading="recordsLoading"
          :data="productionRecords"
          style="width: 100%"
          :empty-text="t('productionReport.emptyRecords')"
          stripe
        >
          <el-table-column
            prop="order_no"
            :label="t('productionReport.colOrderNo')"
            width="140"
          />
          <el-table-column
            prop="product_name"
            :label="t('productionReport.colProductName')"
            min-width="160"
          />
          <el-table-column
            prop="quantity"
            :label="t('productionReport.colQuantity')"
            width="100"
          />
          <el-table-column
            prop="qualified_quantity"
            :label="t('productionReport.colQualifiedQty')"
            width="100"
          />
          <el-table-column
            prop="operator"
            :label="t('productionReport.colOperator')"
            width="100"
          />
          <el-table-column
            prop="status"
            :label="t('productionReport.colStatus')"
            width="90"
          >
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="statusTagType(row.status)"
              >
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="created_at"
            :label="t('productionReport.colCreatedAt')"
            width="170"
          />
        </el-table>
      </div>
    </div>

    <!-- 工单列表 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('productionReport.workOrdersTitle') }}</span>
      </div>
      <div class="content-card__body">
        <el-table
          v-loading="workOrdersLoading"
          :data="workOrders"
          style="width: 100%"
          :empty-text="t('productionReport.emptyWorkOrders')"
          stripe
        >
          <el-table-column
            prop="order_no"
            :label="t('productionReport.colOrderNo')"
            width="140"
          />
          <el-table-column
            prop="product_name"
            :label="t('productionReport.colProductName')"
            min-width="160"
          />
          <el-table-column
            prop="quantity"
            :label="t('productionReport.colQtyShort')"
            width="90"
          />
          <el-table-column
            prop="status"
            :label="t('productionReport.colStatus')"
            width="90"
          >
            <template #default="{ row }">
              <el-tag
                size="small"
                :type="statusTagType(row.status)"
              >
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="priority"
            :label="t('productionReport.colPriority')"
            width="80"
          />
          <el-table-column
            prop="deadline"
            :label="t('productionReport.colDeadline')"
            width="120"
          />
          <el-table-column
            prop="created_at"
            :label="t('productionReport.colCreatedAt')"
            width="170"
          />
        </el-table>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, type Component } from 'vue'
import { ElMessage } from 'element-plus'
import { Download, Top, Bottom, Right } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import * as echarts from 'echarts'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

const { t } = useI18n()

// ========================= 类型定义 =========================
interface SummaryCard {
  label: string
  value: string
  unit: string
  trendIcon: Component
  trendClass: string
}

interface DashboardData {
  total_output: number
  qualified_output: number
  total_orders: number
  active_orders: number
  pass_rate: number
  avg_cycle_time: number
}

interface StatsItem {
  date: string
  plan_output: number
  actual_output: number
  yield_rate: number
  utilization: number
  achievement_rate: number
}

interface TrendRow {
  date: string
  planOutput: number
  actualOutput: number
  yieldRate: string
  utilization: string
  achievementRate: number
}

interface ProductionRecord {
  id: number
  order_no: string
  product_name: string
  quantity: number
  qualified_quantity: number
  operator: string
  status: string
  created_at: string
}

interface WorkOrder {
  id: number
  order_no: string
  product_name: string
  quantity: number
  status: string
  priority: string
  deadline: string
  created_at: string
}

// ========================= 状态 =========================
const loading = ref(false)
const dashboardLoading = ref(false)
const statsLoading = ref(false)
const recordsLoading = ref(false)
const workOrdersLoading = ref(false)
const timeRange = ref('month')
const customDateRange = ref<[Date, Date] | null>(null)
const chartType = ref('bar')

const dashboardData = ref<DashboardData | null>(null)
const trendData = ref<TrendRow[]>([])
const productionRecords = ref<ProductionRecord[]>([])
const workOrders = ref<WorkOrder[]>([])

// ========================= 趋势图表 =========================
const chartEl = ref<HTMLElement | null>(null)
let chartInstance: echarts.ECharts | null = null

/** 渲染生产趋势图表（数据来自真实 /production/stats 接口）。 */
function renderChart() {
  if (!chartEl.value) return
  if (!chartInstance) {
    chartInstance = echarts.init(chartEl.value)
  }
  const dates = trendData.value.map((r) => r.date)
  const planOutputs = trendData.value.map((r) => r.planOutput)
  const actualOutputs = trendData.value.map((r) => r.actualOutput)
  const yieldRates = trendData.value.map((r) => parseFloat(r.yieldRate))
  const utilizations = trendData.value.map((r) => parseFloat(r.utilization))

  const isBar = chartType.value === 'bar'
  const series = isBar
    ? [
        { name: t('productionReport.colPlanOutput'), type: 'bar', barGap: '10%', data: planOutputs, itemStyle: { color: '#909399' } },
        { name: t('productionReport.colActualOutput'), type: 'bar', data: actualOutputs, itemStyle: { color: '#409eff' } },
      ]
    : [
        { name: t('productionReport.colPlanOutput'), type: 'line', smooth: true, data: planOutputs, itemStyle: { color: '#909399' } },
        { name: t('productionReport.colActualOutput'), type: 'line', smooth: true, data: actualOutputs, itemStyle: { color: '#409eff' } },
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
      { name: t('productionReport.colYieldRate'), type: 'line', smooth: true, yAxisIndex: 1, data: yieldRates, itemStyle: { color: '#67c23a' } },
      { name: t('productionReport.colUtilization'), type: 'line', smooth: true, yAxisIndex: 1, data: utilizations, itemStyle: { color: '#e6a23c' } },
    ],
  })
}

/** 图表自适应容器宽度。 */
function resizeChart() {
  chartInstance?.resize()
}

// ========================= 辅助方法 =========================

/** 时间范围映射为天数 */
function timeRangeToDays(range: string): number {
  switch (range) {
    case 'today': return 1
    case 'week': return 7
    case 'month': return 30
    default: return 30
  }
}

/** 自定义日期范围映射为天数 */
function customRangeToDays(range: [Date, Date] | null): number | undefined {
  if (!range) return undefined
  const diffMs = range[1].getTime() - range[0].getTime()
  return Math.max(1, Math.ceil(diffMs / (1000 * 60 * 60 * 24)))
}

/** 状态标签颜色映射 */
function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  const map: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
    completed: 'success',
    producing: 'primary',
    pending: 'warning',
    cancelled: 'danger',
    paused: 'info',
  }
  return map[status] || 'info'
}

// ========================= 计算属性 =========================
const summaryCards = computed<SummaryCard[]>(() => {
  const d = dashboardData.value
  if (!d) return []

  return [
    {
      label: t('productionReport.cardTotalOutput'),
      value: d.total_output.toLocaleString(),
      unit: t('productionReport.unitPiece'),
      trendIcon: Top,
      trendClass: 'trend-up',
    },
    {
      label: t('productionReport.cardPassRate'),
      value: d.pass_rate.toFixed(1),
      unit: '%',
      trendIcon: d.pass_rate >= 98 ? Top : Bottom,
      trendClass: d.pass_rate >= 98 ? 'trend-up' : 'trend-down',
    },
    {
      label: t('productionReport.cardActiveOrders'),
      value: d.active_orders.toString(),
      unit: t('productionReport.unitOrder'),
      trendIcon: Right,
      trendClass: 'trend-stable',
    },
    {
      label: t('productionReport.cardAvgCycle'),
      value: d.avg_cycle_time.toFixed(0),
      unit: t('productionReport.unitMinutes'),
      trendIcon: Right,
      trendClass: 'trend-stable',
    },
  ]
})

// ========================= 请求取消控制 =========================
let currentAbortController: AbortController | null = null

function cancelPendingRequests() {
  if (currentAbortController) {
    currentAbortController.abort()
    currentAbortController = null
  }
}

// ========================= API 调用 =========================
async function fetchDashboard(signal?: AbortSignal) {
  dashboardLoading.value = true
  try {
    const res = await http.get(API_CONFIG.PRODUCTION + '/dashboard', { signal })
    dashboardData.value = res.data?.data ?? null
  } catch (error) {
    if ((error as { name?: string })?.name === 'AbortError') return
    dashboardData.value = null
  } finally {
    dashboardLoading.value = false
  }
}

async function fetchStats(days: number, signal?: AbortSignal) {
  statsLoading.value = true
  try {
    const res = await http.get(API_CONFIG.PRODUCTION + '/stats', { params: { days }, signal })
    const list: StatsItem[] = res.data?.data ?? []
    trendData.value = list.map(item => ({
      date: item.date,
      planOutput: item.plan_output,
      actualOutput: item.actual_output,
      yieldRate: item.yield_rate.toFixed(1) + '%',
      utilization: item.utilization.toFixed(1) + '%',
      achievementRate: Math.min(Math.round(item.achievement_rate), 100),
    }))
  } catch (error) {
    if ((error as { name?: string })?.name === 'AbortError') return
    trendData.value = []
  } finally {
    statsLoading.value = false
  }
}

async function fetchRecords(signal?: AbortSignal) {
  recordsLoading.value = true
  try {
    const res = await http.get(API_CONFIG.PRODUCTION + '/records', { params: { limit: 20 }, signal })
    productionRecords.value = res.data?.data ?? []
  } catch (error) {
    if ((error as { name?: string })?.name === 'AbortError') return
    productionRecords.value = []
  } finally {
    recordsLoading.value = false
  }
}

async function fetchWorkOrders(signal?: AbortSignal) {
  workOrdersLoading.value = true
  try {
    const res = await http.get(API_CONFIG.PRODUCTION + '/work-orders', { params: { limit: 10 }, signal })
    workOrders.value = res.data?.data ?? []
  } catch (error) {
    if ((error as { name?: string })?.name === 'AbortError') return
    workOrders.value = []
  } finally {
    workOrdersLoading.value = false
  }
}

async function fetchAllData() {
  // 取消之前的请求
  cancelPendingRequests()
  
  // 创建新的AbortController
  currentAbortController = new AbortController()
  const signal = currentAbortController.signal
  
  loading.value = true
  const days = timeRange.value === 'custom'
    ? customRangeToDays(customDateRange.value)
    : timeRangeToDays(timeRange.value)

  const promises: Promise<void>[] = [
    fetchDashboard(signal),
    fetchRecords(signal),
    fetchWorkOrders(signal),
  ]
  if (days !== undefined) {
    promises.push(fetchStats(days, signal))
  }

  await Promise.allSettled(promises)
  loading.value = false
}

// ========================= 方法 =========================
function handleTimeRangeChange() {
  fetchAllData()
}

/** 导出当前趋势数据为 CSV 文件（真实导出，非占位）。 */
function handleExport() {
  if (trendData.value.length === 0) {
    ElMessage.warning(t('productionReport.msgExportEmpty'))
    return
  }
  try {
    const header = [
      t('productionReport.colDate'),
      t('productionReport.colPlanOutput'),
      t('productionReport.colActualOutput'),
      t('productionReport.colYieldRate'),
      t('productionReport.colUtilization'),
      t('productionReport.colAchievementRate'),
    ]
    const lines = trendData.value.map((r) =>
      [r.date, r.planOutput, r.actualOutput, r.yieldRate, r.utilization, r.achievementRate + '%'].join(',')
    )
    const csv = '\uFEFF' + [header.join(','), ...lines].join('\n')
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const dateStr = new Date().toISOString().slice(0, 10)
    a.href = url
    a.download = `production_report_${dateStr}.csv`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(t('productionReport.msgExportSuccess'))
  } catch (e: unknown) {
    console.warn('[ProductionReport] export failed:', e)
    ElMessage.error(t('productionReport.msgExportFailed'))
  }
}

// 趋势数据或图表类型变化时重新渲染
watch([trendData, chartType], () => {
  renderChart()
})

// ========================= 生命周期 =========================
onMounted(() => {
  fetchAllData()
  // 等数据加载后渲染图表
  setTimeout(() => renderChart(), 0)
  window.addEventListener('resize', resizeChart)
})

onUnmounted(() => {
  // 组件卸载时取消所有待处理的请求
  cancelPendingRequests()
  window.removeEventListener('resize', resizeChart)
  if (chartInstance) {
    chartInstance.dispose()
    chartInstance = null
  }
})
</script>

<style scoped>
.production-report-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.trend-chart {
  width: 100%;
  height: 340px;
}

/* 汇总卡片 */
.summary-row {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  margin-bottom: 24px;
}

.summary-card {
  text-align: center;
}

.summary-card__header {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  margin-bottom: 12px;
}

.summary-card__label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.summary-card__trend {
  color: var(--success);
}

.summary-card__trend.trend-down {
  color: var(--error);
}

.summary-card__trend.trend-stable {
  color: var(--warning);
}

.summary-card__value {
  font-size: 2rem;
  font-weight: 700;
  color: var(--text-primary);
  line-height: 1.2;
}

.summary-card__unit {
  font-size: 14px;
  color: var(--text-tertiary);
  margin-left: 4px;
}

/* 图表区域 */
.chart-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 16px;
  height: 320px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px dashed var(--border-medium);
}

.chart-placeholder__text {
  margin: 0;
  font-size: 14px;
  color: var(--text-tertiary);
  text-align: center;
  max-width: 400px;
}

.text-warning {
  color: var(--warning);
  font-weight: 500;
}

.text-danger {
  color: var(--error);
  font-weight: 500;
}

/* 响应式 */
@media (max-width: 900px) {
  .summary-row {
    grid-template-columns: repeat(2, 1fr);
  }
}
</style>
