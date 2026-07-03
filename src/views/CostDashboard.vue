<template>
  <div class="cost-dashboard">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('costDashboard.pageTitle') }}</h1>
      </div>
    </div>

    <el-alert
      v-if="budgetExceeded"
      :title="t('costDashboard.alertBudgetExceededTitle')"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <div>
        {{ t('costDashboard.alertBudgetExceededDesc') }}
      </div>
    </el-alert>

    <el-row
      :gutter="16"
      class="budget-status-row"
    >
      <el-col
        v-for="bp in budgetProgresses"
        :key="bp.key"
        :span="6"
      >
        <el-card
          shadow="hover"
          class="budget-card"
          :class="'budget-' + bp.status"
        >
          <div class="budget-card-title">
            {{ bp.label }}
          </div>
          <el-progress
            :percentage="bp.percentage"
            :status="bp.progressStatus"
            :stroke-width="8"
          />
          <div class="budget-card-detail">
            <span class="used">{{ bp.usedStr }}</span>
            <span class="separator">/</span>
            <span class="limit">{{ bp.limitStr }}</span>
          </div>
          <el-tag
            :type="bp.tagType"
            size="small"
          >
            {{ bp.statusLabel }}
          </el-tag>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card
          shadow="hover"
          class="chart-card"
        >
          <template #header>
            <div class="card-header">
              <span>{{ t('costDashboard.chartCostDistribution') }}</span>
              <div>
                <el-select
                  v-model="costDimension"
                  size="small"
                  style="width:120px"
                  @change="loadCostDistribution"
                >
                  <el-option
                    :label="t('costDashboard.dimensionAgent')"
                    value="agent"
                  />
                  <el-option
                    :label="t('costDashboard.dimensionProject')"
                    value="project"
                  />
                  <el-option
                    :label="t('costDashboard.dimensionModel')"
                    value="model"
                  />
                  <el-option
                    :label="t('costDashboard.dimensionProvider')"
                    value="provider"
                  />
                </el-select>
                <el-button
                  size="small"
                  :loading="loading.pie"
                  circle
                  :aria-label="t('costDashboard.refreshCostDistributionAriaLabel')"
                  :title="t('costDashboard.refreshCostDistributionTitle')"
                  style="margin-left:4px"
                  @click="loadCostDistribution"
                >
                  <el-icon :size="16">
                    <Refresh />
                  </el-icon>
                </el-button>
              </div>
            </div>
          </template>
          <div
            ref="pieChartRef"
            class="chart-container"
          />
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card
          shadow="hover"
          class="chart-card"
        >
          <template #header>
            <div class="card-header">
              <span>{{ t('costDashboard.chartCostByType') }}</span>
              <div>
                <el-button
                  size="small"
                  :loading="loading.bar"
                  circle
                  :aria-label="t('costDashboard.refreshCostByTypeAriaLabel')"
                  :title="t('costDashboard.refreshCostByTypeTitle')"
                  @click="loadCostByType"
                >
                  <el-icon :size="16">
                    <Refresh />
                  </el-icon>
                </el-button>
              </div>
            </div>
          </template>
          <div
            ref="barChartRef"
            class="chart-container"
          />
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="24">
        <el-card
          shadow="hover"
          class="chart-card"
        >
          <template #header>
            <div class="card-header">
              <span>{{ t('costDashboard.chartCostTrend') }}</span>
              <div>
                <el-select
                  v-model="trendDays"
                  size="small"
                  style="width:100px"
                  @change="loadCostTrend"
                >
                  <el-option
                    :label="t('costDashboard.days7')"
                    :value="7"
                  />
                  <el-option
                    :label="t('costDashboard.days14')"
                    :value="14"
                  />
                  <el-option
                    :label="t('costDashboard.days30')"
                    :value="30"
                  />
                  <el-option
                    :label="t('costDashboard.days60')"
                    :value="60"
                  />
                </el-select>
                <el-button
                  size="small"
                  :loading="loading.trend"
                  circle
                  :aria-label="t('costDashboard.refreshCostTrendAriaLabel')"
                  :title="t('costDashboard.refreshCostTrendTitle')"
                  style="margin-left:4px"
                  @click="loadCostTrend"
                >
                  <el-icon :size="16">
                    <Refresh />
                  </el-icon>
                </el-button>
              </div>
            </div>
          </template>
          <div
            ref="trendChartRef"
            class="chart-container chart-trend"
          />
        </el-card>
      </el-col>
    </el-row>

    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">{{ t('costDashboard.alertListTitle') }}</span>
        <div>
          <el-select
            v-model="alertFilter"
            size="small"
            style="width:100px"
            @change="loadAlerts"
          >
            <el-option
              :label="t('costDashboard.filterAll')"
              value=""
            />
            <el-option
              :label="t('costDashboard.filterWarning')"
              value="warning"
            />
            <el-option
              :label="t('costDashboard.filterExceeded')"
              value="exceeded"
            />
          </el-select>
          <el-button
            size="small"
            :disabled="!hasUnread"
            style="margin-left:4px"
            @click="markAllRead"
          >
            {{ t('costDashboard.btnMarkAllRead') }}
          </el-button>
          <el-button
            size="small"
            :loading="loading.alerts"
            circle
            :aria-label="t('costDashboard.refreshBudgetAlertsAriaLabel')"
            :title="t('costDashboard.refreshBudgetAlertsTitle')"
            style="margin-left:4px"
            @click="loadAlerts"
          >
            <el-icon :size="16">
              <Refresh />
            </el-icon>
          </el-button>
        </div>
      </div>

      <el-table
        v-loading="loading.alerts"
        :data="alerts"
        style="width: 100%"
        :empty-text="t('costDashboard.emptyAlerts')"
        stripe
      >
        <el-table-column
          :label="t('costDashboard.colUrgency')"
          width="80"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'exceeded' ? 'danger' : 'warning'"
              size="small"
            >
              {{ row.status === 'exceeded' ? t('costDashboard.statusExceeded') : t('costDashboard.statusWarning') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="created_at"
          :label="t('costDashboard.colTime')"
          width="180"
        >
          <template #default="{ row }">
            {{ formatSecondsTimestamp(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="level"
          :label="t('costDashboard.colLevel')"
          width="80"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              type="info"
            >
              {{ budgetLevelLabel(row.level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="scope_id"
          :label="t('costDashboard.colScope')"
          width="140"
        />
        <el-table-column
          prop="resource_type"
          :label="t('costDashboard.colResourceType')"
          width="120"
        />
        <el-table-column
          :label="t('costDashboard.colUsageRatio')"
          width="120"
        >
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round((row.usage_ratio || 0) * 100)"
              :status="row.status === 'exceeded' ? 'exception' : 'warning'"
              :stroke-width="6"
            />
          </template>
        </el-table-column>
        <el-table-column
          prop="message"
          :label="t('costDashboard.colMessage')"
          min-width="300"
          show-overflow-tooltip
        />
        <el-table-column
          :label="t('costDashboard.colStatus')"
          width="80"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.is_read ? 'info' : 'warning'"
            >
              {{ row.is_read ? t('costDashboard.statusRead') : t('costDashboard.statusUnread') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          :label="t('costDashboard.colActions')"
          width="140"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              :disabled="row.is_read"
              @click="markRead(row.id)"
            >
              {{ t('costDashboard.btnMarkRead') }}
            </el-button>
            <el-button
              size="small"
              type="danger"
              text
              @click="deleteAlert(row.id)"
            >
              {{ t('costDashboard.btnDelete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <el-card
      v-if="suggestions.length > 0"
      shadow="hover"
      class="optimization-card"
    >
      <template #header>
        <div class="card-header">
          <span>{{ t('costDashboard.suggestionsTitle') }}</span>
          <el-button
            size="small"
            :loading="loading.suggestions"
            @click="loadSuggestions"
          >
            <el-icon style="margin-right:4px">
              <Refresh />
            </el-icon>{{ t('costDashboard.btnRefresh') }}
          </el-button>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col
          v-for="s in suggestions"
          :key="s.suggestion_id"
          :span="8"
        >
          <el-card
            shadow="never"
            class="suggestion-card"
          >
            <div class="suggestion-header">
              <el-tag
                :type="s.priority === 'high' ? 'danger' : 'warning'"
                size="small"
              >
                {{ s.priority === 'high' ? t('costDashboard.priorityHigh') : t('costDashboard.priorityMedium') }}
              </el-tag>
              <el-tag
                size="small"
                type="info"
                style="margin-left:4px"
              >
                {{ suggestionCategory(s.category) }}
              </el-tag>
            </div>
            <h4 class="suggestion-title">
              {{ s.title }}
            </h4>
            <p class="suggestion-desc">
              {{ s.description }}
            </p>
            <div class="suggestion-stats">
              <div class="stat">
                <span class="stat-value text-danger">{{ formatCost(s.current_cost) }}</span>
                <span class="stat-label">{{ t('costDashboard.statCurrentCost') }}</span>
              </div>
              <div class="stat">
                <span class="stat-value text-success">{{ formatCost(s.estimated_savings) }}</span>
                <span class="stat-label">{{ t('costDashboard.statEstimatedSavings') }}</span>
              </div>
              <div class="stat">
                <span class="stat-value text-warning">{{ s.savings_percentage.toFixed(0) }}%</span>
                <span class="stat-label">{{ t('costDashboard.statSavingsPercentage') }}</span>
              </div>
            </div>
            <p class="suggestion-reco">
              <strong>{{ t('costDashboard.recommendationLabel') }}</strong>{{ s.recommendation }}
            </p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import http from '@/utils/http'
import { formatSecondsTimestamp } from '@/utils/formatters'
import { API_CONFIG, buildApiPath } from '@/config/api'

const { t } = useI18n()

// 类型定义
interface BudgetProgress {
  key: string
  label: string
  percentage: number
  progressStatus?: 'success' | 'warning' | 'exception'
  used: number
  limit: number
  usedStr: string
  limitStr: string
  status: string
  tagType: 'success' | 'warning' | 'danger' | 'info'
  statusLabel: string
}

interface CostAlert {
  id: number
  created_at: number
  level: string
  scope_id: string
  resource_type: string
  usage_ratio: number
  status: 'warning' | 'exceeded'
  message: string
  is_read: 0 | 1
}

interface CostSuggestion {
  suggestion_id: string
  priority: 'high' | 'medium'
  category: string
  title: string
  description: string
  current_cost: number
  estimated_savings: number
  savings_percentage: number
  recommendation: string
}

interface CostSummaryItem {
  scope_id: string
  total_cost: number
  gpu_time_cost: number
  gpu_memory_cost: number
  api_calls_cost: number
  data_transfer_cost: number
}

interface CostTrendItem {
  timestamp: number
  total_cost: number
  gpu_time_cost: number
  gpu_memory_cost: number
  api_calls_cost: number
}

const budgetProgresses = ref<BudgetProgress[]>([])
const alerts = ref<CostAlert[]>([])
const suggestions = ref<CostSuggestion[]>([])
const alertFilter = ref('')
const costDimension = ref('agent')
const trendDays = ref(7)

const pieChartRef = ref<HTMLDivElement>()
const barChartRef = ref<HTMLDivElement>()
const trendChartRef = ref<HTMLDivElement>()
let pieChart: echarts.ECharts | null = null
let barChart: echarts.ECharts | null = null
let trendChart: echarts.ECharts | null = null

const loading = ref({
  pie: false,
  bar: false,
  trend: false,
  alerts: false,
  suggestions: false,
})

const budgetExceeded = computed(() => alerts.value.some((a) => a.status === 'exceeded' && !a.is_read))
const hasUnread = computed(() => alerts.value.some((a) => !a.is_read))

function formatCost(value: number): string {
  if (value >= 1) return `$${value.toFixed(2)}`
  if (value >= 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(6)}`
}

function budgetLevelLabel(level: string): string {
  const map: Record<string, string> = {
    global: t('costDashboard.levelGlobal'),
    project: t('costDashboard.levelProject'),
    agent: t('costDashboard.levelAgent'),
    task: t('costDashboard.levelTask'),
  }
  return map[level] || level
}

function suggestionCategory(cat: string): string {
  const map: Record<string, string> = {
    model_optimization: t('costDashboard.categoryModelOptimization'),
    resource_optimization: t('costDashboard.categoryResourceOptimization'),
    training_efficiency: t('costDashboard.categoryTrainingEfficiency'),
  }
  return map[cat] || cat
}

function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'ok') return 'success'
  if (status === 'warning') return 'warning'
  if (status === 'exceeded') return 'danger'
  return 'info'
}

function formatStatusLabel(status: string): string {
  const map: Record<string, string> = {
    ok: t('costDashboard.budgetStatusOk'),
    warning: t('costDashboard.budgetStatusWarning'),
    exceeded: t('costDashboard.budgetStatusExceeded'),
    disabled: t('costDashboard.budgetStatusDisabled'),
  }
  return map[status] || status
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toFixed(1)
}

async function loadBudgetProgress() {
  try {
    const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/policies'))
    if (!res.data?.ok) return
    const policies = res.data.data || []

    budgetProgresses.value = policies.map((p: {
      level: string
      scope_id: string
      resource_type: string
      usage_ratio: number
      status: string
      current_usage: number
      limit: number
    }) => ({
      key: `${p.level}:${p.scope_id}:${p.resource_type}`,
      label: `${budgetLevelLabel(p.level)} · ${p.resource_type}`,
      percentage: Math.min(Math.round((p.usage_ratio || 0) * 100), 100),
      progressStatus: p.status === 'exceeded' ? 'exception' : p.status === 'warning' ? 'warning' : undefined,
      used: p.current_usage,
      limit: p.limit,
      usedStr: formatNumber(p.current_usage),
      limitStr: formatNumber(p.limit),
      status: p.status,
      tagType: statusTagType(p.status),
      statusLabel: formatStatusLabel(p.status),
    }))
  } catch {
    // 静默处理，用户界面已有 loading 状态
  }
}

async function loadCostDistribution() {
  loading.value.pie = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/summary'), {
      params: { dimension: costDimension.value }
    })
    if (!res.data?.ok) return
    const data: CostSummaryItem[] = res.data.data || []

    const names = data.map((d) => d.scope_id || '(unknown)')
    const values = data.map((d) => d.total_cost || 0)

    if (pieChart) {
      pieChart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: (params: { name: string; value: number; percent: number }) =>
            `${params.name}: $${params.value.toFixed(4)} (${params.percent}%)`,
        },
        series: [{
          type: 'pie',
          radius: ['45%', '75%'],
          center: ['50%', '50%'],
          roseType: 'area',
          itemStyle: { borderRadius: 6, borderColor: 'var(--bg-card)', borderWidth: 2 },
          data: names.map((n: string, i: number) => ({ name: n, value: values[i] })),
          label: { formatter: '{b}\n{d}%' },
        }],
      })
    }
  } catch {
    // 静默处理
  } finally {
    loading.value.pie = false
  }
}

async function loadCostByType() {
  loading.value.bar = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/summary'), {
      params: { dimension: 'agent' }
    })
    if (!res.data?.ok) return
    const data: CostSummaryItem[] = res.data.data || []

    const gpuTimeVals = data.map((d) => d.gpu_time_cost || 0)
    const gpuMemVals = data.map((d) => d.gpu_memory_cost || 0)
    const apiCallVals = data.map((d) => d.api_calls_cost || 0)
    const dataTransferVals = data.map((d) => d.data_transfer_cost || 0)
    const labels = data.map((d) => d.scope_id || '(unknown)')

    if (barChart) {
      barChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
        },
        legend: { data: [t('costDashboard.seriesGpuTime'), t('costDashboard.seriesGpuMemory'), t('costDashboard.seriesApiCalls'), t('costDashboard.seriesDataTransfer')] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { rotate: 30, fontSize: 11 } },
        yAxis: { type: 'value', name: t('costDashboard.chartYAxisName') },
        series: [
          { name: t('costDashboard.seriesGpuTime'), type: 'bar', stack: 'total', data: gpuTimeVals, itemStyle: { color: 'var(--accent-primary)' } },
          { name: t('costDashboard.seriesGpuMemory'), type: 'bar', stack: 'total', data: gpuMemVals, itemStyle: { color: 'var(--success)' } },
          { name: t('costDashboard.seriesApiCalls'), type: 'bar', stack: 'total', data: apiCallVals, itemStyle: { color: 'var(--warning)' } },
          { name: t('costDashboard.seriesDataTransfer'), type: 'bar', stack: 'total', data: dataTransferVals, itemStyle: { color: 'var(--error)' } },
        ],
      })
    }
  } catch {
    // 静默处理
  } finally {
    loading.value.bar = false
  }
}

async function loadCostTrend() {
  loading.value.trend = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/trend'), {
      params: { days: trendDays.value, interval_hours: 24 }
    })
    if (!res.data?.ok) return
    const data: CostTrendItem[] = res.data.data || []

    const times = data.map((d) => {
      const dt = new Date(d.timestamp * 1000)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    })
    const totalCosts = data.map((d) => d.total_cost || 0)
    const gpuTimeCosts = data.map((d) => d.gpu_time_cost || 0)
    const gpuMemCosts = data.map((d) => d.gpu_memory_cost || 0)
    const apiCallCosts = data.map((d) => d.api_calls_cost || 0)

    if (trendChart) {
      trendChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: [t('costDashboard.seriesTotalCost'), t('costDashboard.seriesGpuTime'), t('costDashboard.seriesGpuMemory'), t('costDashboard.seriesApiCalls')] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: times, boundaryGap: false },
        yAxis: { type: 'value', name: t('costDashboard.chartYAxisName') },
        series: [
          {
            name: t('costDashboard.seriesTotalCost'), type: 'line', smooth: true,
            data: totalCosts, lineStyle: { width: 3, color: 'var(--accent-primary)' },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(64,158,255,0.3)' },
              { offset: 1, color: 'rgba(64,158,255,0.05)' },
            ]) },
          },
          { name: t('costDashboard.seriesGpuTime'), type: 'line', smooth: true, data: gpuTimeCosts, lineStyle: { color: 'var(--success)' } },
          { name: t('costDashboard.seriesGpuMemory'), type: 'line', smooth: true, data: gpuMemCosts, lineStyle: { color: 'var(--warning)' } },
          { name: t('costDashboard.seriesApiCalls'), type: 'line', smooth: true, data: apiCallCosts, lineStyle: { color: 'var(--error)' } },
        ],
      })
    }
  } catch {
    // 静默处理
  } finally {
    loading.value.trend = false
  }
}

async function loadAlerts() {
  loading.value.alerts = true
  try {
    const params: Record<string, string | number> = { limit: 100 }
    if (alertFilter.value) params.status = alertFilter.value
    const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/alerts'), { params })
    if (!res.data?.ok) return
    alerts.value = res.data.data || []
  } catch {
    // 静默处理
  } finally {
    loading.value.alerts = false
  }
}

async function loadSuggestions() {
  loading.value.suggestions = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/suggestions'))
    if (!res.data?.ok) return
    suggestions.value = res.data.data || []
  } catch {
    // 静默处理
  } finally {
    loading.value.suggestions = false
  }
}

async function markRead(id: number) {
  try {
    await http.post(buildApiPath(API_CONFIG.COST_BUDGET, `/alerts/${id}/read`))
    const alert = alerts.value.find((a) => a.id === id)
    if (alert) alert.is_read = 1
  } catch {
    // 静默处理
  }
}

async function markAllRead() {
  try {
    await http.post(buildApiPath(API_CONFIG.COST_BUDGET, '/alerts/read-all'))
    alerts.value.forEach((a) => (a.is_read = 1))
  } catch {
    // 静默处理
  }
}

async function deleteAlert(id: number) {
  try {
    await http.delete(buildApiPath(API_CONFIG.COST_BUDGET, `/alerts/${id}`))
    alerts.value = alerts.value.filter((a) => a.id !== id)
  } catch {
    // 静默处理
  }
}

function initCharts() {
  if (pieChartRef.value) {
    pieChart = echarts.init(pieChartRef.value)
  }
  if (barChartRef.value) {
    barChart = echarts.init(barChartRef.value)
  }
  if (trendChartRef.value) {
    trendChart = echarts.init(trendChartRef.value)
  }
}

function resizeCharts() {
  pieChart?.resize()
  barChart?.resize()
  trendChart?.resize()
}

async function loadAll() {
  await Promise.all([
    loadBudgetProgress(),
    loadCostDistribution(),
    loadCostByType(),
    loadCostTrend(),
    loadAlerts(),
    loadSuggestions(),
  ])
}

onMounted(() => {
  nextTick(() => {
    initCharts()
    loadAll()
    window.addEventListener('resize', resizeCharts)
  })
})

onUnmounted(() => {
  pieChart?.dispose()
  barChart?.dispose()
  trendChart?.dispose()
  window.removeEventListener('resize', resizeCharts)
})
</script>

<style scoped>
.cost-dashboard {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

.budget-status-row {
  margin-bottom: 16px;
}

.budget-card {
  text-align: center;
}

.budget-card.budget-warning {
  border-color: var(--warning);
}

.budget-card.budget-exceeded {
  border-color: var(--error);
}

.budget-card-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.budget-card-detail {
  margin: 8px 0;
  font-size: 13px;
}

.budget-card-detail .used {
  color: var(--accent-primary);
  font-weight: 600;
}

.budget-card-detail .separator {
  color: var(--border-medium);
  margin: 0 4px;
}

.budget-card-detail .limit {
  color: var(--text-tertiary);
}

.chart-card {
  margin-bottom: 16px;
}

.chart-container {
  width: 100%;
  height: 320px;
}

.chart-trend {
  height: 280px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.optimization-card {
  margin-bottom: 16px;
}

.suggestion-card {
  margin-bottom: 8px;
}

.suggestion-header {
  margin-bottom: 8px;
}

.suggestion-title {
  margin: 8px 0;
  font-size: 15px;
  color: var(--text-primary);
}

.suggestion-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin-bottom: 12px;
  line-height: 1.6;
}

.suggestion-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px 0;
  border-top: 1px solid var(--border-light);
  border-bottom: 1px solid var(--border-light);
}

.suggestion-stats .stat {
  flex: 1;
  text-align: center;
}

.suggestion-stats .stat-value {
  display: block;
  font-size: 16px;
  font-weight: 700;
}

.suggestion-stats .stat-label {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.suggestion-reco {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.text-danger { color: var(--error); }
.text-success { color: var(--success); }
.text-warning { color: var(--warning); }
</style>
