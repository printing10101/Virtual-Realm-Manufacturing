<template>
  <div class="three-viewer-container">
    <div
      ref="viewerContainer"
      class="viewer-canvas"
    />

    <div class="viewer-controls">
      <div class="control-group">
        <label class="control-label">LOD {{ $t('common.enabled') }}</label>
        <el-switch
          v-model="lodEnabled"
          :active-text="$t('common.on')"
          :inactive-text="$t('common.off')"
          @change="onLODEnabledChange"
        />
      </div>

      <div
        v-if="lodEnabled"
        class="control-group lod-settings"
      >
        <label class="control-label">{{ $t('lod.distanceThresholds') }}</label>

        <div class="threshold-row">
          <span class="threshold-label">{{ $t('lod.highPrecision') }}</span>
          <el-slider
            v-model="lodConfig.levels[0].distance"
            :min="10"
            :max="100"
            :step="5"
            @change="onLODConfigChange"
          />
          <span class="threshold-value">{{ lodConfig.levels[0].distance }}</span>
        </div>

        <div class="threshold-row">
          <span class="threshold-label">{{ $t('lod.mediumPrecision') }}</span>
          <el-slider
            v-model="lodConfig.levels[1].distance"
            :min="50"
            :max="200"
            :step="5"
            @change="onLODConfigChange"
          />
          <span class="threshold-value">{{ lodConfig.levels[1].distance }}</span>
        </div>

        <div class="threshold-row">
          <span class="threshold-label">{{ $t('lod.lowPrecision') }}</span>
          <el-slider
            v-model="lodConfig.levels[2].distance"
            :min="150"
            :max="500"
            :step="10"
            @change="onLODConfigChange"
          />
          <span class="threshold-value">{{ lodConfig.levels[2].distance }}</span>
        </div>
      </div>

      <div
        v-if="lodEnabled"
        class="control-group simplification-settings"
      >
        <label class="control-label">{{ $t('lod.simplification') }}</label>

        <div class="simplification-row">
          <span class="simplification-label">{{ $t('lod.mediumSimplification') }}</span>
          <el-slider
            v-model="lodConfig.levels[1].simplificationRatio"
            :min="0"
            :max="0.8"
            :step="0.1"
            @change="onLODConfigChange"
          />
          <span class="simplification-value">
            {{ Math.round(lodConfig.levels[1].simplificationRatio * 100) }}%
          </span>
        </div>

        <div class="simplification-row">
          <span class="simplification-label">{{ $t('lod.lowSimplification') }}</span>
          <el-slider
            v-model="lodConfig.levels[2].simplificationRatio"
            :min="0.5"
            :max="0.95"
            :step="0.05"
            @change="onLODConfigChange"
          />
          <span class="simplification-value">
            {{ Math.round(lodConfig.levels[2].simplificationRatio * 100) }}%
          </span>
        </div>
      </div>

      <div
        v-if="lodEnabled"
        class="control-group performance-monitor"
      >
        <label class="control-label">{{ $t('lod.performance') }}</label>
        <div class="metrics-row">
          <span class="metric-label">{{ $t('lod.fps') }}</span>
          <span class="metric-value">{{ currentFPS }}</span>
        </div>
        <div class="metrics-row">
          <span class="metric-label">{{ $t('lod.currentLevel') }}</span>
          <span class="metric-value">{{ currentLODLevel }}</span>
        </div>
        <div class="metrics-row">
          <span class="metric-label">{{ $t('lod.distance') }}</span>
          <span class="metric-value">{{ currentDistance.toFixed(1) }}</span>
        </div>
        <div class="metrics-row">
          <span class="metric-label">{{ $t('lod.vertices') }}</span>
          <span class="metric-value">{{ currentVertices.toLocaleString() }}</span>
        </div>
        <div
          v-if="performanceMetrics.fpsWithLOD && performanceMetrics.fpsWithoutLOD"
          class="metrics-row highlight"
        >
          <span class="metric-label">{{ $t('lod.improvement') }}</span>
          <span class="metric-value">
            {{ ((performanceMetrics.fpsWithLOD - performanceMetrics.fpsWithoutLOD) / performanceMetrics.fpsWithoutLOD * 100).toFixed(1) }}%
          </span>
        </div>
      </div>
    </div>

    <div
      v-if="loading"
      class="viewer-loading"
    >
      <el-icon class="loading-icon">
        <Loading />
      </el-icon>
      <span>{{ $t('viewer.loading') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import * as THREE from 'three'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import {
  createLODForModel,
  updateLOD,
  calculateDistanceToModel,
  getDefaultConfig,
  measurePerformance,
  estimateMemoryUsage,
  countVertices,
  type LODConfig,
  type LODPerformanceMetrics,
} from '@/utils/lodHelper'
import { Loading } from '@element-plus/icons-vue'
import { useThreeScene } from '@/composables/useThreeScene'

const props = defineProps<{
  modelUrl?: string
  autoRotate?: boolean
  enableGrid?: boolean
  backgroundColor?: string
}>()

const emit = defineEmits<{
  'model-loaded': [model: THREE.Object3D]
  'lod-level-changed': [level: number]
  'performance-update': [metrics: LODPerformanceMetrics]
}>()

const viewerContainer = ref<HTMLElement>()
const loading = ref(false)

const lodEnabled = ref(true)
const lodConfig = reactive<LODConfig>(getDefaultConfig())
const currentLOD = ref<THREE.LOD | null>(null)
const originalModel = ref<THREE.Object3D | null>(null)
const currentFPS = ref(0)
const currentDistance = ref(0)
const currentLODLevel = ref('N/A')
const currentVertices = ref(0)
const performanceMetrics = reactive<LODPerformanceMetrics>({
  originalVertexCount: 0,
  lodVertexCounts: [],
  memoryBeforeKB: 0,
  memoryAfterKB: 0,
  fpsWithLOD: 0,
  fpsWithoutLOD: 0,
})

let threeScene: ReturnType<typeof useThreeScene> | null = null

onMounted(() => {
  initScene()
  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }
})

onBeforeUnmount(() => {
  threeScene?.cleanup()
})

function initScene() {
  if (!viewerContainer.value) return

  threeScene = useThreeScene({
    container: viewerContainer.value,
    backgroundColor: props.backgroundColor,
    autoRotate: props.autoRotate,
    showGrid: props.enableGrid,
  })

  const { scene, addLight, startAnimation } = threeScene

  addLight(new THREE.AmbientLight(0xffffff, 0.6))

  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8)
  dir1.position.set(10, 10, 10)
  addLight(dir1)

  const dir2 = new THREE.DirectionalLight(0xffffff, 0.4)
  dir2.position.set(-10, 5, -10)
  addLight(dir2)

  startAnimation(() => {
    if (currentLOD.value && lodEnabled.value) {
      updateLOD(currentLOD.value, threeScene!.camera)

      const level = currentLOD.value.getCurrentLevel()
      currentLODLevel.value = level === 0 ? 'High' : level === 1 ? 'Medium' : 'Low'

      if (originalModel.value) {
        currentDistance.value = calculateDistanceToModel(threeScene!.camera, originalModel.value)
      }

      const lodObject = currentLOD.value.levels[level]?.object
      if (lodObject) {
        currentVertices.value = countVertices(lodObject)
      }
    }
  })
}

async function loadModel(url: string) {
  if (!threeScene) return

  loading.value = true

  try {
    clearScene()

    let model: THREE.Object3D | null = null

    if (url.toLowerCase().endsWith('.gltf') || url.toLowerCase().endsWith('.glb')) {
      model = await loadGLTF(url)
    } else if (url.toLowerCase().endsWith('.obj')) {
      model = await loadOBJ(url)
    } else {
      throw new Error(`Unsupported model format: ${url}`)
    }

    if (!model) {
      throw new Error('Failed to load model')
    }

    originalModel.value = model

    const memoryBefore = estimateMemoryUsage(model)
    performanceMetrics.originalVertexCount = countVertices(model)
    performanceMetrics.memoryBeforeKB = memoryBefore

    if (lodEnabled.value) {
      const lod = createLODForModel(model, lodConfig)
      if (lod) {
        currentLOD.value = lod
        threeScene.scene.add(lod)

        const memoryAfter = estimateMemoryUsage(lod)
        performanceMetrics.memoryAfterKB = memoryAfter

        performanceMetrics.lodVertexCounts = lod.levels.map((l) =>
          countVertices(l.object)
        )

        await measureAndComparePerformance()
      }
    } else {
      threeScene.scene.add(model)
    }

    centerCameraOnModel(model)

    emit('model-loaded', model)
  } catch {
    // 模型加载失败，静默处理
  } finally {
    loading.value = false
  }
}

function loadGLTF(url: string): Promise<THREE.Object3D> {
  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader()
    loader.load(
      url,
      (gltf) => resolve(gltf.scene),
      undefined,
      reject
    )
  })
}

function loadOBJ(url: string): Promise<THREE.Object3D> {
  return new Promise((resolve, reject) => {
    const loader = new OBJLoader()
    loader.load(
      url,
      (obj) => resolve(obj),
      undefined,
      reject
    )
  })
}

async function measureAndComparePerformance() {
  if (!threeScene) return

  const { renderer, scene, camera } = threeScene
  const fpsWithLOD = await measurePerformance(renderer, scene, camera, 2000)
  performanceMetrics.fpsWithLOD = fpsWithLOD
  currentFPS.value = fpsWithLOD

  if (currentLOD.value && originalModel.value) {
    scene.remove(currentLOD.value)
    scene.add(originalModel.value)

    const fpsWithoutLOD = await measurePerformance(renderer, scene, camera, 1000)
    performanceMetrics.fpsWithoutLOD = fpsWithoutLOD

    scene.remove(originalModel.value)
    scene.add(currentLOD.value)
  }

  emit('performance-update', { ...performanceMetrics })
}

function centerCameraOnModel(model: THREE.Object3D) {
  if (!threeScene) return

  const { camera, controls } = threeScene

  const box = new THREE.Box3().setFromObject(model)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())

  const maxDim = Math.max(size.x, size.y, size.z)
  const fov = camera.fov * (Math.PI / 180)
  let cameraZ = maxDim / (2 * Math.tan(fov / 2))
  cameraZ *= 1.5

  controls.target.copy(center)
  camera.position.set(center.x, center.y + cameraZ * 0.3, center.z + cameraZ)
  controls.update()
}

function clearScene() {
  if (!threeScene) return

  const { scene } = threeScene
  const toRemove: THREE.Object3D[] = []
  scene.traverse((child) => {
    if (child instanceof THREE.Mesh || child instanceof THREE.LOD) {
      toRemove.push(child)
    }
  })

  toRemove.forEach((obj) => scene.remove(obj))

  currentLOD.value = null
  originalModel.value = null
}

function onLODEnabledChange(enabled: boolean | string | number) {
  if (enabled === true) {
    applyLODToCurrentModel()
  } else {
    removeLODFromCurrentModel()
  }
}

function applyLODToCurrentModel() {
  if (!threeScene || !originalModel.value) return

  const lod = createLODForModel(originalModel.value, lodConfig)
  if (lod) {
    threeScene.scene.remove(originalModel.value)
    threeScene.scene.add(lod)
    currentLOD.value = lod

    performanceMetrics.lodVertexCounts = lod.levels.map((l) =>
      countVertices(l.object)
    )
  }
}

function removeLODFromCurrentModel() {
  if (!threeScene || !originalModel.value || !currentLOD.value) return

  threeScene.scene.remove(currentLOD.value)
  threeScene.scene.add(originalModel.value)
  currentLOD.value = null
}

function onLODConfigChange() {
  if (currentLOD.value && originalModel.value) {
    applyLODToCurrentModel()
  }
}
</script>

<style lang="scss" scoped>
.three-viewer-container {
  position: relative;
  width: 100%;
  height: 100%;
  display: flex;

  .viewer-canvas {
    flex: 1;
    height: 100%;
    min-width: 0;
  }

  .viewer-controls {
    position: absolute;
    top: 20px;
    right: 20px;
    width: 280px;
    background: var(--bg-primary);
    backdrop-filter: blur(10px);
    border-radius: 8px;
    padding: 16px;
    box-shadow: var(--shadow-sm);
    z-index: 10;
    max-height: calc(100% - 40px);
    overflow-y: auto;

    .control-group {
      margin-bottom: 16px;

      &:last-child {
        margin-bottom: 0;
      }

      .control-label {
        display: block;
        font-size: 13px;
        font-weight: 500;
        color: var(--bg-tertiary);
        margin-bottom: 8px;
      }
    }

    .lod-settings {
      border-top: 1px solid var(--border-light);
      padding-top: 16px;

      .threshold-row,
      .simplification-row {
        display: flex;
        align-items: center;
        margin-bottom: 8px;

        .threshold-label,
        .simplification-label {
          width: 80px;
          font-size: 12px;
          color: var(--text-secondary);
        }

        .el-slider {
          flex: 1;
          margin: 0 8px;
        }

        .threshold-value,
        .simplification-value {
          width: 40px;
          text-align: right;
          font-size: 12px;
          font-weight: 500;
          color: var(--bg-tertiary);
        }
      }
    }

    .simplification-settings {
      border-top: 1px solid var(--border-light);
      padding-top: 16px;
    }

    .performance-monitor {
      border-top: 1px solid var(--border-light);
      padding-top: 16px;

      .metrics-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;

        .metric-label {
          font-size: 12px;
          color: var(--text-secondary);
        }

        .metric-value {
          font-size: 12px;
          font-weight: 600;
          color: var(--bg-tertiary);
        }

        &.highlight {
          margin-top: 8px;
          padding: 8px;
          background: linear-gradient(135deg, var(--accent-primary) 0%, var(--accent-hover) 100%);
          border-radius: 6px;

          .metric-label,
          .metric-value {
            color: var(--text-primary);
          }
        }
      }
    }
  }

  .viewer-loading {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 12px;
    color: var(--text-primary);
    font-size: 14px;

    .loading-icon {
      font-size: 32px;
      animation: spin 1s linear infinite;
    }
  }
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
