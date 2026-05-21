<template>
  <div class="goals-page">
    <el-tabs
      v-model="activeTab"
      type="border-card"
    >
      <el-tab-pane
        label="目标树"
        name="tree"
      >
        <GoalTreeView
          :tree-data="goalTree"
          :loading="treeLoading"
          @select="selectGoal"
          @refresh="loadGoalTree"
        />
      </el-tab-pane>
      <el-tab-pane
        label="目标详情"
        name="detail"
      >
        <GoalDetail
          v-if="selectedGoalId"
          :goal-id="selectedGoalId"
          :loading="detailLoading"
          @refresh="loadGoalTree"
        />
        <el-empty
          v-else
          description="请从目标树中选择一个目标查看详情"
        />
      </el-tab-pane>
      <el-tab-pane
        label="创建任务"
        name="create-task"
      >
        <TaskWizard
          :goals="allGoals"
          :loading="taskCreating"
          @created="onTaskCreated"
        />
      </el-tab-pane>
      <el-tab-pane
        label="对齐检查"
        name="alignment"
      >
        <AlignmentChecker
          :summary="alignmentSummary"
          :loading="scanLoading"
          @scan="runAlignmentScan"
          @refresh="loadAlignmentSummary"
        />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import axios from 'axios'
import GoalTreeView from '../components/goals/GoalTreeView.vue'
import GoalDetail from '../components/goals/GoalDetail.vue'
import TaskWizard from '../components/goals/TaskWizard.vue'
import AlignmentChecker from '../components/goals/AlignmentChecker.vue'

const activeTab = ref('tree')
const goalTree = ref<any[]>([])
const allGoals = ref<any[]>([])
const selectedGoalId = ref<string | null>(null)
const treeLoading = ref(false)
const detailLoading = ref(false)
const taskCreating = ref(false)
const scanLoading = ref(false)
const alignmentSummary = ref<any>(null)

const loadGoalTree = async () => {
  treeLoading.value = true
  try {
    const res = await axios.get('/api/v1/goal-alignment/goals/tree')
    goalTree.value = res.data?.data || []
    const goalsRes = await axios.get('/api/v1/goal-alignment/goals')
    allGoals.value = goalsRes.data?.data || []
  } catch (e: any) {
    ElMessage.error('加载目标树失败: ' + (e.message || '未知错误'))
  } finally {
    treeLoading.value = false
  }
}

const selectGoal = (goalId: string) => {
  selectedGoalId.value = goalId
  activeTab.value = 'detail'
}

const onTaskCreated = () => {
  ElMessage.success('任务创建成功')
  loadGoalTree()
}

const runAlignmentScan = async () => {
  scanLoading.value = true
  try {
    await axios.post('/api/v1/goal-alignment/scan')
    await loadAlignmentSummary()
    ElMessage.success('对齐检查完成')
  } catch (e: any) {
    ElMessage.error('对齐检查失败: ' + (e.message || '未知错误'))
  } finally {
    scanLoading.value = false
  }
}

const loadAlignmentSummary = async () => {
  try {
    const res = await axios.get('/api/v1/goal-alignment/summary')
    alignmentSummary.value = res.data?.data
  } catch (e: any) {
    console.error('Failed to load alignment summary:', e)
  }
}

onMounted(() => {
  loadGoalTree()
  loadAlignmentSummary()
})
</script>

<style scoped>
.goals-page {
  padding: 16px;
}

.el-tabs {
  min-height: 600px;
}
</style>
