<template>
  <div
    class="step-card"
    :class="[`step-${step.type}`, `status-${step.status}`]"
  >
    <div class="step-header">
      <div class="step-icon">
        <el-icon :size="20">
          <component :is="stepIcon" />
        </el-icon>
      </div>
      <div class="step-title">
        {{ step.title }}
      </div>
      <div class="step-status">
        <el-tag
          :type="statusTagType"
          size="small"
          effect="dark"
        >
          {{ statusText }}
        </el-tag>
      </div>
      <div
        v-if="step.duration"
        class="step-duration"
      >
        {{ step.duration }}ms
      </div>
    </div>

    <div class="step-evidence">
      <div class="evidence-summary">
        {{ step.evidence.summary }}
      </div>

      <!-- 任务路由依据 -->
      <div
        v-if="step.type === 'task_routing'"
        class="evidence-section"
      >
        <div
          v-if="step.evidence.routingRules?.length"
          class="evidence-block"
        >
          <div class="evidence-label">
            {{ t('stepCard.matchingRules') }}
          </div>
          <div class="rule-list">
            <div
              v-for="(rule, idx) in step.evidence.routingRules"
              :key="idx"
              class="rule-item"
              :class="{ matched: rule.matched }"
            >
              <el-icon :size="14">
                <component :is="rule.matched ? CircleCheck : CircleClose" />
              </el-icon>
              <span>{{ rule.rule }}</span>
              <span
                v-if="rule.description"
                class="rule-desc"
              >- {{ rule.description }}</span>
            </div>
          </div>
        </div>

        <div
          v-if="step.evidence.similarCases?.length"
          class="evidence-block"
        >
          <div class="evidence-label">
            {{ t('stepCard.similarCases') }}
          </div>
          <div class="case-list">
            <div
              v-for="(case_, idx) in step.evidence.similarCases"
              :key="idx"
              class="case-item"
            >
              <span class="case-id">{{ case_.taskId }}</span>
              <el-progress
                :percentage="Math.round(case_.similarity * 100)"
                :stroke-width="6"
                :show-text="false"
                class="similarity-bar"
              />
              <span class="similarity-text">{{ Math.round(case_.similarity * 100) }}%</span>
              <span class="case-result">{{ case_.result }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 物理校验依据 -->
      <div
        v-if="step.type === 'physical_validation'"
        class="evidence-section"
      >
        <div
          v-if="step.evidence.validationParams?.length"
          class="evidence-block"
        >
          <div class="evidence-label">
            {{ t('stepCard.validationParams') }}
          </div>
          <el-table
            :data="step.evidence.validationParams"
            size="small"
            border
          >
            <el-table-column
              prop="name"
              :label="t('stepCard.colParam')"
              width="120"
            />
            <el-table-column
              :label="t('stepCard.colValue')"
              width="100"
            >
              <template #default="{ row }">
                {{ row.value }}{{ row.unit || '' }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('stepCard.colThreshold')"
              width="100"
            >
              <template #default="{ row }">
                ≤ {{ row.threshold }}{{ row.unit || '' }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('stepCard.colResult')"
              width="80"
            >
              <template #default="{ row }">
                <el-tag
                  :type="row.passed ? 'success' : 'danger'"
                  size="small"
                >
                  {{ row.passed ? t('stepCard.resultPass') : t('stepCard.resultFail') }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div
          v-if="step.evidence.physicsFormulas?.length"
          class="evidence-block"
        >
          <div class="evidence-label">
            {{ t('stepCard.physicsFormulas') }}
          </div>
          <div class="formula-list">
            <code
              v-for="(formula, idx) in step.evidence.physicsFormulas"
              :key="idx"
            >
              {{ formula }}
            </code>
          </div>
        </div>
      </div>

      <!-- 主动学习依据 -->
      <div
        v-if="step.type === 'active_learning'"
        class="evidence-section"
      >
        <div
          v-if="step.evidence.learningCurve?.length"
          class="evidence-block"
        >
          <div class="evidence-label">
            {{ t('stepCard.learningCurve') }}
          </div>
          <div class="curve-info">
            <span>Epoch: {{ step.evidence.learningCurve.length }}</span>
            <span>
              {{ t('stepCard.finalLoss') }}: {{ step.evidence.learningCurve[step.evidence.learningCurve.length - 1]?.loss.toFixed(4) }}
            </span>
          </div>
        </div>

        <div
          v-if="step.evidence.sampleComparison?.length"
          class="evidence-block"
        >
          <div class="evidence-label">
            {{ t('stepCard.sampleComparison') }}
          </div>
          <div class="sample-list">
            <div
              v-for="(sample, idx) in step.evidence.sampleComparison"
              :key="idx"
              class="sample-item"
            >
              <span class="sample-source">{{ sample.source }}</span>
              <span
                v-if="sample.label"
                class="sample-label"
              >{{ sample.label }}</span>
              <span class="sample-features">
                {{ t('stepCard.featureDimensions') }}: {{ sample.features.length }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div
      v-if="step.confidence !== undefined"
      class="step-confidence"
    >
      <span class="confidence-label">{{ t('stepCard.confidence') }}</span>
      <el-progress
        :percentage="Math.round(step.confidence * 100)"
        :stroke-width="8"
        :color="confidenceColor"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CircleCheck, CircleClose, Promotion, Check, TrendCharts, Star } from '@element-plus/icons-vue'
import type { ReasoningStep } from '@/api/reasoning'

const { t } = useI18n()

const props = defineProps<{
  step: ReasoningStep
}>()

const stepIcon = computed(() => {
  switch (props.step.type) {
    case 'task_routing':
      return Promotion
    case 'physical_validation':
      return Check
    case 'active_learning':
      return TrendCharts
    case 'recommendation':
      return Star
    default:
      return Promotion
  }
})

const statusTagType = computed(() => {
  switch (props.step.status) {
    case 'completed':
      return 'success'
    case 'running':
      return 'warning'
    case 'failed':
      return 'danger'
    case 'skipped':
      return 'info'
    default:
      return 'info'
  }
})

const statusText = computed(() => {
  switch (props.step.status) {
    case 'pending':
      return t('stepCard.statusPending')
    case 'running':
      return t('stepCard.statusRunning')
    case 'completed':
      return t('stepCard.statusCompleted')
    case 'failed':
      return t('stepCard.statusFailed')
    case 'skipped':
      return t('stepCard.statusSkipped')
    default:
      return t('stepCard.statusUnknown')
  }
})

const confidenceColor = computed(() => {
  const confidence = props.step.confidence || 0
  if (confidence >= 0.8) return '#67c23a'
  if (confidence >= 0.5) return '#e6a23c'
  return '#f56c6c'
})
</script>

<style scoped>
.step-card {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.3s;
}

.step-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.step-card.status-running {
  border-color: var(--warning);
  background: rgba(212, 168, 87, 0.1);
}

.step-card.status-completed {
  border-color: var(--success);
}

.step-card.status-failed {
  border-color: var(--error);
  background: rgba(199, 107, 107, 0.1);
}

.step-header {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.step-icon {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 36px;
  height: 36px;
  border-radius: 50%;
  background: var(--accent-primary);
  color: var(--bg-card);
}

.step-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
}

.step-status {
  flex-shrink: 0;
}

.step-duration {
  font-size: 13px;
  color: var(--text-tertiary);
  flex-shrink: 0;
}

.step-evidence {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.evidence-summary {
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
  margin-bottom: 12px;
}

.evidence-section {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.evidence-block {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.evidence-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-tertiary);
  text-transform: uppercase;
}

.rule-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.rule-item {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 6px 8px;
  border-radius: 4px;
  background: var(--bg-tertiary);
}

.rule-item.matched {
  background: rgba(139, 125, 107, 0.1);
  color: var(--accent-primary);
}

.rule-desc {
  color: var(--text-tertiary);
  font-size: 12px;
}

.case-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.case-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.case-id {
  font-size: 13px;
  font-weight: 600;
  color: var(--accent-primary);
  min-width: 80px;
}

.similarity-bar {
  flex: 1;
  max-width: 120px;
}

.similarity-text {
  font-size: 13px;
  font-weight: 600;
  color: var(--success);
  min-width: 40px;
}

.case-result {
  font-size: 12px;
  color: var(--text-tertiary);
}

.formula-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.formula-list code {
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: var(--text-secondary);
}

.curve-info {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: var(--text-secondary);
  padding: 8px 12px;
  background: var(--bg-tertiary);
  border-radius: 4px;
}

.sample-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.sample-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 8px;
  background: var(--bg-tertiary);
  border-radius: 4px;
  font-size: 13px;
}

.sample-source {
  font-weight: 600;
  color: var(--accent-primary);
}

.sample-label {
  color: var(--success);
}

.sample-features {
  color: var(--text-tertiary);
  font-size: 12px;
}

.step-confidence {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid var(--border-light);
}

.confidence-label {
  font-size: 13px;
  color: var(--text-tertiary);
  margin-bottom: 6px;
  display: block;
}
</style>
