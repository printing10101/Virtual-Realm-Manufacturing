<template>
  <div class="plugin-logs">
    <el-card class="header-card">
      <div class="header-content">
        <h2>插件日志</h2>
        <div class="actions">
          <el-select
            v-model="selectedPlugin"
            placeholder="选择插件"
            style="width: 200px"
          >
            <el-option
              label="全部插件"
              value=""
            />
            <el-option
              v-for="p in plugins"
              :key="p.id"
              :label="p.name"
              :value="p.id"
            />
          </el-select>
          <el-select
            v-model="logLevel"
            placeholder="日志级别"
            style="width: 120px; margin-left: 10px"
          >
            <el-option
              label="全部"
              value=""
            />
            <el-option
              label="DEBUG"
              value="debug"
            />
            <el-option
              label="INFO"
              value="info"
            />
            <el-option
              label="WARNING"
              value="warning"
            />
            <el-option
              label="ERROR"
              value="error"
            />
          </el-select>
          <el-button
            type="primary"
            style="margin-left: 10px"
            @click="refreshLogs"
          >
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-button
            type="success"
            style="margin-left: 10px"
            @click="exportLogs"
          >
            <el-icon><Download /></el-icon> 导出
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card
      class="logs-card"
      style="margin-top: 20px"
    >
      <div class="log-container">
        <div
          v-for="log in filteredLogs"
          :key="log.timestamp"
          class="log-entry"
          :class="log.level"
        >
          <span class="log-time">{{ formatTime(log.timestamp) }}</span>
          <el-tag
            :type="getLevelType(log.level)"
            size="small"
            class="log-level"
          >
            {{ log.level.toUpperCase() }}
          </el-tag>
          <span class="log-plugin">[{{ log.plugin }}]</span>
          <span class="log-message">{{ log.message }}</span>
        </div>
        <el-empty
          v-if="filteredLogs.length === 0"
          description="暂无日志"
        />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Refresh, Download } from '@element-plus/icons-vue'
import { usePluginStore } from '../stores/plugin'

const pluginStore = usePluginStore()
const selectedPlugin = ref('')
const logLevel = ref('')

const plugins = computed(() => pluginStore.plugins)

const logs = ref([
  { timestamp: Date.now() - 60000, level: 'info', plugin: 'fanuc-adapter', message: 'Plugin initialized successfully' },
  { timestamp: Date.now() - 30000, level: 'info', plugin: 'fanuc-adapter', message: 'Connected to machine at 192.168.1.100' },
  { timestamp: Date.now() - 15000, level: 'warning', plugin: 'opcua-source', message: 'Connection timeout, retrying...' },
  { timestamp: Date.now() - 5000, level: 'error', plugin: 'vibration-analyzer', message: 'Failed to process data: invalid format' },
])

const filteredLogs = computed(() => {
  let result = logs.value
  if (selectedPlugin.value) {
    result = result.filter((l) => l.plugin === selectedPlugin.value)
  }
  if (logLevel.value) {
    result = result.filter((l) => l.level === logLevel.value)
  }
  return result.sort((a, b) => b.timestamp - a.timestamp)
})

onMounted(() => {
  pluginStore.fetchPlugins()
})

const refreshLogs = () => {
  ElMessage.success('日志已刷新')
}

const exportLogs = () => {
  ElMessage.success('日志导出成功')
}

const formatTime = (timestamp: number) => {
  return new Date(timestamp).toLocaleTimeString()
}

const getLevelType = (level: string) => {
  switch (level) {
    case 'debug':
      return 'info'
    case 'info':
      return 'success'
    case 'warning':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
}
</script>

<style scoped>
.plugin-logs {
  padding: 20px;
}
.header-card {
  margin-bottom: 20px;
}
.header-content {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
.header-content h2 {
  margin: 0;
}
.actions {
  display: flex;
  align-items: center;
}
.log-container {
  max-height: 600px;
  overflow-y: auto;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 13px;
}
.log-entry {
  display: flex;
  align-items: center;
  padding: 5px 10px;
  border-bottom: 1px solid var(--border-light);
  gap: 10px;
}
.log-entry:hover {
  background-color: var(--bg-secondary);
}
.log-time {
  color: var(--text-tertiary);
  min-width: 80px;
}
.log-level {
  min-width: 60px;
  text-align: center;
}
.log-plugin {
  color: var(--accent-primary);
  min-width: 120px;
}
.log-message {
  color: var(--text-primary);
  flex: 1;
}
</style>
