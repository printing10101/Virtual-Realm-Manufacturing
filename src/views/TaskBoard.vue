<template>
  <div class="task-board-page">
    <div class="board-header">
      <h2>任务看板</h2>
      <div class="board-actions">
        <el-button
          :loading="loading"
          :icon="Refresh"
          @click="loadBoard"
        >
          刷新
        </el-button>
        <el-button
          type="warning"
          :loading="cleaningUp"
          :icon="Delete"
          @click="cleanupExpired"
        >
          清理过期锁
        </el-button>
        <el-button
          type="primary"
          :icon="Lock"
          @click="showLocksDialog = true"
        >
          执行锁管理
        </el-button>
      </div>
    </div>

    <div
      v-loading="loading"
      class="kanban-container"
    >
      <el-row :gutter="16">
        <el-col
          v-for="col in columns"
          :key="col.status"
          :span="col.span"
        >
          <el-card
            :class="['kanban-column', `column-${col.status}`]"
            shadow="hover"
          >
            <template #header>
              <div class="column-header">
                <span>{{ col.label }}</span>
                <el-tag
                  :type="col.tagType"
                  size="small"
                  round
                >
                  {{ getColumnTasks(col.status).length }}
                </el-tag>
              </div>
            </template>

            <div class="column-body">
              <el-empty
                v-if="getColumnTasks(col.status).length === 0"
                :description="`暂无${col.label}任务`"
                :image-size="60"
              />

              <el-card
                v-for="task in getColumnTasks(col.status)"
                :key="task.id"
                class="task-card"
                :body-style="{ padding: '12px' }"
                shadow="hover"
                @click="viewTaskDetail(task)"
              >
                <div class="task-card-header">
                  <el-tag
                    :type="getPriorityTagType(task.priority)"
                    size="small"
                    effect="dark"
                  >
                    {{ getPriorityLabel(task.priority) }}
                  </el-tag>
                  <span class="task-id">{{ task.id }}</span>
                </div>

                <div class="task-title">
                  {{ task.title || task.id }}
                </div>

                <div
                  v-if="task.description"
                  class="task-description"
                >
                  {{ task.description }}
                </div>

                <div class="task-meta">
                  <el-tag
                    v-if="task.status === 'in_progress' && task.assigned_to"
                    type="warning"
                    size="small"
                  >
                    {{ task.assigned_to }}
                  </el-tag>
                  <el-tag
                    v-if="task.status === 'completed' && task.completed_at"
                    type="success"
                    size="small"
                  >
                    {{ formatDate(task.completed_at) }}
                  </el-tag>
                  <el-tag
                    v-if="task.status === 'failed'"
                    type="danger"
                    size="small"
                  >
                    已失败
                  </el-tag>

                  <el-tooltip
                    v-if="task.lock_info && task.lock_info.status === 'active'"
                    :content="`锁剩余时间: ${formatDuration(task.lock_info.time_remaining_seconds, false)}`"
                    placement="top"
                  >
                    <el-progress
                      :percentage="getLockRemainingPercent(task.lock_info)"
                      :stroke-width="6"
                      :show-text="false"
                      style="width: 60px; margin-left: auto;"
                    />
                  </el-tooltip>
                </div>

                <div
                  v-if="task.blockers && task.blockers.length > 0"
                  class="task-blockers"
                >
                  <el-tag
                    v-for="blocker in task.blockers"
                    :key="blocker"
                    size="small"
                    type="danger"
                    effect="plain"
                  >
                    {{ blocker }}
                  </el-tag>
                </div>
              </el-card>
            </div>
          </el-card>
        </el-col>
      </el-row>
    </div>

    <el-dialog
      v-model="detailDialogVisible"
      :title="`任务详情: ${selectedTaskId}`"
      width="700px"
      destroy-on-close
    >
      <div
        v-if="detailLoading"
        v-loading="detailLoading"
        style="min-height: 200px;"
      />

      <template v-else-if="taskDetail">
        <el-descriptions
          :column="2"
          border
          size="small"
        >
          <el-descriptions-item
            label="任务ID"
            :span="2"
          >
            {{ taskDetail.task.id }}
          </el-descriptions-item>
          <el-descriptions-item label="标题">
            {{ taskDetail.task.title }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getTaskStatusTagType(taskDetail.task.status)">
              {{ getTaskStatusLabel(taskDetail.task.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="分配代理">
            {{ taskDetail.task.assigned_to || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="类型">
            {{ taskDetail.task.task_type }}
          </el-descriptions-item>
          <el-descriptions-item label="检出时间">
            {{ taskDetail.task.checked_out_at || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="检出到期">
            {{ taskDetail.task.checkout_expires_at || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="创建时间">
            {{ taskDetail.task.created_at }}
          </el-descriptions-item>
          <el-descriptions-item label="完成时间">
            {{ taskDetail.task.completed_at || '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="GPU需求">
            {{ taskDetail.task.required_gpu_memory ? `${taskDetail.task.required_gpu_memory}GB` : '-' }}
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            {{ getPriorityLabel(taskDetail.task.priority) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">
          执行锁历史
        </el-divider>
        <el-table
          v-if="taskDetail.lock_history && taskDetail.lock_history.length > 0"
          :data="taskDetail.lock_history"
          size="small"
          max-height="200"
        >
          <el-table-column
            prop="action"
            label="操作"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="getLockActionTagType(row.action)"
                size="small"
              >
                {{ getLockActionLabel(row.action) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="agent_id"
            label="代理"
            width="120"
          />
          <el-table-column
            prop="reason"
            label="原因"
            min-width="150"
          />
          <el-table-column
            prop="timestamp"
            label="时间"
            width="170"
          />
        </el-table>
        <el-empty
          v-else
          description="暂无锁历史"
          :image-size="40"
        />

        <el-divider content-position="left">
          失败历史
        </el-divider>
        <el-table
          v-if="taskDetail.failure_history && taskDetail.failure_history.length > 0"
          :data="taskDetail.failure_history"
          size="small"
          max-height="200"
        >
          <el-table-column
            prop="reason"
            label="失败原因"
            width="150"
          >
            <template #default="{ row }">
              <el-tag
                type="danger"
                size="small"
              >
                {{ row.reason }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="message"
            label="详情"
            min-width="200"
          />
          <el-table-column
            prop="agent_id"
            label="代理"
            width="120"
          />
          <el-table-column
            prop="timestamp"
            label="时间"
            width="170"
          />
        </el-table>
        <el-empty
          v-else
          description="暂无失败历史"
          :image-size="40"
        />
      </template>

      <template #footer>
        <el-button @click="detailDialogVisible = false">
          关闭
        </el-button>
        <el-button
          v-if="selectedTask?.status === 'in_progress'"
          type="warning"
          @click="forceReleaseFromDetail"
        >
          强制释放
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showLocksDialog"
      title="执行锁管理"
      width="800px"
      destroy-on-close
    >
      <div v-loading="locksLoading">
        <el-table
          :data="locks"
          size="small"
          max-height="400"
          stripe
        >
          <el-table-column
            prop="task_id"
            label="任务ID"
            width="180"
          />
          <el-table-column
            prop="agent_id"
            label="代理ID"
            width="150"
          />
          <el-table-column
            prop="status"
            label="状态"
            width="110"
          >
            <template #default="{ row }">
              <el-tag
                :type="getLockStatusTagType(row.status)"
                size="small"
              >
                {{ getLockStatusLabel(row.status) }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="is_expired"
            label="是否过期"
            width="90"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.is_expired ? 'danger' : 'success'"
                size="small"
              >
                {{ row.is_expired ? '已过期' : '有效' }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="created_at"
            label="创建时间"
            width="170"
          />
          <el-table-column
            prop="expires_at"
            label="过期时间"
            width="170"
          />
          <el-table-column
            label="操作"
            fixed="right"
            width="100"
          >
            <template #default="{ row }">
              <el-button
                v-if="row.status === 'active'"
                size="small"
                type="danger"
                @click="forceReleaseLock(row.task_id)"
              >
                释放
              </el-button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted } from 'vue'
import { Refresh, Delete, Lock } from '@element-plus/icons-vue'
import http from '@/utils/http'
import { formatDate, formatDuration } from '@/utils/formatters'
import { getPriorityTagType, getPriorityLabel, getTaskStatusTagType, getTaskStatusLabel } from '@/utils/statusHelpers'

interface TaskItem {
  id: string
  title: string
  description: string
  task_type: string
  status: string
  assigned_to: string | null
  priority: number
  checked_out_at: string | null
  checkout_expires_at: string | null
  created_at: string
  completed_at: string | null
  required_gpu_memory: number
  blockers: string[]
  lock_info: LockInfo | null
}

interface LockInfo {
  task_id: string
  agent_id: string
  status: string
  created_at: string
  expires_at: string
  heartbeat_at: string
  released_at: string | null
  release_reason: string | null
  is_expired: boolean
  time_remaining_seconds: number
}

interface BoardData {
  pending: TaskItem[]
  in_progress: TaskItem[]
  completed: TaskItem[]
  failed: TaskItem[]
  cancelled: TaskItem[]
}

interface TaskDetail {
  task: TaskItem
  lock_history: Array<Record<string, unknown>>
  failure_history: Array<Record<string, unknown>>
}

interface LockEntry {
  task_id: string
  agent_id: string
  status: string
  created_at: string
  expires_at: string
  is_expired: boolean
}

const columns = [
  { status: 'pending', label: '待处理', tagType: 'info' as const, span: 4 },
  { status: 'in_progress', label: '进行中', tagType: 'warning' as const, span: 6 },
  { status: 'completed', label: '已完成', tagType: 'success' as const, span: 5 },
  { status: 'failed', label: '失败', tagType: 'danger' as const, span: 5 },
  { status: 'cancelled', label: '已取消', tagType: 'info' as const, span: 4 },
]

const loading = ref(false)
const cleaningUp = ref(false)
const board = ref<BoardData>({
  pending: [],
  in_progress: [],
  completed: [],
  failed: [],
  cancelled: [],
})

const detailDialogVisible = ref(false)
const detailLoading = ref(false)
const selectedTask = ref<TaskItem | null>(null)
const selectedTaskId = ref('')
const taskDetail = ref<TaskDetail | null>(null)

const showLocksDialog = ref(false)
const locksLoading = ref(false)
const locks = ref<LockEntry[]>([])

let pollTimer: ReturnType<typeof setInterval> | null = null

function getColumnTasks(status: string): TaskItem[] {
  return board.value[status as keyof BoardData] || []
}

async function loadBoard() {
  loading.value = true
  try {
    const res = await http.get('/api/v1/task-checkout/board')
    board.value = res.data?.data || {
      pending: [],
      in_progress: [],
      completed: [],
      failed: [],
      cancelled: [],
    }
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error('加载看板失败: ' + errorMsg)
  } finally {
    loading.value = false
  }
}

async function viewTaskDetail(task: TaskItem) {
  selectedTask.value = task
  selectedTaskId.value = task.id
  detailDialogVisible.value = true
  detailLoading.value = true
  taskDetail.value = null

  try {
    const res = await http.get(`/api/v1/task-checkout/tasks/${task.id}/history`)
    taskDetail.value = res.data?.data
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error('加载任务详情失败: ' + errorMsg)
  } finally {
    detailLoading.value = false
  }
}

async function loadLocks() {
  locksLoading.value = true
  try {
    const res = await http.get('/api/v1/task-checkout/locks')
    locks.value = res.data?.data || []
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error('加载锁列表失败: ' + errorMsg)
  } finally {
    locksLoading.value = false
  }
}

async function forceReleaseLock(taskId: string) {
  try {
    await ElMessageBox.confirm(
      `确定要强制释放任务 "${taskId}" 的执行锁吗？该任务将回到待处理状态。`,
      '确认强制释放',
      { confirmButtonText: '释放', cancelButtonText: '取消', type: 'warning' }
    )
    await http.delete(`/api/v1/task-checkout/locks/${taskId}?admin_id=admin`)
    ElMessage.success(`任务 ${taskId} 的锁已释放`)
    await loadLocks()
    await loadBoard()
  } catch (e: unknown) {
    if (e !== 'cancel' && e !== 'close') {
      const errorMsg = e instanceof Error ? e.message : String(e)
      ElMessage.error('释放锁失败: ' + errorMsg)
    }
  }
}

async function forceReleaseFromDetail() {
  if (selectedTask.value) {
    await forceReleaseLock(selectedTask.value.id)
    detailDialogVisible.value = false
  }
}

async function cleanupExpired() {
  cleaningUp.value = true
  try {
    const res = await http.post('/api/v1/task-checkout/cleanup')
    const data = res.data?.data
    ElMessage.success(`清理完成，释放了 ${data?.count || 0} 个过期的锁`)
    await loadBoard()
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error('清理过期锁失败: ' + errorMsg)
  } finally {
    cleaningUp.value = false
  }
}

function getLockRemainingPercent(lockInfo: LockInfo): number {
  if (!lockInfo || lockInfo.is_expired) return 0
  const total = 4 * 3600
  return Math.round((lockInfo.time_remaining_seconds / total) * 100)
}

function getLockActionTagType(action: string): 'success' | 'warning' | 'danger' | 'info' {
  if (action === 'created') return 'success'
  if (action === 'released') return 'info'
  if (action === 'force_released') return 'danger'
  if (action === 'expired') return 'warning'
  return 'info'
}

function getLockActionLabel(action: string): string {
  const map: Record<string, string> = {
    created: '创建',
    released: '释放',
    force_released: '强制释放',
    expired: '过期',
  }
  return map[action] || action
}

function getLockStatusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'active') return 'success'
  if (status === 'released') return 'info'
  if (status === 'force_released') return 'danger'
  if (status === 'expired') return 'warning'
  return 'info'
}

function getLockStatusLabel(status: string): string {
  const map: Record<string, string> = {
    active: '活跃',
    released: '已释放',
    force_released: '强制释放',
    expired: '已过期',
  }
  return map[status] || status
}

onMounted(() => {
  loadBoard()
  pollTimer = setInterval(() => {
    loadBoard()
  }, 30000)
})

onUnmounted(() => {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
})
</script>

<style scoped>
.task-board-page {
  padding: 16px;
  max-width: 1600px;
  margin: 0 auto;
}

.board-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
  padding: 0 4px;
}

.board-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.board-actions {
  display: flex;
  gap: 8px;
}

.kanban-container {
  min-height: 400px;
}

.kanban-column {
  min-height: 300px;
  max-height: calc(100vh - 200px);
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.kanban-column :deep(.el-card__body) {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.kanban-column :deep(.el-card__header) {
  padding: 10px 16px;
}

.column-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.column-body {
  min-height: 100px;
}

.task-card {
  margin-bottom: 8px;
  cursor: pointer;
  transition: box-shadow 0.2s;
  border-left: 3px solid transparent;
}

.task-card:hover {
  box-shadow: var(--shadow-md);
}

.column-pending .task-card {
  border-left-color: var(--border-dark);
}

.column-in_progress .task-card {
  border-left-color: var(--warning);
}

.column-completed .task-card {
  border-left-color: var(--success);
}

.column-failed .task-card {
  border-left-color: var(--error);
}

.column-cancelled .task-card {
  border-left-color: var(--border-medium);
}

.task-card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 4px;
}

.task-id {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: monospace;
}

.task-title {
  font-size: 14px;
  font-weight: 500;
  margin-bottom: 4px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-description {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
}

.task-blockers {
  display: flex;
  gap: 4px;
  margin-top: 6px;
  flex-wrap: wrap;
}
</style>
