<template>
  <el-dialog
    v-model="visible"
    title="STEP 模型 3D 预览"
    width="900px"
    top="3vh"
    :close-on-click-modal="false"
    @opened="initViewer"
    @close="disposeViewer"
    destroy-on-close
  >
    <div class="model-viewer-container">
      <div ref="canvasContainer" class="canvas-container"></div>

      <div class="viewer-controls">
        <el-button-group size="small">
          <el-button @click="fitView">
            <el-icon><aim /></el-icon> 居中
          </el-button>
          <el-button @click="viewFront">前</el-button>
          <el-button @click="viewTop">顶</el-button>
          <el-button @click="viewRight">右</el-button>
          <el-button @click="viewIso">3D</el-button>
        </el-button-group>

        <el-divider direction="vertical" />

        <span class="control-label">透明度</span>
        <el-slider
          v-model="opacity"
          :min="0.1"
          :max="1.0"
          :step="0.05"
          style="width: 120px;"
          @input="updateOpacity"
        />

        <el-divider direction="vertical" />

        <el-switch
          v-model="showGrid"
          active-text="网格"
          @change="toggleGrid"
          size="small"
        />

        <el-divider direction="vertical" />

        <el-switch
          v-model="lodEnabled"
          active-text="LOD"
          @change="toggleLOD"
          size="small"
        />

        <el-divider direction="vertical" />

        <span class="fps-display">{{ fps }} FPS</span>
      </div>

      <div class="model-info-bar" v-if="modelStats">
        <span>顶点: {{ modelStats.vertexCount?.toLocaleString() }}</span>
        <span>三角面: {{ modelStats.faceCount?.toLocaleString() }}</span>
        <span>文件: {{ modelStats.fileSize ? formatFileSize(modelStats.fileSize) : '-' }}</span>
      </div>
    </div>

    <template #footer>
      <el-button @click="visible = false">关闭</el-button>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, watch, nextTick, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'

const props = defineProps<{
  modelUrl: string
  modelName?: string
  faceCount?: number
  vertexCount?: number
  fileSize?: number
}>()

const emit = defineEmits<{
  (e: 'close'): void
}>()

const visible = defineModel<boolean>({ required: true })

const canvasContainer = ref<HTMLDivElement>()
const opacity = ref(0.8)
const showGrid = ref(true)
const lodEnabled = ref(false)
const fps = ref(0)
const modelStats = ref<{
  vertexCount: number
  faceCount: number
  fileSize: number
} | null>(null)

let renderer: THREE.WebGLRenderer | null = null
let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let controls: OrbitControls | null = null
let modelMesh: THREE.Mesh | null = null
let gridHelper: THREE.GridHelper | null = null
let animationId = 0
let fpsFrames = 0
let fpsLastTime = 0
let lod: THREE.LOD | null = null

function initViewer() {
  if (!canvasContainer.value) return

  scene = new THREE.Scene()
  scene.background = new THREE.Color('#1a1a2e')

  const w = canvasContainer.value.clientWidth
  const h = canvasContainer.value.clientHeight
  camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 10000)
  camera.position.set(200, -200, 150)

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))
  renderer.toneMapping = THREE.ACESFilmicToneMapping
  renderer.toneMappingExposure = 1.2
  renderer.shadowMap.enabled = true
  canvasContainer.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.target.set(0, 0, 0)

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const dirLight1 = new THREE.DirectionalLight(0xffffff, 0.8)
  dirLight1.position.set(1, 1, 1)
  scene.add(dirLight1)

  const dirLight2 = new THREE.DirectionalLight(0xffffff, 0.4)
  dirLight2.position.set(-1, -0.5, -0.5)
  scene.add(dirLight2)

  gridHelper = new THREE.GridHelper(500, 20, 0x444466, 0x222244)
  if (showGrid.value) scene.add(gridHelper)

  const axesHelper = new THREE.AxesHelper(100)
  scene.add(axesHelper)

  modelStats.value = {
    vertexCount: props.vertexCount ?? 0,
    faceCount: props.faceCount ?? 0,
    fileSize: props.fileSize ?? 0,
  }

  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }

  const resizeObserver = new ResizeObserver(() => {
    if (!canvasContainer.value || !renderer || !camera) return
    const nw = canvasContainer.value.clientWidth
    const nh = canvasContainer.value.clientHeight
    renderer.setSize(nw, nh)
    camera.aspect = nw / nh
    camera.updateProjectionMatrix()
  })
  resizeObserver.observe(canvasContainer.value)

  fpsFrames = 0
  fpsLastTime = performance.now()
  animate()
}

function loadModel(url: string) {
  if (!scene) return

  if (modelMesh) {
    scene.remove(modelMesh)
    modelMesh.geometry?.dispose()
    ;(modelMesh.material as THREE.Material)?.dispose()
    modelMesh = null
  }
  if (lod) {
    scene.remove(lod)
    lod = null
  }

  const loader = new STLLoader()
  loader.load(
    url,
    (geometry) => {
      if (!scene) return

      geometry.computeVertexNormals()
      geometry.center()

      const material = new THREE.MeshStandardMaterial({
        color: '#5b9bd5',
        metalness: 0.3,
        roughness: 0.4,
        transparent: true,
        opacity: opacity.value,
        side: THREE.DoubleSide,
      })

      const mesh = new THREE.Mesh(geometry, material)
      mesh.castShadow = true
      mesh.receiveShadow = true
      modelMesh = mesh
      scene.add(mesh)

      modelStats.value = {
        vertexCount: geometry.attributes.position.count,
        faceCount: geometry.index
          ? geometry.index.count / 3
          : geometry.attributes.position.count / 3,
        fileSize: props.fileSize ?? 0,
      }

      if (lodEnabled.value) {
        buildLOD(geometry, material)
      }

      fitView()
    },
    () => {},
    (err) => {
      console.error('STL加载失败:', err)
    },
  )
}

function buildLOD(geometry: THREE.BufferGeometry, baseMaterial: THREE.Material) {
  if (!scene || !modelMesh) return

  scene.remove(modelMesh)

  lod = new THREE.LOD()

  const fullGeo = geometry.clone()
  const fullMesh = new THREE.Mesh(fullGeo, baseMaterial.clone())
  lod.addLevel(fullMesh, 0)

  const simplifyRatios = [0.5, 0.8]
  const distances = [200, 500]
  for (let i = 0; i < simplifyRatios.length; i++) {
    const simplified = simplifyGeometry(geometry, simplifyRatios[i])
    if (simplified) {
      const mat = baseMaterial.clone()
      const simpleMesh = new THREE.Mesh(simplified, mat)
      lod.addLevel(simpleMesh, distances[i])
    }
  }

  scene.add(lod)
  modelMesh = fullMesh
}

function simplifyGeometry(
  geometry: THREE.BufferGeometry,
  ratio: number,
): THREE.BufferGeometry | null {
  try {
    const positions = geometry.attributes.position.array as Float32Array
    const indices = geometry.index?.array
    const vertexCount = positions.length / 3

    const step = Math.max(2, Math.round(1 / (1 - ratio)))
    if (step <= 1) return null

    const newPositions: number[] = []
    const seen = new Set<string>()

    for (let i = 0; i < vertexCount; i += step) {
      const x = positions[i * 3]
      const y = positions[i * 3 + 1]
      const z = positions[i * 3 + 2]
      const key = `${Math.round(x * 100)},${Math.round(y * 100)},${Math.round(z * 100)}`
      if (!seen.has(key)) {
        seen.add(key)
        newPositions.push(x, y, z)
      }
    }

    const newGeo = new THREE.BufferGeometry()
    newGeo.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(newPositions, 3),
    )
    newGeo.computeVertexNormals()
    return newGeo
  } catch {
    return null
  }
}

function fitView() {
  if (!modelMesh || !camera || !controls) return
  const box = new THREE.Box3().setFromObject(modelMesh)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z)
  const fov = camera.fov * (Math.PI / 180)
  const distance = maxDim / (2 * Math.tan(fov / 2)) * 1.5

  controls.target.copy(center)
  camera.position.set(
    center.x + distance * 0.7,
    center.y - distance * 0.6,
    center.z + distance * 0.5,
  )
  controls.update()
}

function viewFront() {
  if (!camera || !controls) return
  const target = controls.target.clone()
  camera.position.set(target.x, target.y, target.z + 300)
  controls.update()
}

function viewTop() {
  if (!camera || !controls) return
  const target = controls.target.clone()
  camera.position.set(target.x, target.y + 300, target.z)
  controls.update()
}

function viewRight() {
  if (!camera || !controls) return
  const target = controls.target.clone()
  camera.position.set(target.x + 300, target.y, target.z)
  controls.update()
}

function viewIso() {
  if (!camera || !controls) return
  const target = controls.target.clone()
  const d = 200
  camera.position.set(target.x + d, target.y - d, target.z + d)
  controls.update()
}

function updateOpacity() {
  if (!modelMesh) return
  const mat = modelMesh.material as THREE.MeshStandardMaterial
  mat.opacity = opacity.value
}

function toggleGrid() {
  if (!gridHelper || !scene) return
  if (showGrid.value) {
    scene.add(gridHelper)
  } else {
    scene.remove(gridHelper)
  }
}

function toggleLOD() {
  if (!scene || !modelMesh) return
  if (lodEnabled.value) {
    const geometry = modelMesh.geometry
    const material = modelMesh.material as THREE.Material
    buildLOD(geometry, material)
  } else {
    if (lod) {
      scene.remove(lod)
      lod = null
    }
    if (modelMesh && !scene.children.includes(modelMesh)) {
      scene.add(modelMesh)
    }
  }
}

function animate() {
  animationId = requestAnimationFrame(animate)

  fpsFrames++
  const now = performance.now()
  if (now - fpsLastTime >= 1000) {
    fps.value = fpsFrames
    fpsFrames = 0
    fpsLastTime = now
  }

  controls?.update()
  renderer?.render(scene!, camera!)
}

function disposeViewer() {
  if (animationId) cancelAnimationFrame(animationId)

  controls?.dispose()
  renderer?.dispose()

  if (modelMesh) {
    modelMesh.geometry?.dispose()
    ;(modelMesh.material as THREE.Material)?.dispose()
  }
  if (lod) {
    lod.traverse((obj) => {
      if (obj instanceof THREE.Mesh) {
        obj.geometry?.dispose()
        ;(obj.material as THREE.Material)?.dispose()
      }
    })
  }

  if (canvasContainer.value) {
    canvasContainer.value.innerHTML = ''
  }

  renderer = null
  scene = null
  camera = null
  controls = null
  modelMesh = null
  gridHelper = null
  lod = null
}

function formatFileSize(bytes: number): string {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let s = bytes
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++ }
  return s.toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

watch(() => props.modelUrl, (newUrl) => {
  if (newUrl && scene) {
    loadModel(newUrl)
  }
})
</script>

<style scoped>
.model-viewer-container {
  display: flex;
  flex-direction: column;
  height: 60vh;
}

.canvas-container {
  flex: 1;
  min-height: 400px;
  border-radius: 8px;
  overflow: hidden;
  background: #1a1a2e;
}

.viewer-controls {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  margin-top: 8px;
  background: #f5f7fa;
  border-radius: 6px;
  flex-wrap: wrap;
}

.control-label {
  font-size: 12px;
  color: #606266;
  white-space: nowrap;
}

.fps-display {
  font-size: 12px;
  color: #67c23a;
  font-weight: 600;
  font-family: monospace;
}

.model-info-bar {
  display: flex;
  gap: 16px;
  padding: 6px 12px;
  font-size: 12px;
  color: #909399;
  background: #fafafa;
  border-radius: 4px;
  margin-top: 4px;
}

.model-info-bar span {
  white-space: nowrap;
}
</style>
