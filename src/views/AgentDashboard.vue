<template>
  <div class="agent-dashboard">
    <!-- ==================== 1. Page Header ==================== -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('agentDashboard.pageTitle') }}</h1>
        <p class="subtitle">
          {{ t('agentDashboard.pageSubtitle') }}
        </p>
      </div>
      <div class="page-header__actions">
        <el-select
          v-model="statusFilter"
          :placeholder="t('agentDashboard.placeholderAllStatus')"
          size="small"
          style="width: 140px"
          @change="handleFilterChange"
        >
          <el-option
            :label="t('agentDashboard.statusAll')"
            value="all"
          />
          <el-option
            :label="t('agentDashboard.statusBusy')"
            value="busy"
          />
          <el-option
            :label="t('agentDashboard.statusIdle')"
            value="idle"
          />
          <el-option
            :label="t('agentDashboard.statusPaused')"
            value="paused"
          />
          <el-option
            :label="t('agentDashboard.statusError')"
            value="error"
          />
          <el-option
            :label="t('agentDashboard.statusStopped')"
            value="stopped"
          />
          <el-option
            :label="t('agentDashboard.statusRecovering')"
            value="recovering"
          />
        </el-select>
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="deployDialogVisible = true"
        >
          {{ t('agentDashboard.btnDeployNew') }}
        </el-button>
      </div>
    </div>

    <!-- ==================== 2. Summary Stats Bar ==================== -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-card__content">
          <span class="stat-card__label">{{ t('agentDashboard.statTotal') }}</span>
          <span class="stat-card__value">{{ stats.total }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__content">
          <span class="stat-card__label">{{ t('agentDashboard.statActive') }}</span>
          <span
            class="stat-card__value"
            style="color: var(--success)"
          >{{ stats.active }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__content">
          <span class="stat-card__label">{{ t('agentDashboard.statIdle') }}</span>
          <span class="stat-card__value">{{ stats.idle }}</span>
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-card__content">
          <span class="stat-card__label">{{ t('agentDashboard.statError') }}</span>
          <span
            class="stat-card__value"
            style="color: var(--error)"
          >{{ stats.error }}</span>
        </div>
      </div>
    </div>

    <!-- ==================== 3. Agent Card Grid ==================== -->
    <div
      v-loading="agentStore.loading"
      class="agent-grid"
    >
      <el-card
        v-for="agent in filteredAgents"
        :key="agent.agent_id"
        class="agent-card"
        shadow="never"
      >
        <!-- Card Top: Icon + Agent ID + Status -->
        <div class="agent-card__header">
          <div class="agent-card__icon agent-card__icon--gradient">
            <el-icon
              :size="22"
              color="#fff"
            >
              <Monitor />
            </el-icon>
          </div>
          <div class="agent-card__info">
            <div class="agent-card__name">
              {{ formatAgentId(agent.agent_id) }}
            </div>
            <el-tag
              :type="agentStore.statusTagType(agent.status)"
              size="small"
              effect="light"
              round
            >
              {{ agentStore.statusLabel(agent.status) }}
            </el-tag>
          </div>
        </div>

        <!-- Current Task -->
        <div class="agent-card__desc">
          {{ t('agentDashboard.currentTask', { task: agent.current_task_id || t('agentDashboard.statusIdle') }) }}
        </div>

        <!-- Stats Row -->
        <div class="agent-card__stats">
          <div class="agent-card__stat">
            <span class="agent-card__stat-label">{{ t('agentDashboard.labelStatus') }}</span>
            <span class="agent-card__stat-value">{{ agentStore.statusLabel(agent.status) }}</span>
          </div>
          <div class="agent-card__stat">
            <span class="agent-card__stat-label">{{ t('agentDashboard.labelHeartbeat') }}</span>
            <span class="agent-card__stat-value">{{ agentStore.formatTime(agent.last_heartbeat) }}</span>
          </div>
          <div class="agent-card__stat">
            <span class="agent-card__stat-label">{{ t('agentDashboard.labelUpdated') }}</span>
            <span class="agent-card__stat-value">{{ agentStore.formatTime(agent.updated_at) }}</span>
          </div>
        </div>

        <!-- Action Buttons -->
        <div class="agent-card__actions">
          <el-button
            size="small"
            type="primary"
            text
            :loading="agentStore.detailLoading"
            @click="handleShowDetail(agent)"
          >
            {{ t('agentDashboard.btnDetail') }}
          </el-button>
          <el-button
            size="small"
            type="success"
            text
            :disabled="agent.status === 'stopped'"
            @click="handleResume(agent)"
          >
            {{ t('agentDashboard.btnRestart') }}
          </el-button>
          <el-button
            size="small"
            type="danger"
            text
            @click="handleDelete(agent)"
          >
            {{ t('agentDashboard.btnDelete') }}
          </el-button>
        </div>
      </el-card>

      <!-- Empty State -->
      <div
        v-if="filteredAgents.length === 0 && !agentStore.loading"
        class="agent-grid__empty"
      >
        <el-empty :description="dataLoadError ? t('agentDashboard.emptyLoadFailed') : t('agentDashboard.emptyNoData')" />
      </div>
    </div>

    <!-- ==================== 4. Activity Timeline ==================== -->
    <div class="activity-section">
      <h2 class="section-title">
        {{ t('agentDashboard.sectionActivity') }}
      </h2>
      <el-empty :description="t('agentDashboard.emptyActivityDev')" />
    </div>

    <!-- ==================== 5. Deploy New Agent Modal ==================== -->
    <el-dialog
      v-model="deployDialogVisible"
      :title="t('agentDashboard.dialogDeployTitle')"
      width="520px"
      :close-on-click-modal="false"
      destroy-on-close
    >
      <el-form
        ref="deployFormRef"
        :model="deployForm"
        :rules="deployRules"
        label-width="80px"
        label-position="left"
      >
        <el-form-item
          :label="t('agentDashboard.labelName')"
          prop="name"
        >
          <el-input
            v-model="deployForm.name"
            :placeholder="t('agentDashboard.placeholderName')"
          />
        </el-form-item>
        <el-form-item
          :label="t('agentDashboard.labelType')"
          prop="type"
        >
          <el-select
            v-model="deployForm.type"
            :placeholder="t('agentDashboard.placeholderType')"
            size="small"
            style="width: 100%"
          >
            <el-option
              :label="t('agentDashboard.typeMachining')"
              value="machining"
            />
            <el-option
              :label="t('agentDashboard.typeInspection')"
              value="inspection"
            />
            <el-option
              :label="t('agentDashboard.typeScheduling')"
              value="scheduling"
            />
            <el-option
              :label="t('agentDashboard.typeInventory')"
              value="inventory"
            />
            <el-option
              :label="t('agentDashboard.typeMaintenance')"
              value="maintenance"
            />
            <el-option
              :label="t('agentDashboard.typeOptimization')"
              value="optimization"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="deployDialogVisible = false">
          {{ t('agentDashboard.btnCancel') }}
        </el-button>
        <el-button
          type="primary"
          :loading="deployLoading"
          @click="handleDeploy"
        >
          {{ t('agentDashboard.btnDeploy') }}
        </el-button>
      </template>
    </el-dialog>

    <!-- ==================== 6. Agent Detail Modal ==================== -->
    <el-dialog
      v-model="detailDialogVisible"
      :title="detailTitle"
      width="720px"
      destroy-on-close
    >
      <div v-loading="agentStore.detailLoading">
        <template v-if="agentStore.currentAgent">
          <!-- Basic Info -->
          <div class="detail-info">
            <div class="detail-info__row">
              <span class="detail-info__label">Agent ID</span>
              <span>{{ agentStore.currentAgent.agent_id }}</span>
            </div>
            <div class="detail-info__row">
              <span class="detail-info__label">{{ t('agentDashboard.labelStatus') }}</span>
              <el-tag
                :type="agentStore.statusTagType(agentStore.currentAgent.status)"
                size="small"
                effect="light"
                round
              >
                {{ agentStore.statusLabel(agentStore.currentAgent.status) }}
              </el-tag>
            </div>
            <div class="detail-info__row">
              <span class="detail-info__label">{{ t('agentDashboard.detailCurrentTask') }}</span>
              <span>{{ agentStore.currentAgent.current_task_id || t('agentDashboard.none') }}</span>
            </div>
            <div class="detail-info__row">
              <span class="detail-info__label">{{ t('agentDashboard.detailLastHeartbeat') }}</span>
              <span>{{ agentStore.formatTime(agentStore.currentAgent.last_heartbeat) }}</span>
            </div>
            <div class="detail-info__row">
              <span class="detail-info__label">{{ t('agentDashboard.detailCreatedAt') }}</span>
              <span>{{ agentStore.formatTime(agentStore.currentAgent.created_at) }}</span>
            </div>
            <div class="detail-info__row">
              <span class="detail-info__label">{{ t('agentDashboard.detailUpdatedAt') }}</span>
              <span>{{ agentStore.formatTime(agentStore.currentAgent.updated_at) }}</span>
            </div>
          </div>

          <!-- Session Context -->
          <div
            v-if="agentStore.currentAgent.session_context"
            class="detail-config"
          >
            <h4 class="detail-config__title">
              {{ t('agentDashboard.sectionSessionContext') }}
            </h4>
            <div class="detail-config__row">
              <span class="detail-config__label">{{ t('agentDashboard.detailTaskDesc') }}</span>
              <span>{{ agentStore.currentAgent.session_context.task_description || t('agentDashboard.none') }}</span>
            </div>
            <div class="detail-config__row">
              <span class="detail-config__label">{{ t('agentDashboard.detailCurrentStage') }}</span>
              <span>{{ agentStore.currentAgent.session_context.current_stage || t('agentDashboard.none') }}</span>
            </div>
            <div class="detail-config__row">
              <span class="detail-config__label">{{ t('agentDashboard.detailInjectedSkills') }}</span>
              <span>
                <el-tag
                  v-for="skill in agentStore.currentAgent.session_context.injected_skills"
                  :key="skill"
                  size="small"
                  effect="plain"
                  style="margin-right: 4px; margin-bottom: 2px"
                >
                  {{ skill }}
                </el-tag>
                <span v-if="!agentStore.currentAgent.session_context.injected_skills?.length">{{ t('agentDashboard.none') }}</span>
              </span>
            </div>
          </div>

          <!-- Checkpoint Info -->
          <div
            v-if="agentStore.currentAgent.checkpoint"
            class="detail-config"
          >
            <h4 class="detail-config__title">
              {{ t('agentDashboard.sectionCheckpoint') }}
            </h4>
            <div class="detail-config__row">
              <span class="detail-config__label">{{ t('agentDashboard.detailCheckpointId') }}</span>
              <span>{{ agentStore.currentAgent.checkpoint.checkpoint_id }}</span>
            </div>
            <div class="detail-config__row">
              <span class="detail-config__label">Epoch</span>
              <span>{{ agentStore.currentAgent.checkpoint.epoch }}</span>
            </div>
            <div class="detail-config__row">
              <span class="detail-config__label">Step</span>
              <span>{{ agentStore.currentAgent.checkpoint.step }}</span>
            </div>
            <div class="detail-config__row">
              <span class="detail-config__label">{{ t('agentDashboard.detailBestMetric') }}</span>
              <span>{{ agentStore.currentAgent.checkpoint.best_metric ?? '-' }}</span>
            </div>
          </div>

          <!-- Memory Entries -->
          <div
            v-if="agentStore.currentAgent.memory?.length"
            class="detail-config"
          >
            <h4 class="detail-config__title">
              {{ t('agentDashboard.memoryEntries', { count: agentStore.currentAgent.memory.length }) }}
            </h4>
            <div class="detail-logs">
              <div
                v-for="(entry, idx) in agentStore.currentAgent.memory.slice(0, 10)"
                :key="entry.memory_id || idx"
                class="detail-log-item"
              >
                <div class="detail-log-item__header">
                  <span class="detail-log-item__time">{{ agentStore.formatTime(entry.created_at) }}</span>
                  <el-tag
                    size="small"
                    effect="plain"
                  >
                    {{ entry.memory_type }}
                  </el-tag>
                </div>
                <div class="detail-log-item__text">
                  {{ entry.content.length > 120 ? entry.content.slice(0, 120) + '...' : entry.content }}
                </div>
              </div>
            </div>
          </div>

          <!-- No Detail Data Fallback -->
          <div
            v-if="!agentStore.currentAgent.session_context && !agentStore.currentAgent.checkpoint && !agentStore.currentAgent.memory?.length"
            class="detail-config"
          >
            <p style="margin: 0; color: var(--text-tertiary); font-size: 0.875rem;">
              {{ t('agentDashboard.noDetailData') }}
            </p>
          </div>
        </template>
      </div>

      <template #footer>
        <el-button
          type="success"
          text
          :disabled="!agentStore.currentAgent || agentStore.currentAgent.status === 'stopped'"
          @click="handleResumeFromDetail"
        >
          {{ t('agentDashboard.btnRestart') }}
        </el-button>
        <el-button
          type="danger"
          :disabled="!agentStore.currentAgent"
          @click="handleDeleteFromDetail"
        >
          {{ t('agentDashboard.btnDelete') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Monitor } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useAgentStore } from '@/stores/agents'
import type { AgentSummary } from '@/stores/agents'

/* ------------------------------------------------------------------ */
/*  i18n                                                               */
/* ------------------------------------------------------------------ */
const { t } = useI18n()

/* ------------------------------------------------------------------ */
/*  Store                                                              */
/* ------------------------------------------------------------------ */
const agentStore = useAgentStore()

/* ------------------------------------------------------------------ */
/*  Data Load Error State                                              */
/* ------------------------------------------------------------------ */
const dataLoadError = ref(false)

/* ------------------------------------------------------------------ */
/*  Lifecycle                                                          */
/* ------------------------------------------------------------------ */
onMounted(async () => {
  try {
    await agentStore.fetchAgents()
  } catch {
    dataLoadError.value = true
  }
})

/* ------------------------------------------------------------------ */
/*  Computed: Display Agents & Stats                                   */
/* ------------------------------------------------------------------ */
const displayAgents = computed<AgentSummary[]>(() => agentStore.agents)

const stats = computed(() => {
  const agents = agentStore.agents
  const activeCount = agents.filter((a) => a.status === 'busy').length
  const idleCount = agents.filter((a) => a.status === 'idle').length
  const errorCount = agents.filter((a) => a.status === 'error').length
  return { total: agents.length, active: activeCount, idle: idleCount, error: errorCount }
})

/* ------------------------------------------------------------------ */
/*  Filter                                                             */
/* ------------------------------------------------------------------ */
const statusFilter = ref<string>('all')

const filteredAgents = computed(() => {
  if (statusFilter.value === 'all') return displayAgents.value
  return displayAgents.value.filter((a) => a.status === statusFilter.value)
})

function handleFilterChange(val: string) {
  if (agentStore.agents.length > 0) {
    agentStore.statusFilter = val === 'all' ? null : val
    agentStore.fetchAgents()
  }
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */
function formatAgentId(id: string): string {
  // 将 agent-001 转换为 Agent-001
  if (!id) return '-'
  return id.charAt(0).toUpperCase() + id.slice(1)
}

/* ------------------------------------------------------------------ */
/*  Deploy Dialog                                                       */
/* ------------------------------------------------------------------ */
const deployDialogVisible = ref(false)
const deployLoading = ref(false)
const deployFormRef = ref<FormInstance>()
const deployForm = ref({
  name: '',
  type: '',
})

const deployRules: FormRules = {
  name: [{ required: true, message: t('agentDashboard.msgNameRequired'), trigger: 'blur' }],
  type: [{ required: true, message: t('agentDashboard.msgTypeRequired'), trigger: 'change' }],
}

async function handleDeploy() {
  const valid = await deployFormRef.value?.validate().catch(() => false)
  if (!valid) return

  deployLoading.value = true
  try {
    // TODO: 调用部署 API
    ElMessage.success(t('agentDashboard.msgDeploySuccess', { name: deployForm.value.name }))
    deployDialogVisible.value = false
    deployForm.value = { name: '', type: '' }
  } catch {
    ElMessage.error(t('agentDashboard.msgDeployFailed'))
  } finally {
    deployLoading.value = false
  }
}

/* ------------------------------------------------------------------ */
/*  Detail Dialog                                                       */
/* ------------------------------------------------------------------ */
const detailDialogVisible = ref(false)

const detailTitle = computed(() => {
  if (!agentStore.currentAgent) return t('agentDashboard.detailTitle')
  return t('agentDashboard.detailTitleWithId', { id: formatAgentId(agentStore.currentAgent.agent_id) })
})

async function handleShowDetail(agent: AgentSummary) {
  detailDialogVisible.value = true
  try {
    await agentStore.fetchAgentDetail(agent.agent_id)
  } catch {
    ElMessage.error(t('agentDashboard.msgGetDetailFailed'))
  }
}

/* ------------------------------------------------------------------ */
/*  Card Actions                                                        */
/* ------------------------------------------------------------------ */
async function handleResume(agent: AgentSummary) {
  try {
    await agentStore.resumeAgent(agent.agent_id)
    ElMessage.success(t('agentDashboard.msgRestartSuccess', { id: formatAgentId(agent.agent_id) }))
    await agentStore.fetchAgents()
  } catch {
    ElMessage.error(t('agentDashboard.msgRestartFailed'))
  }
}

async function handleDelete(agent: AgentSummary) {
  try {
    await ElMessageBox.confirm(
      t('agentDashboard.msgDeleteConfirm', { id: formatAgentId(agent.agent_id) }),
      t('agentDashboard.msgDeleteConfirmTitle'),
      {
        confirmButtonText: t('agentDashboard.btnConfirmDelete'),
        cancelButtonText: t('agentDashboard.btnCancel'),
        type: 'warning',
      },
    )
    await agentStore.deleteAgent(agent.agent_id)
    ElMessage.success(t('agentDashboard.msgDeleteSuccess', { id: formatAgentId(agent.agent_id) }))
  } catch {
    // 用户取消
  }
}

/* ------------------------------------------------------------------ */
/*  Detail Dialog Actions                                               */
/* ------------------------------------------------------------------ */
async function handleResumeFromDetail() {
  if (!agentStore.currentAgent) return
  await handleResume(agentStore.currentAgent)
}

async function handleDeleteFromDetail() {
  if (!agentStore.currentAgent) return
  try {
    await ElMessageBox.confirm(
      t('agentDashboard.msgDeleteConfirm', { id: formatAgentId(agentStore.currentAgent.agent_id) }),
      t('agentDashboard.msgDeleteConfirmTitle'),
      {
        confirmButtonText: t('agentDashboard.btnConfirmDelete'),
        cancelButtonText: t('agentDashboard.btnCancel'),
        type: 'warning',
      },
    )
    await agentStore.deleteAgent(agentStore.currentAgent.agent_id)
    detailDialogVisible.value = false
    ElMessage.success(t('agentDashboard.msgDeleteSuccess', { id: formatAgentId(agentStore.currentAgent.agent_id) }))
  } catch {
    // 用户取消
  }
}
</script>

<style scoped>
/* ================================================================ */
/*  Page-level layout                                                  */
/* ================================================================ */
.agent-dashboard {
  max-width: var(--content-max-width);
  margin: 0 auto;
  padding: var(--page-padding);
}

/* ================================================================ */
/*  3. Agent Card Grid                                                 */
/* ================================================================ */
.agent-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 16px;
  margin-bottom: 32px;
}

.agent-grid__empty {
  grid-column: 1 / -1;
  display: flex;
  justify-content: center;
  padding: 60px 0;
}

.agent-card {
  border-radius: var(--radius-lg) !important;
  box-shadow: var(--shadow-sm) !important;
  transition: box-shadow var(--transition-normal), transform var(--transition-normal);
}

.agent-card:hover {
  box-shadow: var(--shadow-md) !important;
  transform: translateY(-2px);
}

/* -- Card Header (icon + name + badge) -- */
.agent-card__header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 10px;
}

.agent-card__icon {
  width: 42px;
  height: 42px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.agent-card__icon--gradient {
  background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary, #5856d6));
}

.agent-card__info {
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.agent-card__name {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--text-primary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* -- Description / Current Task -- */
.agent-card__desc {
  font-size: 0.8125rem;
  color: var(--text-tertiary);
  margin-bottom: 14px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* -- Stats Row -- */
.agent-card__stats {
  display: flex;
  gap: 20px;
  margin-bottom: 14px;
}

.agent-card__stat {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.agent-card__stat-label {
  font-size: 0.6875rem;
  color: var(--text-tertiary);
  text-transform: uppercase;
  letter-spacing: 0.03em;
}

.agent-card__stat-value {
  font-size: 0.8125rem;
  font-weight: 600;
  color: var(--text-primary);
  max-width: 120px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* -- Action Buttons -- */
.agent-card__actions {
  display: flex;
  gap: 4px;
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}

/* ================================================================ */
/*  4. Activity Timeline                                                */
/* ================================================================ */
.section-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

.activity-section {
  margin-bottom: 24px;
}

.timeline-content {
  font-size: 0.875rem;
}

.timeline-content__agent {
  font-weight: 600;
  color: var(--text-primary);
  margin-right: 6px;
}

.timeline-content__action {
  color: var(--text-secondary);
}

/* ================================================================ */
/*  6. Detail Modal internals                                           */
/* ================================================================ */
.detail-info {
  display: flex;
  flex-wrap: wrap;
  gap: 16px 32px;
  margin-bottom: 20px;
}

.detail-info__row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.detail-info__label {
  font-size: 0.8125rem;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.detail-config {
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  padding: 16px;
  margin-bottom: 20px;
}

.detail-config__title,
.detail-logs__title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 12px;
}

.detail-config__row {
  display: flex;
  justify-content: space-between;
  padding: 6px 0;
  font-size: 0.8125rem;
  border-bottom: 1px solid var(--border-light);
}

.detail-config__row:last-child {
  border-bottom: none;
}

.detail-config__label {
  color: var(--text-tertiary);
  flex-shrink: 0;
  margin-right: 12px;
}

.detail-logs {
  max-height: 240px;
  overflow-y: auto;
}

.detail-log-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-light);
}

.detail-log-item:last-child {
  border-bottom: none;
}

.detail-log-item__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 4px;
}

.detail-log-item__time {
  font-size: 0.75rem;
  color: var(--text-tertiary);
}

.detail-log-item__text {
  font-size: 0.8125rem;
  color: var(--text-secondary);
}

/* ================================================================ */
/*  Responsive                                                         */
/* ================================================================ */
@media (max-width: 1024px) {
  .agent-grid {
    grid-template-columns: repeat(2, 1fr);
  }
}

@media (max-width: 640px) {
  .agent-grid {
    grid-template-columns: 1fr;
  }

  .page-header {
    flex-direction: column;
    gap: 12px;
  }
}
</style>
