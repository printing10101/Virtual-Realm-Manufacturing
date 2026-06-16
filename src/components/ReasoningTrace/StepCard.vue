<template>
  <div class="step-card" :class="[`step-${step.type}`, `status-${step.status}`]">
    <div class="step-header">
      <div class="step-icon">
        <el-icon :size="20">
          <component :is="stepIcon" />
        </el-icon>
      </div>
      <div class="step-title">{{ step.title }}</div>
      <div class="step-status">
        <el-tag :type="statusTagType" size="small" effect="dark">
          {{ statusText }}
        </el-tag>
      </div>
      <div class="step-duration" v-if="step.duration">
        {{ step.duration }}ms
      </div>
    </div>

    <div class="step-evidence">
      <div class="evidence-summary">
        {{ step.evidence.summary }}
      </div>

      <!-- 任务路由依据 -->
      <div v-if="step.type === 'task_routing'" class="evidence-section">
        <div v-if="step.evidence.routingRules?.length" class="evidence-block">
          <div class="evidence-label">匹配规则</div>
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
              <span v-if="rule.description" class="rule-desc">- {{ rule.description }}</span>
            </div>
          </div>
        </div>

        <div v-if="step.evidence.similarCases?.length" class="evidence-block">
          <div class="evidence-label">相似案例</div>
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
      <div v-if="step.type === 'physical_validation'" class="evidence-section">
        <div v-if="step.evidence.validationParams?.length" class="evidence-block">
          <div class="evidence-label">校验参数</div>
          <el-table :data="step.evidence.validationParams" size="small" border>
            <el-table-column prop="name" label="参数" width="120" />
            <el-table-column label="值" width="100">
              <template #default="{ row }">
                {{ row.value }}{{ row.unit || '' }}
              </template>
            </el-table-column>
            <el-table-column label="阈值" width="100">
              <template #default="{ row }">
                ≤ {{ row.threshold }}{{ row.unit || '' }}
              </template>
            </el-table-column>
            <el-table-column label="结果" width="80">
              <template #default="{ row }">
                <el-tag :type="row.passed ? 'success' : 'danger'" size="small">
                  {{ row.passed ? '通过' : '失败' }}
                </el-tag>
              </template>
            </el-table-column>
          </el-table>
        </div>

        <div v-if="step.evidence.physicsFormulas?.length" class="evidence-block">
          <div class="evidence-label">物理公式</div>
          <div class="formula-list">
            <code v-for="(formula, idx) in step.evidence.physicsFormulas" :key="idx">
              {{ formula }}
            </code>
          </div>
        </div>
      </div>

      <!-- 主动学习依据 -->
      <div v-if="step.type === 'active_learning'" class="evidence-section">
        <div v-if="step.evidence.learningCurve?.length" class="evidence-block">
          <div class="evidence-label">学习曲线</div>
          <div class="curve-info">
            <span>Epoch: {{ step.evidence.learningCurve.length }}</span>
            <span>
              最终 Loss: {{ step.evidence.learningCurve[step.evidence.learningCurve.length - 1]?.loss.toFixed(4) }}
            </span>
          </div>
        </div>

        <div v-if="step.evidence.sampleComparison?.length" class="evidence-block">
          <div class="evidence-label">样本对比</div>
          <div class="sample-list">
            <div
              v-for="(sample, idx) in step.evidence.sampleComparison"
              :key="idx"
              class="sample-item"
            >
              <span class="sample-source">{{ sample.source }}</span>
              <span v-if="sample.label" class="sample-label">{{ sample.label }}</span>
              <span class="sample-features">
                特征维度: {{ sample.features.length }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div v-if="step.confidence !== undefined" class="step-confidence">
      <span class="confidence-label">置信度</span>
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
import { CircleCheck, CircleClose, Promotion, Check, TrendCharts, Star } from '@element-plus/icons-vue'
import type { ReasoningStep } from '@/api/reasoning'

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
      return '待执行'
    case 'running':
      return '执行中'
    case 'completed':
      return '已完成'
    case 'failed':
      return '失败'
    case 'skipped':
      return '已跳过'
    default:
      return '未知'
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
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 16px;
  margin-bottom: 12px;
  transition: all 0.3s;
}

.step-card:hover {
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.step-card.status-running {
  border-color: #e6a23c;
  background: #fdf6ec;
}

.step-card.status-completed {
  border-color: #67c23a;
}

.step-card.status-failed {
  border-color: #f56c6c;
  background: #fef0f0;
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
  background: #409eff;
  color: white;
}

.step-title {
  flex: 1;
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.step-status {
  flex-shrink: 0;
}

.step-duration {
  font-size: 13px;
  color: #909399;
  flex-shrink: 0;
}

.step-evidence {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.evidence-summary {
  font-size: 14px;
  color: #606266;
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
  color: #909399;
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
  color: #606266;
  padding: 6px 8px;
  border-radius: 4px;
  background: #f5f7fa;
}

.rule-item.matched {
  background: #f0f9ff;
  color: #409eff;
}

.rule-desc {
  color: #909399;
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
  background: #f5f7fa;
  border-radius: 4px;
}

.case-id {
  font-size: 13px;
  font-weight: 600;
  color: #409eff;
  min-width: 80px;
}

.similarity-bar {
  flex: 1;
  max-width: 120px;
}

.similarity-text {
  font-size: 13px;
  font-weight: 600;
  color: #67c23a;
  min-width: 40px;
}

.case-result {
  font-size: 12px;
  color: #909399;
}

.formula-list {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.formula-list code {
  padding: 8px 12px;
  background: #f5f7fa;
  border-radius: 4px;
  font-family: 'Courier New', monospace;
  font-size: 13px;
  color: #606266;
}

.curve-info {
  display: flex;
  gap: 16px;
  font-size: 13px;
  color: #606266;
  padding: 8px 12px;
  background: #f5f7fa;
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
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 13px;
}

.sample-source {
  font-weight: 600;
  color: #409eff;
}

.sample-label {
  color: #67c23a;
}

.sample-features {
  color: #909399;
  font-size: 12px;
}

.step-confidence {
  margin-top: 12px;
  padding-top: 12px;
  border-top: 1px solid #ebeef5;
}

.confidence-label {
  font-size: 13px;
  color: #909399;
  margin-bottom: 6px;
  display: block;
}
</style>
