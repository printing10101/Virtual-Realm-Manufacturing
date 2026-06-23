<template>
  <div class="copilot-recommendation-card">
    <div class="card-header">
      <div class="header-left">
        <el-icon class="ai-icon"><Promotion /></el-icon>
        <span class="card-title">{{ $t('copilot.card.title') }}</span>
      </div>
      <div class="header-right">
        <span class="timestamp">{{ formatTimestamp(timestamp) }}</span>
      </div>
    </div>

    <div class="card-content">
      <div class="recommendation-section">
        <div class="section-label">{{ $t('copilot.card.recommendation') }}</div>
        <div class="recommendation-content">
          <slot name="recommendation">
            <pre class="recommendation-json">{{ formatRecommendation(recommendation) }}</pre>
          </slot>
        </div>
      </div>

      <div class="confidence-section">
        <ConfidenceIndicator :confidence="confidence" />
      </div>

      <div class="reasoning-section">
        <div
          class="reasoning-header"
          @click="toggleReasoning"
        >
          <div class="reasoning-title">
            <el-icon><ChatDotRound /></el-icon>
            <span>{{ $t('copilot.card.reasoning') }}</span>
          </div>
          <el-icon class="collapse-icon" :class="{ 'is-expanded': isReasoningExpanded }">
            <ArrowDown />
          </el-icon>
        </div>

        <div
          v-show="isReasoningExpanded"
          class="reasoning-content"
        >
          <slot name="reasoning">
            <p class="reasoning-text">{{ reasoning }}</p>
          </slot>
        </div>
      </div>

      <div class="alternatives-section" v-if="alternatives && alternatives.length > 0">
        <div class="section-label">{{ $t('copilot.card.alternatives') }}</div>
        <div class="alternatives-list">
          <div
            v-for="(alt, index) in alternatives"
            :key="index"
            class="alternative-item"
          >
            <div class="alternative-header">
              <span class="alternative-label">{{ alt.label || `方案 ${index + 1}` }}</span>
              <el-tag
                :type="getConfidenceTagType(alt.confidence)"
                size="small"
              >
                {{ (alt.confidence * 100).toFixed(0) }}%
              </el-tag>
            </div>
            <div class="alternative-description">{{ alt.description }}</div>
          </div>
        </div>
      </div>
    </div>

    <div class="card-actions">
      <DecisionActions
        ref="actionsRef"
        :disabled="actionsDisabled"
        @accept="handleAccept"
        @modify="handleModify"
        @reject="handleReject"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import { Promotion, ChatDotRound, ArrowDown } from '@element-plus/icons-vue'
import ConfidenceIndicator from './ConfidenceIndicator.vue'
import DecisionActions from './DecisionActions.vue'
import { formatTimestamp } from '@/utils/formatters'
import { getConfidenceTagType } from '@/utils/statusHelpers'

interface AlternativePlan {
  label?: string
  description: string
  confidence: number
  parameters?: Record<string, any>
}

interface Props {
  recommendation: Record<string, any>
  confidence: number
  reasoning: string
  alternatives?: AlternativePlan[]
  timestamp?: number
  actionsDisabled?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  alternatives: () => [],
  timestamp: () => Date.now(),
  actionsDisabled: false
})

const emit = defineEmits<{
  accept: [recommendation: Record<string, any>]
  modify: [recommendation: Record<string, any>]
  reject: [recommendation: Record<string, any>]
}>()

const { t } = useI18n()

const isReasoningExpanded = ref(true)
const actionsRef = ref<InstanceType<typeof DecisionActions> | null>(null)

function formatRecommendation(rec: Record<string, any>): string {
  return JSON.stringify(rec, null, 2)
}

function toggleReasoning() {
  isReasoningExpanded.value = !isReasoningExpanded.value
}

function handleAccept() {
  emit('accept', props.recommendation)
  ElMessage.success(t('copilot.messages.accepted'))
}

function handleModify() {
  emit('modify', props.recommendation)
  ElMessage.info(t('copilot.messages.modifyRequested'))
}

function handleReject() {
  emit('reject', props.recommendation)
  ElMessage.warning(t('copilot.messages.rejected'))
}

function setActionsLoading(loading: boolean) {
  actionsRef.value?.setLoading(loading)
}

defineExpose({
  setActionsLoading
})
</script>

<style scoped>
.copilot-recommendation-card {
  background: var(--bg-card);
  border: 1px solid var(--border-medium);
  border-radius: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
  overflow: hidden;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 16px 20px;
  background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-hover) 100%);
  color: var(--bg-card);
}

.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
}

.ai-icon {
  font-size: 20px;
}

.card-title {
  font-size: 16px;
  font-weight: 600;
}

.header-right {
  display: flex;
  align-items: center;
}

.timestamp {
  font-size: 13px;
  opacity: 0.9;
}

.card-content {
  padding: 20px;
}

.section-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  margin-bottom: 12px;
}

.recommendation-section {
  margin-bottom: 20px;
}

.recommendation-content {
  background: var(--bg-tertiary);
  border-radius: 6px;
  padding: 12px;
}

.recommendation-json {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  white-space: pre-wrap;
  word-break: break-all;
  font-family: 'Courier New', monospace;
}

.confidence-section {
  margin-bottom: 20px;
}

.reasoning-section {
  margin-bottom: 20px;
  border: 1px solid var(--border-medium);
  border-radius: 6px;
  overflow: hidden;
}

.reasoning-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  background: var(--bg-tertiary);
  cursor: pointer;
  transition: background 0.2s;
}

.reasoning-header:hover {
  background: var(--bg-secondary);
}

.reasoning-title {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.collapse-icon {
  transition: transform 0.3s;
}

.collapse-icon.is-expanded {
  transform: rotate(180deg);
}

.reasoning-content {
  padding: 16px;
  background: var(--bg-card);
}

.reasoning-text {
  margin: 0;
  font-size: 14px;
  color: var(--text-secondary);
  line-height: 1.6;
}

.alternatives-section {
  margin-top: 20px;
}

.alternatives-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alternative-item {
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  border: 1px solid var(--border-medium);
}

.alternative-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.alternative-label {
  font-size: 14px;
  font-weight: 500;
  color: var(--text-primary);
}

.alternative-description {
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.card-actions {
  border-top: 1px solid var(--border-medium);
  background: var(--bg-secondary);
}
</style>
