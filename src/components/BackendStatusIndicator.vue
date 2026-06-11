<script setup lang="ts">
import { computed } from 'vue'
import { useBackendStatus, type BackendStatusKind } from '@/composables/useBackendStatus'

const { state, restart, tauriMode } = useBackendStatus()

const indicator = computed(() => {
  const map: Record<BackendStatusKind, { color: string; label: string; pulse: boolean }> = {
    idle: { color: '#909399', label: '未启动', pulse: false },
    starting: { color: '#E6A23C', label: '启动中', pulse: true },
    running: { color: '#67C23A', label: '运行中', pulse: false },
    stopping: { color: '#E6A23C', label: '停止中', pulse: true },
    crashed: { color: '#F56C6C', label: '已崩溃', pulse: true },
    failed: { color: '#F56C6C', label: '启动失败', pulse: false },
    stopped: { color: '#909399', label: '已停止', pulse: false },
  }
  return map[state.status] || map.idle
})
</script>

<template>
  <div v-if="tauriMode" class="backend-status-indicator" :title="state.message">
    <span class="dot" :class="{ pulse: indicator.pulse }" :style="{ background: indicator.color }"></span>
    <span class="label" :style="{ color: indicator.color }">{{ indicator.label }}</span>
    <el-button
      v-if="state.status === 'crashed' || state.status === 'failed'"
      link
      type="primary"
      size="small"
      @click="restart"
    >
      重启
    </el-button>
  </div>
</template>

<style scoped>
.backend-status-indicator {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 2px 8px;
  font-size: 12px;
  user-select: none;
}
.dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  display: inline-block;
}
.dot.pulse {
  animation: pulse 1.4s ease-in-out infinite;
}
.label {
  font-weight: 500;
}
@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.3); }
}
</style>
