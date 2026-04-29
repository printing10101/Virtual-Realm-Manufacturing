<template>
  <div class="three-viewer" ref="viewerContainer">
    <div v-if="!isLoaded" class="loading-overlay">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>{{ loadingText }}</p>
    </div>
    <div class="controls-panel" v-show="isLoaded">
      <el-button-group>
        <el-button :type="wireframeMode ? 'primary' : ''" @click="toggleWireframe">
          {{ wireframeMode ? '线框模式' : '实体模式' }}
        </el-button>
        <el-button @click="toggleGrid">
          {{ showGrid ? '隐藏网格' : '显示网格' }}
        </el-button>
        <el-button @click="resetCamera">重置视角</el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onUnmounted, watch } from 'vue'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { Loading } from '@element-plus/icons-vue'

const props = defineProps<{
  modelUrl?: string
  autoRotate?: boolean
}>()

const viewerContainer = ref<HTMLElement | null>(null)
const isLoaded = ref(false)
const loadingText = ref('正在加载模型...')
const wireframeMode = ref(false)
const showGrid = ref(true)

let scene: THREE.Scene
let camera: THREE.PerspectiveCamera
let renderer: THREE.WebGLRenderer
let controls: OrbitControls
let gridHelper: THREE.GridHelper
let modelMesh: THREE.Object3D | null = null
let animationId: number

onMounted(() => {
  initThreeJS()
  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }
})

onUnmounted(() => {
  if (animationId) {
    cancelAnimationFrame(animationId)
  }
  window.removeEventListener('resize', onWindowResize)
  if (renderer) {
    renderer.dispose()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
  }
})

watch(() => props.modelUrl, (newUrl: string | undefined) => {
  if (newUrl) {
    loadModel(newUrl)
  }
})

function initThreeJS() {
  if (!viewerContainer.value) return

  scene = new THREE.Scene()
  scene.background = new THREE.Color(0xf0f0f0)

  const container = viewerContainer.value
  const width = container.clientWidth || 800
  const height = container.clientHeight || 600

  camera = new THREE.PerspectiveCamera(75, width / height, 0.1, 10000)
  camera.position.set(100, 100, 100)

  renderer = new THREE.WebGLRenderer({ antialias: true })
  renderer.setSize(width, height)
  renderer.setPixelRatio(window.devicePixelRatio)
  container.appendChild(renderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.05
  controls.autoRotate = props.autoRotate || false

  const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
  scene.add(ambientLight)

  const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
  directionalLight.position.set(100, 100, 50)
  scene.add(directionalLight)

  gridHelper = new THREE.GridHelper(200, 20)
  scene.add(gridHelper)

  window.addEventListener('resize', onWindowResize)
  animate()
}

function onWindowResize() {
  if (!viewerContainer.value) return
  const width = viewerContainer.value.clientWidth
  const height = viewerContainer.value.clientHeight
  
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function animate() {
  animationId = requestAnimationFrame(animate)
  controls.update()
  renderer.render(scene, camera)
}

async function loadModel(url: string) {
  isLoaded.value = false
  loadingText.value = '正在加载模型...'

  if (modelMesh) {
    scene.remove(modelMesh)
    modelMesh = null
  }

  try {
    const extension = url.split('.').pop()?.toLowerCase()
    
    if (extension === 'stl') {
      await loadSTL(url)
    } else if (extension === 'obj') {
      await loadOBJ(url)
    } else if (extension === 'gltf' || extension === 'glb') {
      await loadGLTF(url)
    } else {
      throw new Error(`不支持的模型格式: ${extension}`)
    }

    isLoaded.value = true
  } catch (error) {
    loadingText.value = `加载失败: ${(error as Error).message}`
    console.error('模型加载失败:', error)
  }
}

function loadSTL(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const loader = new STLLoader()
    loader.load(
      url,
      (geometry: THREE.BufferGeometry) => {
        geometry.computeVertexNormals()
        const material = new THREE.MeshPhongMaterial({
          color: 0x409EFF,
          specular: 0x111111,
          shininess: 200,
          wireframe: wireframeMode.value
        })
        modelMesh = new THREE.Mesh(geometry, material)
        
        geometry.computeBoundingBox()
        const boundingBox = geometry.boundingBox!
        const center = new THREE.Vector3()
        boundingBox.getCenter(center)
        modelMesh.position.sub(center)
        
        scene.add(modelMesh)
        if (modelMesh) {
          centerCamera(boundingBox)
        }
        resolve()
      },
      undefined,
      (error: unknown) => reject(error)
    )
  })
}

function loadOBJ(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const loader = new OBJLoader()
    loader.load(
      url,
      (object: THREE.Group) => {
        object.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.material = new THREE.MeshPhongMaterial({
              color: 0x409EFF,
              specular: 0x111111,
              shininess: 200,
              wireframe: wireframeMode.value
            })
          }
        })
        modelMesh = object
        scene.add(modelMesh)
        const boundingBox = new THREE.Box3().setFromObject(object)
        if (modelMesh) {
          centerCamera(boundingBox)
        }
        resolve()
      },
      undefined,
      (error: unknown) => reject(error)
    )
  })
}

function loadGLTF(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    const loader = new GLTFLoader()
    loader.load(
      url,
      (gltf: any) => {
        const sceneObj = gltf.scene
        if (!sceneObj) {
          reject(new Error('GLTF 场景对象为空'))
          return
        }
        modelMesh = sceneObj
        scene.add(sceneObj)
        
        const boundingBox = new THREE.Box3().setFromObject(sceneObj)
        centerCamera(boundingBox)
        resolve()
      },
      undefined,
      (error: unknown) => reject(error)
    )
  })
}

function centerCamera(boundingBox: THREE.Box3) {
  const size = new THREE.Vector3()
  boundingBox.getSize(size)
  const maxDim = Math.max(size.x, size.y, size.z)
  const fov = camera.fov * (Math.PI / 180)
  let cameraZ = maxDim / 2 / Math.tan(fov / 2)
  cameraZ *= 1.5
  
  camera.position.set(cameraZ, cameraZ, cameraZ)
  camera.lookAt(0, 0, 0)
  controls.target.set(0, 0, 0)
  controls.update()
}

function toggleWireframe() {
  wireframeMode.value = !wireframeMode.value
  if (modelMesh) {
    modelMesh.traverse((child) => {
      if (child instanceof THREE.Mesh && child.material) {
        child.material.wireframe = wireframeMode.value
      }
    })
  }
}

function toggleGrid() {
  showGrid.value = !showGrid.value
  gridHelper.visible = showGrid.value
}

function resetCamera() {
  camera.position.set(100, 100, 100)
  camera.lookAt(0, 0, 0)
  controls.target.set(0, 0, 0)
  controls.update()
}

defineExpose({
  loadModel,
  toggleWireframe,
  toggleGrid,
  resetCamera
})
</script>

<style scoped lang="scss">
.three-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  min-height: 500px;
  background: #f0f0f0;
  border-radius: 8px;
  overflow: hidden;

  .loading-overlay {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    background: rgba(240, 240, 240, 0.9);
    z-index: 10;

    .loading-icon {
      font-size: 48px;
      animation: rotate 2s linear infinite;
      margin-bottom: 16px;
    }

    p {
      margin: 0;
      color: #606266;
      font-size: 14px;
    }
  }

  .controls-panel {
    position: absolute;
    top: 16px;
    right: 16px;
    z-index: 5;
  }
}

@keyframes rotate {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}
</style>
