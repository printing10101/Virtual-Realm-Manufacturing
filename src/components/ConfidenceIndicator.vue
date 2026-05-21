<template>
  <div
    class="confidence-indicator"
    @mouseenter="showTooltip = true"
    @mouseleave="showTooltip = false"
  >
    <div class="confidence-bar-container">
      <div
        class="confidence-bar-fill"
        :style="{
          width: `${confidence * 100}%`,
          backgroundColor: getConfidenceColor(confidence),
        }"
      />
      <div class="confidence-bar-label">
        {{ (confidence * 100).toFixed(0) }}%
      </div>
    </div>

    <div
      v-if="showTooltip && showTooltipOnHover"
      class="confidence-tooltip"
    >
      <div class="tooltip-header">
        <span class="tooltip-title">置信度详情</span>
        <span
          class="tooltip-value"
          :style="{ color: getConfidenceColor(confidence) }"
        >
          {{ (confidence * 100).toFixed(2) }}%
        </span>
      </div>
      <div class="tooltip-body">
        <p><strong>等级:</strong> {{ getConfidenceLabel(confidence) }}</p>
        <p><strong>说明:</strong> {{ confidenceDescription }}</p>
        <div
          v-if="recommendation"
          class="tooltip-recommendation"
        >
          <strong>建议:</strong> {{ recommendation }}
        </div>
      </div>
    </div>

    <div
      v-if="showLabel"
      class="confidence-text"
      :style="{ color: getConfidenceColor(confidence) }"
    >
      {{ getConfidenceLabel(confidence) }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { getConfidenceColor, getConfidenceLabel } from '@/utils/statusHelpers'

interface Props {
  confidence: number
  showLabel?: boolean
  showTooltipOnHover?: boolean
  showNumericValue?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showLabel: true,
  showTooltipOnHover: true,
  showNumericValue: true,
})

const showTooltip = ref(false)

const confidenceDescription = computed(() => {
  if (props.confidence >= 0.8) {
    return 'AI对该预测结果有较高把握，建议可以直接采用。'
  }
  if (props.confidence >= 0.5) {
    return 'AI对该预测结果有一定把握，建议结合实际情况综合判断。'
  }
  return 'AI对该预测结果把握较低，强烈建议参考备选方案或人工审核。'
})

const recommendation = computed(() => {
  if (props.confidence >= 0.8) {
    return '可以直接采用AI推荐结果'
  }
  if (props.confidence >= 0.5) {
    return '建议审查后采用，注意关注潜在风险'
  }
  return '建议修改或拒绝AI推荐，使用人工判断'
})
</script>

<style scoped>
.confidence-indicator {
  position: relative;
  display: inline-block;
  width: 100%;
}

.confidence-bar-container {
  position: relative;
  height: 24px;
  background: #f0f0f0;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: inset 0 1px 3px rgba(0, 0, 0, 0.1);
}

.confidence-bar-fill {
  height: 100%;
  transition: width 0.5s ease, background-color 0.3s ease;
  border-radius: 12px;
}

.confidence-bar-label {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
  z-index: 1;
}

.confidence-tooltip {
  position: absolute;
  bottom: calc(100% + 8px);
  left: 50%;
  transform: translateX(-50%);
  background: #fff;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 12px;
  min-width: 280px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  z-index: 1000;
  animation: fadeIn 0.2s ease;
}

@keyframes fadeIn {
  from {
    opacity: 0;
    transform: translateX(-50%) translateY(4px);
  }
  to {
    opacity: 1;
    transform: translateX(-50%) translateY(0);
  }
}

.tooltip-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
  padding-bottom: 8px;
  border-bottom: 1px solid #ebeef5;
}

.tooltip-title {
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.tooltip-value {
  font-size: 16px;
  font-weight: 700;
}

.tooltip-body {
  font-size: 13px;
  color: #606266;
  line-height: 1.6;
}

.tooltip-body p {
  margin: 4px 0;
}

.tooltip-recommendation {
  margin-top: 8px;
  padding: 8px;
  background: #f5f7fa;
  border-radius: 4px;
  font-size: 12px;
  color: #409eff;
}

.confidence-text {
  margin-top: 4px;
  font-size: 12px;
  font-weight: 500;
  text-align: center;
}
</style>
