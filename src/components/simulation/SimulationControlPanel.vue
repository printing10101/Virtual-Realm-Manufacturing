<template>
  <div class="simulation-control-panel">
    <div class="panel-header">
      <h3>仿真控制</h3>
      <span class="status-badge" :class="simulationStatusClass">
        {{ simulationStatusLabel }}
      </span>
    </div>

    <div class="panel-body">
      <div class="config-section">
        <div class="config-row">
          <label>体素尺寸 (mm)</label>
          <el-slider
            v-model="voxelSize"
            :min="0.2"
            :max="5.0"
            :step="0.1"
            :disabled="isRunning"
            show-input
            :format-tooltip="(v: number) => v.toFixed(1) + ' mm'"
          />
        </div>

        <div class="config-row">
          <label>刀具类型</label>
          <el-select
            v-model="toolType"
            :disabled="isRunning"
            style="width: 100%"
          >
            <el-option label="平底刀 (Flat)" value="flat" />
            <el-option label="球头刀 (Ball)" value="ball" />
            <el-option label="钻头 (Drill)" value="drill" />
          </el-select>
        </div>

        <div class="config-row">
          <label>刀具直径 (mm)</label>
          <el-input-number
            v-model="toolDiameter"
            :min="0.5"
            :max="300"
            :step="1"
            :disabled="isRunning"
            controls-position="right"
            style="width: 100%"
          />
        </div>

        <div class="config-row">
          <label>安全高度 (mm)</label>
          <el-input-number
            v-model="safeZHeight"
            :min="0"
            :max="200"
            :step="5"
            :disabled="isRunning"
            controls-position="right"
            style="width: 100%"
          />
        </div>

        <div class="config-row">
          <label>G代码</label>
          <el-input
            v-model="gcodeInput"
            type="textarea"
            :rows="4"
            :disabled="isRunning"
            placeholder="输入G代码或留空使用默认刀路..."
          />
        </div>

        <el-button
          type="primary"
          :loading="isRunning"
          :disabled="isRunning"
          class="run-btn"
          @click="runSimulation"
        >
          {{ isRunning ? '仿真中...' : '运行仿真' }}
        </el-button>
      </div>

      <div class="divider" />

      <div class="playback-section" v-if="resultLoaded">
        <h4>刀路回放</h4>

        <div class="playback-controls">
          <el-button-group>
            <el-button :icon="VideoPlay" :disabled="playState === 'playing'" @click="togglePlay">
              {{ playState === 'playing' ? '暂停' : '播放' }}
            </el-button>
            <el-button :disabled="playState === 'playing'" @click="stepForward">
              步进
            </el-button>
            <el-button :disabled="playState === 'playing'" @click="resetPlayback">
              重置
            </el-button>
          </el-button-group>
        </div>

        <div class="progress-section">
          <span class="progress-label">
            刀位点 {{ currentSegment + 1 }} / {{ totalSegments }}
          </span>
          <el-slider
            v-model="currentSegment"
            :min="0"
            :max="totalSegments - 1"
            :step="1"
            :disabled="playState === 'playing'"
            @change="onSliderChange"
          />
        </div>

        <div class="speed-section">
          <label>回放速度</label>
          <el-slider
            v-model="playSpeed"
            :min="1"
            :max="20"
            :step="1"
            show-input
          />
        </div>
      </div>

      <div class="divider" v-if="resultLoaded" />

      <div class="stats-section" v-if="resultLoaded && simulationResult">
        <h4>仿真统计</h4>
        <div class="stat-row">
          <span>耗时</span>
          <span>{{ simulationResult.duration_seconds.toFixed(2) }}s</span>
        </div>
        <div class="stat-row">
          <span>体素总数</span>
          <span>{{ simulationResult.voxel_count.toLocaleString() }}</span>
        </div>
        <div class="stat-row">
          <span>切除体素</span>
          <span>{{ simulationResult.removed_voxel_count.toLocaleString() }}</span>
        </div>
        <div class="stat-row">
          <span>材料去除率</span>
          <span>{{ removalRate }}%</span>
        </div>
        <div class="stat-row">
          <span>刀位点数</span>
          <span>{{ simulationResult.toolpath_segment_count }}</span>
        </div>
      </div>
    </div>

    <div class="panel-footer" v-if="errorMessage">
      <el-alert
        :title="errorMessage"
        type="error"
        :closable="true"
        show-icon
        @close="errorMessage = ''"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { VideoPlay } from '@element-plus/icons-vue'
import type {
  SimulationResult,
  SimulationRequest,
  ToolpathSegmentData,
  PlaybackState,
} from '@/types'
import axios from 'axios'

const props = defineProps<{
  projectId?: string
  stockStlPath?: string
}>()

const emit = defineEmits<{
  'simulation-result': [result: SimulationResult]
  'segment-change': [index: number]
  'toolpath-update': [segments: ToolpathSegmentData[]]
  'state-change': [state: PlaybackState]
}>()

const voxelSize = ref(1.0)
const toolType = ref<'flat' | 'ball' | 'drill'>('flat')
const toolDiameter = ref(10.0)
const toolLength = ref(50.0)
const toolCornerRadius = ref(0.0)
const safeZHeight = ref(10.0)
const gcodeInput = ref('')
const isRunning = ref(false)
const errorMessage = ref('')

const resultLoaded = ref(false)
const simulationResult = ref<SimulationResult | null>(null)
const playState = ref<PlaybackState>('idle')
const currentSegment = ref(0)
const totalSegments = ref(0)
const playSpeed = ref(5)
const targetFps = ref(30)

let playTimer: ReturnType<typeof setInterval> | null = null

const simulationStatusLabel = computed(() => {
  if (isRunning.value) return '运行中'
  if (resultLoaded.value) return '已完成'
  return '就绪'
})

const simulationStatusClass = computed(() => ({
  'status-ready': !isRunning.value && !resultLoaded.value,
  'status-running': isRunning.value,
  'status-done': resultLoaded.value,
}))

const removalRate = computed(() => {
  if (!simulationResult.value || simulationResult.value.voxel_count === 0) return '0.0'
  return (
    (simulationResult.value.removed_voxel_count / simulationResult.value.voxel_count) *
    100
  ).toFixed(1)
})

function togglePlay(): void {
  if (playState.value === 'playing') {
    pausePlayback()
  } else {
    startPlayback()
  }
}

function startPlayback(): void {
  playState.value = 'playing'
  emit('state-change', 'playing')

  const interval = 1000 / (playSpeed.value * targetFps.value)
  playTimer = setInterval(() => {
    if (currentSegment.value < totalSegments.value - 1) {
      currentSegment.value++
      emit('segment-change', currentSegment.value)
    } else {
      pausePlayback()
    }
  }, Math.max(interval, 50))
}

function pausePlayback(): void {
  if (playTimer) {
    clearInterval(playTimer)
    playTimer = null
  }
  playState.value = 'paused'
  emit('state-change', 'paused')
}

function stepForward(): void {
  if (currentSegment.value < totalSegments.value - 1) {
    currentSegment.value++
    emit('segment-change', currentSegment.value)
  }
}

function resetPlayback(): void {
  pausePlayback()
  currentSegment.value = 0
  playState.value = 'idle'
  emit('segment-change', 0)
  emit('state-change', 'idle')
}

function onSliderChange(val: number | number[]): void {
  emit('segment-change', typeof val === 'number' ? val : val[0])
}

async function runSimulation(): Promise<void> {
  isRunning.value = true
  errorMessage.value = ''

  try {
    const request: SimulationRequest = {
      project_id: props.projectId || 'default',
      voxel_size: voxelSize.value,
      tool_diameter: toolDiameter.value,
      tool_length: toolLength.value,
      tool_type: toolType.value,
      tool_corner_radius: toolCornerRadius.value,
      gcode: gcodeInput.value,
      safe_z_height: safeZHeight.value,
      stock_stl_path: props.stockStlPath || '',
    }

    const response = await axios.post('/api/simulation/run', request)
    const data = response.data

    if (data.code !== 0) {
      errorMessage.value = data.message || '仿真执行失败'
      return
    }

    const result = data.data as SimulationResult
    simulationResult.value = result
    resultLoaded.value = true
    totalSegments.value = result.toolpath_segment_count
    currentSegment.value = 0

    emit('simulation-result', result)
  } catch (err: any) {
    errorMessage.value = err.response?.data?.message || err.message || '网络请求失败'
  } finally {
    isRunning.value = false
  }
}

onBeforeUnmount(() => {
  pausePlayback()
})

watch(playSpeed, () => {
  if (playState.value === 'playing') {
    pausePlayback()
    startPlayback()
  }
})
</script>

<style lang="scss" scoped>
.simulation-control-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
  border-left: 1px solid #e0e0e0;
  font-size: 13px;

  .panel-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 16px;
    border-bottom: 1px solid #eee;

    h3 {
      margin: 0;
      font-size: 15px;
      font-weight: 600;
      color: #1a1a2e;
    }

    .status-badge {
      padding: 3px 10px;
      border-radius: 12px;
      font-size: 11px;
      font-weight: 500;

      &.status-ready { background: #e8f5e9; color: #2e7d32; }
      &.status-running { background: #fff3e0; color: #e65100; }
      &.status-done { background: #e3f2fd; color: #1565c0; }
    }
  }

  .panel-body {
    flex: 1;
    overflow-y: auto;
    padding: 12px 16px;
  }

  .panel-footer {
    padding: 10px 16px;
    border-top: 1px solid #eee;
  }

  .config-section {
    .config-row {
      margin-bottom: 14px;

      label {
        display: block;
        font-size: 12px;
        font-weight: 500;
        color: #555;
        margin-bottom: 6px;
      }
    }

    .run-btn {
      width: 100%;
      margin-top: 8px;
      font-weight: 500;
    }
  }

  .divider {
    height: 1px;
    background: #eee;
    margin: 16px 0;
  }

  .playback-section {
    h4 {
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 600;
      color: #333;
    }

    .playback-controls {
      margin-bottom: 12px;
    }

    .progress-section {
      margin-bottom: 10px;

      .progress-label {
        font-size: 11px;
        color: #888;
        margin-bottom: 4px;
        display: block;
      }
    }

    .speed-section {
      label {
        display: block;
        font-size: 12px;
        color: #666;
        margin-bottom: 4px;
      }
    }
  }

  .stats-section {
    h4 {
      margin: 0 0 10px;
      font-size: 13px;
      font-weight: 600;
      color: #333;
    }

    .stat-row {
      display: flex;
      justify-content: space-between;
      padding: 5px 0;
      border-bottom: 1px solid #f5f5f5;

      span:first-child {
        color: #888;
        font-size: 12px;
      }
      span:last-child {
        color: #333;
        font-weight: 500;
        font-size: 12px;
      }
    }
  }
}
</style>
