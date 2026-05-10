<template>
  <div class="three-viewer-container">
    <div ref="viewerContainer" class="viewer-canvas"></div>

    <div class="viewer-controls">
      <div class="control-group">
        <label class="control-label">LOD {{ $t('common.enabled') }}</label>
        <el-switch
          v-model="lodEnabled"
          @change="onLODEnabledChange"
          :active-text="$t('common.on')"
          :inactive-text="$t('common.off')"
        />
      </div>

      <div v-if="lodEnabled" class="control-group lod-settings">
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

      <div v-if="lodEnabled" class="control-group simplification-settings">
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

      <div v-if="lodEnabled" class="control-group performance-monitor">
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
        <div v-if="performanceMetrics.fpsWithLOD && performanceMetrics.fpsWithoutLOD" class="metrics-row highlight">
          <span class="metric-label">{{ $t('lod.improvement') }}</span>
          <span class="metric-value">
            {{ ((performanceMetrics.fpsWithLOD - performanceMetrics.fpsWithoutLOD) / performanceMetrics.fpsWithoutLOD * 100).toFixed(1) }}%
          </span>
        </div>
      </div>
    </div>

    <div v-if="loading" class="viewer-loading">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <span>{{ $t('viewer.loading') }}</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import {
  createLODForModel,
  updateLOD,
  calculateDistanceToModel,
  getDefaultConfig,
  updateLODConfig,
  measurePerformance,
  estimateMemoryUsage,
  countVertices,
  type LODConfig,
  type LODPerformanceMetrics,
} from '@/utils/lodHelper'
import { Loading } from '@element-plus/icons-vue'

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

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let animationId: number | null = null

onMounted(() => {
  initScene()
  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }
})

onBeforeUnmount(() => {
  cleanup()
})

function initScene() {
  if (!viewerContainer.value) return

  const width = viewerContainer.value.clientWidth
  const height = viewerContainer.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color(props.backgroundColor || '#1a1a2e')

  camera = new THREE.PerspectiveCamera(60, width / height, 0.1, 10000)
  camera.position.set(0, 50, 100)

  renderer = new THREE.WebGLRenderer({
    antialias: true,
    alpha: false,
  })
  renderer.setSize(width, height)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2

  viewerContainer.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.autoRotate = props.autoRotate || false
  controls.autoRotateSpeed = 1.0

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const directionalLight1 = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight1.position.set(10, 10, 10)
  scene.add(directionalLight1)

  const directionalLight2 = new THREE.DirectionalLight(0xffffff, 0.4)
  directionalLight2.position.set(-10, 5, -10)
  scene.add(directionalLight2)

  if (props.enableGrid) {
    const gridHelper = new THREE.GridHelper(200, 20, 0x444444, 0x222222)
    scene.add(gridHelper)
  }

  const resizeObserver = new ResizeObserver(() => {
    if (!viewerContainer.value || !camera || !renderer) return
    const w = viewerContainer.value.clientWidth
    const h = viewerContainer.value.clientHeight
    camera.aspect = w / h
    camera.updateProjectionMatrix()
    renderer.setSize(w, h)
  })
  resizeObserver.observe(viewerContainer.value)

  startAnimation()
}

function startAnimation() {
  function animate() {
    animationId = requestAnimationFrame(animate)

    if (controls) {
      controls.update()
    }

    if (currentLOD.value && camera && lodEnabled.value) {
      updateLOD(currentLOD.value, camera)

      const level = currentLOD.value.getCurrentLevel()
      currentLODLevel.value = level === 0 ? 'High' : level === 1 ? 'Medium' : 'Low'

      if (originalModel.value) {
        currentDistance.value = calculateDistanceToModel(camera, originalModel.value)
      }

      const vertices = currentLOD.value.getCurrentObject()
      currentVertices.value = countVertices(vertices)
    }

    if (renderer && scene && camera) {
      renderer.render(scene, camera)
    }
  }

  animate()
}

async function loadModel(url: string) {
  if (!scene || !renderer) return

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
        scene.add(lod)

        const memoryAfter = estimateMemoryUsage(lod)
        performanceMetrics.memoryAfterKB = memoryAfter

        performanceMetrics.lodVertexCounts = lod.levels.map((l) =>
          countVertices(l.object)
        )

        await measureAndComparePerformance()
      }
    } else {
      scene.add(model)
    }

    centerCameraOnModel(model)

    emit('model-loaded', model)
  } catch (error) {
    console.error('Failed to load model:', error)
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
  if (!renderer || !scene || !camera) return

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
  if (!camera || !controls) return

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
  if (!scene) return

  const toRemove: THREE.Object3D[] = []
  scene.traverse((child) => {
    if (child instanceof THREE.Mesh || child instanceof THREE.LOD) {
      toRemove.push(child)
    }
  })

  toRemove.forEach((obj) => scene!.remove(obj))

  currentLOD.value = null
  originalModel.value = null
}

function onLODEnabledChange(enabled: boolean) {
  if (enabled) {
    applyLODToCurrentModel()
  } else {
    removeLODFromCurrentModel()
  }
}

function applyLODToCurrentModel() {
  if (!scene || !originalModel.value) return

  const lod = createLODForModel(originalModel.value, lodConfig)
  if (lod) {
    scene.remove(originalModel.value)
    scene.add(lod)
    currentLOD.value = lod

    performanceMetrics.lodVertexCounts = lod.levels.map((l) =>
      countVertices(l.object)
    )
  }
}

function removeLODFromCurrentModel() {
  if (!scene || !originalModel.value || !currentLOD.value) return

  scene.remove(currentLOD.value)
  scene.add(originalModel.value)
  currentLOD.value = null
}

function onLODConfigChange() {
  if (currentLOD.value && originalModel.value) {
    applyLODToCurrentModel()
  }
}

function cleanup() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }

  if (controls) {
    controls.dispose()
    controls = null
  }

  if (renderer) {
    renderer.dispose()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
    renderer = null
  }

  clearScene()
  scene = null
  camera = null
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
    background: rgba(255, 255, 255, 0.95);
    backdrop-filter: blur(10px);
    border-radius: 8px;
    padding: 16px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
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
        color: #333;
        margin-bottom: 8px;
      }
    }

    .lod-settings {
      border-top: 1px solid #eee;
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
          color: #666;
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
          color: #333;
        }
      }
    }

    .simplification-settings {
      border-top: 1px solid #eee;
      padding-top: 16px;
    }

    .performance-monitor {
      border-top: 1px solid #eee;
      padding-top: 16px;

      .metrics-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 4px 0;

        .metric-label {
          font-size: 12px;
          color: #666;
        }

        .metric-value {
          font-size: 12px;
          font-weight: 600;
          color: #333;
        }

        &.highlight {
          margin-top: 8px;
          padding: 8px;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          border-radius: 6px;

          .metric-label,
          .metric-value {
            color: white;
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
    color: white;
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
