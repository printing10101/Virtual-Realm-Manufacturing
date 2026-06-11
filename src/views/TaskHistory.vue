<template>
  <div class="task-history-page">
    <el-card>
      <template #header>
        <div class="header-with-actions">
          <span>{{ $t('taskHistory.title') }}</span>
          <div class="header-actions">
            <el-select
              v-model="filterStatus"
              :placeholder="$t('taskHistory.filterStatus')"
              clearable
              style="width: 150px; margin-right: 10px;"
            >
              <el-option
                :label="$t('taskHistory.statusAll')"
                value=""
              />
              <el-option
                :label="$t('taskHistory.statusCompleted')"
                value="completed"
              />
              <el-option
                :label="$t('taskHistory.statusTraining')"
                value="running"
              />
              <el-option
                :label="$t('taskHistory.statusCancelled')"
                value="cancelled"
              />
              <el-option
                :label="$t('taskHistory.statusFailed')"
                value="failed"
              />
              <el-option
                :label="$t('taskHistory.statusQueued')"
                value="queued"
              />
            </el-select>
            <el-button
              :loading="loading"
              @click="loadTasks"
            >
              {{ $t('taskHistory.refresh') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-table
        v-loading="loading"
        :data="tasks"
        style="width: 100%"
        stripe
      >
        <el-table-column
          prop="job_id"
          :label="$t('taskHistory.colJobId')"
          width="200"
        >
          <template #default="{ row }">
            <el-tag
              type="info"
              size="small"
              class="job-id-tag"
            >
              {{ row.job_id }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="task_type"
          :label="$t('taskHistory.colType')"
          width="150"
        >
          <template #default="{ row }">
            {{ getTaskTypeText(row.task_type) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="status"
          :label="$t('taskHistory.colStatus')"
          width="100"
        >
          <template #default="{ row }">
            <el-tag :type="getTaskStatusTagType(row.status)">
              {{ getTaskStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="progress"
          :label="$t('taskHistory.colProgress')"
          width="150"
        >
          <template #default="{ row }">
            <el-progress
              :percentage="Math.round(row.progress)"
              :stroke-width="12"
            />
          </template>
        </el-table-column>
        <el-table-column
          prop="created_at"
          :label="$t('taskHistory.colCreated')"
          width="180"
        >
          <template #default="{ row }">
            {{ formatDate(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="duration_seconds"
          :label="$t('taskHistory.colDuration')"
          width="100"
        >
          <template #default="{ row }">
            {{ row.duration_seconds ? `${row.duration_seconds.toFixed(1)}${$t('taskHistory.durationSuffix')}` : '-' }}
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('taskHistory.colActions')"
          fixed="right"
          width="180"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              @click="viewTaskDetail(row)"
            >
              {{ $t('taskHistory.detail') }}
            </el-button>
            <el-button
              size="small"
              type="success"
              :disabled="row.status !== 'completed' && row.status !== 'failed'"
              @click="rerunTask(row)"
            >
              {{ $t('taskHistory.rerun') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        style="margin-top: 20px; justify-content: center;"
        layout="prev, pager, next"
        @current-change="handlePageChange"
      />
    </el-card>

    <el-dialog
      v-model="detailDialogVisible"
      :title="$t('taskHistory.detailDialogTitle')"
      width="600px"
    >
      <el-descriptions
        v-if="selectedTask"
        :column="1"
        border
      >
        <el-descriptions-item :label="$t('taskHistory.colJobId')">
          {{ selectedTask.job_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('taskHistory.colType')">
          {{ getTaskTypeText(selectedTask.task_type) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('taskHistory.colStatus')">
          <el-tag :type="getTaskStatusTagType(selectedTask.status)">
            {{ getTaskStatusLabel(selectedTask.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('taskHistory.colProgress')">
          {{ Math.round(selectedTask.progress) }}%
        </el-descriptions-item>
        <el-descriptions-item :label="$t('taskHistory.colCreated')">
          {{ formatDate(selectedTask.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.started_at"
          :label="$t('taskHistory.startTime')"
        >
          {{ formatDate(selectedTask.started_at) }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.completed_at"
          :label="$t('taskHistory.completeTime')"
        >
          {{ formatDate(selectedTask.completed_at) }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.duration_seconds"
          :label="$t('taskHistory.colDuration')"
        >
          {{ selectedTask.duration_seconds.toFixed(1) }}{{ $t('taskHistory.durationSuffix') }}
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.error"
          :label="$t('taskHistory.errorInfo')"
        >
          <el-alert
            :title="selectedTask.error"
            type="error"
            :closable="false"
            show-icon
          />
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.params"
          :label="$t('taskHistory.trainParams')"
        >
          <pre>{{ JSON.stringify(selectedTask.params, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.metrics"
          :label="$t('taskHistory.trainMetrics')"
        >
          <pre>{{ JSON.stringify(selectedTask.metrics, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedTask.result"
          :label="$t('taskHistory.result')"
        >
          <pre>{{ JSON.stringify(selectedTask.result, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { formatDate } from '@/utils/formatters'
import { getTaskStatusTagType, getTaskStatusLabel } from '@/utils/statusHelpers'

const { t } = useI18n()
const router = useRouter()

const loading = ref(false)
const tasks = ref<any[]>([])
const total = ref(0)
const currentPage = ref(1)
const pageSize = 20
const filterStatus = ref('')

const detailDialogVisible = ref(false)
const selectedTask = ref<any>(null)

async function loadTasks() {
  loading.value = true
  try {
    const params: any = {
      limit: pageSize,
      offset: (currentPage.value - 1) * pageSize,
    }
    if (filterStatus.value) {
      params.status = filterStatus.value
    }

    const res = await axios.get('/api/v1/jobs', { params })
    tasks.value = res.data.data.jobs || []
    total.value = res.data.data.total || 0
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || t('taskHistory.loadFailed')
    ElMessage.error(errorMsg)
  } finally {
    loading.value = false
  }
}

function handlePageChange(page: number) {
  currentPage.value = page
  loadTasks()
}

function viewTaskDetail(task: any) {
  selectedTask.value = task
  detailDialogVisible.value = true
}

async function rerunTask(task: any) {
  if (!task.params) {
    ElMessage.warning(t('taskHistory.cannotRerun'))
    return
  }

  try {
    let res
    if (task.task_type === 'lnn_training') {
      res = await axios.post('/api/v1/lnn/train', {
        model_name: task.params.model_name,
        data_path: task.params.data_path,
        hyperparameters: task.params.hyperparameters,
        device: task.params.device,
      })
    } else if (task.task_type === 'lnn_batch_inference') {
      res = await axios.post('/api/v1/lnn/batch-inference', {
        model_name: task.params.model_name,
        input_data: task.params.input_data,
        batch_size: task.params.batch_size,
      })
    }

    const newJobId = res?.data.data?.job_id
    if (!newJobId) {
      ElMessage.error(t('taskHistory.noNewJobId'))
      return
    }

    ElMessage.success(t('taskHistory.newJobStarted', { jobId: newJobId }))

    router.push({ name: 'workspace', query: { tab: 'train', jobId: newJobId } })
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || t('taskHistory.rerunFailed')
    ElMessage.error(errorMsg)
  }
}

function getTaskTypeText(type: string): string {
  // Translate via i18n key from the pre-defined map
  return t(`taskHistory.typeMap.${type}`) || type
}

watch(filterStatus, () => {
  currentPage.value = 1
  loadTasks()
})

onMounted(() => {
  loadTasks()
})
</script>

<style scoped>
.task-history-page {
  max-width: 1400px;
  margin: 0 auto;
}

.header-with-actions {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  align-items: center;
}

.job-id-tag {
  font-family: monospace;
  font-size: 12px;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
}
</style>
