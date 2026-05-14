<template>
  <div class="goal-tree-view">
    <div class="tree-header">
      <h3>目标层级结构</h3>
      <el-button size="small" :loading="loading" @click="$emit('refresh')">
        <el-icon><Refresh /></el-icon>
        刷新
      </el-button>
    </div>
    <el-tree
      v-loading="loading"
      :data="treeData"
      :props="treeProps"
      node-key="id"
      default-expand-all
      highlight-current
      @node-click="handleNodeClick"
    >
      <template #default="{ node: _node, data }">
        <span class="tree-node">
          <el-tag size="small" :type="levelTagType(data.level)">
            {{ levelLabel(data.level) }}
          </el-tag>
          <span class="node-name">{{ data.name }}</span>
          <el-tag size="small" :type="statusTagType(data.status)">
            {{ statusLabel(data.status) }}
          </el-tag>
        </span>
      </template>
    </el-tree>
  </div>
</template>

<script setup lang="ts">
import { Refresh } from '@element-plus/icons-vue'

defineProps<{
  treeData: any[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'select', goalId: string): void
  (e: 'refresh'): void
}>()

const treeProps = {
  children: 'children',
  label: 'name',
}

const handleNodeClick = (data: any) => {
  emit('select', data.id)
}

const levelLabel = (level: string) => {
  const map: Record<string, string> = {
    mission: '使命',
    strategic_goal: '战略目标',
    project: '项目',
    task: '任务',
  }
  return map[level] || level
}

const levelTagType = (level: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    mission: 'danger',
    strategic_goal: 'warning',
    project: 'primary',
    task: 'success',
  }
  return map[level] || 'info'
}

const statusLabel = (status: string) => {
  const map: Record<string, string> = {
    not_started: '未开始',
    in_progress: '进行中',
    completed: '已完成',
    cancelled: '已取消',
    needs_review: '需重估',
  }
  return map[status] || status
}

const statusTagType = (status: string): 'primary' | 'success' | 'warning' | 'info' | 'danger' => {
  const map: Record<string, 'primary' | 'success' | 'warning' | 'info' | 'danger'> = {
    not_started: 'info',
    in_progress: 'primary',
    completed: 'success',
    cancelled: 'danger',
    needs_review: 'warning',
  }
  return map[status] || 'info'
}
</script>

<style scoped>
.goal-tree-view {
  padding: 8px;
}

.tree-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.tree-header h3 {
  margin: 0;
  font-size: 16px;
}

.tree-node {
  display: flex;
  align-items: center;
  gap: 8px;
}

.node-name {
  font-weight: 500;
}
</style>
