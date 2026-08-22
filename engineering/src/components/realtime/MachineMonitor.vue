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
import { computed, ref } from 'vue'

interface MonitorAlert {
  alert_id: string
  message: string
  priority: number
  alert_type: string
}

// 模拟数据源：真实场景下由 WebSocket（MTConnectStreamServer）推送
const connected = ref(false)
const spindleSpeed = ref(0)
const spindleLoad = ref(0)
const feedrate = ref(0)
const vibration = ref(0)
const alerts = ref<MonitorAlert[]>([])
const lastUpdated = ref<Date | null>(null)

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

/** 模拟连接：真实场景走 WebSocket 订阅 */
function connect(): void {
  connected.value = true
  lastUpdated.value = new Date()
  // 模拟数据流（占位；真实实现替换为 store.subscribeMachine）
  spindleSpeed.value = 8000
  spindleLoad.value = 55
  feedrate.value = 500
  vibration.value = 2.3
  alerts.value = []
}

/** 手动刷新（真实场景调用 /api/v1/experience/stats 或 WS 拉取） */
function refresh(): void {
  lastUpdated.value = new Date()
}
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
