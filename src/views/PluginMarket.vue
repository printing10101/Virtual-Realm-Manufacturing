<template>
  <div class="plugin-market">
    <el-card class="header-card">
      <div class="header-content">
        <h2>插件市场</h2>
        <el-input
          v-model="searchQuery"
          placeholder="搜索插件..."
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
              安装
            </el-button>
            <el-button
              size="small"
              @click="handleViewDetail(plugin)"
            >
              详情
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-empty
      v-if="filteredPlugins.length === 0"
      description="暂无可用插件"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Search, Setting } from '@element-plus/icons-vue'

const searchQuery = ref('')

const marketplacePlugins = ref([
  { id: 'fanuc-adapter', name: '发那科适配器', version: '1.0.0', description: '支持发那科系列机床通信', plugin_type: 'adapter', author: '灵境制造团队' },
  { id: 'siemens-adapter', name: '西门子适配器', version: '1.0.0', description: '支持西门子840D/828D系统', plugin_type: 'adapter', author: '灵境制造团队' },
  { id: 'opcua-source', name: 'OPC UA数据源', version: '2.0.0', description: 'OPC UA协议数据采集', plugin_type: 'data_source', author: '灵境制造团队' },
  { id: 'modbus-source', name: 'Modbus数据源', version: '1.7.0', description: 'Modbus RTU/TCP数据采集', plugin_type: 'data_source', author: '灵境制造团队' },
  { id: 'vibration-analyzer', name: '振动分析器', version: '1.0.0', description: '机床振动频谱分析', plugin_type: 'analyzer', author: '灵境制造团队' },
  { id: '3d-monitor', name: '3D监控', version: '1.0.0', description: '三维机床状态监控', plugin_type: 'visualization', author: '灵境制造团队' },
])

const filteredPlugins = computed(() => {
  if (!searchQuery.value) return marketplacePlugins.value
  const query = searchQuery.value.toLowerCase()
  return marketplacePlugins.value.filter(
    (p) => p.name.toLowerCase().includes(query) || p.description.toLowerCase().includes(query) || p.plugin_type.toLowerCase().includes(query)
  )
})

const handleInstall = (plugin: any) => {
  ElMessage.success(`插件 "${plugin.name}" 安装已开始`)
}

const handleViewDetail = (plugin: any) => {
  ElMessage.info(`查看插件 "${plugin.name}" 详情`)
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
