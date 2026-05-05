<template>
  <div class="status-overview">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <h3>{{ t('modelManagement.localModel') }}</h3>
              <el-tag :type="modelStatus.local_model?.available ? 'success' : 'danger'">
                {{ modelStatus.local_model?.available ? t('common.online') : t('common.offline') }}
              </el-tag>
            </div>
          </template>
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item :label="t('modelManagement.modelName')">
              {{ modelStatus.local_model?.name || '-' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.baseUrl')">
              {{ modelStatus.local_model?.base_url || '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <div class="card-header">
              <h3>{{ t('modelManagement.cloudModel') }}</h3>
              <el-tag :type="modelStatus.cloud_model?.available ? 'success' : 'warning'">
                {{ modelStatus.cloud_model?.available ? t('common.connected') : t('common.notConfigured') }}
              </el-tag>
            </div>
          </template>
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item :label="t('modelManagement.provider')">
              {{ modelStatus.cloud_model?.provider || '-' }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.modelName')">
              {{ modelStatus.cloud_model?.name || '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>

    <el-row
      :gutter="20"
      style="margin-top: 20px;"
    >
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.routePolicy') }}</h3>
          </template>
          <el-descriptions
            :column="4"
            border
          >
            <el-descriptions-item :label="t('modelManagement.fallbackThreshold')">
              {{ modelStatus.config?.fallback_threshold || 3 }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.localTimeout')">
              {{ modelStatus.config?.local_timeout || 30 }}s
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.autoTrigger')">
              {{ modelStatus.config?.finetune_auto_trigger ? t('common.enabled') : t('common.disabled') }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.minSamples')">
              {{ modelStatus.config?.finetune_min_samples || 50 }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

defineProps<{
  modelStatus: {
    local_model?: { name: string; available: boolean; base_url: string }
    cloud_model?: { provider: string; name: string; available: boolean }
    config?: {
      fallback_threshold?: number
      local_timeout?: number
      finetune_auto_trigger?: boolean
      finetune_min_samples?: number
    }
  }
}>()
</script>

<style scoped lang="scss">
.status-overview {
  .card-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    h3 {
      margin: 0;
      font-size: 16px;
      color: #303133;
    }
  }
}
</style>
