<template>
  <div class="plugin-manager">
    <el-card class="header-card">
      <div class="header-content">
        <h2>{{ t('pluginManager.pageTitle') }}</h2>
        <div class="actions">
          <el-button
            type="primary"
            @click="refreshPlugins"
          >
            <el-icon><Refresh /></el-icon> {{ t('pluginManager.btnRefresh') }}
          </el-button>
          <el-input
            v-model="searchQuery"
            :placeholder="t('pluginManager.searchPlaceholder')"
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
            {{ t('pluginManager.statTotal') }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card enabled">
          <div class="stat-value">
            {{ enabledPlugins.length }}
          </div>
          <div class="stat-label">
            {{ t('pluginManager.statEnabled') }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card disabled">
          <div class="stat-value">
            {{ disabledPlugins.length }}
          </div>
          <div class="stat-label">
            {{ t('pluginManager.statDisabled') }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card class="stat-card error">
          <div class="stat-value">
            {{ errorPlugins.length }}
          </div>
          <div class="stat-label">
            {{ t('pluginManager.statError') }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="plugins-card">
      <el-tabs v-model="activeTab">
        <el-tab-pane
          :label="t('pluginManager.tabAll')"
          name="all"
        >
          <el-table
            :data="filteredPlugins"
            stripe
          >
            <el-table-column
              prop="id"
              :label="t('pluginManager.colId')"
              width="150"
            />
            <el-table-column
              prop="name"
              :label="t('pluginManager.colName')"
              width="150"
            />
            <el-table-column
              prop="version"
              :label="t('pluginManager.colVersion')"
              width="80"
            />
            <el-table-column
              prop="plugin_type"
              :label="t('pluginManager.colType')"
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
              :label="t('pluginManager.colStatus')"
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
              :label="t('pluginManager.colDescription')"
              min-width="200"
              show-overflow-tooltip
            />
            <el-table-column
              :label="t('pluginManager.colActions')"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="handleDetail(row.id)"
                >
                  {{ t('pluginManager.btnDetail') }}
                </el-button>
                <el-button
                  v-if="row.status === 'enabled'"
                  size="small"
                  type="warning"
                  @click="handleDisable(row.id)"
                >
                  {{ t('pluginManager.btnDisable') }}
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="handleEnable(row.id)"
                >
                  {{ t('pluginManager.btnEnable') }}
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="handleUninstall(row.id)"
                >
                  {{ t('pluginManager.btnUninstall') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane
          :label="t('pluginManager.tabAdapter')"
          name="adapter"
        >
          <el-table
            :data="adapterPlugins"
            stripe
          >
            <el-table-column
              prop="id"
              :label="t('pluginManager.colId')"
              width="150"
            />
            <el-table-column
              prop="name"
              :label="t('pluginManager.colName')"
              width="150"
            />
            <el-table-column
              prop="version"
              :label="t('pluginManager.colVersion')"
              width="80"
            />
            <el-table-column
              prop="status"
              :label="t('pluginManager.colStatus')"
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
              :label="t('pluginManager.colDescription')"
              min-width="200"
              show-overflow-tooltip
            />
            <el-table-column
              :label="t('pluginManager.colActions')"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="handleDetail(row.id)"
                >
                  {{ t('pluginManager.btnDetail') }}
                </el-button>
                <el-button
                  v-if="row.status === 'enabled'"
                  size="small"
                  type="warning"
                  @click="handleDisable(row.id)"
                >
                  {{ t('pluginManager.btnDisable') }}
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="handleEnable(row.id)"
                >
                  {{ t('pluginManager.btnEnable') }}
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="handleUninstall(row.id)"
                >
                  {{ t('pluginManager.btnUninstall') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
        <el-tab-pane
          :label="t('pluginManager.tabDataSource')"
          name="data_source"
        >
          <el-table
            :data="dataSourcePlugins"
            stripe
          >
            <el-table-column
              prop="id"
              :label="t('pluginManager.colId')"
              width="150"
            />
            <el-table-column
              prop="name"
              :label="t('pluginManager.colName')"
              width="150"
            />
            <el-table-column
              prop="version"
              :label="t('pluginManager.colVersion')"
              width="80"
            />
            <el-table-column
              prop="status"
              :label="t('pluginManager.colStatus')"
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
              :label="t('pluginManager.colDescription')"
              min-width="200"
              show-overflow-tooltip
            />
            <el-table-column
              :label="t('pluginManager.colActions')"
              width="200"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="handleDetail(row.id)"
                >
                  {{ t('pluginManager.btnDetail') }}
                </el-button>
                <el-button
                  v-if="row.status === 'enabled'"
                  size="small"
                  type="warning"
                  @click="handleDisable(row.id)"
                >
                  {{ t('pluginManager.btnDisable') }}
                </el-button>
                <el-button
                  v-else
                  size="small"
                  type="success"
                  @click="handleEnable(row.id)"
                >
                  {{ t('pluginManager.btnEnable') }}
                </el-button>
                <el-button
                  size="small"
                  type="danger"
                  @click="handleUninstall(row.id)"
                >
                  {{ t('pluginManager.btnUninstall') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </el-tab-pane>
      </el-tabs>
    </el-card>

    <el-dialog
      v-model="detailDialogVisible"
      :title="currentPlugin?.metadata?.name || t('pluginManager.detailDialogTitle')"
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
          <el-descriptions-item :label="t('pluginManager.detailId')">
            {{ currentPlugin.metadata.id }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('pluginManager.detailVersion')">
            {{ currentPlugin.metadata.version }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('pluginManager.detailAuthor')">
            {{ currentPlugin.metadata.author }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('pluginManager.detailStatus')">
            <el-tag :type="statusType">
              {{ currentPlugin.metadata.status }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('pluginManager.detailType')">
            {{ currentPlugin.metadata.plugin_type }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('pluginManager.detailCompatibility')">
            {{ currentPlugin.metadata.min_core_version }} - {{ currentPlugin.metadata.max_core_version }}
          </el-descriptions-item>
        </el-descriptions>

        <div class="section">
          <h4>{{ t('pluginManager.sectionDescription') }}</h4>
          <p>{{ currentPlugin.metadata.description }}</p>
        </div>

        <div class="section">
          <h4>{{ t('pluginManager.sectionCapabilities') }}</h4>
          <el-tag
            v-for="cap in currentPlugin.capabilities"
            :key="cap"
            style="margin-right: 5px; margin-bottom: 5px"
          >
            {{ cap }}
          </el-tag>
        </div>

        <div class="section">
          <h4>{{ t('pluginManager.sectionDependencies') }}</h4>
          <DependencyTree
            v-if="currentPlugin.dependency_tree"
            :tree="currentPlugin.dependency_tree"
          />
        </div>

        <div
          v-if="currentPlugin.worker"
          class="section"
        >
          <h4>{{ t('pluginManager.sectionWorkerInfo') }}</h4>
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item :label="t('pluginManager.detailWorkerStatus')">
              {{ currentPlugin.worker.status }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('pluginManager.detailPid')">
              {{ currentPlugin.worker.pid }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('pluginManager.detailPort')">
              {{ currentPlugin.worker.port }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('pluginManager.detailUptime')">
              {{ formatUptime(currentPlugin.worker.uptime) }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <div class="section">
          <h4>{{ t('pluginManager.sectionConfig') }}</h4>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { usePluginStore } from '../stores/plugin'
import type { PluginDetail } from '../stores/plugin'
import { Refresh, Search } from '@element-plus/icons-vue'
import DependencyTree from '../components/plugin/DependencyTree.vue'

const { t } = useI18n()
const pluginStore = usePluginStore()
const searchQuery = ref('')
const activeTab = ref('all')
const detailDialogVisible = ref(false)
const currentPlugin = ref<PluginDetail | null>(null)
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
  ElMessage.success(t('pluginManager.msgRefreshed'))
}

const handleEnable = async (pluginId: string) => {
  await pluginStore.enablePlugin(pluginId)
  ElMessage.success(t('pluginManager.msgEnabled'))
}

const handleDisable = async (pluginId: string) => {
  await pluginStore.disablePlugin(pluginId)
  ElMessage.success(t('pluginManager.msgDisabled'))
}

const handleUninstall = async (pluginId: string) => {
  try {
    await ElMessageBox.confirm(t('pluginManager.msgUninstallConfirm'), t('pluginManager.msgUninstallConfirmTitle'), {
      confirmButtonText: t('pluginManager.btnUninstallConfirm'),
      cancelButtonText: t('pluginManager.btnCancel'),
      type: 'warning',
    })
    await pluginStore.uninstallPlugin(pluginId)
    ElMessage.success(t('pluginManager.msgUninstalled'))
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
  if (!seconds) return t('pluginManager.txtNA')
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  return t('pluginManager.uptimeFormat', { hours, minutes })
}

const handleConfigChange = async () => {
  if (!currentPlugin.value) return
  try {
    const config = JSON.parse(configJson.value)
    await pluginStore.updatePluginConfig(currentPlugin.value.metadata.id, config)
    ElMessage.success(t('pluginManager.msgConfigUpdated'))
  } catch {
    ElMessage.error(t('pluginManager.msgInvalidJson'))
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
  color: var(--accent-primary);
}
.stat-label {
  color: var(--text-tertiary);
  margin-top: 5px;
}
.stat-card.enabled .stat-value {
  color: var(--success);
}
.stat-card.disabled .stat-value {
  color: var(--warning);
}
.stat-card.error .stat-value {
  color: var(--error);
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
  color: var(--text-primary);
}
</style>
