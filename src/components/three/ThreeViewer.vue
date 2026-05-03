<template>
  <div class="three-viewer" ref="viewerContainer">
    <div v-if="!isLoaded && !hasError" class="loading-overlay">
      <el-icon class="loading-icon"><Loading /></el-icon>
      <p>{{ loadingText }}</p>
    </div>
    <div v-if="hasError" class="error-overlay">
      <el-icon class="error-icon"><CircleClose /></el-icon>
      <p>{{ errorText }}</p>
      <el-button type="primary" size="small" @click="retryLoad">{{ t('common.retry') }}</el-button>
    </div>
    <div class="controls-panel" v-show="isLoaded">
      <el-button-group>
        <el-button :type="wireframeMode ? 'primary' : ''" @click="toggleWireframe">
          {{ wireframeMode ? t('viewer.wireframeMode') : t('viewer.solidMode') }}
        </el-button>
        <el-button @click="toggleGrid">
          {{ showGrid ? t('viewer.hideGrid') : t('viewer.showGrid') }}
        </el-button>
        <el-button @click="resetCamera">{{ t('viewer.resetCamera') }}</el-button>
      </el-button-group>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, nextTick } from 'vue'
import { useI18n } from 'vue-i18n'
import * as THREE from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { STLLoader } from 'three/examples/jsm/loaders/STLLoader.js'
import { OBJLoader } from 'three/examples/jsm/loaders/OBJLoader.js'
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js'
import { Loading, CircleClose } from '@element-plus/icons-vue'
import { THREE_VIEWER_CONFIG } from '@/constants'

const props = withDefaults(defineProps<{
  modelUrl?: string
  autoRotate?: boolean
}>(), {
  autoRotate: false,
})

const { t } = useI18n()

const viewerContainer = ref<HTMLElement | null>(null)
const isLoaded = ref(false)
const hasError = ref(false)
const loadingText = ref('正在加载模型...')
const errorText = ref('')
const wireframeMode = ref(false)
const showGrid = ref(true)

let scene: THREE.Scene | null = null
let camera: THREE.PerspectiveCamera | null = null
let renderer: THREE.WebGLRenderer | null = null
let controls: OrbitControls | null = null
let gridHelper: THREE.GridHelper | null = null
let modelMesh: THREE.Object3D | null = null
let animationId: number | null = null
let lastModelUrl: string | null = null

onMounted(async () => {
  await nextTick()
  initThreeJS()
  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }
})

onBeforeUnmount(() => {
  cleanup()
})

watch(() => props.modelUrl, async (newUrl: string | undefined) => {
  if (newUrl && newUrl !== lastModelUrl) {
    try {
      await loadModel(newUrl)
    } catch {
      hasError.value = true
    }
  }
})

function cleanup() {
  if (animationId) {
    cancelAnimationFrame(animationId)
    animationId = null
  }
  
  if (modelMesh) {
    disposeObject(modelMesh)
    modelMesh = null
  }
  
  if (gridHelper) {
    gridHelper.geometry?.dispose()
    if (gridHelper.material) {
      if (Array.isArray(gridHelper.material)) {
        gridHelper.material.forEach(mat => mat.dispose())
      } else {
        gridHelper.material.dispose()
      }
    }
    gridHelper = null
  }
  
  if (scene) {
    scene.clear()
    scene = null
  }
  
  if (controls) {
    controls.dispose()
    controls = null
  }
  
  if (renderer) {
    renderer.dispose()
    renderer.forceContextLoss()
    if (renderer.domElement.parentNode) {
      renderer.domElement.parentNode.removeChild(renderer.domElement)
    }
    renderer = null
  }
  
  camera = null
  
  window.removeEventListener('resize', onWindowResize)
}

function disposeObject(obj: THREE.Object3D) {
  obj.traverse((child) => {
    if (child instanceof THREE.Mesh) {
      child.geometry.dispose()
      if (Array.isArray(child.material)) {
        child.material.forEach(mat => {
          disposeTextures(mat)
          mat.dispose()
        })
      } else if (child.material) {
        disposeTextures(child.material)
        child.material.dispose()
      }
    }
  })
  if (obj.parent) {
    obj.parent.remove(obj)
  }
}

function disposeTextures(material: THREE.Material) {
  Object.values(material).forEach((value) => {
    if (value instanceof THREE.Texture) {
      value.dispose()
    } else if (value && typeof value === 'object' && 'isTexture' in value && value.dispose) {
      (value as THREE.Texture).dispose()
    }
  })
}

function initThreeJS() {
  if (!viewerContainer.value) return

  if (scene || camera || renderer) {
    cleanup()
  }

  try {
    scene = new THREE.Scene()
    scene.background = new THREE.Color(THREE_VIEWER_CONFIG.SCENE_BACKGROUND_COLOR)

    const container = viewerContainer.value
    const width = container.clientWidth || 800
    const height = container.clientHeight || 600

    camera = new THREE.PerspectiveCamera(
      THREE_VIEWER_CONFIG.CAMERA_FOV,
      width / height,
      THREE_VIEWER_CONFIG.CAMERA_NEAR,
      THREE_VIEWER_CONFIG.CAMERA_FAR
    )
    camera.position.set(
      THREE_VIEWER_CONFIG.CAMERA_POSITION.x,
      THREE_VIEWER_CONFIG.CAMERA_POSITION.y,
      THREE_VIEWER_CONFIG.CAMERA_POSITION.z
    )

    renderer = new THREE.WebGLRenderer({ antialias: true })
    if (!renderer.capabilities.isWebGL2) {
      console.warn('WebGL 2.0 不可用，降级到 WebGL 1.0')
    }
    renderer.setSize(width, height)
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, THREE_VIEWER_CONFIG.MAX_PIXEL_RATIO))
    container.appendChild(renderer.domElement)

    controls = new OrbitControls(camera, renderer.domElement)
    controls.enableDamping = true
    controls.dampingFactor = THREE_VIEWER_CONFIG.DAMPING_FACTOR
    controls.autoRotate = props.autoRotate

    const ambientLight = new THREE.AmbientLight(0xffffff, 0.6)
    scene.add(ambientLight)

    const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8)
    directionalLight.position.set(100, 100, 50)
    scene.add(directionalLight)

    gridHelper = new THREE.GridHelper(THREE_VIEWER_CONFIG.GRID_SIZE, THREE_VIEWER_CONFIG.GRID_DIVISIONS)
    scene.add(gridHelper)

    window.addEventListener('resize', onWindowResize)
    animate()
  } catch (error) {
    hasError.value = true
    errorText.value = `3D 查看器初始化失败: ${error instanceof Error ? error.message : String(error)}`
    console.error('Three.js 初始化失败:', error)
  }
}

function onWindowResize() {
  if (!viewerContainer.value || !camera || !renderer) return
  const width = viewerContainer.value.clientWidth
  const height = viewerContainer.value.clientHeight
  
  if (width === 0 || height === 0) return
  
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
}

function animate() {
  animationId = requestAnimationFrame(animate)
  if (controls) controls.update()
  if (renderer && scene && camera) renderer.render(scene, camera)
}

async function loadModel(url: string) {
  if (!scene || !renderer) {
    await nextTick()
    if (!scene) initThreeJS()
    if (!scene) return
  }

  lastModelUrl = url
  isLoaded.value = false
  hasError.value = false
  loadingText.value = '正在加载模型...'

  if (modelMesh && scene) {
    disposeObject(modelMesh)
    modelMesh = null
  }

  try {
    const extension = getExtension(url)
    
    if (!extension || !isValidModelExtension(extension)) {
      throw new Error(`不支持的模型格式: ${extension || '未知'}`)
    }
    
    switch (extension) {
      case 'stl':
        await loadSTL(url)
        break
      case 'obj':
        await loadOBJ(url)
        break
      case 'gltf':
      case 'glb':
        await loadGLTF(url)
        break
    }

    isLoaded.value = true
  } catch (error) {
    hasError.value = true
    errorText.value = `加载失败: ${(error as Error).message}`
    console.error('模型加载失败:', error)
  }
}

function getExtension(url: string): string | null {
  const parts = url.split('?')[0].split('.')
  return parts.length > 1 ? parts.pop()?.toLowerCase() ?? null : null
}

function isValidModelExtension(ext: string): boolean {
  return THREE_VIEWER_CONFIG.SUPPORTED_FORMATS.includes(ext as typeof THREE_VIEWER_CONFIG.SUPPORTED_FORMATS[number])
}

function loadSTL(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!scene) { reject(new Error('场景未初始化')); return }
    
    const loader = new STLLoader()
    loader.load(
      url,
      (geometry: THREE.BufferGeometry) => {
        geometry.computeVertexNormals()
        const material = new THREE.MeshPhongMaterial({
          color: THREE_VIEWER_CONFIG.MODEL_COLOR,
          specular: THREE_VIEWER_CONFIG.MODEL_SPECULAR,
          shininess: THREE_VIEWER_CONFIG.MODEL_SHININESS,
          wireframe: wireframeMode.value
        })
        modelMesh = new THREE.Mesh(geometry, material)
        
        geometry.computeBoundingBox()
        const boundingBox = geometry.boundingBox
        if (boundingBox) {
          const center = new THREE.Vector3()
          boundingBox.getCenter(center)
          modelMesh.position.sub(center)
        }
        
        if (scene) {
          scene.add(modelMesh)
        }
        centerCamera()
        resolve()
      },
      undefined,
      (error: unknown) => reject(new Error(`STL加载失败: ${(error as Error).message}`))
    )
  })
}

function loadOBJ(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!scene) { reject(new Error('场景未初始化')); return }
    
    const loader = new OBJLoader()
    loader.load(
      url,
      (object: THREE.Group) => {
        object.traverse((child) => {
          if (child instanceof THREE.Mesh) {
            child.material = new THREE.MeshPhongMaterial({
              color: THREE_VIEWER_CONFIG.MODEL_COLOR,
              specular: THREE_VIEWER_CONFIG.MODEL_SPECULAR,
              shininess: THREE_VIEWER_CONFIG.MODEL_SHININESS,
              wireframe: wireframeMode.value
            })
          }
        })
        modelMesh = object
        if (modelMesh && scene) {
          scene.add(modelMesh)
          centerCamera()
        }
        resolve()
      },
      undefined,
      (error: unknown) => reject(new Error(`OBJ加载失败: ${(error as Error).message}`))
    )
  })
}

function loadGLTF(url: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (!scene) { reject(new Error('场景未初始化')); return }
    
    const loader = new GLTFLoader()
    loader.load(
      url,
      (gltf: { scene: THREE.Group }) => {
        const sceneObj = gltf.scene
        if (!sceneObj) {
          reject(new Error('GLTF 场景对象为空'))
          return
        }
        modelMesh = sceneObj
        if (modelMesh && scene) {
          scene.add(sceneObj)
          centerCamera()
        }
        resolve()
      },
      undefined,
      (error: unknown) => reject(new Error(`GLTF加载失败: ${(error as Error).message}`))
    )
  })
}

function centerCamera() {
  if (!camera || !controls || !modelMesh) return
  
  const boundingBox = new THREE.Box3().setFromObject(modelMesh)
  const size = new THREE.Vector3()
  boundingBox.getSize(size)
  
  const maxDim = Math.max(size.x, size.y, size.z, 1)
  const fov = camera.fov * (Math.PI / 180)
  const cameraZ = (maxDim / 2 / Math.tan(fov / 2)) * THREE_VIEWER_CONFIG.CAMERA_DISTANCE_FACTOR
  
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
        const mat = child.material as THREE.MeshPhongMaterial
        if (mat.wireframe !== undefined) {
          mat.wireframe = wireframeMode.value
          mat.needsUpdate = true
        }
      }
    })
  }
}

function toggleGrid() {
  showGrid.value = !showGrid.value
  if (gridHelper) gridHelper.visible = showGrid.value
}

function resetCamera() {
  if (!camera || !controls) return
  camera.position.set(
    THREE_VIEWER_CONFIG.CAMERA_POSITION.x,
    THREE_VIEWER_CONFIG.CAMERA_POSITION.y,
    THREE_VIEWER_CONFIG.CAMERA_POSITION.z
  )
  camera.lookAt(0, 0, 0)
  controls.target.set(0, 0, 0)
  controls.update()
}

function retryLoad() {
  hasError.value = false
  errorText.value = ''
  cleanup()
  if (!scene || !renderer) {
    initThreeJS()
  }
  if (lastModelUrl) {
    loadModel(lastModelUrl)
  }
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
  height: 600px;
  min-height: 500px;
  background: #f0f0f0;
  border-radius: 8px;
  overflow: hidden;

  .loading-overlay,
  .error-overlay {
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

    .loading-icon,
    .error-icon {
      font-size: 48px;
      margin-bottom: 16px;
    }

    .loading-icon {
      animation: rotate 2s linear infinite;
    }

    .error-icon {
      color: #f56c6c;
    }

    p {
      margin: 0 0 16px;
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
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}
</style>
