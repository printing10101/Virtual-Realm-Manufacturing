<template>
  <div class="copilot-confidence-indicator">
    <div class="confidence-header">
      <span class="confidence-label">{{ $t('copilot.confidence.label') }}</span>
      <span 
        class="confidence-value" 
        :style="{ color: confidenceColor }"
      >
        {{ (confidence * 100).toFixed(1) }}%
      </span>
    </div>
    
    <div class="confidence-bar-wrapper">
      <div class="confidence-bar-bg">
        <div 
          class="confidence-bar-fill"
          :style="{ 
            width: `${confidence * 100}%`,
            backgroundColor: confidenceColor
          }"
        />
      </div>
      <div class="confidence-markers">
        <span class="marker">0%</span>
        <span class="marker">50%</span>
        <span class="marker">100%</span>
      </div>
    </div>
    
    <div class="confidence-description">
      <el-icon :style="{ color: confidenceColor }">
        <component :is="confidenceIcon" />
      </el-icon>
      <span :style="{ color: confidenceColor }">{{ confidenceText }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { CircleCheck, Warning, CircleClose } from '@element-plus/icons-vue'

interface Props {
  confidence: number
}

const props = defineProps<Props>()

const { t } = useI18n()

const confidenceColor = computed(() => {
  if (props.confidence >= 0.8) return '#67c23a'
  if (props.confidence >= 0.5) return '#e6a23c'
  return '#f56c6c'
})

const confidenceIcon = computed(() => {
  if (props.confidence >= 0.8) return CircleCheck
  if (props.confidence >= 0.5) return Warning
  return CircleClose
})

const confidenceText = computed(() => {
  if (props.confidence >= 0.8) return t('copilot.confidence.high')
  if (props.confidence >= 0.5) return t('copilot.confidence.medium')
  return t('copilot.confidence.low')
})
</script>

<style scoped>
.copilot-confidence-indicator {
  width: 100%;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 8px;
}

.confidence-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.confidence-label {
  font-size: 14px;
  font-weight: 500;
  color: #606266;
}

.confidence-value {
  font-size: 18px;
  font-weight: 600;
}

.confidence-bar-wrapper {
  margin-bottom: 8px;
}

.confidence-bar-bg {
  width: 100%;
  height: 8px;
  background: #e4e7ed;
  border-radius: 4px;
  overflow: hidden;
}

.confidence-bar-fill {
  height: 100%;
  transition: width 0.3s ease, background-color 0.3s ease;
  border-radius: 4px;
}

.confidence-markers {
  display: flex;
  justify-content: space-between;
  margin-top: 4px;
  font-size: 11px;
  color: #909399;
}

.confidence-description {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  margin-top: 8px;
}
</style>
