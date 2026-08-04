<template>
  <div
    v-loading="agentStore.detailLoading"
    class="agent-detail-page"
  >
    <div class="detail-header">
      <el-button
        :icon="ArrowLeft"
        @click="$router.push({ name: 'agent-dashboard' })"
      >
        {{ t('agentDetail.btnBackToList') }}
      </el-button>
      <h2 v-if="agentStore.currentAgent">
        {{ t('agentDetail.agentDetailTitle', { agentId: agentStore.currentAgent.agent_id }) }}
      </h2>
      <div
        v-if="agentStore.currentAgent"
        class="detail-actions"
      >
        <el-tag
          :type="agentStore.statusTagType(agentStore.currentAgent.status)"
          size="large"
        >
          {{ agentStore.statusLabel(agentStore.currentAgent.status) }}
        </el-tag>
        <el-button
          type="primary"
          size="small"
          @click="refreshDetail"
        >
          {{ t('agentDetail.btnRefresh') }}
        </el-button>
        <el-button
          type="warning"
          size="small"
          @click="showCloneDialog = true"
        >
          {{ t('agentDetail.btnClone') }}
        </el-button>
      </div>
    </div>

    <el-empty
      v-if="!agentStore.currentAgent && !agentStore.detailLoading"
      :description="t('agentDetail.emptyAgentNotFound')"
    />

    <template v-if="agentStore.currentAgent">
      <el-row
        :gutter="16"
        class="info-row"
      >
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              {{ t('agentDetail.sectionBasicInfo') }}
            </template>
            <el-descriptions
              :column="1"
              size="small"
              border
            >
              <el-descriptions-item :label="t('agentDetail.labelAgentId')">
                {{ agentStore.currentAgent.agent_id }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelCurrentTask')">
                {{ agentStore.currentAgent.current_task_id || t('agentDetail.textNone') }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelLastHeartbeat')">
                {{ agentStore.formatTime(agentStore.currentAgent.last_heartbeat) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelCreatedAt')">
                {{ agentStore.formatTime(agentStore.currentAgent.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelUpdatedAt')">
                {{ agentStore.formatTime(agentStore.currentAgent.updated_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelSchemaVersion')">
                {{ agentStore.currentAgent.state_version?.schema_version || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              {{ t('agentDetail.sectionSessionContext') }}
            </template>
            <el-descriptions
              :column="1"
              size="small"
              border
            >
              <el-descriptions-item :label="t('agentDetail.labelTaskType')">
                {{ agentStore.currentAgent.session_context?.task_type || '-' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelCurrentStage')">
                {{ agentStore.currentAgent.session_context?.current_stage || '-' }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelTaskDescription')">
                <el-text truncated>
                  {{ agentStore.currentAgent.session_context?.task_description || t('agentDetail.textNone') }}
                </el-text>
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelInjectedSkills')">
                <el-tag
                  v-for="skill in agentStore.currentAgent.session_context?.injected_skills || []"
                  :key="skill"
                  size="small"
                  style="margin: 2px"
                >
                  {{ skill }}
                </el-tag>
                <span v-if="!(agentStore.currentAgent.session_context?.injected_skills || []).length">-</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelActiveContextKeys')">
                <el-tag
                  v-for="key in agentStore.currentAgent.session_context?.active_context_keys || []"
                  :key="key"
                  size="small"
                  type="info"
                  style="margin: 2px"
                >
                  {{ key }}
                </el-tag>
                <span v-if="!(agentStore.currentAgent.session_context?.active_context_keys || []).length">-</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('agentDetail.labelConversationHistory')">
                {{ t('agentDetail.textEntriesCount', { count: (agentStore.currentAgent.session_context?.conversation_history || []).length }) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card
            shadow="hover"
            class="checkpoint-card"
          >
            <template #header>
              <div class="card-header-flex">
                <span>{{ t('agentDetail.sectionCurrentCheckpoint') }}</span>
                <el-button
                  size="small"
                  type="primary"
                  @click="showCheckpointDialog = true"
                >
                  {{ t('agentDetail.btnSaveManually') }}
                </el-button>
              </div>
            </template>
            <template v-if="agentStore.currentAgent.checkpoint">
              <el-descriptions
                :column="1"
                size="small"
                border
              >
                <el-descriptions-item :label="t('agentDetail.labelCheckpointId')">
                  {{ agentStore.currentAgent.checkpoint.checkpoint_id }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('agentDetail.labelEpoch')">
                  {{ agentStore.currentAgent.checkpoint.epoch }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('agentDetail.labelStep')">
                  {{ agentStore.currentAgent.checkpoint.step }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('agentDetail.labelBestMetric')">
                  {{ agentStore.currentAgent.checkpoint.best_metric ?? '-' }}
                  <span v-if="agentStore.currentAgent.checkpoint.best_metric !== null">
                    ({{ agentStore.currentAgent.checkpoint.best_metric_name }})
                  </span>
                </el-descriptions-item>
                <el-descriptions-item :label="t('agentDetail.labelType')">
                  {{ agentStore.currentAgent.checkpoint.checkpoint_type }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('agentDetail.labelFileSize')">
                  {{ formatBytes(agentStore.currentAgent.checkpoint.file_size_bytes) }}
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <el-empty
              v-else
              :description="t('agentDetail.emptyNoCheckpoint')"
              :image-size="60"
            />
          </el-card>
        </el-col>
      </el-row>

      <AgentMemoryPanel
        :memory="agentStore.currentAgent.memory || []"
        :view-mode="viewMode"
        @update:view-mode="viewMode = $event"
      />

      <AgentCheckpointHistory
        :checkpoints="agentStore.currentAgent.checkpoints_history || []"
        @rollback="handleRollback"
      />
    </template>

    <AgentSaveCheckpointDialog
      :visible="showCheckpointDialog"
      @update:visible="showCheckpointDialog = $event"
      @save="handleSaveCheckpoint"
    />

    <AgentCloneDialog
      :visible="showCloneDialog"
      @update:visible="showCloneDialog = $event"
      @clone="handleClone"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { ArrowLeft } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useAgentStore } from '@/stores/agents'

import AgentMemoryPanel from '@/components/agent/AgentMemoryPanel.vue'
import AgentCheckpointHistory from '@/components/agent/AgentCheckpointHistory.vue'
import AgentSaveCheckpointDialog from '@/components/agent/AgentSaveCheckpointDialog.vue'
import AgentCloneDialog from '@/components/agent/AgentCloneDialog.vue'

const { t } = useI18n()
const agentStore = useAgentStore()
const route = useRoute()
const agentId = computed(() => route.params.agentId as string)

const viewMode = ref<'list' | 'chart'>('list')
const showCheckpointDialog = ref(false)
const showCloneDialog = ref(false)

onMounted(() => {
  refreshDetail()
})

watch(agentId, () => {
  refreshDetail()
})

async function refreshDetail() {
  await agentStore.fetchAgentDetail(agentId.value)
}

function formatBytes(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let size = bytes
  while (size >= 1024 && i < units.length - 1) {
    size /= 1024
    i++
  }
  return `${size.toFixed(1)} ${units[i]}`
}

async function handleSaveCheckpoint(data: {
  epoch: number
  step: number
  best_metric_name: string
  best_metric: string
  checkpoint_type: string
}) {
  try {
    const payload: Record<string, unknown> = {
      epoch: data.epoch,
      step: data.step,
      best_metric_name: data.best_metric_name,
      checkpoint_type: data.checkpoint_type,
    }
    if (data.best_metric) {
      payload.best_metric = parseFloat(data.best_metric)
    }
    await agentStore.saveCheckpoint(agentId.value, payload)
    ElMessage.success(t('agentDetail.msgSaveCheckpointSuccess'))
    showCheckpointDialog.value = false
    refreshDetail()
  } catch (e: unknown) {
    ElMessage.error(t('agentDetail.msgSaveCheckpointFailed', { error: (e as Error).message }))
  }
}

async function handleRollback(checkpointId: string) {
  try {
    await agentStore.rollbackCheckpoint(agentId.value, checkpointId)
    ElMessage.success(t('agentDetail.msgRollbackSuccess'))
    refreshDetail()
  } catch (e: unknown) {
    ElMessage.error(t('agentDetail.msgRollbackFailed', { error: (e as Error).message }))
  }
}

async function handleClone(targetId: string) {
  if (!targetId) {
    ElMessage.warning(t('agentDetail.msgCloneTargetRequired'))
    return
  }
  try {
    await agentStore.cloneAgent(agentId.value, targetId)
    ElMessage.success(t('agentDetail.msgCloneSuccess', { agentId: targetId }))
    showCloneDialog.value = false
  } catch (e: unknown) {
    ElMessage.error(t('agentDetail.msgCloneFailed', { error: (e as Error).message }))
  }
}
</script>

<style scoped>
.agent-detail-page {
  max-width: 1400px;
  margin: 0 auto;
}

.detail-header {
  display: flex;
  align-items: center;
  gap: 16px;
  margin-bottom: 20px;
}

.detail-header h2 {
  margin: 0;
  flex: 1;
}

.detail-actions {
  display: flex;
  gap: 8px;
  align-items: center;
}

.info-row {
  margin-bottom: 16px;
}

.card-header-flex {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>