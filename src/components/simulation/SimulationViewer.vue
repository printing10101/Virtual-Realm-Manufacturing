<template>
  <div class="simulation-viewer">
    <div
      ref="containerRef"
      class="viewer-canvas"
    />

    <div
      v-if="!initialized"
      class="viewer-placeholder"
    >
      <p>3D仿真场景已就绪</p>
      <p class="hint">
        请运行仿真以加载模型
      </p>
    </div>

    <div
      v-if="loading"
      class="viewer-overlay"
    >
      <span class="loading-text">仿真计算中...</span>
      <div class="progress-bar">
        <div
          class="progress-fill"
          :style="{ width: progress + '%' }"
        />
      </div>
    </div>

    <div class="coordinate-axes">
      <span class="axis-x">X</span>
      <span class="axis-y">Y</span>
      <span class="axis-z">Z</span>
    </div>

    <div
      v-if="fps > 0"
      class="fps-counter"
    >
      FPS: {{ fps }}
    </div>
  </div>
</template>

<script setup lang="ts">
import * as THREE from 'three'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import type { SimulationResult, CollisionInfo, ToolpathSegmentData } from '@/types'
import { useThreeScene } from '@/composables/useThreeScene'

const props = defineProps<{
  stockStlUrl?: string
  resultStlUrl?: string
  collisionData?: CollisionInfo
  toolpathSegments?: ToolpathSegmentData[]
  backgroundColor?: string
  showGrid?: boolean
  playing?: boolean
  playSpeed?: number
  currentSegmentIndex?: number
}>()

const emit = defineEmits<{
  'segment-change': [index: number]
  'fps-update': [fps: number]
  'collision-click': [position: [number, number, number]]
}>()

const containerRef = ref<HTMLElement>()
const initialized = ref(false)
const loading = ref(false)
const progress = ref(0)
const fps = ref(0)

let threeScene: ReturnType<typeof useThreeScene> | null = null

let stockMesh: THREE.Mesh | null = null
let resultMesh: THREE.Mesh | null = null
let toolPathLine: THREE.Line | null = null
let toolPathPoints: THREE.Points | null = null
let collisionMarkers: THREE.Group | null = null
let toolIndicator: THREE.Mesh | null = null

let fpsFrameCount = 0
let fpsLastTime = performance.now()

const stockMaterial = new THREE.MeshPhongMaterial({
  color: 0x888888,
  specular: 0x333333,
  shininess: 30,
  transparent: true,
  opacity: 0.7,
  side: THREE.DoubleSide,
})

const resultMaterial = new THREE.MeshPhongMaterial({
  color: 0x4caf50,
  specular: 0x222222,
  shininess: 40,
  side: THREE.DoubleSide,
})

const collisionMaterial = new THREE.MeshPhongMaterial({
  color: 0xff1744,
  emissive: 0x330000,
  emissiveIntensity: 0.8,
  shininess: 100,
})

onMounted(() => {
  initScene()
  initialized.value = true

  if (props.stockStlUrl) {
    loadStockModel(props.stockStlUrl)
  }
  if (props.resultStlUrl) {
    loadResultModel(props.resultStlUrl)
  }
  if (props.toolpathSegments && props.toolpathSegments.length > 0) {
    drawToolpath(props.toolpathSegments)
  }
  if (props.collisionData?.collided) {
    drawCollisionMarkers(props.collisionData)
  }
})

onBeforeUnmount(() => {
  threeScene?.cleanup()
})

watch(() => props.stockStlUrl, (url) => {
  if (url) loadStockModel(url)
})

watch(() => props.resultStlUrl, (url) => {
  if (url) loadResultModel(url)
})

watch(() => props.toolpathSegments, (segments) => {
  if (segments && segments.length > 0) drawToolpath(segments)
})

watch(() => props.collisionData, (data) => {
  if (data?.collided) drawCollisionMarkers(data)
})

watch(() => props.currentSegmentIndex, (idx) => {
  if (idx != null && props.toolpathSegments) {
    updateToolIndicator(idx)
  }
})

function initScene() {
  if (!containerRef.value) return

  threeScene = useThreeScene({
    container: containerRef.value,
    backgroundColor: props.backgroundColor,
    fov: 50,
    cameraPosition: [200, -200, 150],
    dampingFactor: 0.08,
    showGrid: props.showGrid !== false,
    gridSize: 300,
  })

  const { scene, addLight } = threeScene

  const ambient = new THREE.AmbientLight(0xffffff, 0.6)
  addLight(ambient)

  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8)
  dir1.position.set(100, 100, 150)
  addLight(dir1)

  const dir2 = new THREE.DirectionalLight(0xffffff, 0.3)
  dir2.position.set(-100, -50, 50)
  addLight(dir2)

  if (props.showGrid !== false) {
    const grid2 = new THREE.GridHelper(300, 20, 0x333333, 0x111111)
    grid2.position.z = 40
    scene.add(grid2)
  }

  collisionMarkers = new THREE.Group()
  scene.add(collisionMarkers)

  threeScene.controls.target.set(0, 0, 25)

  threeScene.startAnimation(() => {
    fpsFrameCount++
    const now = performance.now()
    if (now - fpsLastTime >= 1000) {
      fps.value = fpsFrameCount
      emit('fps-update', fpsFrameCount)
      fpsFrameCount = 0
      fpsLastTime = now
    }
  })
}

async function loadStockModel(url: string): Promise<void> {
  if (!threeScene) return
  loading.value = true

  try {
    if (stockMesh) {
      threeScene.scene.remove(stockMesh)
      stockMesh.geometry?.dispose()
      stockMesh = null
    }

    const geometry = await loadSTLGeometry(url)
    stockMesh = new THREE.Mesh(geometry, stockMaterial)
    threeScene.scene.add(stockMesh)

    fitCameraToModel(stockMesh)
  } catch (err) {
    console.error('Failed to load stock model:', err)
  } finally {
    loading.value = false
  }
}

async function loadResultModel(url: string): Promise<void> {
  if (!threeScene) return
  loading.value = true

  try {
    if (resultMesh) {
      threeScene.scene.remove(resultMesh)
      resultMesh.geometry?.dispose()
      resultMesh = null
    }

    const geometry = await loadSTLGeometry(url)
    resultMesh = new THREE.Mesh(geometry, resultMaterial)
    threeScene.scene.add(resultMesh)

    if (!stockMesh) fitCameraToModel(resultMesh)

    if (stockMesh) {
      stockMesh.material = stockMaterial.clone()
      ;(stockMesh.material as THREE.MeshPhongMaterial).opacity = 0.35
      stockMesh.material.transparent = true
    }
  } catch (err) {
    console.error('Failed to load result model:', err)
  } finally {
    loading.value = false
  }
}

function loadSTLGeometry(url: string): Promise<THREE.BufferGeometry> {
  return new Promise((resolve, reject) => {
    const loader = new STLLoader()
    loader.load(
      url,
      (geometry) => resolve(geometry),
      (xhr) => {
        if (xhr.lengthComputable) {
          progress.value = Math.round((xhr.loaded / xhr.total) * 100)
        }
      },
      reject,
    )
  })
}

function drawToolpath(segments: ToolpathSegmentData[]): void {
  if (!threeScene) return

  const { scene } = threeScene

  if (toolPathLine) {
    scene.remove(toolPathLine)
    toolPathLine.geometry?.dispose()
    toolPathLine = null
  }
  if (toolPathPoints) {
    scene.remove(toolPathPoints)
    toolPathPoints.geometry?.dispose()
    toolPathPoints = null
  }

  const colors: Record<string, number> = {
    rapid: 0xff5252,
    linear: 0x4caf50,
    arc: 0x448aff,
    dwell: 0xffc107,
  }

  for (const seg of segments) {
    const pointsArr = [
      new THREE.Vector3(...seg.start_point),
      new THREE.Vector3(...seg.end_point),
    ]
    const segGeom = new THREE.BufferGeometry().setFromPoints(pointsArr)
    const segLine = new THREE.Line(
      segGeom,
      new THREE.LineBasicMaterial({
        color: colors[seg.type] || 0xffffff,
        linewidth: 1,
        transparent: true,
        opacity: seg.type === 'rapid' ? 0.5 : 0.9,
      }),
    )
    if (!toolPathLine) {
      toolPathLine = segLine
    } else {
      toolPathLine.add(segLine)
    }
  }

  scene.add(toolPathLine!)

  const allPoints: THREE.Vector3[] = []
  for (const seg of segments) {
    allPoints.push(new THREE.Vector3(...seg.start_point))
  }
  allPoints.push(new THREE.Vector3(...segments[segments.length - 1].end_point))

  const ptsGeom = new THREE.BufferGeometry().setFromPoints(allPoints)
  toolPathPoints = new THREE.Points(
    ptsGeom,
    new THREE.PointsMaterial({ color: 0xffffff, size: 0.5 }),
  )
  scene.add(toolPathPoints)
}

function drawCollisionMarkers(collision: CollisionInfo): void {
  if (!threeScene || !collisionMarkers) return

  while (collisionMarkers.children.length > 0) {
    const child = collisionMarkers.children[0]
    if (child instanceof THREE.Mesh) {
      child.geometry?.dispose()
    }
    collisionMarkers.remove(child)
  }

  const sphereGeom = new THREE.SphereGeometry(1.5, 16, 16)

  for (const pos of collision.collision_positions) {
    const sphere = new THREE.Mesh(sphereGeom, collisionMaterial.clone())
    sphere.position.set(pos[0], pos[1], pos[2])
    sphere.userData = { isCollisionMarker: true, position: pos }

    const ringGeom = new THREE.TorusGeometry(2.0, 0.3, 8, 16)
    const ring = new THREE.Mesh(ringGeom, collisionMaterial.clone())
    ring.position.copy(sphere.position)
    ring.userData = { isCollisionMarker: true, position: pos }

    collisionMarkers.add(sphere)
    collisionMarkers.add(ring)
  }
}

function focusOnCollision(position: [number, number, number]): void {
  if (!threeScene) return

  const { camera, controls } = threeScene
  const target = new THREE.Vector3(...position)

  const startPos = camera.position.clone()
  const endPos = new THREE.Vector3(
    target.x + 30,
    target.y - 30,
    target.z + 30,
  )

  const startTarget = controls.target.clone()
  const duration = 800
  const startTime = performance.now()

  function animate(time: number) {
    const elapsed = time - startTime
    const t = Math.min(elapsed / duration, 1.0)
    const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t

    camera.position.lerpVectors(startPos, endPos, ease)
    controls.target.lerpVectors(startTarget, target, ease)
    controls.update()

    if (t < 1.0) {
      requestAnimationFrame(animate)
    }
  }
  requestAnimationFrame(animate)
}

function updateToolIndicator(segmentIndex: number): void {
  if (!threeScene || !props.toolpathSegments) return

  const { scene } = threeScene

  if (toolIndicator) {
    scene.remove(toolIndicator)
    toolIndicator.geometry?.dispose()
    toolIndicator = null
  }

  const seg = props.toolpathSegments[segmentIndex]
  if (!seg) return

  const geom = new THREE.ConeGeometry(2, 8, 8, 4)
  toolIndicator = new THREE.Mesh(
    geom,
    new THREE.MeshPhongMaterial({ color: 0xffd740, emissive: 0x332200 }),
  )
  const pos = new THREE.Vector3(...seg.end_point)
  toolIndicator.position.copy(pos)
  scene.add(toolIndicator)
}

function fitCameraToModel(mesh: THREE.Mesh): void {
  if (!threeScene) return

  const { camera, controls } = threeScene

  const box = new THREE.Box3().setFromObject(mesh)
  const center = box.getCenter(new THREE.Vector3())
  const size = box.getSize(new THREE.Vector3())
  const maxDim = Math.max(size.x, size.y, size.z)
  const fov = camera.fov * (Math.PI / 180)
  const cameraZ = maxDim / (2 * Math.tan(fov / 2)) * 1.5

  controls.target.copy(center)
  camera.position.set(center.x, center.y - cameraZ * 0.5, center.z + cameraZ)
  controls.update()
}

defineExpose({ focusOnCollision })
</script>

<style lang="scss" scoped>
.simulation-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;

  .viewer-canvas {
    width: 100%;
    height: 100%;
  }

  .viewer-placeholder {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    color: rgba(255, 255, 255, 0.6);
    pointer-events: none;

    p {
      margin: 4px 0;
      font-size: 16px;
    }
    .hint {
      font-size: 13px;
      opacity: 0.7;
    }
  }

  .viewer-overlay {
    position: absolute;
    bottom: 40px;
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 8px;
    background: rgba(0, 0, 0, 0.75);
    padding: 12px 24px;
    border-radius: 8px;

    .loading-text {
      color: #fff;
      font-size: 13px;
    }

    .progress-bar {
      width: 200px;
      height: 4px;
      background: rgba(255, 255, 255, 0.2);
      border-radius: 2px;
      overflow: hidden;

      .progress-fill {
        height: 100%;
        background: linear-gradient(90deg, #4caf50, #8bc34a);
        border-radius: 2px;
        transition: width 0.3s ease;
      }
    }
  }

  .coordinate-axes {
    position: absolute;
    bottom: 12px;
    left: 12px;
    display: flex;
    gap: 8px;

    span {
      width: 20px;
      height: 20px;
      display: flex;
      align-items: center;
      justify-content: center;
      border-radius: 4px;
      font-size: 11px;
      font-weight: 700;
      color: #fff;
    }

    .axis-x { background: #ff5252; }
    .axis-y { background: #4caf50; }
    .axis-z { background: #448aff; }
  }

  .fps-counter {
    position: absolute;
    top: 12px;
    left: 12px;
    background: rgba(0, 0, 0, 0.6);
    color: #8bc34a;
    padding: 4px 10px;
    border-radius: 4px;
    font-size: 12px;
    font-family: monospace;
  }
}
</style>
