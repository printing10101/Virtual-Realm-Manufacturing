<template>
  <div class="task-card" :class="statusClass" @click="$emit('click', task)">
    <div class="task-card-header">
      <div class="task-type-icon">
        <component :is="typeIcon" class="icon" />
      </div>
      <div class="task-type-label">{{ typeLabel }}</div>
      <div class="status-badge" :class="statusClass">{{ statusLabel }}</div>
    </div>
    <div class="task-card-body">
      <div class="task-message">{{ task.message || '等待开始...' }}</div>
      <div class="task-progress-bar">
        <div class="task-progress-fill" :style="{ width: `${task.progress}%` }"></div>
      </div>
      <div class="task-progress-text">{{ Math.round(task.progress) }}%</div>
    </div>
    <div class="task-card-footer">
      <span class="task-time">{{ formatTime(task.updated_at) }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/services/taskService'

const props = defineProps<{
  task: Task
}>()

defineEmits<{
  click: [task: Task]
}>()

const statusClass = computed(() => {
  return `status-${props.task.status}`
})

const statusLabel = computed(() => {
  const labels: Record<string, string> = {
    pending: '等待中',
    running: '运行中',
    success: '已完成',
    failed: '失败',
    cancelled: '已取消'
  }
  return labels[props.task.status] || props.task.status
})

const typeLabel = computed(() => {
  const labels: Record<string, string> = {
    process_generation: '工艺参数生成',
    report_generation: '报告生成',
    simulation_validation: '仿真验证',
    cad_generation: '模型生成',
    workflow_execution: '工作流执行'
  }
  return labels[props.task.task_type] || props.task.task_type
})

const typeIcon = computed(() => {
  return 'div'
})

function formatTime(timeStr: string): string {
  const date = new Date(timeStr)
  const now = new Date()
  const diff = now.getTime() - date.getTime()
  
  if (diff < 60000) return '刚刚'
  if (diff < 3600000) return `${Math.floor(diff / 60000)}分钟前`
  if (diff < 86400000) return `${Math.floor(diff / 3600000)}小时前`
  return date.toLocaleDateString('zh-CN')
}
</script>

<style scoped>
.task-card {
  background: #fff;
  border-radius: 8px;
  padding: 12px;
  margin-bottom: 8px;
  cursor: pointer;
  border: 1px solid #e8e8e8;
  transition: all 0.2s;
}

.task-card:hover {
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-color: #409EFF;
}

.task-card-header {
  display: flex;
  align-items: center;
  margin-bottom: 8px;
}

.task-type-icon {
  width: 24px;
  height: 24px;
  border-radius: 4px;
  background: #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-right: 8px;
}

.task-type-label {
  font-size: 12px;
  color: #666;
  flex: 1;
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
}

.status-pending {
  background: #f0f0f0;
  color: #999;
}

.status-running {
  background: #e6f7ff;
  color: #1890ff;
}

.status-success {
  background: #f6ffed;
  color: #52c41a;
}

.status-failed {
  background: #fff2f0;
  color: #ff4d4f;
}

.status-cancelled {
  background: #f5f5f5;
  color: #999;
}

.task-card-body {
  margin-bottom: 8px;
}

.task-message {
  font-size: 13px;
  color: #333;
  margin-bottom: 6px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.task-progress-bar {
  height: 4px;
  background: #f0f0f0;
  border-radius: 2px;
  overflow: hidden;
}

.task-progress-fill {
  height: 100%;
  background: #409EFF;
  transition: width 0.3s ease;
}

.status-running .task-progress-fill {
  background: linear-gradient(90deg, #409EFF, #69c0ff);
}

.status-success .task-progress-fill {
  background: #52c41a;
}

.status-failed .task-progress-fill {
  background: #ff4d4f;
}

.task-progress-text {
  font-size: 11px;
  color: #999;
  text-align: right;
  margin-top: 4px;
}

.task-card-footer {
  display: flex;
  justify-content: flex-end;
}

.task-time {
  font-size: 11px;
  color: #bbb;
}
</style>
