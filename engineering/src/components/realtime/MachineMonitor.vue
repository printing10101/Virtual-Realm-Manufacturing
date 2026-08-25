<!-- 机床实时监控面板（Phase A 前端：状态指示 + 实时数据 + 预警） -->
<template>
  <div class="machine-monitor">
    <el-card shadow="never">
      <template #header>
        <div class="card-header">
          <span>机床实时监控</span>
          <el-tag :type="statusTagType" size="small">{{ statusLabel }}</el-tag>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :span="6">
          <el-statistic title="主轴转速 (RPM)" :value="spindleSpeed" />
        </el-col>
        <el-col :span="6">
          <el-statistic
            title="主轴负载 (%)"
            :value="spindleLoad"
            :value-style="loadValueStyle"
          />
        </el-col>
        <el-col :span="6">
          <el-statistic title="进给 (mm/min)" :value="feedrate" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="振动 (mm/s)" :value="vibration" :value-style="vibrationStyle" />
        </el-col>
      </el-row>

      <el-divider />

      <div class="alerts">
        <el-alert
          v-for="alert in alerts"
          :key="alert.alert_id"
          :title="alert.message"
          :type="alertTypeToEl(alert.priority)"
          show-icon
          :closable="false"
          class="alert-item"
        />
        <el-empty v-if="alerts.length === 0" description="暂无预警" :image-size="40" />
      </div>

      <div class="monitor-footer">
        <el-button size="small" :disabled="!connected" @click="refresh">
          手动刷新
        </el-button>
        <el-button size="small" type="primary" :disabled="connected" @click="connect">
          连接机床
        </el-button>
        <span v-if="lastUpdated" class="last-updated">
          更新于 {{ lastUpdated.toLocaleTimeString() }}
        </span>
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { resolveBackendUrl } from '@/utils/http'

interface MonitorAlert {
  alert_id: string
  message: string
  priority: number
  alert_type: string
}

interface MonitorEvent {
  event_type: 'data' | 'alert' | 'status' | 'ping'
  event_id?: string
  timestamp?: string
  data?: { spindle_speed: number; spindle_load: number; feedrate: number; execution: string } | null
  message?: string
  priority?: number
  alert_type?: string
}

// 实时数据源：WebSocket（/api/v1/monitor/ws）由 MTConnect 模拟 Agent 推送
const connected = ref(false)
const spindleSpeed = ref(0)
const spindleLoad = ref(0)
const feedrate = ref(0)
const vibration = ref(0)
const alerts = ref<MonitorAlert[]>([])
const lastUpdated = ref<Date | null>(null)

let ws: WebSocket | null = null

const statusLabel = computed(() => (connected.value ? '已连接' : '未连接'))
const statusTagType = computed(() => (connected.value ? 'success' : 'info'))

const loadValueStyle = computed(() => ({
  color: spindleLoad.value > 80 ? 'var(--el-color-danger)' : undefined,
}))

const vibrationStyle = computed(() => ({
  color: vibration.value > 5 ? 'var(--el-color-danger)' : undefined,
}))

/** 优先级(1-10) → Element Plus alert type */
function alertTypeToEl(priority: number): 'success' | 'warning' | 'error' {
  if (priority >= 7) return 'error'
  if (priority >= 4) return 'warning'
  return 'success'
}

/** 构造 WebSocket URL：兼容浏览器开发（vite proxy 相对路径）与 Tauri 桌面（resolveBackendUrl 携带端口） */
function buildWsUrl(): string {
  const url = resolveBackendUrl('/api/v1/monitor/ws')
  return url.replace(/^http/, 'ws')
}

function handleEvent(evt: MessageEvent): void {
  let msg: MonitorEvent
  try {
    msg = JSON.parse(String(evt.data)) as MonitorEvent
  } catch {
    return
  }
  if (msg.event_type === 'data' && msg.data) {
    spindleSpeed.value = msg.data.spindle_speed ?? 0
    spindleLoad.value = msg.data.spindle_load ?? 0
    feedrate.value = msg.data.feedrate ?? 0
    lastUpdated.value = new Date()
  } else if (msg.event_type === 'alert') {
    alerts.value.push({
      alert_id: msg.event_id ?? String(Date.now()),
      message: msg.message ?? '未知告警',
      priority: msg.priority ?? 1,
      alert_type: msg.alert_type ?? 'unknown',
    })
    // 保留最近 5 条，避免列表无限增长
    if (alerts.value.length > 5) alerts.value.shift()
  }
}

/** 连接机床：建立 WebSocket 订阅实时数据流 */
function connect(): void {
  if (connected.value || ws) return
  try {
    ws = new WebSocket(buildWsUrl())
  } catch {
    return
  }
  ws.onopen = () => {
    connected.value = true
    ws?.send(JSON.stringify({ action: 'subscribe', machine_id: 'VM-001' }))
  }
  ws.onmessage = handleEvent
  ws.onclose = () => {
    connected.value = false
    ws = null
  }
  ws.onerror = () => {
    connected.value = false
  }
}

/** 手动刷新（保留连接，仅更新时间戳） */
function refresh(): void {
  lastUpdated.value = new Date()
}

onUnmounted(() => {
  if (ws) {
    ws.onclose = null
    ws.close()
    ws = null
  }
})
</script>

<style scoped>
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.alerts {
  min-height: 60px;
}
.alert-item {
  margin-bottom: 8px;
}
.monitor-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 12px;
}
.last-updated {
  font-size: 12px;
  color: var(--el-text-color-secondary);
}
</style>
