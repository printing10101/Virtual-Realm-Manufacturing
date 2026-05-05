<template>
  <div class="model-view">
    <el-row :gutter="20">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <h2>{{ t('modelManagement.title') }}</h2>
              <el-button
                :icon="Refresh"
                :loading="loading"
                @click="refreshStatus"
              >
                {{ t('common.refresh') }}
              </el-button>
            </div>
          </template>

          <el-tabs v-model="activeTab">
            <el-tab-pane
              :label="t('modelManagement.status')"
              name="status"
            >
              <StatusOverview :model-status="modelStatus" />
            </el-tab-pane>

            <el-tab-pane
              :label="t('modelManagement.routeStats')"
              name="routeStats"
            >
              <RouteStats :stats="routerStats" />
            </el-tab-pane>

            <el-tab-pane
              :label="t('modelManagement.routeTest')"
              name="routeTest"
            >
              <RouteTester />
            </el-tab-pane>

            <el-tab-pane
              :label="t('modelManagement.finetune')"
              name="finetune"
            >
              <FineTuneManager
                :finetune-status="finetuneStatus"
                @trigger="triggerFinetune"
                @rollback="rollbackModel"
              />
            </el-tab-pane>

            <el-tab-pane
              :label="t('modelManagement.config')"
              name="config"
            >
              <ModelConfig
                :config="modelConfig"
                @update="updateConfig"
              />
            </el-tab-pane>
          </el-tabs>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import StatusOverview from '@/components/model/StatusOverview.vue'
import RouteStats from '@/components/model/RouteStats.vue'
import RouteTester from '@/components/model/RouteTester.vue'
import FineTuneManager from '@/components/model/FineTuneManager.vue'
import ModelConfig from '@/components/model/ModelConfig.vue'

const { t } = useI18n()
const activeTab = ref('status')
const loading = ref(false)

const modelStatus = ref({
  local_model: { name: '', available: false, base_url: '' },
  cloud_model: { provider: '', name: '', available: false },
  router_stats: {},
  finetune_status: {},
  config: {}
})

const routerStats = ref({
  total_calls: 0,
  local_calls: 0,
  cloud_calls: 0,
  fallback_calls: 0,
  avg_duration_ms: 0,
  route_history: []
})

const finetuneStatus = ref({
  status: 'idle',
  last_finetune_date: undefined as string | undefined,
  model_path: undefined as string | undefined,
  history: []
})

const modelConfig = ref({
  local_model: 'qwen2.5:7b',
  cloud_provider: 'openai',
  cloud_model: 'gpt-4o',
  fallback_threshold: 3,
  local_timeout: 30,
  finetune_auto_trigger: false,
  finetune_min_samples: 50,
  finetune_interval_days: 7
})

onMounted(() => {
  refreshStatus()
})

async function refreshStatus() {
  loading.value = true
  try {
    const response = await fetch('/api/v1/models/status')
    const result = await response.json()
    if (result.code === 200) {
      modelStatus.value = result.data
      routerStats.value = result.data.router_stats || {}
      finetuneStatus.value = result.data.finetune_status || {}
      modelConfig.value = {
        ...modelConfig.value,
        ...result.data.config
      }
    }
  } catch (error) {
    ElMessage.error('获取模型状态失败')
  } finally {
    loading.value = false
  }
}

async function triggerFinetune(force: boolean = false) {
  try {
    const response = await fetch('/api/v1/models/finetune/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ force })
    })
    const result = await response.json()
    if (result.code === 200) {
      ElMessage.success('微调触发成功')
      refreshStatus()
    } else {
      ElMessage.error(result.message || '微调触发失败')
    }
  } catch (error) {
    ElMessage.error('微调触发失败')
  }
}

async function rollbackModel() {
  try {
    const response = await fetch('/api/v1/models/finetune/rollback', {
      method: 'POST'
    })
    const result = await response.json()
    if (result.code === 200) {
      ElMessage.success('模型回滚成功')
      refreshStatus()
    } else {
      ElMessage.error(result.message || '模型回滚失败')
    }
  } catch (error) {
    ElMessage.error('模型回滚失败')
  }
}

async function updateConfig(config: any) {
  try {
    const response = await fetch('/api/v1/models/config', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(config)
    })
    const result = await response.json()
    if (result.code === 200) {
      ElMessage.success('配置更新成功')
      refreshStatus()
    } else {
      ElMessage.error(result.message || '配置更新失败')
    }
  } catch (error) {
    ElMessage.error('配置更新失败')
  }
}
</script>

<style scoped lang="scss">
.model-view {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h2 {
      margin: 0;
      font-size: 20px;
      color: #303133;
    }
  }

  :deep(.el-tabs) {
    margin-top: 20px;
  }
}
</style>
