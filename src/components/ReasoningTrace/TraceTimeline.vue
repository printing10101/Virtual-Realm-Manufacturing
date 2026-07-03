<template>
  <div class="trace-timeline">
    <div class="timeline-controls">
      <el-button-group>
        <el-button
          :icon="VideoPlay"
          :disabled="isPlaying || !steps.length"
          @click="play"
        >
          {{ t('traceTimeline.play') }}
        </el-button>
        <el-button
          :icon="VideoPause"
          :disabled="!isPlaying"
          @click="pause"
        >
          {{ t('traceTimeline.pause') }}
        </el-button>
        <el-button
          :icon="DArrowLeft"
          :disabled="isPlaying || currentIndex <= 0"
          @click="prevStep"
        >
          {{ t('traceTimeline.prevStep') }}
        </el-button>
        <el-button
          :icon="DArrowRight"
          :disabled="isPlaying || currentIndex >= steps.length - 1"
          @click="nextStep"
        >
          {{ t('traceTimeline.nextStep') }}
        </el-button>
      </el-button-group>

      <el-select
        v-model="playbackSpeed"
        style="width: 120px; margin-left: 12px"
      >
        <el-option
          :value="0.5"
          label="0.5x"
        />
        <el-option
          :value="1"
          label="1x"
        />
        <el-option
          :value="2"
          label="2x"
        />
        <el-option
          :value="4"
          label="4x"
        />
      </el-select>

      <div
        v-if="steps.length"
        class="progress-info"
      >
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
          <el-icon
            v-if="index < currentIndex"
            :size="14"
          >
            <Check />
          </el-icon>
          <el-icon
            v-else-if="index === currentIndex"
            :size="14"
          >
            <Loading />
          </el-icon>
        </div>
        <div class="node-label">
          {{ step.title }}
        </div>
        <div
          v-if="step.timestamp"
          class="node-time"
        >
          {{ formatTime(step.timestamp) }}
        </div>
      </div>
      <div
        class="timeline-line"
        :style="{ width: `${(currentIndex / Math.max(steps.length - 1, 1)) * 100}%` }"
      />
    </div>

    <div
      v-if="currentStep"
      class="timeline-content"
    >
      <StepCard :step="currentStep" />
    </div>

    <div
      v-else
      class="timeline-empty"
    >
      <el-empty :description="t('traceTimeline.empty')" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onUnmounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { VideoPlay, VideoPause, DArrowLeft, DArrowRight, Check, Loading } from '@element-plus/icons-vue'
import StepCard from './StepCard.vue'
import type { ReasoningStep } from '@/api/reasoning'

const { t } = useI18n()

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
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: 8px;
  padding: 20px;
}

.timeline-controls {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-light);
}

.progress-info {
  margin-left: auto;
  font-size: 14px;
  color: var(--text-secondary);
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
  background: var(--accent-primary);
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
  background: var(--border-light);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--bg-card);
  transition: all 0.3s;
}

.timeline-node.active .node-dot {
  background: var(--accent-primary);
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.2);
}

.timeline-node.completed .node-dot {
  background: var(--success);
}

.node-label {
  font-size: 13px;
  color: var(--text-secondary);
  text-align: center;
  max-width: 100px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.timeline-node.active .node-label {
  color: var(--accent-primary);
  font-weight: 600;
}

.node-time {
  font-size: 12px;
  color: var(--text-tertiary);
}

.timeline-content {
  margin-top: 20px;
}

.timeline-empty {
  margin-top: 20px;
}
</style>
