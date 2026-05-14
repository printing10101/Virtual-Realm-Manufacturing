<template>
  <div class="alignment-checker">
    <div class="checker-header">
      <h3>目标对齐检查器</h3>
      <el-button type="primary" :loading="loading" @click="$emit('scan')">
        <el-icon><Search /></el-icon>
        运行检查
      </el-button>
    </div>

    <el-card v-if="summary" class="summary-card">
      <el-row :gutter="16">
        <el-col :span="6">
          <el-statistic title="总任务数" :value="summary.total_tasks" />
        </el-col>
        <el-col :span="6">
          <el-statistic title="已对齐" :value="summary.aligned_tasks">
            <template #suffix>
              <span class="suffix-success"> 个</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="未对齐" :value="summary.unaligned_tasks">
            <template #suffix>
              <span class="suffix-danger"> 个</span>
            </template>
          </el-statistic>
        </el-col>
        <el-col :span="6">
          <el-statistic title="对齐率" :value="summary.alignment_rate" :precision="1">
            <template #suffix>
              <span>%</span>
            </template>
          </el-statistic>
        </el-col>
      </el-row>
    </el-card>

    <el-alert
      v-if="summary && summary.alignment_rate < 100"
      title="存在对齐问题"
      type="warning"
      :closable="false"
      style="margin: 16px 0"
    >
      <div>发现 {{ summary.issues?.length || 0 }} 个任务未正确关联目标链，请及时修复。</div>
    </el-alert>

    <el-alert
      v-if="summary && summary.alignment_rate === 100"
      title="所有任务已正确对齐"
      type="success"
      :closable="false"
      style="margin: 16px 0"
    >
      <div>所有任务均已关联到正确的目标链。</div>
    </el-alert>

    <el-card v-if="summary && summary.issues && summary.issues.length > 0" class="issues-card">
      <template #header>
        <span>对齐问题详情</span>
      </template>
      <el-table :data="summary.issues" style="width: 100%">
        <el-table-column prop="task_id" label="任务ID" width="180" />
        <el-table-column prop="task_title" label="任务标题" />
        <el-table-column prop="issue" label="问题描述" />
        <el-table-column prop="severity" label="严重度" width="100">
          <template #default="{ row }">
            <el-tag :type="row.severity === 'high' ? 'danger' : 'warning'" size="small">
              {{ row.severity }}
            </el-tag>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <div class="chain-visualizer" v-if="chainData">
      <h4>目标链可视化</h4>
      <el-card>
        <div class="chain-flow">
        <template v-for="(node, idx) in chainData" :key="node.id">
          <div
            class="chain-node"
            :class="node.level"
          >
            <div class="node-level">{{ levelLabel(node.type || node.level) }}</div>
            <div class="node-name">{{ node.name }}</div>
          </div>
          <span v-if="idx < chainData.length - 1" class="chain-arrow">→</span>
        </template>
        </div>
      </el-card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Search } from '@element-plus/icons-vue'

defineProps<{
  summary: any | null
  loading: boolean
  chainData?: any[] | null
}>()

defineEmits<{
  (e: 'scan'): void
  (e: 'refresh'): void
}>()

const levelLabel = (level: string) => {
  const map: Record<string, string> = { mission: '使命', strategic_goal: '战略目标', project: '项目', task: '任务' }
  return map[level] || level
}
</script>

<style scoped>
.alignment-checker { padding: 8px; }
.checker-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.checker-header h3 { margin: 0; }
.summary-card { margin-bottom: 16px; }
.suffix-success { color: #67c23a; }
.suffix-danger { color: #f56c6c; }
.issues-card { margin-bottom: 16px; }
.chain-visualizer { margin-top: 24px; }
.chain-visualizer h4 { margin: 0 0 12px; }
.chain-flow { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.chain-node {
  padding: 8px 16px;
  border-radius: 8px;
  text-align: center;
  min-width: 120px;
}
.chain-node.mission { background: #fef0f0; border: 1px solid #f56c6c; }
.chain-node.strategic_goal { background: #fdf6ec; border: 1px solid #e6a23c; }
.chain-node.project { background: #ecf5ff; border: 1px solid #409eff; }
.chain-node.task { background: #f0f9eb; border: 1px solid #67c23a; }
.node-level { font-size: 12px; color: #666; margin-bottom: 4px; }
.node-name { font-weight: 600; font-size: 14px; }
.chain-arrow { font-size: 20px; color: #999; }
</style>
