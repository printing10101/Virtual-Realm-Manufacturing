<template>
  <div class="finetune-manager">
    <el-row :gutter="20">
      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.finetuneStatus') }}</h3>
          </template>
          <el-descriptions
            :column="2"
            border
          >
            <el-descriptions-item :label="t('modelManagement.status')">
              <el-tag :type="getStatusType(finetuneStatus?.status ?? 'idle')">
                {{ getStatusLabel(finetuneStatus?.status ?? 'idle') }}
              </el-tag>
            </el-descriptions-item>
            <el-descriptions-item :label="t('modelManagement.lastFinetune')">
              {{ finetuneStatus?.last_finetune_date ? formatDate(finetuneStatus.last_finetune_date) : '-' }}
            </el-descriptions-item>
          </el-descriptions>
        </el-card>
      </el-col>

      <el-col :span="12">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.actions') }}</h3>
          </template>
          <div class="action-buttons">
            <el-button
              type="primary"
              :loading="triggering"
              @click="$emit('trigger', false)"
            >
              {{ t('modelManagement.triggerFinetune') }}
            </el-button>
            <el-button
              type="warning"
              :loading="triggering"
              @click="$emit('trigger', true)"
            >
              {{ t('modelManagement.forceTrigger') }}
            </el-button>
            <el-button
              type="danger"
              :loading="rollingback"
              @click="$emit('rollback')"
            >
              {{ t('modelManagement.rollback') }}
            </el-button>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-row style="margin-top: 20px;">
      <el-col :span="24">
        <el-card shadow="hover">
          <template #header>
            <h3>{{ t('modelManagement.finetuneHistory') }}</h3>
          </template>
          <el-table
            :data="historyData"
            style="width: 100%;"
            border
          >
            <el-table-column
              prop="timestamp"
              :label="t('modelManagement.time')"
            />
            <el-table-column
              prop="status"
              :label="t('modelManagement.status')"
            >
              <template #default="{ row }">
                <el-tag :type="getStatusType(row.status)">
                  {{ getStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column :label="t('modelManagement.details')">
              <template #default="{ row }">
                {{ JSON.stringify(row.details).slice(0, 100) }}
              </template>
            </el-table-column>
          </el-table>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()
const triggering = ref(false)
const rollingback = ref(false)

const props = defineProps<{
  finetuneStatus?: {
    status?: string
    last_finetune_date?: string
    history?: Array<{ status: string; timestamp: string; details: any }>
  }
}>()

const historyData = computed(() => {
  return (props.finetuneStatus?.history || []).map(h => ({
    timestamp: formatDate(h.timestamp),
    status: h.status,
    details: h.details
  })).reverse().slice(0, 20)
})

function formatDate(dateStr: string) {
  if (!dateStr) return '-'
  try {
    const date = new Date(dateStr)
    return date.toLocaleString('zh-CN')
  } catch {
    return dateStr
  }
}

function getStatusType(status: string) {
  switch (status) {
    case 'completed': return 'success'
    case 'running': return 'warning'
    case 'failed': return 'danger'
    case 'rolled_back': return 'info'
    default: return 'info'
  }
}

function getStatusLabel(status: string) {
  switch (status) {
    case 'completed': return '已完成'
    case 'running': return '进行中'
    case 'failed': return '失败'
    case 'rolled_back': return '已回滚'
    case 'idle': return '空闲'
    default: return status
  }
}
</script>

<style scoped lang="scss">
.finetune-manager {
  h3 {
    margin: 0;
    font-size: 16px;
    color: #303133;
  }

  .action-buttons {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }
}
</style>
