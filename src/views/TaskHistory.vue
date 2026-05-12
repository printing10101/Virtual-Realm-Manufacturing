<template>
  <div class="task-history-page">
    <el-card>
      <template #header>
        <div class="header-with-actions">
          <span>任务历史</span>
          <div class="header-actions">
            <el-select v-model="filterStatus" placeholder="筛选状态" clearable style="width: 150px; margin-right: 10px;">
              <el-option label="全部" value="" />
              <el-option label="已完成" value="completed" />
              <el-option label="训练中" value="running" />
              <el-option label="已取消" value="cancelled" />
              <el-option label="失败" value="failed" />
              <el-option label="排队中" value="queued" />
            </el-select>
            <el-button @click="loadTasks" :loading="loading">刷新</el-button>
          </div>
        </div>
      </template>

      <el-table :data="tasks" style="width: 100%" v-loading="loading" stripe>
        <el-table-column prop="job_id" label="任务ID" width="200">
          <template #default="{ row }">
            <el-tag type="info" size="small" class="job-id-tag">{{ row.job_id }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="task_type" label="任务类型" width="150">
          <template #default="{ row }">
            {{ getTaskTypeText(row.task_type) }}
          </template>
        </el-table-column>
        <el-table-column prop="status" label="状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusTagType(row.status)">
              {{ getStatusText(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="progress" label="进度" width="150">
          <template #default="{ row }">
            <el-progress :percentage="Math.round(row.progress)" :stroke-width="12" />
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="创建时间" width="180">
          <template #default="{ row }">
            {{ formatTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="duration_seconds" label="耗时" width="100">
          <template #default="{ row }">
            {{ row.duration_seconds ? `${row.duration_seconds.toFixed(1)}s` : '-' }}
          </template>
        </el-table-column>
        <el-table-column label="操作" fixed="right" width="180">
          <template #default="{ row }">
            <el-button size="small" type="primary" @click="viewTaskDetail(row)">详情</el-button>
            <el-button
              size="small"
              type="success"
              @click="rerunTask(row)"
              :disabled="row.status !== 'completed' && row.status !== 'failed'"
            >
              重新执行
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > pageSize"
        :current-page="currentPage"
        :page-size="pageSize"
        :total="total"
        @current-change="handlePageChange"
        style="margin-top: 20px; justify-content: center;"
        layout="prev, pager, next"
      />
    </el-card>

    <el-dialog v-model="detailDialogVisible" title="任务详情" width="600px">
      <el-descriptions v-if="selectedTask" :column="1" border>
        <el-descriptions-item label="任务ID">{{ selectedTask.job_id }}</el-descriptions-item>
        <el-descriptions-item label="任务类型">{{ getTaskTypeText(selectedTask.task_type) }}</el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="getStatusTagType(selectedTask.status)">
            {{ getStatusText(selectedTask.status) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="进度">{{ Math.round(selectedTask.progress) }}%</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatTime(selectedTask.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="开始时间" v-if="selectedTask.started_at">{{ formatTime(selectedTask.started_at) }}</el-descriptions-item>
        <el-descriptions-item label="完成时间" v-if="selectedTask.completed_at">{{ formatTime(selectedTask.completed_at) }}</el-descriptions-item>
        <el-descriptions-item label="耗时" v-if="selectedTask.duration_seconds">{{ selectedTask.duration_seconds.toFixed(1) }}秒</el-descriptions-item>
        <el-descriptions-item label="错误信息" v-if="selectedTask.error">
          <el-alert :title="selectedTask.error" type="error" :closable="false" show-icon />
        </el-descriptions-item>
        <el-descriptions-item label="训练参数" v-if="selectedTask.params">
          <pre>{{ JSON.stringify(selectedTask.params, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="训练指标" v-if="selectedTask.metrics">
          <pre>{{ JSON.stringify(selectedTask.metrics, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="结果" v-if="selectedTask.result">
          <pre>{{ JSON.stringify(selectedTask.result, null, 2) }}</pre>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import axios from 'axios'
import { ElMessage } from 'element-plus'

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
    const errorMsg = e?.response?.data?.message || e?.message || '获取任务列表失败'
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
    ElMessage.warning('无法重新执行此任务，缺少参数信息')
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

    const newJobId = res.data.data?.job_id
    if (!newJobId) {
      ElMessage.error('未获取到新任务ID')
      return
    }

    ElMessage.success(`新任务已启动，任务ID: ${newJobId}`)

    router.push({ name: 'workspace', query: { tab: 'train', jobId: newJobId } })
  } catch (e: any) {
    const errorMsg = e?.response?.data?.message || e?.message || '重新执行失败'
    ElMessage.error(errorMsg)
  }
}

function formatTime(timestamp: string): string {
  if (!timestamp) return '-'
  try {
    const date = new Date(timestamp)
    return date.toLocaleString('zh-CN', {
      year: 'numeric',
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    })
  } catch {
    return timestamp
  }
}

function getTaskTypeText(type: string): string {
  const map: Record<string, string> = {
    lnn_training: 'LNN训练',
    lnn_batch_inference: '批量推理',
    lnn_inference: '推理',
    data_processing: '数据处理',
    model_export: '模型导出',
    model_quantization: '模型量化',
  }
  return map[type] || type
}

function getStatusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
  if (status === 'completed') return 'success'
  if (status === 'running') return ''
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  if (status === 'queued') return 'info'
  return 'info'
}

function getStatusText(status: string): string {
  const map: Record<string, string> = {
    queued: '排队中',
    running: '训练中',
    completed: '已完成',
    failed: '失败',
    cancelled: '已取消',
  }
  return map[status] || status
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