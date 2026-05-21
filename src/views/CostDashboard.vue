<template>
  <div class="cost-dashboard">
    <el-alert
      v-if="budgetExceeded"
      title="预算超限警告"
      type="error"
      :closable="false"
      show-icon
      style="margin-bottom: 16px"
    >
      <div>
        部分预算已达到或超过限额，新任务可能被阻止执行。请尽快调整预算或减少资源消耗。
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
              <span>成本维度分布</span>
              <div>
                <el-select
                  v-model="costDimension"
                  size="small"
                  style="width:120px"
                  @change="loadCostDistribution"
                >
                  <el-option
                    label="按代理"
                    value="agent"
                  />
                  <el-option
                    label="按项目"
                    value="project"
                  />
                  <el-option
                    label="按模型"
                    value="model"
                  />
                  <el-option
                    label="按提供商"
                    value="provider"
                  />
                </el-select>
                <el-button
                  size="small"
                  :loading="loading.pie"
                  circle
                  style="margin-left:4px"
                  @click="loadCostDistribution"
                >
                  <el-icon><Refresh /></el-icon>
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
              <span>成本分类对比</span>
              <div>
                <el-button
                  size="small"
                  :loading="loading.bar"
                  circle
                  @click="loadCostByType"
                >
                  <el-icon><Refresh /></el-icon>
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
              <span>成本趋势分析</span>
              <div>
                <el-select
                  v-model="trendDays"
                  size="small"
                  style="width:100px"
                  @change="loadCostTrend"
                >
                  <el-option
                    label="7天"
                    :value="7"
                  />
                  <el-option
                    label="14天"
                    :value="14"
                  />
                  <el-option
                    label="30天"
                    :value="30"
                  />
                  <el-option
                    label="60天"
                    :value="60"
                  />
                </el-select>
                <el-button
                  size="small"
                  :loading="loading.trend"
                  circle
                  style="margin-left:4px"
                  @click="loadCostTrend"
                >
                  <el-icon><Refresh /></el-icon>
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

    <el-card
      shadow="hover"
      class="alerts-card"
    >
      <template #header>
        <div class="card-header">
          <span>预算告警列表</span>
          <div>
            <el-select
              v-model="alertFilter"
              size="small"
              style="width:100px"
              @change="loadAlerts"
            >
              <el-option
                label="全部"
                value=""
              />
              <el-option
                label="警告"
                value="warning"
              />
              <el-option
                label="超限"
                value="exceeded"
              />
            </el-select>
            <el-button
              size="small"
              :disabled="!hasUnread"
              style="margin-left:4px"
              @click="markAllRead"
            >
              全部已读
            </el-button>
            <el-button
              size="small"
              :loading="loading.alerts"
              circle
              style="margin-left:4px"
              @click="loadAlerts"
            >
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading.alerts"
        :data="alerts"
        style="width: 100%"
        empty-text="暂无告警"
      >
        <el-table-column
          label="紧急度"
          width="80"
        >
          <template #default="{ row }">
            <el-tag
              :type="row.status === 'exceeded' ? 'danger' : 'warning'"
              size="small"
            >
              {{ row.status === 'exceeded' ? '超限' : '警告' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="created_at"
          label="时间"
          width="180"
        >
          <template #default="{ row }">
            {{ formatSecondsTimestamp(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="level"
          label="层级"
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
          label="范围"
          width="140"
        />
        <el-table-column
          prop="resource_type"
          label="资源类型"
          width="120"
        />
        <el-table-column
          label="使用率"
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
          label="信息"
          min-width="300"
          show-overflow-tooltip
        />
        <el-table-column
          label="状态"
          width="80"
        >
          <template #default="{ row }">
            <el-tag
              size="small"
              :type="row.is_read ? 'info' : 'warning'"
            >
              {{ row.is_read ? '已读' : '未读' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          label="操作"
          width="140"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              :disabled="row.is_read"
              @click="markRead(row.id)"
            >
              已读
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="deleteAlert(row.id)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-card
      v-if="suggestions.length > 0"
      shadow="hover"
      class="optimization-card"
    >
      <template #header>
        <div class="card-header">
          <span>智能成本优化建议</span>
          <el-button
            size="small"
            :loading="loading.suggestions"
            @click="loadSuggestions"
          >
            <el-icon style="margin-right:4px">
              <Refresh />
            </el-icon>刷新
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
                {{ s.priority === 'high' ? '高优先' : '中优先' }}
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
                <span class="stat-label">当前成本</span>
              </div>
              <div class="stat">
                <span class="stat-value text-success">{{ formatCost(s.estimated_savings) }}</span>
                <span class="stat-label">预估节省</span>
              </div>
              <div class="stat">
                <span class="stat-value text-warning">{{ s.savings_percentage.toFixed(0) }}%</span>
                <span class="stat-label">节省比例</span>
              </div>
            </div>
            <p class="suggestion-reco">
              <strong>建议：</strong>{{ s.recommendation }}
            </p>
          </el-card>
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>

<script lang="ts" setup>
import { ref, onMounted, onUnmounted, nextTick, computed } from 'vue'
import axios from 'axios'
import * as echarts from 'echarts'
import { Refresh } from '@element-plus/icons-vue'
import { formatSecondsTimestamp } from '@/utils/formatters'

const API_BASE = '/api/v1/cost-budget'

const budgetProgresses = ref<any[]>([])
const alerts = ref<any[]>([])
const suggestions = ref<any[]>([])
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

const budgetExceeded = computed(() => alerts.value.some((a: any) => a.status === 'exceeded' && !a.is_read))
const hasUnread = computed(() => alerts.value.some((a: any) => !a.is_read))

function formatCost(value: number): string {
  if (value >= 1) return `$${value.toFixed(2)}`
  if (value >= 0.01) return `$${value.toFixed(4)}`
  return `$${value.toFixed(6)}`
}

function budgetLevelLabel(level: string): string {
  const map: Record<string, string> = {
    global: '全局',
    project: '项目',
    agent: '代理',
    task: '任务',
  }
  return map[level] || level
}

function suggestionCategory(cat: string): string {
  const map: Record<string, string> = {
    model_optimization: '模型优化',
    resource_optimization: '资源优化',
    training_efficiency: '训练效率',
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
  const map: Record<string, string> = { ok: '正常', warning: '警告', exceeded: '超限', disabled: '禁用' }
  return map[status] || status
}

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return n.toFixed(1)
}

async function loadBudgetProgress() {
  try {
    const res = await axios.get(`${API_BASE}/policies`)
    if (!res.data?.ok) return
    const policies = res.data.data || []

    budgetProgresses.value = policies.map((p: any) => ({
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
  } catch (e) {
    console.error('Failed to load budget progress:', e)
  }
}

async function loadCostDistribution() {
  loading.value.pie = true
  try {
    const res = await axios.get(`${API_BASE}/summary`, {
      params: { dimension: costDimension.value }
    })
    if (!res.data?.ok) return
    const data = res.data.data || []

    const names = data.map((d: any) => d.scope_id || '(unknown)')
    const values = data.map((d: any) => d.total_cost || 0)

    if (pieChart) {
      pieChart.setOption({
        tooltip: {
          trigger: 'item',
          formatter: (params: any) =>
            `${params.name}: $${params.value.toFixed(4)} (${params.percent}%)`,
        },
        series: [{
          type: 'pie',
          radius: ['45%', '75%'],
          center: ['50%', '50%'],
          roseType: 'area',
          itemStyle: { borderRadius: 6, borderColor: '#fff', borderWidth: 2 },
          data: names.map((n: string, i: number) => ({ name: n, value: values[i] })),
          label: { formatter: '{b}\n{d}%' },
        }],
      })
    }
  } catch (e) {
    console.error('Failed to load cost distribution:', e)
  } finally {
    loading.value.pie = false
  }
}

async function loadCostByType() {
  loading.value.bar = true
  try {
    const res = await axios.get(`${API_BASE}/summary`, {
      params: { dimension: 'agent' }
    })
    if (!res.data?.ok) return
    const data = res.data.data || []

    const gpuTimeVals = data.map((d: any) => d.gpu_time_cost || 0)
    const gpuMemVals = data.map((d: any) => d.gpu_memory_cost || 0)
    const apiCallVals = data.map((d: any) => d.api_calls_cost || 0)
    const dataTransferVals = data.map((d: any) => d.data_transfer_cost || 0)
    const labels = data.map((d: any) => d.scope_id || '(unknown)')

    if (barChart) {
      barChart.setOption({
        tooltip: {
          trigger: 'axis',
          axisPointer: { type: 'shadow' },
        },
        legend: { data: ['GPU时间', 'GPU内存', 'API调用', '数据传输'] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: labels, axisLabel: { rotate: 30, fontSize: 11 } },
        yAxis: { type: 'value', name: '成本 ($)' },
        series: [
          { name: 'GPU时间', type: 'bar', stack: 'total', data: gpuTimeVals, itemStyle: { color: '#409EFF' } },
          { name: 'GPU内存', type: 'bar', stack: 'total', data: gpuMemVals, itemStyle: { color: '#67C23A' } },
          { name: 'API调用', type: 'bar', stack: 'total', data: apiCallVals, itemStyle: { color: '#E6A23C' } },
          { name: '数据传输', type: 'bar', stack: 'total', data: dataTransferVals, itemStyle: { color: '#F56C6C' } },
        ],
      })
    }
  } catch (e) {
    console.error('Failed to load cost by type:', e)
  } finally {
    loading.value.bar = false
  }
}

async function loadCostTrend() {
  loading.value.trend = true
  try {
    const res = await axios.get(`${API_BASE}/trend`, {
      params: { days: trendDays.value, interval_hours: 24 }
    })
    if (!res.data?.ok) return
    const data = res.data.data || []

    const times = data.map((d: any) => {
      const dt = new Date(d.timestamp * 1000)
      return `${dt.getMonth() + 1}/${dt.getDate()}`
    })
    const totalCosts = data.map((d: any) => d.total_cost || 0)
    const gpuTimeCosts = data.map((d: any) => d.gpu_time_cost || 0)
    const gpuMemCosts = data.map((d: any) => d.gpu_memory_cost || 0)
    const apiCallCosts = data.map((d: any) => d.api_calls_cost || 0)

    if (trendChart) {
      trendChart.setOption({
        tooltip: { trigger: 'axis' },
        legend: { data: ['总成本', 'GPU时间', 'GPU内存', 'API调用'] },
        grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
        xAxis: { type: 'category', data: times, boundaryGap: false },
        yAxis: { type: 'value', name: '成本 ($)' },
        series: [
          {
            name: '总成本', type: 'line', smooth: true,
            data: totalCosts, lineStyle: { width: 3, color: '#409EFF' },
            areaStyle: { color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
              { offset: 0, color: 'rgba(64,158,255,0.3)' },
              { offset: 1, color: 'rgba(64,158,255,0.05)' },
            ]) },
          },
          { name: 'GPU时间', type: 'line', smooth: true, data: gpuTimeCosts, lineStyle: { color: '#67C23A' } },
          { name: 'GPU内存', type: 'line', smooth: true, data: gpuMemCosts, lineStyle: { color: '#E6A23C' } },
          { name: 'API调用', type: 'line', smooth: true, data: apiCallCosts, lineStyle: { color: '#F56C6C' } },
        ],
      })
    }
  } catch (e) {
    console.error('Failed to load cost trend:', e)
  } finally {
    loading.value.trend = false
  }
}

async function loadAlerts() {
  loading.value.alerts = true
  try {
    const params: any = { limit: 100 }
    if (alertFilter.value) params.status = alertFilter.value
    const res = await axios.get(`${API_BASE}/alerts`, { params })
    if (!res.data?.ok) return
    alerts.value = res.data.data || []
  } catch (e) {
    console.error('Failed to load alerts:', e)
  } finally {
    loading.value.alerts = false
  }
}

async function loadSuggestions() {
  loading.value.suggestions = true
  try {
    const res = await axios.get(`${API_BASE}/suggestions`)
    if (!res.data?.ok) return
    suggestions.value = res.data.data || []
  } catch (e) {
    console.error('Failed to load suggestions:', e)
  } finally {
    loading.value.suggestions = false
  }
}

async function markRead(id: number) {
  try {
    await axios.post(`${API_BASE}/alerts/${id}/read`)
    const alert = alerts.value.find((a: any) => a.id === id)
    if (alert) alert.is_read = 1
  } catch (e) {
    console.error('Failed to mark read:', e)
  }
}

async function markAllRead() {
  try {
    await axios.post(`${API_BASE}/alerts/read-all`)
    alerts.value.forEach((a: any) => (a.is_read = 1))
  } catch (e) {
    console.error('Failed to mark all read:', e)
  }
}

async function deleteAlert(id: number) {
  try {
    await axios.delete(`${API_BASE}/alerts/${id}`)
    alerts.value = alerts.value.filter((a: any) => a.id !== id)
  } catch (e) {
    console.error('Failed to delete alert:', e)
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
  padding: 0;
}

.budget-status-row {
  margin-bottom: 16px;
}

.budget-card {
  text-align: center;
}

.budget-card.budget-warning {
  border-color: #e6a23c;
}

.budget-card.budget-exceeded {
  border-color: #f56c6c;
}

.budget-card-title {
  font-size: 14px;
  font-weight: 600;
  color: #606266;
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
  color: #409EFF;
  font-weight: 600;
}

.budget-card-detail .separator {
  color: #C0C4CC;
  margin: 0 4px;
}

.budget-card-detail .limit {
  color: #909399;
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

.alerts-card {
  margin-bottom: 16px;
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
  color: #303133;
}

.suggestion-desc {
  font-size: 13px;
  color: #606266;
  margin-bottom: 12px;
  line-height: 1.6;
}

.suggestion-stats {
  display: flex;
  gap: 16px;
  margin-bottom: 12px;
  padding: 8px 0;
  border-top: 1px solid #EBEEF5;
  border-bottom: 1px solid #EBEEF5;
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
  color: #909399;
  margin-top: 2px;
}

.suggestion-reco {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.text-danger { color: #F56C6C; }
.text-success { color: #67C23A; }
.text-warning { color: #E6A23C; }
</style>
