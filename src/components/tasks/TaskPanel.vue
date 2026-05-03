<template>
  <div class="task-panel" :class="{ hidden: !taskPanelVisible }">
    <div class="task-panel-header">
      <h3 class="panel-title">
        <el-icon class="panel-icon"><Tickets /></el-icon>
        任务面板
        <span class="task-count" v-if="runningCount > 0">{{ runningCount }}</span>
      </h3>
      <button class="collapse-btn" @click="toggleTaskPanel">
        <el-icon><Close /></el-icon>
      </button>
    </div>

    <div class="task-panel-body">
      <div class="task-filters">
        <select v-model="statusFilter" @change="applyFilter" class="filter-select">
          <option value="">全部状态</option>
          <option value="running">运行中</option>
          <option value="pending">等待中</option>
          <option value="success">已完成</option>
          <option value="failed">失败</option>
          <option value="cancelled">已取消</option>
        </select>
        <select v-model="typeFilter" @change="applyFilter" class="filter-select">
          <option value="">全部类型</option>
          <option value="process_generation">工艺参数</option>
          <option value="report_generation">报告生成</option>
          <option value="simulation_validation">仿真验证</option>
          <option value="cad_generation">模型生成</option>
          <option value="workflow_execution">工作流</option>
        </select>
      </div>

      <div class="task-list" v-if="tasks.length > 0">
        <TaskCard
          v-for="task in tasks"
          :key="task.task_id"
          :task="task"
          @click="showDetail"
        />
      </div>

      <div class="empty-tasks" v-else>
        <svg viewBox="0 0 1024 1024" width="48" height="48" class="empty-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#d9d9d9"/>
          <path d="M464 336c0-26.5 21.5-48 48-48s48 21.5 48 48v240c0 26.5-21.5 48-48 48s-48-21.5-48-48V336z" fill="#d9d9d9"/>
          <path d="M512 688c-26.5 0-48 21.5-48 48s21.5 48 48 48 48-21.5 48-48-21.5-48-48-48z" fill="#d9d9d9"/>
        </svg>
        <p>暂无任务</p>
      </div>
    </div>

    <TaskDetail
      v-if="selectedTask"
      :task="selectedTask"
      @close="selectedTask = null"
      @cancel="cancelSelectedTask"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, watch } from 'vue'
import { Tickets, Close } from '@element-plus/icons-vue'
import { useAppStore } from '@/stores/app'
import { useTaskList, type Task, taskService } from '@/services/taskService'
import TaskCard from './TaskCard.vue'
import TaskDetail from './TaskDetail.vue'

const appStore = useAppStore()

const {
  tasks,
  fetchTasks,
  setFilter,
  startAutoRefresh,
  stopAutoRefresh
} = useTaskList()

const taskPanelVisible = computed({
  get: () => appStore.taskPanelVisible,
  set: (val: boolean) => {
    if (!val) {
      appStore.toggleTaskPanel()
    }
  }
})

const selectedTask = computed<Task | null>({
  get: () => appStore.selectedTask,
  set: (val) => { appStore.selectedTask = val }
})

const statusFilter = computed({
  get: () => appStore.taskStatusFilter,
  set: (val) => { appStore.taskStatusFilter = val }
})

const typeFilter = computed({
  get: () => appStore.taskTypeFilter,
  set: (val) => { appStore.taskTypeFilter = val }
})

const runningCount = computed(() => {
  return tasks.value.filter(t => t.status === 'running').length
})

watch(() => appStore.taskPanelVisible, (visible) => {
  if (visible) {
    fetchTasks()
    startAutoRefresh(3000)
  } else {
    stopAutoRefresh()
  }
})

function toggleTaskPanel() {
  appStore.toggleTaskPanel()
}

function applyFilter() {
  setFilter(
    statusFilter.value as any || undefined,
    typeFilter.value as any || undefined
  )
}

function showDetail(task: Task) {
  appStore.selectedTask = task
}

async function cancelSelectedTask() {
  if (selectedTask.value) {
    try {
      await taskService.cancelTask(selectedTask.value.task_id)
      appStore.selectedTask = null
      fetchTasks()
    } catch (e) {
      console.error('取消任务失败:', e)
    }
  }
}
</script>

<style scoped>
.task-panel {
  position: fixed;
  right: 0;
  top: 60px;
  bottom: 0;
  width: 320px;
  background: #fff;
  box-shadow: -2px 0 8px rgba(0, 0, 0, 0.1);
  display: flex;
  flex-direction: column;
  z-index: 100;
  transition: transform 0.3s ease;
}

.task-panel.hidden {
  transform: translateX(100%);
}

.task-panel-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.panel-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.panel-icon {
  color: #409EFF;
}

.task-count {
  background: #ff4d4f;
  color: #fff;
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  min-width: 16px;
  text-align: center;
}

.collapse-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: #999;
}

.collapse-btn:hover {
  color: #333;
}

.task-panel-body {
  flex: 1;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.task-filters {
  padding: 12px;
  display: flex;
  gap: 8px;
  border-bottom: 1px solid #f0f0f0;
}

.filter-select {
  flex: 1;
  padding: 6px 8px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
}

.filter-select:focus {
  outline: none;
  border-color: #409EFF;
}

.task-list {
  flex: 1;
  overflow-y: auto;
  padding: 12px;
}

.empty-tasks {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: #999;
}

.empty-icon {
  margin-bottom: 12px;
}
</style>
