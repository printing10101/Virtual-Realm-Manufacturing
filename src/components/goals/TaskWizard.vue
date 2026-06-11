<template>
  <div class="task-wizard">
    <el-steps
      :active="currentStep"
      finish-status="success"
      style="margin-bottom: 24px"
    >
      <el-step :title="t('taskWizard.step1Title')" />
      <el-step :title="t('taskWizard.step2Title')" />
      <el-step :title="t('taskWizard.step3Title')" />
    </el-steps>

    <div
      v-if="currentStep === 0"
      class="step-content"
    >
      <h4>{{ t('taskWizard.selectGoalTitle') }}</h4>
      <el-input
        v-model="searchQuery"
        :placeholder="t('taskWizard.searchGoalPlaceholder')"
        prefix-icon="Search"
        style="margin-bottom: 16px"
      />
      <el-radio-group
        v-model="selectedParentId"
        class="goal-radio-group"
      >
        <el-card
          v-for="goal in filteredGoals"
          :key="goal.id"
          class="goal-option"
          :class="{ selected: selectedParentId === goal.id }"
          shadow="hover"
          @click="selectedParentId = goal.id"
        >
          <el-radio
            :value="goal.id"
            style="width: 100%"
          >
            <div class="goal-option-content">
              <el-tag
                size="small"
                :type="getGoalLevelTagType(goal.level)"
              >
                {{ getGoalLevelLabel(goal.level) }}
              </el-tag>
              <strong>{{ goal.name }}</strong>
              <p class="goal-option-desc">
                {{ goal.description }}
              </p>
            </div>
          </el-radio>
        </el-card>
      </el-radio-group>
      <el-empty
        v-if="filteredGoals.length === 0"
        :description="t('taskWizard.noGoalMatched')"
      />
    </div>

    <div
      v-if="currentStep === 1"
      class="step-content"
    >
      <el-form
        :model="taskForm"
        label-width="100px"
      >
        <el-form-item :label="t('taskWizard.taskTitle')">
          <el-input
            v-model="taskForm.title"
            :placeholder="t('taskWizard.taskTitlePlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('taskWizard.taskDesc')">
          <el-input
            v-model="taskForm.description"
            type="textarea"
            :rows="3"
            :placeholder="t('taskWizard.taskDescPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('taskWizard.taskType')">
          <el-select
            v-model="taskForm.task_type"
            style="width: 100%"
          >
            <el-option
              :label="t('taskWizard.typePrediction')"
              value="prediction"
            />
            <el-option
              :label="t('taskWizard.typeTraining')"
              value="training"
            />
            <el-option
              :label="t('taskWizard.typeAnalysis')"
              value="analysis"
            />
            <el-option
              :label="t('taskWizard.typeExecution')"
              value="execution"
            />
            <el-option
              :label="t('taskWizard.typeReview')"
              value="review"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="t('taskWizard.blockers')">
          <el-select
            v-model="taskForm.blockers"
            multiple
            filterable
            style="width: 100%"
          >
            <el-option
              :label="t('taskWizard.blockersNone')"
              value=""
            />
          </el-select>
          <span class="form-hint">{{ t('taskWizard.blockersHint') }}</span>
        </el-form-item>
      </el-form>
    </div>

    <div
      v-if="currentStep === 2"
      class="step-content"
    >
      <h4>{{ t('taskWizard.confirmTitle') }}</h4>
      <el-descriptions
        :column="1"
        border
      >
        <el-descriptions-item :label="t('taskWizard.parentGoal')">
          {{ selectedParentGoal?.name || '-' }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('taskWizard.taskTitle')">
          {{ taskForm.title }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('taskWizard.taskDesc')">
          {{ taskForm.description }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('taskWizard.taskType')">
          {{ taskForm.task_type }}
        </el-descriptions-item>
      </el-descriptions>
      <el-alert
        v-if="goalChainPreview.length > 0"
        :title="t('taskWizard.goalChainPreview')"
        type="info"
        :closable="false"
        style="margin-top: 16px"
      >
        <el-breadcrumb separator=" > ">
          <el-breadcrumb-item
            v-for="g in goalChainPreview"
            :key="g.id"
          >
            {{ g.name }}
          </el-breadcrumb-item>
        </el-breadcrumb>
      </el-alert>
    </div>

    <div class="wizard-actions">
      <el-button
        v-if="currentStep > 0"
        @click="currentStep--"
      >
        {{ t('taskWizard.prevStep') }}
      </el-button>
      <el-button
        v-if="currentStep < 2"
        type="primary"
        :disabled="!canProceed"
        @click="currentStep++"
      >
        {{ t('taskWizard.nextStep') }}
      </el-button>
      <el-button
        v-if="currentStep === 2"
        type="primary"
        :loading="loading"
        @click="submitTask"
      >
        {{ t('taskWizard.createTask') }}
      </el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import axios from 'axios'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { getGoalLevelLabel, getGoalLevelTagType } from '@/utils/statusHelpers'

const { t } = useI18n()

const props = defineProps<{
  goals: any[]
  loading: boolean
}>()

const emit = defineEmits<{
  (e: 'created'): void
}>()

const currentStep = ref(0)
const searchQuery = ref('')
const selectedParentId = ref<string | undefined>(undefined)
const taskForm = ref({
  title: '',
  description: '',
  task_type: 'prediction',
  blockers: [] as string[],
})

const filteredGoals = computed(() => {
  if (!searchQuery.value) return props.goals
  const q = searchQuery.value.toLowerCase()
  return props.goals.filter((g: any) =>
    g.name.toLowerCase().includes(q) || g.description.toLowerCase().includes(q)
  )
})

const selectedParentGoal = computed(() => {
  return props.goals.find((g: any) => g.id === selectedParentId.value) || null
})

const goalChainPreview = computed(() => {
  if (!selectedParentGoal.value) return []
  const chain: any[] = [selectedParentGoal.value]
  let parent = selectedParentGoal.value
  while (parent?.parent_id) {
    const p = props.goals.find((g: any) => g.id === parent.parent_id)
    if (p) {
      chain.push(p)
      parent = p
    } else {
      break
    }
  }
  return chain.reverse()
})

const canProceed = computed(() => {
  if (currentStep.value === 0) return !!selectedParentId.value
  if (currentStep.value === 1) return !!taskForm.value.title
  return true
})

const submitTask = async () => {
  if (!selectedParentId.value) {
    ElMessage.warning(t('taskWizard.selectParentFirst'))
    return
  }
  try {
    await axios.post('/api/v1/goal-alignment/tasks', {
      title: taskForm.value.title,
      description: taskForm.value.description,
      task_type: taskForm.value.task_type,
      parent_goal_id: selectedParentId.value,
      blockers: taskForm.value.blockers,
    })
    emit('created')
    taskForm.value = { title: '', description: '', task_type: 'prediction', blockers: [] }
    selectedParentId.value = undefined
    currentStep.value = 0
  } catch (e: any) {
    ElMessage.error(t('taskWizard.createFailed', { message: e.response?.data?.message || e.message }))
  }
}
</script>

<style scoped>
.task-wizard { max-width: 800px; margin: 0 auto; }
.step-content { min-height: 300px; padding: 16px 0; }
.goal-radio-group { display: flex; flex-direction: column; gap: 8px; }
.goal-option { cursor: pointer; border: 2px solid transparent; }
.goal-option.selected { border-color: #409eff; }
.goal-option-content { display: flex; flex-direction: column; gap: 4px; }
.goal-option-desc { margin: 4px 0 0; color: #666; font-size: 13px; }
.form-hint { display: block; color: #999; font-size: 12px; margin-top: 4px; }
.wizard-actions { display: flex; justify-content: center; gap: 12px; padding: 16px 0; }
</style>
