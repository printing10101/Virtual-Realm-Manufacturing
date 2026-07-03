<template>
  <div class="goals-page">
    <el-tabs
      v-model="activeTab"
      type="border-card"
    >
      <el-tab-pane
        :label="t('goals.tabTree')"
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
        :label="t('goals.tabDetail')"
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
          :description="t('goals.emptySelectGoal')"
        />
      </el-tab-pane>
      <el-tab-pane
        :label="t('goals.tabCreateTask')"
        name="create-task"
      >
        <TaskWizard
          :goals="allGoals"
          :loading="taskCreating"
          @created="onTaskCreated"
        />
      </el-tab-pane>
      <el-tab-pane
        :label="t('goals.tabAlignment')"
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
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import http from '@/utils/http'
import GoalTreeView from '../components/goals/GoalTreeView.vue'
import GoalDetail from '../components/goals/GoalDetail.vue'
import TaskWizard from '../components/goals/TaskWizard.vue'
import AlignmentChecker from '../components/goals/AlignmentChecker.vue'
import { API_CONFIG, buildApiPath } from '@/config/api'

const { t } = useI18n()

interface GoalNode {
  id: string
  name: string
  level: string
  status: string
  children?: GoalNode[]
}

interface AlignmentSummary {
  total_goals: number
  aligned_count: number
  alignment_rate: number
  [key: string]: unknown
}

const activeTab = ref('tree')
const goalTree = ref<GoalNode[]>([])
const allGoals = ref<GoalNode[]>([])
const selectedGoalId = ref<string | null>(null)
const treeLoading = ref(false)
const detailLoading = ref(false)
const taskCreating = ref(false)
const scanLoading = ref(false)
const alignmentSummary = ref<AlignmentSummary | null>(null)

const loadGoalTree = async () => {
  treeLoading.value = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.GOAL_ALIGNMENT, '/goals/tree'))
    goalTree.value = res.data?.data || []
    const goalsRes = await http.get(buildApiPath(API_CONFIG.GOAL_ALIGNMENT, '/goals'))
    allGoals.value = goalsRes.data?.data || []
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('goals.errorLoadTree') + errorMsg)
  } finally {
    treeLoading.value = false
  }
}

const selectGoal = (goalId: string) => {
  selectedGoalId.value = goalId
  activeTab.value = 'detail'
}

const onTaskCreated = () => {
  ElMessage.success(t('goals.successTaskCreated'))
  loadGoalTree()
}

const runAlignmentScan = async () => {
  scanLoading.value = true
  try {
    await http.post(buildApiPath(API_CONFIG.GOAL_ALIGNMENT, '/scan'))
    await loadAlignmentSummary()
    ElMessage.success(t('goals.successAlignmentComplete'))
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('goals.errorAlignmentFailed') + errorMsg)
  } finally {
    scanLoading.value = false
  }
}

const loadAlignmentSummary = async () => {
  try {
    const res = await http.get(buildApiPath(API_CONFIG.GOAL_ALIGNMENT, '/summary'))
    alignmentSummary.value = res.data?.data
  } catch {
    // 静默处理
  }
}

onMounted(() => {
  loadGoalTree()
  loadAlignmentSummary()
})
</script>

<style scoped>
.goals-page {
  padding: var(--spacing-md);
}

.el-tabs {
  min-height: 600px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
}
</style>
