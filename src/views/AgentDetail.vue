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
        返回列表
      </el-button>
      <h2 v-if="agentStore.currentAgent">
        代理详情: {{ agentStore.currentAgent.agent_id }}
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
          刷新
        </el-button>
        <el-button
          type="warning"
          size="small"
          @click="showCloneDialog = true"
        >
          克隆
        </el-button>
      </div>
    </div>

    <el-empty
      v-if="!agentStore.currentAgent && !agentStore.detailLoading"
      description="未找到代理信息"
    />

    <template v-if="agentStore.currentAgent">
      <el-row
        :gutter="16"
        class="info-row"
      >
        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              基本信息
            </template>
            <el-descriptions
              :column="1"
              size="small"
              border
            >
              <el-descriptions-item label="代理ID">
                {{ agentStore.currentAgent.agent_id }}
              </el-descriptions-item>
              <el-descriptions-item label="当前任务">
                {{ agentStore.currentAgent.current_task_id || '无' }}
              </el-descriptions-item>
              <el-descriptions-item label="最后心跳">
                {{ agentStore.formatTime(agentStore.currentAgent.last_heartbeat) }}
              </el-descriptions-item>
              <el-descriptions-item label="创建时间">
                {{ agentStore.formatTime(agentStore.currentAgent.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="更新时间">
                {{ agentStore.formatTime(agentStore.currentAgent.updated_at) }}
              </el-descriptions-item>
              <el-descriptions-item label="Schema版本">
                {{ agentStore.currentAgent.state_version?.schema_version || '-' }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>
        </el-col>

        <el-col :span="8">
          <el-card shadow="hover">
            <template #header>
              会话上下文
            </template>
            <el-descriptions
              :column="1"
              size="small"
              border
            >
              <el-descriptions-item label="任务类型">
                {{ agentStore.currentAgent.session_context?.task_type || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="当前阶段">
                {{ agentStore.currentAgent.session_context?.current_stage || '-' }}
              </el-descriptions-item>
              <el-descriptions-item label="任务描述">
                <el-text truncated>
                  {{ agentStore.currentAgent.session_context?.task_description || '无' }}
                </el-text>
              </el-descriptions-item>
              <el-descriptions-item label="已注入技能">
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
              <el-descriptions-item label="活跃上下文键">
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
              <el-descriptions-item label="对话历史">
                {{ (agentStore.currentAgent.session_context?.conversation_history || []).length }} 条
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
                <span>当前检查点</span>
                <el-button
                  size="small"
                  type="primary"
                  @click="showCheckpointDialog = true"
                >
                  手动保存
                </el-button>
              </div>
            </template>
            <template v-if="agentStore.currentAgent.checkpoint">
              <el-descriptions
                :column="1"
                size="small"
                border
              >
                <el-descriptions-item label="检查点ID">
                  {{ agentStore.currentAgent.checkpoint.checkpoint_id }}
                </el-descriptions-item>
                <el-descriptions-item label="Epoch">
                  {{ agentStore.currentAgent.checkpoint.epoch }}
                </el-descriptions-item>
                <el-descriptions-item label="Step">
                  {{ agentStore.currentAgent.checkpoint.step }}
                </el-descriptions-item>
                <el-descriptions-item label="最佳指标">
                  {{ agentStore.currentAgent.checkpoint.best_metric ?? '-' }}
                  <span v-if="agentStore.currentAgent.checkpoint.best_metric !== null">
                    ({{ agentStore.currentAgent.checkpoint.best_metric_name }})
                  </span>
                </el-descriptions-item>
                <el-descriptions-item label="类型">
                  {{ agentStore.currentAgent.checkpoint.checkpoint_type }}
                </el-descriptions-item>
                <el-descriptions-item label="文件大小">
                  {{ formatBytes(agentStore.currentAgent.checkpoint.file_size_bytes) }}
                </el-descriptions-item>
              </el-descriptions>
            </template>
            <el-empty
              v-else
              description="暂无检查点"
              :image-size="60"
            />
          </el-card>
        </el-col>
      </el-row>

      <el-card
        shadow="hover"
        class="memory-card"
      >
        <template #header>
          <div class="card-header-flex">
            <span>代理记忆 ({{ agentStore.currentAgent.memory?.length || 0 }} 条)</span>
            <el-button
              size="small"
              @click="viewMode = viewMode === 'list' ? 'chart' : 'list'"
            >
              {{ viewMode === 'list' ? '可视化' : '列表' }}
            </el-button>
          </div>
        </template>
        <template v-if="viewMode === 'list'">
          <el-table
            v-if="(agentStore.currentAgent.memory || []).length > 0"
            :data="sortedMemory"
            stripe
            max-height="300"
          >
            <el-table-column
              prop="memory_type"
              label="类型"
              width="100"
            >
              <template #default="{ row }">
                <el-tag size="small">
                  {{ row.memory_type }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="content"
              label="内容"
              min-width="200"
            >
              <template #default="{ row }">
                <el-text truncated>
                  {{ row.content }}
                </el-text>
              </template>
            </el-table-column>
            <el-table-column
              prop="importance"
              label="重要性"
              width="120"
              sortable
            >
              <template #default="{ row }">
                <el-progress
                  :percentage="Math.round(row.importance * 100)"
                  :stroke-width="8"
                  :color="importanceColor(row.importance)"
                />
              </template>
            </el-table-column>
            <el-table-column
              prop="tags"
              label="标签"
              width="160"
            >
              <template #default="{ row }">
                <el-tag
                  v-for="tag in (row.tags || [])"
                  :key="tag"
                  size="small"
                  style="margin: 1px"
                >
                  {{ tag }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              label="访问次数"
              width="80"
              sortable
              prop="access_count"
            />
          </el-table>
          <el-empty
            v-else
            description="空记忆"
            :image-size="50"
          />
        </template>
        <template v-else>
          <div class="memory-chart-container">
            <div
              v-for="entry in sortedMemory.slice(0, 20)"
              :key="entry.memory_id"
              class="memory-bar-item"
            >
              <div class="memory-bar-label">
                <el-tag
                  size="small"
                  :type="entry.memory_type === 'observation' ? 'info' : entry.memory_type === 'decision' ? 'warning' : 'success'"
                >
                  {{ entry.memory_type }}
                </el-tag>
                <el-text
                  truncated
                  class="memory-bar-text"
                >
                  {{ entry.content.substring(0, 60) }}
                </el-text>
              </div>
              <div class="memory-bar-track">
                <div
                  class="memory-bar-fill"
                  :style="{
                    width: Math.round(entry.importance * 100) + '%',
                    backgroundColor: importanceColor(entry.importance)
                  }"
                />
              </div>
              <span class="memory-bar-value">{{ Math.round(entry.importance * 100) }}%</span>
            </div>
            <el-empty
              v-if="sortedMemory.length === 0"
              description="空记忆"
              :image-size="50"
            />
          </div>
        </template>
      </el-card>

      <el-card
        v-if="(agentStore.currentAgent.checkpoints_history || []).length > 0"
        shadow="hover"
        class="history-card"
      >
        <template #header>
          <span>检查点历史 ({{ agentStore.currentAgent.checkpoints_history.length }} 个)</span>
        </template>
        <el-timeline>
          <el-timeline-item
            v-for="ckpt in agentStore.currentAgent.checkpoints_history.slice(0, 10)"
            :key="ckpt.checkpoint_id"
            :timestamp="agentStore.formatTime(ckpt.created_at)"
            placement="top"
          >
            <el-card
              shadow="hover"
              size="small"
            >
              <div class="checkpoint-timeline-item">
                <el-tag size="small">
                  {{ ckpt.checkpoint_type }}
                </el-tag>
                <span>Epoch {{ ckpt.epoch }}, Step {{ ckpt.step }}</span>
                <span v-if="ckpt.best_metric !== null">
                  最佳 {{ ckpt.best_metric_name }}: {{ ckpt.best_metric }}
                </span>
                <el-button
                  size="small"
                  type="warning"
                  @click="handleRollback(ckpt.checkpoint_id)"
                >
                  回滚
                </el-button>
              </div>
            </el-card>
          </el-timeline-item>
        </el-timeline>
      </el-card>
    </template>

    <el-dialog
      v-model="showCheckpointDialog"
      title="手动保存检查点"
      width="480px"
    >
      <el-form label-position="top">
        <el-form-item label="Epoch">
          <el-input-number
            v-model="checkpointForm.epoch"
            :min="0"
          />
        </el-form-item>
        <el-form-item label="Step">
          <el-input-number
            v-model="checkpointForm.step"
            :min="0"
          />
        </el-form-item>
        <el-form-item label="最佳指标值">
          <el-input
            v-model="checkpointForm.best_metric"
            placeholder="可选"
          />
        </el-form-item>
        <el-form-item label="指标名称">
          <el-input
            v-model="checkpointForm.best_metric_name"
            placeholder="如 loss, accuracy"
          />
        </el-form-item>
        <el-form-item label="检查点类型">
          <el-select v-model="checkpointForm.checkpoint_type">
            <el-option
              label="手动"
              value="manual"
            />
            <el-option
              label="自动"
              value="auto"
            />
            <el-option
              label="Epoch"
              value="epoch"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCheckpointDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleSaveCheckpoint"
        >
          保存
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showCloneDialog"
      title="克隆代理状态"
      width="400px"
    >
      <el-form label-position="top">
        <el-form-item label="目标代理ID">
          <el-input
            v-model="cloneTargetId"
            placeholder="输入新代理ID"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCloneDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="handleClone"
        >
          克隆
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { ArrowLeft } from '@element-plus/icons-vue'
import { useAgentStore } from '@/stores/agents'

const agentStore = useAgentStore()
const route = useRoute()
const agentId = computed(() => route.params.agentId as string)

const viewMode = ref<'list' | 'chart'>('list')
const showCheckpointDialog = ref(false)
const showCloneDialog = ref(false)
const cloneTargetId = ref('')

const checkpointForm = ref({
  epoch: 0,
  step: 0,
  best_metric_name: 'loss',
  best_metric: '' as string,
  checkpoint_type: 'manual',
})

const sortedMemory = computed(() => {
  const mem = [...(agentStore.currentAgent?.memory || [])]
  return mem.sort((a, b) => b.importance - a.importance)
})

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

function importanceColor(imp: number): string {
  if (imp >= 0.8) return 'var(--error)'
  if (imp >= 0.5) return 'var(--warning)'
  if (imp >= 0.3) return 'var(--accent-primary)'
  return 'var(--text-tertiary)'
}

async function handleSaveCheckpoint() {
  try {
    const data: Record<string, any> = {
      epoch: checkpointForm.value.epoch,
      step: checkpointForm.value.step,
      best_metric_name: checkpointForm.value.best_metric_name,
      checkpoint_type: checkpointForm.value.checkpoint_type,
    }
    if (checkpointForm.value.best_metric) {
      data.best_metric = parseFloat(checkpointForm.value.best_metric)
    }
    await agentStore.saveCheckpoint(agentId.value, data)
    ElMessage.success('检查点保存成功')
    showCheckpointDialog.value = false
    refreshDetail()
  } catch (e: any) {
    ElMessage.error(`保存失败: ${e.message}`)
  }
}

async function handleRollback(checkpointId: string) {
  try {
    await agentStore.rollbackCheckpoint(agentId.value, checkpointId)
    ElMessage.success('回滚成功')
    refreshDetail()
  } catch (e: any) {
    ElMessage.error(`回滚失败: ${e.message}`)
  }
}

async function handleClone() {
  if (!cloneTargetId.value) {
    ElMessage.warning('请输入目标代理ID')
    return
  }
  try {
    await agentStore.cloneAgent(agentId.value, cloneTargetId.value)
    ElMessage.success(`已克隆到 ${cloneTargetId.value}`)
    showCloneDialog.value = false
    cloneTargetId.value = ''
  } catch (e: any) {
    ElMessage.error(`克隆失败: ${e.message}`)
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

.checkpoint-timeline-item {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.memory-card {
  margin-bottom: 16px;
}

.history-card {
  margin-bottom: 16px;
}

.memory-chart-container {
  max-height: 400px;
  overflow-y: auto;
}

.memory-bar-item {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 4px 0;
}

.memory-bar-label {
  width: 260px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: 4px;
}

.memory-bar-text {
  font-size: 0.82rem;
}

.memory-bar-track {
  flex: 1;
  height: 18px;
  background: var(--bg-secondary);
  border-radius: 9px;
  overflow: hidden;
}

.memory-bar-fill {
  height: 100%;
  border-radius: 9px;
  transition: width 0.3s;
}

.memory-bar-value {
  width: 40px;
  font-size: 0.75rem;
  color: var(--text-tertiary);
  text-align: right;
}
</style>
