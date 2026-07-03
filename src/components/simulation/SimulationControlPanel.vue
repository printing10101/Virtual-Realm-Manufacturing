<template>
  <div class="simulation-control-panel">
    <!-- Row 1: Simulation Parameters -->
    <div class="param-row">
      <div class="param-group">
        <label class="param-label">{{ t('simulation.controlPanel.voxelSize') }}</label>
        <el-input-number
          v-model="localVoxelSize"
          :min="0.1"
          :max="10"
          :step="0.1"
          size="small"
          :controls="false"
          class="dark-input-number"
        />
      </div>

      <div class="param-group">
        <label class="param-label">{{ t('simulation.controlPanel.toolType') }}</label>
        <el-select
          v-model="localToolType"
          size="small"
          class="dark-select"
        >
          <el-option
            :label="t('simulation.controlPanel.toolFlat')"
            value="flat"
          />
          <el-option
            :label="t('simulation.controlPanel.toolBall')"
            value="ball"
          />
          <el-option
            :label="t('simulation.controlPanel.toolDrill')"
            value="drill"
          />
        </el-select>
      </div>

      <div class="param-group">
        <label class="param-label">{{ t('simulation.controlPanel.toolDiameter') }}</label>
        <el-input-number
          v-model="localToolDiameter"
          :min="0.1"
          :max="50"
          :step="0.1"
          size="small"
          :controls="false"
          class="dark-input-number"
        />
      </div>

      <div class="param-group">
        <label class="param-label">{{ t('simulation.controlPanel.safeHeight') }}</label>
        <el-input-number
          v-model="localSafeZ"
          :min="1"
          :max="200"
          :step="1"
          size="small"
          :controls="false"
          class="dark-input-number"
        />
      </div>

      <div class="param-group gcode-group">
        <label class="param-label">{{ t('simulation.controlPanel.gcode') }}</label>
        <el-input
          v-model="localGcode"
          size="small"
          :placeholder="t('simulation.controlPanel.gcodePlaceholder')"
          class="dark-input"
        />
      </div>

      <div class="param-group run-group">
        <el-button
          type="primary"
          size="small"
          :loading="isRunning"
          @click="handleRun"
        >
          <el-icon
            v-if="!isRunning"
            class="btn-icon"
          >
            <VideoPlay />
          </el-icon>
          {{ t('simulation.controlPanel.runSimulation') }}
        </el-button>
      </div>
    </div>

    <!-- Row 2: Playback Controls -->
    <div class="playback-row">
      <div class="playback-buttons">
        <el-button
          class="play-btn"
          :type="isRunning ? 'warning' : 'success'"
          circle
          size="small"
          @click="handlePlayPause"
        >
          <el-icon>
            <VideoPause v-if="isRunning" />
            <VideoPlay v-else />
          </el-icon>
        </el-button>

        <el-button
          class="step-btn"
          type="info"
          plain
          circle
          size="small"
          @click="handleStep"
        >
          <el-icon><DArrowRight /></el-icon>
        </el-button>

        <el-button
          class="reset-btn"
          type="info"
          plain
          circle
          size="small"
          @click="handleReset"
        >
          <el-icon><RefreshLeft /></el-icon>
        </el-button>
      </div>

      <div class="speed-selector">
        <button
          v-for="opt in speedOptions"
          :key="opt.value"
          class="speed-pill"
          :class="{ active: currentSpeed === opt.value }"
          @click="selectSpeed(opt.value)"
        >
          {{ opt.label }}
        </button>
      </div>

      <div class="progress-text">
        {{ t('simulation.controlPanel.toolpathPoint', { current: currentToolpathIndex, total: totalToolpathPoints }) }}
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  VideoPlay,
  VideoPause,
  DArrowRight,
  RefreshLeft,
} from '@element-plus/icons-vue'

const { t } = useI18n()

export interface SimulationControlPanelProps {
  modelValue: boolean
  voxelSize?: number
  toolType?: string
  toolDiameter?: number
  safeZ?: number
  gcode?: string
}

const props = withDefaults(defineProps<SimulationControlPanelProps>(), {
  voxelSize: 1,
  toolType: 'flat',
  toolDiameter: 6,
  safeZ: 30,
  gcode: '',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'run'): void
  (e: 'play'): void
  (e: 'pause'): void
  (e: 'step'): void
  (e: 'reset'): void
  (e: 'speed-change', speed: number): void
}>()

const isRunning = computed({
  get: () => props.modelValue,
  set: (val: boolean) => emit('update:modelValue', val),
})

// Local form values synced with props
const localVoxelSize = ref(props.voxelSize)
const localToolType = ref(props.toolType)
const localToolDiameter = ref(props.toolDiameter)
const localSafeZ = ref(props.safeZ)
const localGcode = ref(props.gcode)

// Sync props -> local refs
watch(() => props.voxelSize, (v) => { localVoxelSize.value = v })
watch(() => props.toolType, (v) => { localToolType.value = v })
watch(() => props.toolDiameter, (v) => { localToolDiameter.value = v })
watch(() => props.safeZ, (v) => { localSafeZ.value = v })
watch(() => props.gcode, (v) => { localGcode.value = v })

// Speed options
const speedOptions = [
  { label: '0.5x', value: 0.5 },
  { label: '1x', value: 1 },
  { label: '2x', value: 2 },
  { label: '4x', value: 4 },
] as const

const currentSpeed = ref<number>(1)
const currentToolpathIndex = ref<number>(0)
const totalToolpathPoints = ref<number>(0)

function selectSpeed(speed: number) {
  currentSpeed.value = speed
  emit('speed-change', speed)
}

function handleRun() {
  if (!localGcode.value.trim()) {
    ElMessage.warning(t('simulation.controlPanel.msgEnterGcode'))
    return
  }
  currentToolpathIndex.value = 0
  totalToolpathPoints.value = 0
  isRunning.value = true
  emit('run')
}

function handlePlayPause() {
  if (isRunning.value) {
    isRunning.value = false
    emit('pause')
  } else {
    if (totalToolpathPoints.value === 0) {
      ElMessage.info(t('simulation.controlPanel.msgNoToolpathData'))
      return
    }
    isRunning.value = true
    emit('play')
  }
}

function handleStep() {
  emit('step')
}

function handleReset() {
  isRunning.value = false
  currentSpeed.value = 1
  currentToolpathIndex.value = 0
  totalToolpathPoints.value = 0
  emit('reset')
}
</script>

<style scoped>
.simulation-control-panel {
  background: var(--bg-card, #1A2744);
  border: 1px solid var(--border-light, rgba(255, 255, 255, 0.08));
  border-radius: 12px;
  padding: 16px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* ---- Row 1: Parameters ---- */
.param-row {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  flex-wrap: wrap;
}

.param-group {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.param-label {
  font-size: 11px;
  color: var(--text-muted, #6B7B96);
  white-space: nowrap;
  user-select: none;
}

.gcode-group {
  flex: 1 1 160px;
  min-width: 120px;
}

.gcode-group .dark-input :deep(.el-input__wrapper) {
  width: 100%;
}

.run-group {
  justify-content: flex-end;
}

/* ---- Dark overrides for Element Plus inputs ---- */
.dark-input-number,
.dark-select,
.dark-input {
  --el-fill-color-blank: var(--bg-secondary, #243352);
  --el-border-color: var(--border-light, rgba(255, 255, 255, 0.08));
  --el-border-color-hover: var(--accent-primary, #4A90D9);
  --el-text-color-regular: var(--text-primary, #E8ECF4);
  --el-input-bg-color: var(--bg-secondary, #243352);
  --el-input-text-color: var(--text-primary, #E8ECF4);
  --el-input-border-color: var(--border-light, rgba(255, 255, 255, 0.08));
  --el-input-hover-border-color: var(--accent-primary, #4A90D9);
}

.dark-input-number :deep(.el-input__wrapper),
.dark-select :deep(.el-input__wrapper),
.dark-input :deep(.el-input__wrapper) {
  background-color: var(--bg-secondary, #243352);
  box-shadow: 0 0 0 1px var(--border-light, rgba(255, 255, 255, 0.08)) inset;
}

.dark-input-number :deep(.el-input__wrapper:hover),
.dark-select :deep(.el-input__wrapper:hover),
.dark-input :deep(.el-input__wrapper:hover) {
  box-shadow: 0 0 0 1px var(--accent-primary, #4A90D9) inset;
}

.dark-input-number :deep(.el-input__inner),
.dark-input :deep(.el-input__inner) {
  color: var(--text-primary, #E8ECF4);
  -webkit-text-fill-color: var(--text-primary, #E8ECF4);
}

.dark-select :deep(.el-select__placeholder) {
  color: var(--text-secondary, #A8B4C8);
}

.dark-select :deep(.el-select__selected-item span) {
  color: var(--text-primary, #E8ECF4);
}

.dark-input :deep(.el-input__inner::placeholder) {
  color: var(--text-muted, #6B7B96);
}

.dark-select :deep(.el-popper) {
  --el-fill-color-blank: var(--bg-secondary, #243352);
  --el-border-color-light: var(--border-light, rgba(255, 255, 255, 0.08));
  --el-text-color-regular: var(--text-primary, #E8ECF4);
  --el-bg-color: var(--bg-secondary, #243352);
}

.btn-icon {
  margin-right: 4px;
}

/* ---- Row 2: Playback ---- */
.playback-row {
  display: flex;
  align-items: center;
  gap: 16px;
}

.playback-buttons {
  display: flex;
  align-items: center;
  gap: 8px;
}

.play-btn {
  width: 32px;
  height: 32px;
}

.step-btn,
.reset-btn {
  width: 28px;
  height: 28px;
}

/* ---- Speed pills ---- */
.speed-selector {
  display: flex;
  gap: 4px;
  margin-left: auto;
}

.speed-pill {
  padding: 3px 10px;
  border: 1px solid var(--border-light, rgba(255, 255, 255, 0.08));
  border-radius: 999px;
  background: transparent;
  color: var(--text-secondary, #A8B4C8);
  font-size: 12px;
  cursor: pointer;
  transition: all 0.2s ease;
  user-select: none;
  line-height: 1.4;
}

.speed-pill:hover {
  border-color: var(--accent-primary, #4A90D9);
  color: var(--text-primary, #E8ECF4);
}

.speed-pill.active {
  background: var(--accent-primary, #4A90D9);
  border-color: var(--accent-primary, #4A90D9);
  color: #ffffff;
}

/* ---- Progress text ---- */
.progress-text {
  font-size: 12px;
  color: var(--text-muted, #6B7B96);
  white-space: nowrap;
  min-width: 110px;
  text-align: right;
}
</style>
