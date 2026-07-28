<template>
  <div class="plugin-market">
    <el-card class="header-card">
      <div class="header-content">
        <h2>{{ t('pluginMarket.pageTitle') }}</h2>
        <el-input
          v-model="searchQuery"
          :placeholder="t('pluginMarket.placeholderSearch')"
          style="width: 300px"
          clearable
        >
          <template #prefix>
            <el-icon><Search /></el-icon>
          </template>
        </el-input>
      </div>
    </el-card>

    <el-row
      :gutter="16"
      style="margin-top: 20px"
    >
      <el-col
        v-for="plugin in filteredPlugins"
        :key="plugin.id"
        :xs="24"
        :sm="12"
        :md="8"
        :lg="6"
      >
        <el-card
          class="plugin-card"
          shadow="hover"
        >
          <div class="plugin-icon">
            <el-icon :size="48">
              <Setting />
            </el-icon>
          </div>
          <h3 class="plugin-name">
            {{ plugin.name }}
          </h3>
          <p class="plugin-desc">
            {{ plugin.description }}
          </p>
          <div class="plugin-meta">
            <el-tag size="small">
              {{ plugin.plugin_type }}
            </el-tag>
            <span class="version">v{{ plugin.version }}</span>
          </div>
          <div class="plugin-actions">
            <el-button
              type="primary"
              size="small"
              @click="handleInstall(plugin)"
            >
              {{ t('pluginMarket.btnInstall') }}
            </el-button>
            <el-button
              size="small"
              @click="handleViewDetail(plugin)"
            >
              {{ t('pluginMarket.btnDetail') }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty
      v-if="filteredPlugins.length === 0"
      :description="t('pluginMarket.emptyNoPlugin')"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Search, Setting } from '@element-plus/icons-vue'

const { t } = useI18n()

interface MarketplacePlugin {
  id: string
  name: string
  version: string
  description: string
  plugin_type: string
  author: string
}

const searchQuery = ref('')

const marketplacePlugins = ref<MarketplacePlugin[]>([
  { id: 'fanuc-adapter', name: t('pluginMarket.pluginFanucAdapter'), version: '1.0.0', description: t('pluginMarket.pluginFanucAdapterDesc'), plugin_type: 'adapter', author: t('pluginMarket.pluginAuthor') },
  { id: 'siemens-adapter', name: t('pluginMarket.pluginSiemensAdapter'), version: '1.0.0', description: t('pluginMarket.pluginSiemensAdapterDesc'), plugin_type: 'adapter', author: t('pluginMarket.pluginAuthor') },
  { id: 'opcua-source', name: t('pluginMarket.pluginOpcuaSource'), version: '2.0.0', description: t('pluginMarket.pluginOpcuaSourceDesc'), plugin_type: 'data_source', author: t('pluginMarket.pluginAuthor') },
  { id: 'modbus-source', name: t('pluginMarket.pluginModbusSource'), version: '1.7.0', description: t('pluginMarket.pluginModbusSourceDesc'), plugin_type: 'data_source', author: t('pluginMarket.pluginAuthor') },
  { id: 'vibration-analyzer', name: t('pluginMarket.pluginVibrationAnalyzer'), version: '1.0.0', description: t('pluginMarket.pluginVibrationAnalyzerDesc'), plugin_type: 'analyzer', author: t('pluginMarket.pluginAuthor') },
  { id: '3d-monitor', name: t('pluginMarket.plugin3dMonitor'), version: '1.0.0', description: t('pluginMarket.plugin3dMonitorDesc'), plugin_type: 'visualization', author: t('pluginMarket.pluginAuthor') },
])

const filteredPlugins = computed(() => {
  if (!searchQuery.value) return marketplacePlugins.value
  const query = searchQuery.value.toLowerCase()
  return marketplacePlugins.value.filter(
    (p) => p.name.toLowerCase().includes(query) || p.description.toLowerCase().includes(query) || p.plugin_type.toLowerCase().includes(query)
  )
})

const handleInstall = (plugin: MarketplacePlugin) => {
  ElMessage.success(t('pluginMarket.msgInstallStarted', { name: plugin.name }))
}

const handleViewDetail = (plugin: MarketplacePlugin) => {
  ElMessage.info(t('pluginMarket.msgViewDetail', { name: plugin.name }))
}
</script>

<style scoped>
.plugin-market {
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
.plugin-card {
  text-align: center;
  margin-bottom: 16px;
}
.plugin-icon {
  color: var(--accent-primary);
  margin-bottom: 10px;
}
.plugin-name {
  margin: 10px 0 5px;
  font-size: 16px;
}
.plugin-desc {
  color: var(--text-tertiary);
  font-size: 13px;
  margin: 5px 0 15px;
  min-height: 40px;
}
.plugin-meta {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 10px;
  margin-bottom: 15px;
}
.version {
  color: var(--text-secondary);
  font-size: 12px;
}
.plugin-actions {
  display: flex;
  justify-content: center;
  gap: 10px;
}
</style>
