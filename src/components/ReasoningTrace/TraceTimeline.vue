<template>
  <div class="trace-timeline">
    <div class="timeline-controls">
      <el-button-group>
        <el-button :icon="VideoPlay" @click="play" :disabled="isPlaying || !steps.length">
          播放
        </el-button>
        <el-button :icon="VideoPause" @click="pause" :disabled="!isPlaying">
          暂停
        </el-button>
        <el-button :icon="DArrowLeft" @click="prevStep" :disabled="isPlaying || currentIndex <= 0">
          上一步
        </el-button>
        <el-button :icon="DArrowRight" @click="nextStep" :disabled="isPlaying || currentIndex >= steps.length - 1">
          下一步
        </el-button>
      </el-button-group>

      <el-select v-model="playbackSpeed" style="width: 120px; margin-left: 12px">
        <el-option :value="0.5" label="0.5x" />
        <el-option :value="1" label="1x" />
        <el-option :value="2" label="2x" />
        <el-option :value="4" label="4x" />
      </el-select>

      <div class="progress-info" v-if="steps.length">
        <span>{{ currentIndex + 1 }} / {{ steps.length }}</span>
        <span v-if="currentStep">- {{ currentStep.title }}</span>
      </div>
    </div>

    <div class="timeline-track">
      <div
        v-for="(step, index) in steps"
        :key="step.id"
        class="timeline-node"
        :class="{
          active: index === currentIndex,
          completed: index < currentIndex,
          pending: index > currentIndex
        }"
        @click="goToStep(index)"
      >
        <div class="node-dot">
          <el-icon v-if="index < currentIndex" :size="14"><Check /></el-icon>
          <el-icon v-else-if="index === currentIndex" :size="14"><Loading /></el-icon>
        </div>
        <div class="node-label">{{ step.title }}</div>
        <div class="node-time" v-if="step.timestamp">
          {{ formatTime(step.timestamp) }}
        </div>
      </div>
      <div class="timeline-line" :style="{ width: `${(currentIndex / Math.max(steps.length - 1, 1)) * 100}%` }" />
    </div>

    <div class="timeline-content" v-if="currentStep">
      <StepCard :step="currentStep" />
    </div>

    <div class="timeline-empty" v-else>
      <el-empty description="暂无推理步骤" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { VideoPlay, VideoPause, DArrowLeft, DArrowRight, Check, Loading } from '@element-plus/icons-vue'
import StepCard from './StepCard.vue'
import type { ReasoningStep } from '@/api/reasoning'

const props = defineProps<{
  steps: ReasoningStep[]
  autoPlay?: boolean
}>()

const emit = defineEmits<{
  stepChange: [step: ReasoningStep, index: number]
  playStateChange: [isPlaying: boolean]
}>()

const currentIndex = ref(0)
const isPlaying = ref(false)
const playbackSpeed = ref(1)
let playTimer: ReturnType<typeof setInterval> | null = null

const currentStep = computed(() => props.steps[currentIndex.value] || null)

function play() {
  if (isPlaying.value || !props.steps.length) return
  isPlaying.value = true
  emit('playStateChange', true)
  startAutoPlay()
}

function pause() {
  if (!isPlaying.value) return
  isPlaying.value = false
  emit('playStateChange', false)
  stopAutoPlay()
}

function startAutoPlay() {
  stopAutoPlay()
  playTimer = setInterval(() => {
    if (currentIndex.value < props.steps.length - 1) {
      currentIndex.value++
      emit('stepChange', currentStep.value!, currentIndex.value)
    } else {
      pause()
    }
  }, 2000 / playbackSpeed.value)
}

function stopAutoPlay() {
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
}

function prevStep() {
  if (currentIndex.value > 0) {
    currentIndex.value--
    emit('stepChange', currentStep.value!, currentIndex.value)
  }
}

function nextStep() {
  if (currentIndex.value < props.steps.length - 1) {
    currentIndex.value++
    emit('stepChange', currentStep.value!, currentIndex.value)
  }
}

function goToStep(index: number) {
  if (index >= 0 && index < props.steps.length) {
    currentIndex.value = index
    emit('stepChange', currentStep.value!, currentIndex.value)
  }
}

function formatTime(timestamp: number): string {
  const date = new Date(timestamp)
  return `${date.getHours().toString().padStart(2, '0')}:${date.getMinutes().toString().padStart(2, '0')}:${date.getSeconds().toString().padStart(2, '0')}`
}

watch(playbackSpeed, () => {
  if (isPlaying.value) {
    startAutoPlay()
  }
})

watch(() => props.steps, (newSteps) => {
  if (newSteps.length && currentIndex.value >= newSteps.length) {
    currentIndex.value = newSteps.length - 1
  }
}, { deep: true })

onUnmounted(() => {
  stopAutoPlay()
})

defineExpose({
  play,
  pause,
  prevStep,
  nextStep,
  goToStep,
  currentIndex,
  isPlaying
})
</script>

<style scoped>
.trace-timeline {
  background: white;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  padding: 20px;
}

.timeline-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid #ebeef5;
}

.progress-info {
  margin-left: auto;
  font-size: 14px;
  color: #606266;
}

.timeline-track {
  position: relative;
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 20px 0 40px;
  margin-bottom: 20px;
}

.timeline-line {
  position: absolute;
  top: 28px;
  left: 0;
  height: 2px;
  background: #409eff;
  transition: width 0.3s;
  z-index: 0;
}

.timeline-node {
  position: relative;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  z-index: 1;
  flex: 1;
}

.node-dot {
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: #e4e7ed;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  transition: all 0.3s;
}

.timeline-node.active .node-dot {
  background: #409eff;
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.2);
}

.timeline-node.completed .node-dot {
  background: #67c23a;
}

.node-label {
  font-size: 13px;
  color: #606266;
  text-align: center;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-node.active .node-label {
  color: #409eff;
  font-weight: 600;
}

.node-time {
  font-size: 12px;
  color: #909399;
}

.timeline-content {
  margin-top: 20px;
}

.timeline-empty {
  margin-top: 20px;
}
</style>
