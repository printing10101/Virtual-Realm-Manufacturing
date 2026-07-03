<template>
  <div class="task-board-page">
    <!-- ===== Page Header ===== -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('taskBoard.pageTitle') }}</h1>
      </div>
      <div class="page-header__actions">
        <el-button-group>
          <el-button
            :type="viewMode === 'kanban' ? 'primary' : 'default'"
            size="small"
            @click="viewMode = 'kanban'"
          >
            {{ t('taskBoard.btnKanban') }}
          </el-button>
          <el-button
            :type="viewMode === 'list' ? 'primary' : 'default'"
            size="small"
            @click="viewMode = 'list'"
          >
            {{ t('taskBoard.btnList') }}
          </el-button>
        </el-button-group>
        <el-button
          size="small"
          :icon="Filter"
          @click="filterVisible = !filterVisible"
        >
          {{ t('taskBoard.btnFilter') }}
        </el-button>
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="handleCreate"
        >
          {{ t('taskBoard.btnCreateTask') }}
        </el-button>
      </div>
    </div>

    <!-- ===== Filter Panel (collapsible, inline below header) ===== -->
    <div
      class="filter-panel-wrapper"
      :class="{ collapsed: !filterVisible }"
    >
      <div class="filter-bar">
        <div class="filter-row">
          <div class="filter-item">
            <span class="filter-label">{{ t('taskBoard.labelPriority') }}</span>
            <el-select
              v-model="filters.priority"
              :placeholder="t('taskBoard.placeholderAll')"
              size="small"
              style="width: 120px"
              clearable
            >
              <el-option
                :label="t('taskBoard.priorityHigh')"
                value="high"
              />
              <el-option
                :label="t('taskBoard.priorityMedium')"
                value="medium"
              />
              <el-option
                :label="t('taskBoard.priorityLow')"
                value="low"
              />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">{{ t('taskBoard.labelAssignee') }}</span>
            <el-select
              v-model="filters.assignee"
              :placeholder="t('taskBoard.placeholderAll')"
              size="small"
              style="width: 120px"
              clearable
            >
              <el-option
                v-for="name in assigneeOptions"
                :key="name"
                :label="name"
                :value="name"
              />
            </el-select>
          </div>
          <div class="filter-item">
            <span class="filter-label">{{ t('taskBoard.labelDateRange') }}</span>
            <el-date-picker
              v-model="filters.dateRange"
              type="daterange"
              :range-separator="t('taskBoard.rangeSeparator')"
              :start-placeholder="t('taskBoard.placeholderStartDate')"
              :end-placeholder="t('taskBoard.placeholderEndDate')"
              size="small"
              style="width: 260px"
              value-format="YYYY-MM-DD"
            />
          </div>
          <div class="filter-item">
            <span class="filter-label">{{ t('taskBoard.labelTaskType') }}</span>
            <el-select
              v-model="filters.taskType"
              :placeholder="t('taskBoard.placeholderAll')"
              size="small"
              style="width: 140px"
              clearable
            >
              <el-option
                v-for="opt in taskTypeOptions"
                :key="opt"
                :label="opt"
                :value="opt"
              />
            </el-select>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== Loading State ===== -->
    <div
      v-if="tasksStore.loading && allTasks.length === 0"
      class="board-loading"
    >
      <el-skeleton
        :rows="6"
        animated
      />
    </div>

    <!-- ===== Error Banner (non-blocking) ===== -->
    <div
      v-if="fetchFailed && allTasks.length === 0"
      class="error-banner"
    >
      <el-icon :size="16">
        <WarningFilled />
      </el-icon>
      <span>{{ t('taskBoard.msgDataLoadFailed') }}</span>
      <el-button
        text
        type="primary"
        size="small"
        @click="retryFetch"
      >
        {{ t('taskBoard.btnRetry') }}
      </el-button>
    </div>

    <!-- ===== Empty State ===== -->
    <div
      v-else-if="!tasksStore.loading && allTasks.length === 0"
      class="empty-state"
    >
      <el-empty :description="t('taskBoard.emptyNoTasks')" />
    </div>

    <!-- ===== Kanban View ===== -->
    <template v-else>
      <div
        v-if="viewMode === 'kanban'"
        class="kanban-container"
      >
        <div class="kanban-board">
          <div
            v-for="column in filteredColumns"
            :key="column.key"
            class="kanban-column"
          >
            <div class="column-header">
              <div class="column-header-left">
                <span
                  class="column-dot"
                  :class="`dot-${column.key}`"
                />
                <span class="column-name">{{ column.label }}</span>
              </div>
              <span
                class="column-badge"
                :class="`badge-${column.key}`"
              >
                {{ column.items.length }}
              </span>
            </div>
            <div class="column-body">
              <div
                v-for="task in column.items"
                :key="task.job_id"
                class="task-card"
                :class="`priority-${mapPriority(task)}`"
                @click="openDetail(task)"
              >
                <div class="task-card-header">
                  <span class="task-type-tag">{{ task.task_type }}</span>
                  <span class="task-date">{{ formatDate(task.created_at) }}</span>
                </div>
                <div class="task-title">
                  {{ task.job_id }}
                </div>
                <div
                  v-if="getParamDesc(task)"
                  class="task-desc"
                >
                  {{ getParamDesc(task) }}
                </div>
                <div
                  v-if="task.error"
                  class="task-error"
                >
                  <el-icon :size="14">
                    <CircleCloseFilled />
                  </el-icon>
                  {{ truncate(task.error, 60) }}
                </div>
                <div class="task-footer">
                  <div
                    class="avatar"
                    :style="{ backgroundColor: avatarColor(task.owner_id || '') }"
                  >
                    {{ (task.owner_id || '?').charAt(0).toUpperCase() }}
                  </div>
                  <div
                    v-if="task.status === 'running'"
                    class="task-progress"
                  >
                    <el-progress
                      :percentage="Math.round(task.progress)"
                      :stroke-width="6"
                      :show-text="false"
                    />
                    <span class="progress-text">{{ Math.round(task.progress) }}%</span>
                  </div>
                </div>
              </div>
              <div
                v-if="column.items.length === 0"
                class="column-empty"
              >
                {{ t('taskBoard.emptyColumn') }}
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- ===== List View ===== -->
      <div v-else>
        <div class="content-card">
          <div class="content-card__body">
            <el-table
              :data="flatFilteredTasks"
              stripe
              style="width: 100%"
            >
              <el-table-column
                prop="job_id"
                :label="t('taskBoard.colJobId')"
                min-width="180"
                show-overflow-tooltip
              />
              <el-table-column
                prop="task_type"
                :label="t('taskBoard.colType')"
                width="130"
              />
              <el-table-column
                :label="t('taskBoard.colStatus')"
                width="110"
              >
                <template #default="{ row }">
                  <el-tag
                    :type="statusTagType(row.status)"
                    size="small"
                    effect="light"
                  >
                    {{ statusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                :label="t('taskBoard.colProgress')"
                width="140"
              >
                <template #default="{ row }">
                  <el-progress
                    :percentage="Math.round(row.progress)"
                    :stroke-width="8"
                    :show-text="true"
                  />
                </template>
              </el-table-column>
              <el-table-column
                prop="owner_id"
                :label="t('taskBoard.colAssignee')"
                width="100"
                show-overflow-tooltip
              />
              <el-table-column
                :label="t('taskBoard.colCreatedAt')"
                width="170"
              >
                <template #default="{ row }">
                  {{ formatDate(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column
                :label="t('taskBoard.colActions')"
                width="100"
                fixed="right"
              >
                <template #default="{ row }">
                  <el-button
                    v-if="row.status === 'running' || row.status === 'queued' || row.status === 'pending'"
                    text
                    type="danger"
                    size="small"
                    @click.stop="handleCancel(row.job_id)"
                  >
                    {{ t('taskBoard.btnCancel') }}
                  </el-button>
                  <el-button
                    text
                    type="primary"
                    size="small"
                    @click.stop="openDetail(row as TaskInfo)"
                  >
                    {{ t('taskBoard.btnDetail') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </div>
        </div>
      </div>
    </template>

    <!-- ===== Task Detail Side Panel ===== -->
    <transition name="slide-panel">
      <div
        v-if="detailVisible"
        class="detail-overlay"
        @click.self="closeDetail"
      >
        <div class="detail-panel">
          <div class="detail-header">
            <h3 class="detail-title">
              {{ t('taskBoard.detailTitle') }}
            </h3>
            <el-button
              :icon="Close"
              text
              @click="closeDetail"
            />
          </div>

          <template v-if="detailTask">
            <div class="detail-body">
              <div class="detail-field">
                <label class="field-label">{{ t('taskBoard.detailJobId') }}</label>
                <div class="field-value mono">
                  {{ detailTask.job_id }}
                </div>
              </div>

              <div class="detail-field">
                <label class="field-label">{{ t('taskBoard.detailTaskType') }}</label>
                <div class="field-value">
                  {{ detailTask.task_type }}
                </div>
              </div>

              <div class="detail-field-row">
                <div class="detail-field">
                  <label class="field-label">{{ t('taskBoard.detailStatus') }}</label>
                  <el-tag
                    :type="statusTagType(detailTask.status)"
                    effect="light"
                  >
                    {{ statusLabel(detailTask.status) }}
                  </el-tag>
                </div>
                <div class="detail-field">
                  <label class="field-label">{{ t('taskBoard.detailProgress') }}</label>
                  <el-progress
                    :percentage="Math.round(detailTask.progress)"
                    :stroke-width="10"
                    :show-text="true"
                    style="width: 100%"
                  />
                </div>
              </div>

              <div class="detail-field">
                <label class="field-label">{{ t('taskBoard.detailAssignee') }}</label>
                <div class="field-value">
                  <div
                    class="avatar"
                    :style="{ backgroundColor: avatarColor(detailTask.owner_id || '') }"
                  >
                    {{ (detailTask.owner_id || '?').charAt(0).toUpperCase() }}
                  </div>
                  <span style="margin-left: 8px">{{ detailTask.owner_id || '-' }}</span>
                </div>
              </div>

              <div class="detail-field">
                <label class="field-label">{{ t('taskBoard.detailCreatedAt') }}</label>
                <div class="field-value">
                  {{ formatDate(detailTask.created_at) }}
                </div>
              </div>

              <div
                v-if="detailTask.duration_seconds != null"
                class="detail-field"
              >
                <label class="field-label">{{ t('taskBoard.detailDuration') }}</label>
                <div class="field-value">
                  {{ formatDuration(detailTask.duration_seconds) }}
                </div>
              </div>

              <div class="detail-field">
                <label class="field-label">{{ t('taskBoard.detailParams') }}</label>
                <div class="field-value code-block">
                  <pre>{{ JSON.stringify(detailTask.params || {}, null, 2) }}</pre>
                </div>
              </div>

              <div
                v-if="detailTask.result"
                class="detail-field"
              >
                <label class="field-label">{{ t('taskBoard.detailResult') }}</label>
                <div class="field-value code-block">
                  <pre>{{ JSON.stringify(detailTask.result, null, 2) }}</pre>
                </div>
              </div>

              <div
                v-if="detailTask.error"
                class="detail-field"
              >
                <label class="field-label">{{ t('taskBoard.detailError') }}</label>
                <div class="field-value error-text">
                  {{ detailTask.error }}
                </div>
              </div>
            </div>

            <div class="detail-footer">
              <el-button
                v-if="
                  detailTask.status === 'running' ||
                    detailTask.status === 'queued' ||
                    detailTask.status === 'pending'
                "
                type="danger"
                text
                size="small"
                @click="handleCancel(detailTask.job_id); closeDetail()"
              >
                {{ t('taskBoard.btnCancelTask') }}
              </el-button>
              <el-button
                size="small"
                @click="closeDetail"
              >
                {{ t('taskBoard.btnClose') }}
              </el-button>
            </div>
          </template>
        </div>
      </div>
    </transition>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import {
  Filter,
  Plus,
  Close,
  WarningFilled,
  CircleCloseFilled,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useTasksStore, type TaskInfo } from '@/stores/tasks'
import type { TagType } from '@/utils/statusHelpers'

/* ------------------------------------------------------------------ */
/*  i18n                                                               */
/* ------------------------------------------------------------------ */
const { t } = useI18n()

/* ------------------------------------------------------------------ */
/*  Store                                                              */
/* ------------------------------------------------------------------ */
const tasksStore = useTasksStore()

/* ------------------------------------------------------------------ */
/*  State                                                              */
/* ------------------------------------------------------------------ */
const viewMode = ref<'kanban' | 'list'>('kanban')
const filterVisible = ref(true)
const fetchFailed = ref(false)

const filters = reactive({
  priority: '' as string,
  assignee: '' as string,
  dateRange: null as [string, string] | null,
  taskType: '' as string,
})

const detailVisible = ref(false)
const detailTask = ref<TaskInfo | null>(null)

/* ------------------------------------------------------------------ */
/*  Lifecycle                                                          */
/* ------------------------------------------------------------------ */
onMounted(async () => {
  try {
    await tasksStore.fetchTasks()
  } catch {
    fetchFailed.value = true
  }
  if (tasksStore.error && tasksStore.tasks.length === 0) {
    fetchFailed.value = true
  }
})

async function retryFetch() {
  fetchFailed.value = false
  try {
    await tasksStore.fetchTasks()
    if (!tasksStore.error) {
      fetchFailed.value = false
    }
  } catch {
    fetchFailed.value = true
  }
}

/* ------------------------------------------------------------------ */
/*  Computed — task source                                             */
/* ------------------------------------------------------------------ */
const allTasks = computed<TaskInfo[]>(() => {
  return tasksStore.tasks
})

/* ------------------------------------------------------------------ */
/*  Computed — derived filter options                                  */
/* ------------------------------------------------------------------ */
const assigneeOptions = computed(() => {
  const set = new Set<string>()
  allTasks.value.forEach(task => { if (task.owner_id) set.add(task.owner_id) })
  return Array.from(set).sort()
})

const taskTypeOptions = computed(() => {
  const set = new Set<string>()
  allTasks.value.forEach(task => set.add(task.task_type))
  return Array.from(set).sort()
})

/* ------------------------------------------------------------------ */
/*  Computed — kanban columns                                          */
/* ------------------------------------------------------------------ */
interface KanbanColumn {
  key: string
  label: string
  items: TaskInfo[]
}

const kanbanColumns = computed<KanbanColumn[]>(() => {
  const src = allTasks.value
  return [
    {
      key: 'pending',
      label: t('taskBoard.colPending'),
      items: src.filter(task => task.status === 'pending' || task.status === 'queued'),
    },
    {
      key: 'running',
      label: t('taskBoard.colRunning'),
      items: src.filter(task => task.status === 'running'),
    },
    {
      key: 'review',
      label: t('taskBoard.colReview'),
      items: src.filter(task => task.status === 'completed'),
    },
    {
      key: 'done',
      label: t('taskBoard.colDone'),
      items: src.filter(task => task.status === 'failed' || task.status === 'cancelled'),
    },
  ]
})

/* ------------------------------------------------------------------ */
/*  Computed — filtered kanban columns (applies user filters)           */
/* ------------------------------------------------------------------ */
const filteredColumns = computed<KanbanColumn[]>(() => {
  return kanbanColumns.value.map(col => ({
    ...col,
    items: col.items.filter(task => applyFilters(task)),
  }))
})

/* flat list for table view */
const flatFilteredTasks = computed(() => {
  return allTasks.value.filter(task => applyFilters(task))
})

function applyFilters(task: TaskInfo): boolean {
  if (filters.priority && mapPriority(task) !== filters.priority) return false
  if (filters.assignee && task.owner_id !== filters.assignee) return false
  if (filters.taskType && task.task_type !== filters.taskType) return false
  if (filters.dateRange && filters.dateRange[0] && filters.dateRange[1]) {
    const d = task.created_at.slice(0, 10)
    if (d < filters.dateRange[0] || d > filters.dateRange[1]) return false
  }
  return true
}

/* ------------------------------------------------------------------ */
/*  Helpers — map TaskInfo fields to UI concepts                       */
/* ------------------------------------------------------------------ */
function mapPriority(task: TaskInfo): 'high' | 'medium' | 'low' {
  if (task.status === 'failed') return 'high'
  if (task.error) return 'high'
  const p = task.params?.priority as string | undefined
  if (p === 'high' || p === 'urgent') return 'high'
  if (p === 'low') return 'low'
  // Default: running = high, completed/pending = medium
  if (task.status === 'running') return 'medium'
  return 'medium'
}

function getParamDesc(task: TaskInfo): string {
  if (!task.params) return ''
  const entries = Object.entries(task.params).filter(
    ([k]) => !['priority', 'revision'].includes(k)
  )
  if (entries.length === 0) return ''
  return entries
    .map(([k, v]) => `${k}: ${v}`)
    .join(' | ')
}

function statusLabel(status: TaskInfo['status']): string {
  const map: Record<TaskInfo['status'], string> = {
    pending: t('taskBoard.statusPending'),
    queued: t('taskBoard.statusQueued'),
    running: t('taskBoard.statusRunning'),
    completed: t('taskBoard.statusCompleted'),
    failed: t('taskBoard.statusFailed'),
    cancelled: t('taskBoard.statusCancelled'),
  }
  return map[status] || status
}

function statusTagType(status: TaskInfo['status']): TagType {
  const map: Record<TaskInfo['status'], TagType> = {
    pending: 'info',
    queued: 'warning',
    running: 'primary',
    completed: 'success',
    failed: 'danger',
    cancelled: 'info',
  }
  return map[status] || 'info'
}

/* ------------------------------------------------------------------ */
/*  Helpers — formatting                                              */
/* ------------------------------------------------------------------ */
function formatDate(iso: string): string {
  if (!iso) return '-'
  const d = new Date(iso)
  if (isNaN(d.getTime())) return iso
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  const h = String(d.getHours()).padStart(2, '0')
  const min = String(d.getMinutes()).padStart(2, '0')
  return `${y}-${m}-${day} ${h}:${min}`
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  if (m < 60) return `${m}m ${s}s`
  const h = Math.floor(m / 60)
  const rm = m % 60
  return `${h}h ${rm}m`
}

function truncate(str: string, max: number): string {
  if (!str) return ''
  return str.length > max ? str.slice(0, max) + '...' : str
}

/* ------------------------------------------------------------------ */
/*  Avatar color                                                       */
/* ------------------------------------------------------------------ */
const avatarColorMap: Record<string, string> = {
  [t('taskBoard.userZhangSan')]: '#007aff',
  [t('taskBoard.userLiSi')]: '#34c759',
  [t('taskBoard.userWangWu')]: '#ff9500',
  [t('taskBoard.userZhaoLiu')]: '#af52de',
}

function avatarColor(name: string): string {
  return avatarColorMap[name] || '#8e897f'
}

/* ------------------------------------------------------------------ */
/*  Actions                                                            */
/* ------------------------------------------------------------------ */
function openDetail(task: TaskInfo) {
  detailTask.value = { ...task }
  detailVisible.value = true
}

function closeDetail() {
  detailVisible.value = false
  detailTask.value = null
}

async function handleCancel(jobId: string) {
  await tasksStore.cancelTask(jobId)
  ElMessage.success(t('taskBoard.msgTaskCancelled'))
}

function handleCreate() {
  ElMessage.info(t('taskBoard.msgCreateTaskWip'))
}
</script>

<style scoped>
/* ==================== Page Layout ==================== */
.task-board-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* ==================== Filter Panel — smooth height collapse ==================== */
.filter-panel-wrapper {
  max-height: 120px;
  overflow: hidden;
  margin-bottom: 24px;
  transition: max-height 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    margin-bottom 0.35s cubic-bezier(0.4, 0, 0.2, 1),
    opacity 0.25s ease;
  opacity: 1;
}

.filter-panel-wrapper.collapsed {
  max-height: 0;
  margin-bottom: 0;
  opacity: 0;
}

.filter-bar {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  padding: 16px 20px;
  box-shadow: var(--shadow-sm);
}

.filter-row {
  display: flex;
  align-items: flex-end;
  gap: 20px;
  flex-wrap: wrap;
}

.filter-item {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.filter-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

/* ==================== Error Banner ==================== */
.error-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  margin-bottom: 16px;
  background: #fef0f0;
  border: 1px solid #fde2e2;
  border-radius: var(--radius-md);
  color: var(--error, #f56c6c);
  font-size: 13px;
}

.error-banner .el-button {
  margin-left: auto;
}

/* ==================== Board Loading ==================== */
.board-loading {
  padding: 40px 0;
}

/* ==================== Empty State ==================== */
.empty-state {
  padding: 60px 0;
}

/* ==================== Kanban Board ==================== */
.kanban-container {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.kanban-board {
  display: flex;
  gap: 16px;
  min-width: 900px;
}

/* ==================== Column ==================== */
.kanban-column {
  flex: 1 1 0;
  min-width: 0;
  display: flex;
  flex-direction: column;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  border: 1px solid var(--border-light);
}

.column-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px 12px;
  border-bottom: 1px solid var(--border-light);
}

.column-header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.column-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  flex-shrink: 0;
}

.dot-pending { background: var(--bg-500, #909399); }
.dot-running { background: var(--brand-500, #409eff); }
.dot-review { background: var(--warning, #e6a23c); }
.dot-done { background: var(--success, #67c23a); }

.column-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.column-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 22px;
  height: 22px;
  padding: 0 6px;
  border-radius: 11px;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
}

.badge-pending { background: var(--bg-500, #909399); }
.badge-running { background: var(--brand-500, #409eff); }
.badge-review { background: var(--warning, #e6a23c); }
.badge-done { background: var(--success, #67c23a); }

.column-body {
  flex: 1;
  padding: 12px;
  display: flex;
  flex-direction: column;
  gap: 10px;
  min-height: 120px;
  max-height: calc(100vh - 320px);
  overflow-y: auto;
}

.column-empty {
  display: flex;
  align-items: center;
  justify-content: center;
  flex: 1;
  font-size: 13px;
  color: var(--text-tertiary);
}

/* ==================== Task Card ==================== */
.task-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: 14px 14px 12px;
  box-shadow: var(--shadow-sm);
  border-left: 4px solid transparent;
  cursor: pointer;
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.task-card:hover {
  box-shadow: var(--shadow-md);
  transform: translateY(-1px);
}

/* Priority left border colors */
.task-card.priority-high {
  border-left-color: var(--error, #f56c6c);
}
.task-card.priority-medium {
  border-left-color: var(--warning, #e6a23c);
}
.task-card.priority-low {
  border-left-color: var(--info, #909399);
}

.task-card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}

.task-type-tag {
  display: inline-block;
  padding: 1px 6px;
  font-size: 11px;
  font-weight: 500;
  color: var(--brand-500, #409eff);
  background: rgba(64, 158, 255, 0.08);
  border-radius: 4px;
}

.task-date {
  font-size: 11px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.task-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  line-height: 1.4;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-error {
  display: flex;
  align-items: flex-start;
  gap: 4px;
  font-size: 11px;
  color: var(--error, #f56c6c);
  line-height: 1.4;
  word-break: break-all;
}

.task-error .el-icon {
  margin-top: 1px;
  flex-shrink: 0;
}

.task-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-top: 6px;
  padding-top: 8px;
  border-top: 1px solid var(--border-light);
}

/* Avatar */
.avatar {
  width: 26px;
  height: 26px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  flex-shrink: 0;
}

/* Progress in card footer */
.task-progress {
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
}

.task-progress .el-progress {
  flex: 1;
}

.progress-text {
  font-size: 11px;
  font-weight: 600;
  color: var(--text-secondary);
  flex-shrink: 0;
}

/* ==================== Detail Side Panel ==================== */
.detail-overlay {
  position: fixed;
  top: 0;
  right: 0;
  bottom: 0;
  left: 0;
  z-index: 1000;
  background: rgba(0, 0, 0, 0.25);
  display: flex;
  justify-content: flex-end;
}

.detail-panel {
  width: 400px;
  max-width: 100vw;
  height: 100vh;
  background: var(--bg-card);
  box-shadow: var(--shadow-xl);
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.detail-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 20px 24px 16px;
  border-bottom: 1px solid var(--border-light);
  flex-shrink: 0;
}

.detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.detail-field-row {
  display: flex;
  gap: 16px;
}

.detail-field-row .detail-field {
  flex: 1;
}

.detail-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.field-label {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary);
}

.field-value {
  font-size: 14px;
  color: var(--text-primary);
  line-height: 1.5;
  display: flex;
  align-items: center;
}

.field-value.mono {
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  word-break: break-all;
}

.field-value.code-block {
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-sm);
  padding: 10px 12px;
  overflow-x: auto;
}

.field-value.code-block pre {
  margin: 0;
  font-family: 'SF Mono', 'Menlo', 'Consolas', monospace;
  font-size: 12px;
  line-height: 1.5;
  white-space: pre-wrap;
  word-break: break-all;
}

.field-value.error-text {
  color: var(--error, #f56c6c);
}

.detail-footer {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-light);
  flex-shrink: 0;
}

/* panel slide animation */
.slide-panel-enter-active,
.slide-panel-leave-active {
  transition: all 0.3s ease;
}
.slide-panel-enter-from .detail-panel,
.slide-panel-leave-to .detail-panel {
  transform: translateX(100%);
}
.slide-panel-enter-from,
.slide-panel-leave-to {
  opacity: 0;
}

/* ==================== Responsive ==================== */
@media (max-width: 1200px) {
  .kanban-board {
    min-width: 800px;
  }
}

@media (max-width: 768px) {
  .task-board-page {
    padding: 16px;
  }

  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .filter-row {
    flex-direction: column;
    gap: 12px;
  }

  .detail-panel {
    width: 100vw;
  }
}
</style>
