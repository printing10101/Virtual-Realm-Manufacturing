<template>
  <div class="toolpath-canvas" ref="canvasRef" @contextmenu.prevent>
    <div v-if="!initialized" class="canvas-placeholder">
      <p>3D 刀路编辑场景</p>
      <p class="hint">请加载刀路数据以开始编辑</p>
    </div>

    <div class="fps-counter" v-if="fps > 0">FPS: {{ fps }}</div>

    <div class="coordinate-axes">
      <span class="axis-x">X</span>
      <span class="axis-y">Y</span>
      <span class="axis-z">Z</span>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import type { EditableToolpathSegment } from './types/editor'
import {
  useToolpathInteraction,
  createSegmentLine,
  getSegmentColor,
} from './composables/useToolpathInteraction'

const props = defineProps<{
  segments: EditableToolpathSegment[]
  hoveredSegmentId: string | null
}>()

const emit = defineEmits<{
  'hover-change': [segmentId: string | null]
  'segment-click': [segmentId: string]
  'context-menu': [x: number, y: number, segmentId: string]
}>()

const canvasRef = ref<HTMLElement>()
const initialized = ref(false)
const fps = ref(0)

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let animationId: number | null = null

const cameraRef = ref<THREE.PerspectiveCamera | null>(null)
const segmentLines = ref<Map<string, THREE.Line>>(new Map())
let frameCount = 0
let fpsTime = performance.now()

const { onMouseMove, onContextMenuEvent, onClick, dispose: disposeInteraction } =
  useToolpathInteraction(
    canvasRef,
    cameraRef,
    segmentLines,
    computed(() => props.segments),
    (id) => emit('hover-change', id),
    (x, y, id) => emit('context-menu', x, y, id),
    (id) => emit('segment-click', id),
  )

onMounted(() => {
  initScene()
  initialized.value = true
})

onBeforeUnmount(() => {
  cleanup()
})

watch(
  () => props.segments,
  () => {
    redrawSegments()
  },
  { deep: true },
)

function initScene() {
  if (!canvasRef.value) return

  const w = canvasRef.value.clientWidth
  const h = canvasRef.value.clientHeight

  scene = new THREE.Scene()
  scene.background = new THREE.Color('#1a1a2e')

  camera = new THREE.PerspectiveCamera(50, w / h, 0.1, 10000)
  camera.position.set(200, -200, 150)
  camera.lookAt(0, 0, 30)
  cameraRef.value = camera

  renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false })
  renderer.setSize(w, h)
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2))

  canvasRef.value.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.target.set(0, 0, 25)

  const ambient = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambient)
  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8)
  dir1.position.set(100, 100, 150)
  scene.add(dir1)
  const dir2 = new THREE.DirectionalLight(0xffffff, 0.3)
  dir2.position.set(-100, -50, 50)
  scene.add(dir2)

  const grid = new THREE.GridHelper(300, 20, 0x444444, 0x222222)
  scene.add(grid)

  renderer.domElement.addEventListener('mousemove', onMouseMove)
  renderer.domElement.addEventListener('contextmenu', onContextMenuEvent)
  renderer.domElement.addEventListener('click', onClick)

  const resizeObserver = new ResizeObserver(() => {
    if (!canvasRef.value || !camera || !renderer) return
    const nw = canvasRef.value.clientWidth
    const nh = canvasRef.value.clientHeight
    camera.aspect = nw / nh
    camera.updateProjectionMatrix()
    renderer.setSize(nw, nh)
  })
  resizeObserver.observe(canvasRef.value)

  startAnimation()
}

function startAnimation() {
  const animate = () => {
    animationId = requestAnimationFrame(animate)
    if (controls) controls.update()
    if (renderer && scene && camera) {
      renderer.render(scene, camera)
    }
    frameCount++
    const now = performance.now()
    if (now - fpsTime >= 1000) {
      fps.value = frameCount
      frameCount = 0
      fpsTime = now
    }
  }
  animate()
}

function redrawSegments() {
  if (!scene) return

  segmentLines.value.forEach((line) => {
    scene!.remove(line)
    line.geometry?.dispose()
    ;(line.material as THREE.Material)?.dispose()
  })
  segmentLines.value.clear()

  for (const seg of props.segments) {
    if (seg.isDeleted) continue

    const color = getSegmentColor(seg.type)
    const line = createSegmentLine(seg, color)
    scene.add(line)
    segmentLines.value.set(seg.id, line)
  }
}

function cleanup() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  if (renderer) {
    renderer.domElement.removeEventListener('mousemove', onMouseMove)
    renderer.domElement.removeEventListener('contextmenu', onContextMenuEvent)
    renderer.domElement.removeEventListener('click', onClick)
  }
  disposeInteraction()
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
  scene = null
  camera = null
  cameraRef.value = null
}
</script>

<style lang="scss" scoped>
.toolpath-canvas {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  cursor: crosshair;

  .canvas-placeholder {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    text-align: center;
    color: rgba(255, 255, 255, 0.5);
    p { margin: 4px 0; font-size: 16px; }
    .hint { font-size: 13px; opacity: 0.7; }
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

  .coordinate-axes {
    position: absolute;
    bottom: 12px;
    left: 12px;
    display: flex;
    gap: 8px;
    span {
      width: 20px; height: 20px;
      display: flex; align-items: center; justify-content: center;
      border-radius: 4px; font-size: 11px; font-weight: 700; color: #fff;
    }
    .axis-x { background: #ff5252; }
    .axis-y { background: #4caf50; }
    .axis-z { background: #448aff; }
  }
}
</style>
