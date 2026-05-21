<template>
  <div class="plugin-manager">
    <el-card class="header-card">
      <div class="header-content">
        <h2>插件管理</h2>
        <div class="actions">
          <el-button
            type="primary"
            @click="refreshPlugins"
          >
            <el-icon><Refresh /></el-icon> 刷新
          </el-button>
          <el-input
            v-model="searchQuery"
            placeholder="搜索插件..."
            style="width: 200px; margin-left: 10px"
            clearable
          >
            <template #prefix>
              <el-icon><Search /></el-icon>
            </template>
          </el-input>
        </div>
      </div>
    </el-card>

    <el-row
      :gutter="16"
      class="stats-row"
    >
      <el-col :span="6">
        <el-card class="stat-card">
          <div class="stat-value">
            {{ plugins.length }}
          </div>
          <div class="stat-label">
            总计
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card enabled">
          <div class="stat-value">
            {{ enabledPlugins.length }}
          </div>
          <div class="stat-label">
            已启用
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card disabled">
          <div class="stat-value">
            {{ disabledPlugins.length }}
          </div>
          <div class="stat-label">
            已停用
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card error">
          <div class="stat-value">
            {{ errorPlugins.length }}
          </div>
          <div class="stat-label">
            异常
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="plugins-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane
          label="全部"
          name="all"
        >
          <el-table
            :data="filteredPlugins"
            stripe
          >
            <el-table-column
              prop="id"
              label="ID"
              width="150"
            />
            <el-table-column
              prop="name"
              label="名称"
              width="150"
            />
            <el-table-column
              prop="version"
              label="版本"
              width="80"
            />
            <el-table-column
              prop="plugin_type"
              label="类型"
              width="100"
            >
              <template #default="{ row }">
                <el-tag size="small">
                  {{ row.plugin_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="status"
              label="状态"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="getStatusType(row.status)"
                  size="small"
                >
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="description"
              label="描述"
              min-width="200"
              show-overflow-tooltip
            />
            <el-table-column
              label="操作"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="handleDetail(row.id)"
                >
                  详情
                </el-button>
                <el-button
                  v-if="row.status === 'enabled'"
                  size="small"
                  type="warning"
                  @click="handleDisable(row.id)"
                >
                  停用
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="handleEnable(row.id)"
                >
                  启用
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="handleUninstall(row.id)"
                >
                  卸载
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane
          label="适配器"
          name="adapter"
        >
          <el-table
            :data="adapterPlugins"
            stripe
          >
            <el-table-column
              prop="id"
              label="ID"
              width="150"
            />
            <el-table-column
              prop="name"
              label="名称"
              width="150"
            />
            <el-table-column
              prop="version"
              label="版本"
              width="80"
            />
            <el-table-column
              prop="status"
              label="状态"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="getStatusType(row.status)"
                  size="small"
                >
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="description"
              label="描述"
              min-width="200"
              show-overflow-tooltip
            />
            <el-table-column
              label="操作"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="handleDetail(row.id)"
                >
                  详情
                </el-button>
                <el-button
                  v-if="row.status === 'enabled'"
                  size="small"
                  type="warning"
                  @click="handleDisable(row.id)"
                >
                  停用
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="handleEnable(row.id)"
                >
                  启用
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="handleUninstall(row.id)"
                >
                  卸载
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane
          label="数据源"
          name="data_source"
        >
          <el-table
            :data="dataSourcePlugins"
            stripe
          >
            <el-table-column
              prop="id"
              label="ID"
              width="150"
            />
            <el-table-column
              prop="name"
              label="名称"
              width="150"
            />
            <el-table-column
              prop="version"
              label="版本"
              width="80"
            />
            <el-table-column
              prop="status"
              label="状态"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="getStatusType(row.status)"
                  size="small"
                >
                  {{ row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="description"
              label="描述"
              min-width="200"
              show-overflow-tooltip
            />
            <el-table-column
              label="操作"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="handleDetail(row.id)"
                >
                  详情
                </el-button>
                <el-button
                  v-if="row.status === 'enabled'"
                  size="small"
                  type="warning"
                  @click="handleDisable(row.id)"
                >
                  停用
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="handleEnable(row.id)"
                >
                  启用
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="handleUninstall(row.id)"
                >
                  卸载
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog
      v-model="detailDialogVisible"
      :title="currentPlugin?.metadata?.name || '插件详情'"
      width="800px"
    >
      <div
        v-if="currentPlugin"
        class="plugin-detail"
      >
        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item label="ID">
            {{ currentPlugin.metadata.id }}
          </el-descriptions-item>
          <el-descriptions-item label="版本">
            {{ currentPlugin.metadata.version }}
          </el-descriptions-item>
          <el-descriptions-item label="作者">
            {{ currentPlugin.metadata.author }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="statusType">
              {{ currentPlugin.metadata.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ currentPlugin.metadata.plugin_type }}
          </el-descriptions-item>
          <el-descriptions-item label="兼容性">
            {{ currentPlugin.metadata.min_core_version }} - {{ currentPlugin.metadata.max_core_version }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="section">
          <h4>描述</h4>
          <p>{{ currentPlugin.metadata.description }}</p>
        </div>

        <div class="section">
          <h4>能力声明</h4>
          <el-tag
            v-for="cap in currentPlugin.capabilities"
            :key="cap"
            style="margin-right: 5px; margin-bottom: 5px"
          >
            {{ cap }}
          </el-tag>
        </div>

        <div class="section">
          <h4>依赖关系</h4>
          <DependencyTree
            v-if="currentPlugin.dependency_tree"
            :tree="currentPlugin.dependency_tree"
          />
        </div>

        <div
          v-if="currentPlugin.worker"
          class="section"
        >
          <h4>Worker信息</h4>
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item label="状态">
              {{ currentPlugin.worker.status }}
            </el-descriptions-item>
            <el-descriptions-item label="PID">
              {{ currentPlugin.worker.pid }}
            </el-descriptions-item>
            <el-descriptions-item label="端口">
              {{ currentPlugin.worker.port }}
            </el-descriptions-item>
            <el-descriptions-item label="运行时长">
              {{ formatUptime(currentPlugin.worker.uptime) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="section">
          <h4>配置</h4>
          <el-input
            v-model="configJson"
            type="textarea"
            :rows="5"
            @blur="handleConfigChange"
          />
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { usePluginStore } from '../stores/plugin'
import { Refresh, Search } from '@element-plus/icons-vue'
import DependencyTree from '../components/plugin/DependencyTree.vue'

const pluginStore = usePluginStore()
const searchQuery = ref('')
const activeTab = ref('all')
const detailDialogVisible = ref(false)
const currentPlugin = ref<any>(null)
const configJson = ref('{}')

const plugins = computed(() => pluginStore.plugins)
const enabledPlugins = computed(() => pluginStore.enabledPlugins)
const disabledPlugins = computed(() => pluginStore.disabledPlugins)
const adapterPlugins = computed(() => pluginStore.adapterPlugins)
const dataSourcePlugins = computed(() => pluginStore.dataSourcePlugins)

const errorPlugins = computed(() => plugins.value.filter((p) => p.status === 'error'))

const filteredPlugins = computed(() => {
  if (!searchQuery.value) return plugins.value
  const query = searchQuery.value.toLowerCase()
  return plugins.value.filter(
    (p) => p.name.toLowerCase().includes(query) || p.id.toLowerCase().includes(query) || p.description.toLowerCase().includes(query)
  )
})

const statusType = computed(() => {
  const status = currentPlugin.value?.metadata?.status
  switch (status) {
    case 'enabled':
      return 'success'
    case 'disabled':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
})

onMounted(() => {
  pluginStore.fetchPlugins()
})

const refreshPlugins = () => {
  pluginStore.fetchPlugins()
  ElMessage.success('插件列表已刷新')
}

const handleEnable = async (pluginId: string) => {
  await pluginStore.enablePlugin(pluginId)
  ElMessage.success('插件已启用')
}

const handleDisable = async (pluginId: string) => {
  await pluginStore.disablePlugin(pluginId)
  ElMessage.success('插件已停用')
}

const handleUninstall = async (pluginId: string) => {
  try {
    await ElMessageBox.confirm('确定要卸载此插件吗？此操作不可恢复。', '确认卸载', {
      confirmButtonText: '卸载',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await pluginStore.uninstallPlugin(pluginId)
    ElMessage.success('插件已卸载')
  } catch (_e) {
    // Silently ignore uninstall errors
  }
}

const handleDetail = async (pluginId: string) => {
  await pluginStore.fetchPluginDetail(pluginId)
  currentPlugin.value = pluginStore.currentPlugin
  configJson.value = JSON.stringify(pluginStore.currentPlugin?.metadata.config || {}, null, 2)
  detailDialogVisible.value = true
}

const formatUptime = (seconds: number) => {
  if (!seconds) return 'N/A'
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return `${hours}h ${minutes}m`
}

const handleConfigChange = async () => {
  if (!currentPlugin.value) return
  try {
    const config = JSON.parse(configJson.value)
    await pluginStore.updatePluginConfig(currentPlugin.value.metadata.id, config)
    ElMessage.success('配置已更新')
  } catch {
    ElMessage.error('无效的JSON格式')
  }
}

const getStatusType = (status: string) => {
  switch (status) {
    case 'enabled':
      return 'success'
    case 'disabled':
      return 'warning'
    case 'error':
      return 'danger'
    default:
      return 'info'
  }
}
</script>

<style scoped>
.plugin-manager {
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
.stats-row {
  margin-bottom: 20px;
}
.stat-card {
  text-align: center;
}
.stat-value {
  font-size: 32px;
  font-weight: bold;
  color: #409eff;
}
.stat-label {
  color: #909399;
  margin-top: 5px;
}
.stat-card.enabled .stat-value {
  color: #67c23a;
}
.stat-card.disabled .stat-value {
  color: #e6a23c;
}
.stat-card.error .stat-value {
  color: #f56c6c;
}
.plugins-card {
  min-height: 400px;
}
.plugin-detail {
  padding: 10px 0;
}
.section {
  margin-top: 20px;
}
.section h4 {
  margin-bottom: 10px;
  color: #303133;
}
</style>
