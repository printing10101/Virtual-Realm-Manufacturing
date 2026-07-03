<template>
  <div class="home-page">
    <!-- Page Header -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('home.pageTitle') }}</h1>
      </div>
    </div>

    <!-- 1. Welcome Banner -->
    <section class="welcome-banner">
      <div class="banner-content">
        <div class="banner-text">
          <h2>{{ greeting }}{{ t('home.greetingOperator') }}</h2>
          <p class="banner-date">
            {{ currentDateTime }}
          </p>
        </div>
      </div>
      <div class="banner-illustration">
        <svg
          viewBox="0 0 120 120"
          class="banner-svg"
        >
          <rect
            x="15"
            y="50"
            width="90"
            height="55"
            rx="6"
            fill="rgba(255,255,255,0.15)"
          />
          <rect
            x="25"
            y="35"
            width="25"
            height="20"
            rx="3"
            fill="rgba(255,255,255,0.2)"
          />
          <rect
            x="55"
            y="25"
            width="25"
            height="30"
            rx="3"
            fill="rgba(255,255,255,0.25)"
          />
          <rect
            x="25"
            y="75"
            width="70"
            height="8"
            rx="2"
            fill="rgba(255,255,255,0.1)"
          />
          <rect
            x="25"
            y="88"
            width="70"
            height="8"
            rx="2"
            fill="rgba(255,255,255,0.1)"
          />
          <circle
            cx="95"
            cy="30"
            r="12"
            fill="none"
            stroke="rgba(255,255,255,0.4)"
            stroke-width="2"
          />
          <circle
            cx="95"
            cy="30"
            r="5"
            fill="rgba(255,255,255,0.3)"
          />
          <line
            x1="95"
            y1="15"
            x2="95"
            y2="20"
            stroke="rgba(255,255,255,0.4)"
            stroke-width="2"
          />
          <line
            x1="95"
            y1="40"
            x2="95"
            y2="45"
            stroke="rgba(255,255,255,0.4)"
            stroke-width="2"
          />
          <line
            x1="80"
            y1="30"
            x2="85"
            y2="30"
            stroke="rgba(255,255,255,0.4)"
            stroke-width="2"
          />
          <line
            x1="105"
            y1="30"
            x2="110"
            y2="30"
            stroke="rgba(255,255,255,0.4)"
            stroke-width="2"
          />
          <circle
            cx="35"
            cy="22"
            r="5"
            fill="rgba(255,255,255,0.15)"
          />
          <circle
            cx="40"
            cy="15"
            r="7"
            fill="rgba(255,255,255,0.1)"
          />
          <circle
            cx="38"
            cy="7"
            r="4"
            fill="rgba(255,255,255,0.06)"
          />
        </svg>
      </div>
    </section>

    <!-- 2. Time Range Filter -->
    <section class="time-filter">
      <div class="filter-group">
        <button
          v-for="range in timeRanges"
          :key="range.key"
          :class="['filter-btn', { active: activeRange === range.key }]"
          @click="activeRange = range.key"
        >
          {{ range.label }}
        </button>
      </div>
    </section>

    <!-- 3. KPI Cards -->
    <div class="stats-row">
      <div
        v-for="kpi in kpiCards"
        :key="kpi.title"
        class="stat-card"
      >
        <div
          class="stat-card__icon"
          :style="{ background: kpi.iconBg }"
        >
          <el-icon
            :size="24"
            :style="{ color: kpi.color }"
          >
            <component :is="kpi.icon" />
          </el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__label">{{ kpi.title }}</span>
          <span class="stat-card__value">{{ kpi.value }}</span>
          <span
            class="stat-card__trend"
            :class="kpi.isPositive ? 'stat-card__trend--up' : 'stat-card__trend--down'"
          >
            {{ kpi.isPositive ? '↑' : '↓' }} {{ kpi.change }}
          </span>
        </div>
      </div>
    </div>

    <!-- 4. Two-column Layout -->
    <section class="content-row">
      <!-- Left: Production Progress Table -->
      <div class="content-card">
        <div class="content-card__header">
          <span class="content-card__title">{{ t('home.cardProductionProgress') }}</span>
          <el-tag
            v-if="tasksStore.error"
            type="warning"
            size="small"
            effect="plain"
          >
            {{ t('home.msgDataLoadFailed') }}
          </el-tag>
        </div>
        <div class="content-card__body">
          <el-table
            :data="displayWorkOrders"
            style="width: 100%"
            stripe
          >
            <el-table-column
              prop="orderNo"
              :label="t('home.labelOrderNo')"
              width="130"
            />
            <el-table-column
              prop="productName"
              :label="t('home.labelProductName')"
              min-width="140"
            />
            <el-table-column
              prop="process"
              :label="t('home.labelProcess')"
              width="100"
            />
            <el-table-column
              :label="t('home.labelProgress')"
              width="180"
            >
              <template #default="{ row }">
                <el-progress
                  :percentage="row.progress"
                  :stroke-width="8"
                  :color="row.progress === 100 ? 'var(--success)' : 'var(--accent-primary)'"
                />
              </template>
            </el-table-column>
            <el-table-column
              :label="t('home.labelStatus')"
              width="100"
              align="center"
            >
              <template #default="{ row }">
                <el-tag
                  :type="statusTagType(row.status)"
                  size="small"
                  effect="light"
                >
                  {{ row.statusLabel }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              :label="t('home.labelAction')"
              width="80"
              align="center"
            >
              <template #default>
                <el-button
                  type="primary"
                  text
                  size="small"
                >
                  {{ t('home.btnDetail') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </div>

      <!-- Right: Real-time Alerts -->
      <div class="panel panel-alerts">
        <div class="panel-header">
          <h3 class="panel-title">
            {{ t('home.cardRealTimeAlerts') }}
          </h3>
          <el-badge
            :value="alerts.length"
            class="alert-badge"
          />
        </div>
        <div class="alert-list">
          <div
            v-if="alertsLoading"
            class="alert-empty"
          >
            {{ t('home.msgAlertsLoading') }}
          </div>
          <div
            v-else-if="alertsError"
            class="alert-empty"
          >
            {{ t('home.msgAlertsLoadFailed') }}
          </div>
          <div
            v-else-if="alerts.length === 0"
            class="alert-empty"
          >
            {{ t('home.msgNoAlerts') }}
          </div>
          <template v-else>
            <div
              v-for="(alert, index) in alerts"
              :key="index"
              class="alert-item"
            >
              <span
                class="alert-dot"
                :style="{ background: alert.severityColor }"
              />
              <div class="alert-content">
                <span class="alert-message">{{ alert.message }}</span>
                <span class="alert-time">{{ alert.time }}</span>
              </div>
            </div>
          </template>
        </div>
      </div>
    </section>

    <!-- 5. Quick Actions -->
    <section class="quick-actions">
      <h3 class="section-title">
        {{ t('home.cardQuickActions') }}
      </h3>
      <div class="action-grid">
        <el-button
          v-for="action in quickActions"
          :key="action.label"
          class="action-btn"
          @click="handleAction(action)"
        >
          <el-icon :size="20">
            <component :is="action.icon" />
          </el-icon>
          <span>{{ action.label }}</span>
        </el-button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, markRaw, onMounted, onUnmounted, type Component } from 'vue'
import { useRouter } from 'vue-router'
import { useI18n } from 'vue-i18n'
import {
  Box,
  CircleCheck,
  Setting,
  Tickets,
  Plus,
  DataLine,
  Document,
  Monitor,
} from '@element-plus/icons-vue'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'
import { useAgentStore } from '@/stores/agents'
import { useTasksStore } from '@/stores/tasks'
import type { TaskInfo } from '@/stores/tasks'

// ---------------------------------------------------------------------------
// Stores
// ---------------------------------------------------------------------------
const agentStore = useAgentStore()
const tasksStore = useTasksStore()
const router = useRouter()
const { t } = useI18n()

// ---------------------------------------------------------------------------
// WorkOrder 类型
// ---------------------------------------------------------------------------
interface WorkOrder {
  orderNo: string
  productName: string
  process: string
  progress: number
  status: string
  statusLabel: string
}

// ---------------------------------------------------------------------------
// Computed — 使用 Store 数据
// ---------------------------------------------------------------------------
const displayAgents = computed(() => agentStore.agents)

const displayTasks = computed(() => tasksStore.tasks)

/** 将 tasksStore 数据映射为工单表格格式 */
const displayWorkOrders = computed<WorkOrder[]>(() => {
  const tasks = displayTasks.value

  const statusMap: Record<string, string> = {
    pending: t('home.statusPending'),
    queued: t('home.statusQueued'),
    running: t('home.statusRunning'),
    completed: t('home.statusCompleted'),
    failed: t('home.statusFailed'),
    cancelled: t('home.statusCancelled'),
  }

  return tasks.map((task) => ({
    orderNo: task.job_id,
    productName: (task.params?.product as string) || task.task_type,
    process: (task.params?.process as string) || task.task_type,
    progress: task.progress ?? 0,
    status: task.status,
    statusLabel: statusMap[task.status] || task.status,
  }))
})

// ---------------------------------------------------------------------------
// Greeting & Clock
// ---------------------------------------------------------------------------
const now = ref(new Date())
let timer: ReturnType<typeof setInterval>

// 告警 & KPI 响应式状态
const alerts = ref<Array<{ message: string; severityColor: string; time: string }>>([])
const alertsLoading = ref(false)
const alertsError = ref(false)

interface ProductionDashboard {
  total_output: number
  qualified_output: number
  total_orders: number
  active_orders: number
  pass_rate: number
  avg_cycle_time: number
}

const productionData = ref<ProductionDashboard | null>(null)
const productionLoading = ref(false)
const productionError = ref(false)

onMounted(async () => {
  // 时钟
  timer = setInterval(() => { now.value = new Date() }, 1000)

  // 并行请求 4 个独立数据源，减少总等待时间
  alertsLoading.value = true
  productionLoading.value = true

  const [agentsResult, tasksResult, alertsResult, dashboardResult] = await Promise.allSettled([
    agentStore.fetchAgents(),
    tasksStore.fetchTasks(),
    http.get(API_CONFIG.EQUIPMENT + '/alarms/'),
    http.get(API_CONFIG.PRODUCTION + '/dashboard'),
  ])

  // 处理告警数据
  try {
    if (alertsResult.status === 'fulfilled') {
      const list = alertsResult.value.data?.data ?? []
      const severityColorMap: Record<string, string> = {
        high: 'var(--error)',
        medium: 'var(--warning)',
        low: 'var(--info)',
      }
      alerts.value = list.map((a: { message?: string; severity?: string; created_at?: string }) => ({
        message: a.message || t('home.msgUnknownAlert'),
        severityColor: severityColorMap[a.severity || 'low'] || 'var(--info)',
        time: a.created_at ? formatRelativeTime(a.created_at) : t('home.msgJustNow'),
      }))
    }
  } catch {
    alertsError.value = true
    alerts.value = []
  } finally {
    alertsLoading.value = false
  }

  // 处理生产仪表板数据
  try {
    if (dashboardResult.status === 'fulfilled') {
      const data = dashboardResult.value.data?.data
      if (data) productionData.value = data
    }
  } catch {
    productionError.value = true
    productionData.value = null
  } finally {
    productionLoading.value = false
  }
})

onUnmounted(() => { clearInterval(timer) })

const greeting = computed(() => {
  const h = now.value.getHours()
  if (h < 6) return t('home.greetingEarlyMorning')
  if (h < 12) return t('home.greetingMorning')
  if (h < 14) return t('home.greetingNoon')
  if (h < 18) return t('home.greetingAfternoon')
  return t('home.greetingEvening')
})

const currentDateTime = computed(() => {
  const d = now.value
  const pad = (n: number) => String(n).padStart(2, '0')
  const weekDays = [
    t('home.weekdaySun'),
    t('home.weekdayMon'),
    t('home.weekdayTue'),
    t('home.weekdayWed'),
    t('home.weekdayThu'),
    t('home.weekdayFri'),
    t('home.weekdaySat'),
  ]
  const time = `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
  return t('home.dateFormat', {
    year: d.getFullYear(),
    month: pad(d.getMonth() + 1),
    day: pad(d.getDate()),
    weekday: weekDays[d.getDay()],
    time,
  })
})

// ---------------------------------------------------------------------------
// Time Range Filter
// ---------------------------------------------------------------------------
const timeRanges = computed(() => [
  { key: 'today', label: t('home.rangeToday') },
  { key: 'week', label: t('home.rangeWeek') },
  { key: 'month', label: t('home.rangeMonth') },
])
const activeRange = ref('today')

// ---------------------------------------------------------------------------
// KPI Cards — 从生产仪表板 API 获取真实数据
// ---------------------------------------------------------------------------
interface KpiCard {
  title: string
  value: string
  change: string
  isPositive: boolean
  icon: Component
  color: string
  iconBg: string
}

const kpiCards = computed<KpiCard[]>(() => {
  const tasks = displayTasks.value
  const stats = tasksStore.stats
  const pd = productionData.value

  // 今日产量
  const hasRealStats = stats && stats.total_tasks > 0
  const productionCount = pd
    ? pd.total_output.toLocaleString() + t('home.unitPiece')
    : hasRealStats
      ? stats.completed_tasks.toLocaleString() + t('home.unitPiece')
      : productionLoading.value
        ? t('home.loadingText')
        : '--'

  const productionChange = hasRealStats && stats.completed_tasks > 0
    ? `+${stats.completed_tasks}%`
    : '--'

  // 良品率
  const passRateValue = pd
    ? (pd.pass_rate * 100).toFixed(1) + '%'
    : productionLoading.value
      ? t('home.loadingText')
      : '--'

  // 设备稼动率 — 暂无独立 API，显示加载中或暂无数据
  const utilizationValue = productionLoading.value
    ? t('home.loadingText')
    : '--'

  // 在制工单：running + pending
  const activeOrders = tasks.filter(
    (task) => task.status === 'running' || task.status === 'pending'
  ).length
  const activeOrdersDisplay = hasRealStats || tasks.length > 0
    ? activeOrders + t('home.unitOrder')
    : '--'
  const activeOrdersChange = tasks.length > 0 ? String(activeOrders) : '--'

  return [
    {
      title: t('home.statTodayOutput'),
      value: productionCount,
      change: productionChange,
      isPositive: true,
      icon: markRaw(Box),
      color: 'var(--brand-500)',
      iconBg: 'var(--info-bg)',
    },
    {
      title: t('home.statPassRate'),
      value: passRateValue,
      change: '--',
      isPositive: true,
      icon: markRaw(CircleCheck),
      color: 'var(--success)',
      iconBg: 'var(--success-bg)',
    },
    {
      title: t('home.statUtilization'),
      value: utilizationValue,
      change: '--',
      isPositive: false,
      icon: markRaw(Setting),
      color: 'var(--warning)',
      iconBg: 'var(--warning-bg)',
    },
    {
      title: t('home.statActiveOrders'),
      value: activeOrdersDisplay,
      change: activeOrdersChange,
      isPositive: true,
      icon: markRaw(Tickets),
      color: 'var(--info)',
      iconBg: 'var(--info-bg)',
    },
  ]
})

// ---------------------------------------------------------------------------
// Status helpers
// ---------------------------------------------------------------------------
function statusTagType(status: string): 'success' | 'warning' | 'info' | 'danger' | 'primary' {
  if (status === 'completed') return 'success'
  if (status === 'running' || status === 'queued') return 'warning'
  if (status === 'pending') return 'info'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'info'
  return 'info'
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function formatRelativeTime(dateStr: string): string {
  const date = new Date(dateStr)
  const diff = Math.floor((Date.now() - date.getTime()) / 1000)
  if (diff < 60) return t('home.msgJustNow')
  if (diff < 3600) return t('home.timeMinutesAgo', { n: Math.floor(diff / 60) })
  if (diff < 86400) return t('home.timeHoursAgo', { n: Math.floor(diff / 3600) })
  return t('home.timeDaysAgo', { n: Math.floor(diff / 86400) })
}

// ---------------------------------------------------------------------------
// Alerts — 从 API 获取真实告警（已在 onMounted 中加载）
// ---------------------------------------------------------------------------

// ---------------------------------------------------------------------------
// Quick Actions
// ---------------------------------------------------------------------------
interface QuickAction {
  label: string
  icon: Component
  route: string
}

const quickActions = computed<QuickAction[]>(() => [
  { label: t('home.btnNewOrder'), icon: markRaw(Plus), route: '/process-planning' },
  { label: t('home.btnStartInspection'), icon: markRaw(DataLine), route: '/quality-inspection' },
  { label: t('home.btnViewReport'), icon: markRaw(Document), route: '/production-report' },
  { label: t('home.btnEquipmentInspection'), icon: markRaw(Monitor), route: '/equipment-monitor' },
])

function handleAction(action: QuickAction) {
  router.push(action.route)
}
</script>

<style scoped>
.home-page {
  max-width: var(--content-max-width);
  margin: 0 auto;
  display: flex;
  flex-direction: column;
  gap: 24px;
  padding: var(--page-padding);
}

/* ===== Welcome Banner ===== */
.welcome-banner {
  position: relative;
  background: linear-gradient(135deg, var(--brand-500), var(--brand-300));
  border-radius: var(--radius-lg);
  padding: 32px 40px;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: space-between;
  box-shadow: var(--shadow-md);
}

.banner-text h2 {
  margin: 0 0 6px;
  font-size: 1.5rem;
  font-weight: 700;
  color: #fff;
}

.banner-date {
  margin: 0;
  font-size: 0.9rem;
  color: rgba(255, 255, 255, 0.75);
}

.banner-illustration {
  position: absolute;
  right: 32px;
  top: 50%;
  transform: translateY(-50%);
  opacity: 0.7;
  pointer-events: none;
}

.banner-svg {
  width: 140px;
  height: 140px;
}

/* ===== Time Range Filter ===== */
.time-filter {
  display: flex;
  justify-content: flex-end;
}

.filter-group {
  display: flex;
  gap: 0;
  background: var(--bg-tertiary);
  border-radius: var(--radius-md);
  padding: 3px;
}

.filter-btn {
  padding: 8px 24px;
  border: none;
  background: transparent;
  border-radius: calc(var(--radius-md) - 2px);
  font-size: 0.875rem;
  font-weight: 500;
  color: var(--text-secondary);
  cursor: pointer;
  transition: all var(--transition-fast);
  font-family: var(--font-sans);
}

.filter-btn.active {
  background: var(--accent-primary);
  color: #fff;
  box-shadow: var(--shadow-sm);
}

.filter-btn:not(.active):hover {
  color: var(--text-primary);
  background: var(--bg-card);
}

/* ===== Content Row (Two-column) ===== */
.content-row {
  display: grid;
  grid-template-columns: 3fr 2fr;
  gap: 20px;
}

/* ===== Alerts Panel ===== */
.alert-badge {
  flex-shrink: 0;
}

.alert-list {
  padding: 0 20px 16px;
  display: flex;
  flex-direction: column;
  gap: 0;
}

.alert-empty {
  padding: 24px 0;
  text-align: center;
  font-size: 0.85rem;
  color: var(--text-tertiary);
}

.alert-item {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 12px 0;
  border-bottom: 1px solid var(--border-light);
}

.alert-item:last-child {
  border-bottom: none;
}

.alert-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
  margin-top: 5px;
}

.alert-content {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.alert-message {
  font-size: 0.85rem;
  color: var(--text-primary);
  line-height: 1.4;
}

.alert-time {
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

/* ===== Quick Actions ===== */
.section-title {
  margin: 0 0 14px;
  font-size: 1rem;
  font-weight: 600;
  color: var(--text-primary);
}

.action-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  height: 48px;
  border-radius: var(--radius-md) !important;
  font-size: 0.9rem;
  font-weight: 500;
  border: 1px solid var(--border-light) !important;
  background: var(--bg-card) !important;
  color: var(--text-primary) !important;
  transition: all var(--transition-fast);
}

.action-btn:hover {
  border-color: var(--accent-primary) !important;
  color: var(--accent-primary) !important;
  box-shadow: var(--shadow-sm);
}
</style>
