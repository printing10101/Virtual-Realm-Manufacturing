<template>
  <div class="task-detail-overlay" @click.self="$emit('close')">
    <div class="task-detail-modal">
      <div class="task-detail-header">
        <h3 class="task-detail-title">{{ typeLabel }} - {{ statusLabel }}</h3>
        <button class="task-detail-close" @click="$emit('close')">
          <svg viewBox="0 0 1024 1024" width="16" height="16">
            <path d="M563.8 512l262.5-312.9c4.4-5.2.7-13.1-6.1-13.1h-79.8c-4.7 0-9.2 2.1-12.3 5.7L512 449.8 295.9 191.7c-3-3.6-7.5-5.7-12.3-5.7H203.8c-6.8 0-10.5 7.9-6.1 13.1L460.2 512 197.7 824.9A7.95 7.95 0 0 0 203.8 838h79.8c4.7 0 9.2-2.1 12.3-5.7L512 574.1l216.1 258.1c3 3.6 7.5 5.7 12.3 5.7h79.8c6.8 0 10.5-7.9 6.1-13.1L563.8 512z"/>
          </svg>
        </button>
      </div>
      
      <div class="task-detail-body" v-if="task">
        <div class="detail-section">
          <h4 class="section-title">基本信息</h4>
          <div class="detail-grid">
            <div class="detail-item">
              <span class="detail-label">任务ID</span>
              <span class="detail-value code">{{ task.task_id }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">任务类型</span>
              <span class="detail-value">{{ typeLabel }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">当前状态</span>
              <span class="detail-value">
                <span class="status-badge" :class="`status-${task.status}`">{{ statusLabel }}</span>
              </span>
            </div>
            <div class="detail-item">
              <span class="detail-label">进度</span>
              <span class="detail-value">{{ Math.round(task.progress) }}%</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">创建时间</span>
              <span class="detail-value">{{ formatFullTime(task.created_at) }}</span>
            </div>
            <div class="detail-item">
              <span class="detail-label">更新时间</span>
              <span class="detail-value">{{ formatFullTime(task.updated_at) }}</span>
            </div>
          </div>
        </div>

        <div class="detail-section">
          <h4 class="section-title">当前进度</h4>
          <div class="progress-section">
            <div class="progress-bar-large">
              <div class="progress-fill-large" :style="{ width: `${task.progress}%` }"></div>
            </div>
            <div class="current-message">{{ task.message || '无' }}</div>
          </div>
        </div>

        <div class="detail-section" v-if="task.result">
          <h4 class="section-title">执行结果</h4>
          <pre class="result-json">{{ JSON.stringify(task.result, null, 2) }}</pre>
        </div>

        <div class="detail-section" v-if="task.error">
          <h4 class="section-title">错误信息</h4>
          <div class="error-message">{{ task.error }}</div>
        </div>

        <div class="detail-section" v-if="task.params">
          <h4 class="section-title">任务参数</h4>
          <pre class="params-json">{{ JSON.stringify(task.params, null, 2) }}</pre>
        </div>
      </div>

      <div class="task-detail-footer">
        <button class="btn-cancel" v-if="canCancel" @click="$emit('cancel')">
          取消任务
        </button>
        <button class="btn-close" @click="$emit('close')">
          关闭
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { Task } from '@/services/taskService'

const props = defineProps<{
  task: Task | null
}>()

defineEmits<{
  close: []
  cancel: []
}>()

const canCancel = computed(() => {
  if (!props.task) return false
  return ['pending', 'running'].includes(props.task.status)
})

const statusLabel = computed(() => {
  if (!props.task) return ''
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
  if (!props.task) return ''
  const labels: Record<string, string> = {
    process_generation: '工艺参数生成',
    report_generation: '报告生成',
    simulation_validation: '仿真验证',
    cad_generation: '模型生成',
    workflow_execution: '工作流执行'
  }
  return labels[props.task.task_type] || props.task.task_type
})

function formatFullTime(timeStr: string): string {
  const date = new Date(timeStr)
  return date.toLocaleString('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
}
</script>

<style scoped>
.task-detail-overlay {
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.task-detail-modal {
  background: #fff;
  border-radius: 12px;
  width: 90%;
  max-width: 600px;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
}

.task-detail-header {
  padding: 16px 20px;
  border-bottom: 1px solid #f0f0f0;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.task-detail-title {
  margin: 0;
  font-size: 16px;
  font-weight: 600;
  color: #333;
}

.task-detail-close {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: #999;
}

.task-detail-close:hover {
  color: #333;
}

.task-detail-body {
  padding: 20px;
  overflow-y: auto;
  flex: 1;
}

.detail-section {
  margin-bottom: 20px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: #333;
  margin: 0 0 12px 0;
  padding-bottom: 8px;
  border-bottom: 1px dashed #e8e8e8;
}

.detail-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.detail-item {
  display: flex;
  flex-direction: column;
}

.detail-label {
  font-size: 12px;
  color: #999;
  margin-bottom: 4px;
}

.detail-value {
  font-size: 13px;
  color: #333;
}

.detail-value.code {
  font-family: monospace;
  font-size: 11px;
  word-break: break-all;
}

.status-badge {
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 10px;
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

.progress-section {
  padding: 12px;
  background: #f9f9f9;
  border-radius: 8px;
}

.progress-bar-large {
  height: 8px;
  background: #e8e8e8;
  border-radius: 4px;
  overflow: hidden;
  margin-bottom: 8px;
}

.progress-fill-large {
  height: 100%;
  background: #409EFF;
  transition: width 0.3s ease;
}

.current-message {
  font-size: 13px;
  color: #666;
}

.result-json, .params-json {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 6px;
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
  margin: 0;
}

.error-message {
  background: #fff2f0;
  color: #ff4d4f;
  padding: 12px;
  border-radius: 6px;
  font-size: 13px;
}

.task-detail-footer {
  padding: 12px 20px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}

.btn-cancel, .btn-close {
  padding: 8px 16px;
  border-radius: 6px;
  font-size: 13px;
  cursor: pointer;
  border: 1px solid #d9d9d9;
}

.btn-cancel {
  background: #fff2f0;
  color: #ff4d4f;
  border-color: #ffccc7;
}

.btn-cancel:hover {
  background: #ffccc7;
}

.btn-close {
  background: #fff;
  color: #333;
}

.btn-close:hover {
  background: #f5f5f5;
}
</style>
