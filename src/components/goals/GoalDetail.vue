<template>
  <div class="goal-detail" v-loading="loading">
    <template v-if="goal">
      <el-card class="detail-header">
        <div class="header-row">
          <el-tag :type="levelTagType(goal.level)">
            {{ levelLabel(goal.level) }}
          </el-tag>
          <h2 class="goal-title">{{ goal.name }}</h2>
          <el-tag :type="statusTagType(goal.status)">
            {{ statusLabel(goal.status) }}
          </el-tag>
        </div>
        <p class="goal-desc">{{ goal.description }}</p>
        <div class="meta-row">
          <span>版本: v{{ goal.version }}</span>
          <span v-if="goal.parent_id">父目标: {{ goal.parent_id }}</span>
        </div>
      </el-card>

      <el-card class="progress-card">
        <template #header>
          <span>目标进度</span>
        </template>
        <el-progress
          :percentage="progress.progress_percent || 0"
          :stroke-width="12"
          :status="progressColor"
        />
        <div class="progress-stats">
          <span>总任务: {{ progress.total_tasks || 0 }}</span>
          <span>已完成: {{ progress.completed_tasks || 0 }}</span>
          <span>进行中: {{ progress.in_progress_tasks || 0 }}</span>
        </div>
      </el-card>

      <el-card class="tasks-card">
        <template #header>
          <span>关联任务</span>
        </template>
        <el-empty v-if="!associatedTasks || associatedTasks.length === 0" description="暂无关联任务" />
        <el-table v-else :data="groupedTasks" style="width: 100%">
          <el-table-column prop="status" label="状态" width="120">
            <template #default="{ row }">
              <el-tag :type="taskStatusTagType(row.status)" size="small">
                {{ row.status }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="count" label="数量" width="80" />
        </el-table>
      </el-card>

      <el-card class="history-card">
        <template #header>
          <div class="history-header">
            <span>变更历史</span>
            <el-button size="small" @click="loadHistory">刷新</el-button>
          </div>
        </template>
        <el-timeline v-if="history.length > 0">
          <el-timeline-item
            v-for="item in history"
            :key="item.id"
            :timestamp="formatTimestamp(item.changed_at)"
            placement="top"
          >
            <el-card>
              <p><strong>变更人:</strong> {{ item.changed_by }}</p>
              <p><strong>字段:</strong> {{ item.field_name }}</p>
              <p><strong>变更前:</strong> {{ item.old_value }}</p>
              <p><strong>变更后:</strong> {{ item.new_value }}</p>
            </el-card>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无变更记录" />
      </el-card>
    </template>
    <el-empty v-else description="未找到目标" />
  </div>
</template>

<script setup lang="ts">
import { ref, watch, computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'

const props = defineProps<{
  goalId: string
  loading: boolean
}>()

defineEmits<{
  (e: 'refresh'): void
}>()

const goal = ref<any>(null)
const progress = ref<any>({})
const history = ref<any[]>([])
const associatedTasks = ref<any[]>([])

const progressColor = computed((): 'success' | 'warning' | 'exception' | '' | undefined => {
  const pct = progress.value.progress_percent || 0
  if (pct >= 100) return 'success'
  if (pct >= 50) return ''
  return 'warning'
})

const groupedTasks = computed(() => {
  if (!associatedTasks.value || associatedTasks.value.length === 0) return []
  const map = new Map<string, number>()
  associatedTasks.value.forEach((t: any) => {
    map.set(t.status, (map.get(t.status) || 0) + 1)
  })
  return Array.from(map.entries()).map(([status, count]) => ({ status, count }))
})

const loadGoal = async () => {
  try {
    const res = await axios.get(`/api/v1/goal-alignment/goals/${props.goalId}`)
    goal.value = res.data?.data
  } catch (e) {
    ElMessage.error('加载目标详情失败')
  }
}

const loadProgress = async () => {
  try {
    const res = await axios.get(`/api/v1/goal-alignment/goals/${props.goalId}/progress`)
    progress.value = res.data?.data || {}
  } catch (e) {
    console.error('Failed to load progress:', e)
  }
}

const loadHistory = async () => {
  try {
    const res = await axios.get(`/api/v1/goal-alignment/goals/${props.goalId}/history`)
    history.value = res.data?.data || []
  } catch (e) {
    console.error('Failed to load history:', e)
  }
}

watch(() => props.goalId, () => {
  loadGoal()
  loadProgress()
  loadHistory()
}, { immediate: true })

onMounted(() => {
  loadGoal()
  loadProgress()
  loadHistory()
})

const levelLabel = (level: string) => {
  const map: Record<string, string> = { mission: '使命', strategic_goal: '战略目标', project: '项目', task: '任务' }
  return map[level] || level
}
const levelTagType = (level: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = { mission: 'danger', strategic_goal: 'warning', project: 'primary', task: 'success' }
  return map[level] || 'info'
}
const statusLabel = (status: string) => {
  const map: Record<string, string> = { not_started: '未开始', in_progress: '进行中', completed: '已完成', cancelled: '已取消', needs_review: '需重估' }
  return map[status] || status
}
const statusTagType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = { not_started: 'info', in_progress: 'primary', completed: 'success', cancelled: 'danger', needs_review: 'warning' }
  return map[status] || 'info'
}
const taskStatusTagType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = { pending: 'info', in_progress: 'primary', completed: 'success', failed: 'danger', cancelled: 'danger' }
  return map[status] || 'info'
}
const formatTimestamp = (ts: number | null) => {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString('zh-CN')
}
</script>

<style scoped>
.goal-detail { padding: 8px; }
.detail-header { margin-bottom: 16px; }
.header-row { display: flex; align-items: center; gap: 12px; margin-bottom: 12px; }
.goal-title { margin: 0; font-size: 18px; }
.goal-desc { color: #666; margin: 8px 0; }
.meta-row { display: flex; gap: 16px; color: #999; font-size: 13px; }
.progress-card { margin-bottom: 16px; }
.progress-stats { display: flex; gap: 16px; margin-top: 8px; color: #666; }
.tasks-card { margin-bottom: 16px; }
.history-card { margin-bottom: 16px; }
.history-header { display: flex; justify-content: space-between; align-items: center; }
</style>
