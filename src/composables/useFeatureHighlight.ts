/**
 * 特征高亮业务逻辑
 * 封装 AI 关注特征的选中、高亮、多窗口同步、悬停信息等能力
 */

import { ref, computed, type Ref } from 'vue'
import * as THREE from 'three'

/** 特征数据类型 */
export interface FeatureInfo {
  id: string
  name: string
  type: string
  description: string
  /** 特征在模型上的几何信息 */
  geometry: {
    center: [number, number, number]
    boundingBox?: {
      min: [number, number, number]
      max: [number, number, number]
    }
    faceIndices?: number[]
  }
  /** AI 分析附加信息 */
  aiInfo?: {
    importance: number
    reason: string
    category: string
  }
}

/** 高亮配置 */
export interface HighlightConfig {
  /** 高亮颜色 */
  highlightColor: number
  /** 高亮 emissive 颜色 */
  emissiveColor: number
  /** 高亮 emissive 强度 */
  emissiveIntensity: number
  /** 轮廓线颜色 */
  outlineColor: number
  /** 轮廓线宽度 */
  outlineWidth: number
  /** 是否启用脉冲动画 */
  pulseAnimation: boolean
  /** 脉冲动画速度 */
  pulseSpeed: number
}

/** 默认高亮配置 */
const DEFAULT_HIGHLIGHT_CONFIG: HighlightConfig = {
  highlightColor: 0x00ff88,
  emissiveColor: 0x00ff88,
  emissiveIntensity: 0.6,
  outlineColor: 0x00ffaa,
  outlineWidth: 3,
  pulseAnimation: true,
  pulseSpeed: 2.0,
}

/** 悬停信息 */
export interface HoverInfo {
  feature: FeatureInfo
  screenPosition: { x: number; y: number }
  timestamp: number
}

/** 多窗口同步事件名 */
const SYNC_EVENT_NAME = 'feature-highlight-sync'

/** 同步消息类型 */
interface SyncMessage {
  type: 'select' | 'clear' | 'hover'
  featureId: string | null
  source: string
  timestamp: number
}

/**
 * 特征高亮可组合函数
 */
export function useFeatureHighlight(options: {
  scene?: Ref<THREE.Scene | null>
  camera?: Ref<THREE.PerspectiveCamera | null>
  renderer?: Ref<THREE.WebGLRenderer | null>
  modelGroup?: Ref<THREE.Object3D | null>
  featuresRef?: Ref<FeatureInfo[]>
} = {}) {
  // --- 状态 ---
  const selectedFeatureId = ref<string | null>(null)
  const hoveredFeatureId = ref<string | null>(null)
  // 使用外部传入的 ref，或创建内部 ref
  const features = options.featuresRef ?? ref<FeatureInfo[]>([])
  const highlightConfig = ref<HighlightConfig>({ ...DEFAULT_HIGHLIGHT_CONFIG })
  const hoverInfo = ref<HoverInfo | null>(null)
  const syncEnabled = ref(true)

  // 内部引用
  const highlightMeshes = new Map<string, THREE.Object3D[]>()
  const originalMaterials = new Map<string, THREE.Material | THREE.Material[]>()
  let pulsePhase = 0
  let syncChannel: BroadcastChannel | null = null
  const instanceId = `highlight-${Math.random().toString(36).slice(2, 9)}`

  // --- 计算属性 ---
  const selectedFeature = computed(() => {
    if (!selectedFeatureId.value) return null
    return features.value.find(f => f.id === selectedFeatureId.value) ?? null
  })

  const hoveredFeature = computed(() => {
    if (!hoveredFeatureId.value) return null
    return features.value.find(f => f.id === hoveredFeatureId.value) ?? null
  })

  const hasSelection = computed(() => selectedFeatureId.value !== null)

  // --- 初始化同步通道 ---
  function initSyncChannel() {
    if (typeof BroadcastChannel === 'undefined') return
    try {
      syncChannel = new BroadcastChannel(SYNC_EVENT_NAME)
      syncChannel.onmessage = (event: MessageEvent<SyncMessage>) => {
        const msg = event.data
        // 忽略自己发出的消息
        if (msg.source === instanceId) return
        // 忽略延迟超过 50ms 的消息
        if (Date.now() - msg.timestamp > 50) return

        if (msg.type === 'select' && msg.featureId) {
          applyHighlight(msg.featureId, false)
        } else if (msg.type === 'clear') {
          clearHighlight(false)
        }
      }
    } catch {
      syncChannel = null
    }
  }

  function broadcastSync(type: SyncMessage['type'], featureId: string | null) {
    if (!syncEnabled.value || !syncChannel) return
    const msg: SyncMessage = {
      type,
      featureId,
      source: instanceId,
      timestamp: Date.now(),
    }
    try {
      syncChannel.postMessage(msg)
    } catch {
      // BroadcastChannel 不可用时静默失败
    }
  }

  // --- 特征管理 ---
  function setFeatures(newFeatures: FeatureInfo[]) {
    features.value = newFeatures
  }

  // --- 高亮核心逻辑 ---
  function applyHighlight(featureId: string, broadcast = true) {
    const startTime = performance.now()

    // 先清除旧高亮
    removeCurrentHighlight()

    const feature = features.value.find(f => f.id === featureId)
    if (!feature) return

    selectedFeatureId.value = featureId

    // 广播同步消息（即使没有 scene/modelGroup 也要广播）
    if (broadcast) {
      broadcastSync('select', featureId)
    }

    const scene = options.scene?.value
    const modelGroup = options.modelGroup?.value
    if (!scene || !modelGroup) return

    const config = highlightConfig.value

    // 查找模型上与特征关联的 mesh
    const targetMeshes = findFeatureMeshes(modelGroup, feature)

    if (targetMeshes.length === 0) {
      // 如果没有直接关联的 mesh，在特征中心创建高亮标记
      createHighlightMarker(scene, feature, config)
    } else {
      // 对找到的 mesh 应用高亮材质
      applyHighlightToMeshes(targetMeshes, feature.id, config)
    }

    const elapsed = performance.now() - startTime
    if (elapsed > 100) {
      console.warn(`特征高亮响应时间 ${elapsed.toFixed(1)}ms 超过 100ms 目标`)
    }
  }

  function clearHighlight(broadcast = true) {
    removeCurrentHighlight()
    selectedFeatureId.value = null

    if (broadcast) {
      broadcastSync('clear', null)
    }
  }

  function removeCurrentHighlight() {
    const scene = options.scene?.value

    // 恢复原始材质
    const modelGroup = options.modelGroup?.value
    if (modelGroup) {
      originalMaterials.forEach((mat, meshId) => {
        modelGroup.traverse((child) => {
          if ((child as THREE.Mesh & { uuid: string }).uuid === meshId) {
            ;(child as THREE.Mesh).material = mat
          }
        })
      })
    }
    originalMaterials.clear()

    // 移除高亮标记 mesh
    if (scene) {
      highlightMeshes.forEach((meshes) => {
        meshes.forEach((mesh) => {
          scene.remove(mesh)
          if (mesh instanceof THREE.Mesh) {
            mesh.geometry?.dispose()
            if (mesh.material instanceof THREE.Material) {
              mesh.material.dispose()
            }
          }
        })
      })
    }
    highlightMeshes.clear()
  }

  function findFeatureMeshes(modelGroup: THREE.Object3D, feature: FeatureInfo): THREE.Mesh[] {
    const meshes: THREE.Mesh[] = []

    // 通过 face indices 查找
    if (feature.geometry.faceIndices && feature.geometry.faceIndices.length > 0) {
      modelGroup.traverse((child) => {
        if (child instanceof THREE.Mesh && child.geometry) {
          const geo = child.geometry as THREE.BufferGeometry
          const indexAttr = geo.index
          if (indexAttr) {
            const faceSet = new Set(feature.geometry.faceIndices)
            for (let i = 0; i < indexAttr.count; i += 3) {
              if (faceSet.has(i / 3)) {
                meshes.push(child)
                break
              }
            }
          }
        }
      })
    }

    // 通过 bounding box 范围查找
    if (meshes.length === 0 && feature.geometry.boundingBox) {
      const { min, max } = feature.geometry.boundingBox
      const box = new THREE.Box3(
        new THREE.Vector3(min[0], min[1], min[2]),
        new THREE.Vector3(max[0], max[1], max[2]),
      )

      modelGroup.traverse((child) => {
        if (child instanceof THREE.Mesh && child.geometry) {
          const meshBox = new THREE.Box3().setFromObject(child)
          if (box.intersectsBox(meshBox)) {
            meshes.push(child)
          }
        }
      })
    }

    return meshes
  }

  function applyHighlightToMeshes(
    meshes: THREE.Mesh[],
    featureId: string,
    config: HighlightConfig,
  ) {
    const scene = options.scene?.value
    if (!scene) return

    const highlightObjects: THREE.Object3D[] = []

    meshes.forEach((mesh) => {
      // 保存原始材质
      originalMaterials.set(mesh.uuid, mesh.material)

      // 应用高亮材质
      const highlightMat = new THREE.MeshPhongMaterial({
        color: config.highlightColor,
        emissive: config.emissiveColor,
        emissiveIntensity: config.emissiveIntensity,
        transparent: true,
        opacity: 0.85,
        side: THREE.DoubleSide,
      })
      mesh.material = highlightMat

      // 创建轮廓线
      if (mesh.geometry) {
        const edges = new THREE.EdgesGeometry(mesh.geometry, 15)
        const lineMat = new THREE.LineBasicMaterial({
          color: config.outlineColor,
          linewidth: config.outlineWidth,
        })
        const outline = new THREE.LineSegments(edges, lineMat)
        outline.position.copy(mesh.position)
        outline.rotation.copy(mesh.rotation)
        outline.scale.copy(mesh.scale)
        outline.userData = { isHighlightOutline: true, featureId }

        // 将轮廓添加到 mesh 的父节点
        if (mesh.parent) {
          mesh.parent.add(outline)
        } else {
          scene.add(outline)
        }
        highlightObjects.push(outline)
      }
    })

    highlightMeshes.set(featureId, highlightObjects)
  }

  function createHighlightMarker(
    scene: THREE.Scene,
    feature: FeatureInfo,
    config: HighlightConfig,
  ) {
    const center = new THREE.Vector3(...feature.geometry.center)

    // 创建脉冲球体标记
    const sphereGeo = new THREE.SphereGeometry(2, 16, 16)
    const sphereMat = new THREE.MeshPhongMaterial({
      color: config.highlightColor,
      emissive: config.emissiveColor,
      emissiveIntensity: config.emissiveIntensity,
      transparent: true,
      opacity: 0.8,
    })
    const sphere = new THREE.Mesh(sphereGeo, sphereMat)
    sphere.position.copy(center)
    sphere.userData = { isHighlightMarker: true, featureId: feature.id }
    scene.add(sphere)

    // 创建环形指示器
    const ringGeo = new THREE.TorusGeometry(3, 0.3, 8, 32)
    const ringMat = new THREE.MeshBasicMaterial({
      color: config.outlineColor,
      transparent: true,
      opacity: 0.6,
    })
    const ring = new THREE.Mesh(ringGeo, ringMat)
    ring.position.copy(center)
    ring.userData = { isHighlightMarker: true, featureId: feature.id }
    scene.add(ring)

    highlightMeshes.set(feature.id, [sphere, ring])
  }

  // --- 悬停处理 ---
  function handleHover(featureId: string | null, screenX?: number, screenY?: number) {
    if (featureId === hoveredFeatureId.value) return

    hoveredFeatureId.value = featureId

    if (!featureId) {
      hoverInfo.value = null
      return
    }

    const feature = features.value.find(f => f.id === featureId)
    if (!feature) {
      hoverInfo.value = null
      return
    }

    hoverInfo.value = {
      feature,
      screenPosition: { x: screenX ?? 0, y: screenY ?? 0 },
      timestamp: Date.now(),
    }
  }

  // --- 脉冲动画更新（在渲染循环中调用） ---
  function updatePulseAnimation(deltaTime: number) {
    if (!highlightConfig.value.pulseAnimation) return
    if (highlightMeshes.size === 0) return

    pulsePhase += deltaTime * highlightConfig.value.pulseSpeed
    const pulseFactor = 0.8 + 0.2 * Math.sin(pulsePhase)

    highlightMeshes.forEach((meshes) => {
      meshes.forEach((obj) => {
        if (obj instanceof THREE.Mesh && obj.material instanceof THREE.MeshPhongMaterial) {
          obj.material.emissiveIntensity = highlightConfig.value.emissiveIntensity * pulseFactor
        }
        if (obj.userData?.isHighlightMarker) {
          const baseScale = obj.userData.featureId ? 1.0 : 1.0
          const s = baseScale * (0.95 + 0.05 * Math.sin(pulsePhase))
          obj.scale.set(s, s, s)
        }
      })
    })
  }

  // --- Raycasting 拾取 ---
  function pickFeatureAtScreen(
    clientX: number,
    clientY: number,
  ): FeatureInfo | null {
    const camera = options.camera?.value
    const renderer = options.renderer?.value
    const modelGroup = options.modelGroup?.value
    if (!camera || !renderer || !modelGroup || features.value.length === 0) return null

    const rect = renderer.domElement.getBoundingClientRect()
    const mouse = new THREE.Vector2(
      ((clientX - rect.left) / rect.width) * 2 - 1,
      -((clientY - rect.top) / rect.height) * 2 + 1,
    )

    const raycaster = new THREE.Raycaster()
    raycaster.setFromCamera(mouse, camera)

    const intersects = raycaster.intersectObject(modelGroup, true)
    if (intersects.length === 0) return null

    // 找到最近的交叉点，然后匹配到最近的特征
    const hitPoint = intersects[0].point
    let closestFeature: FeatureInfo | null = null
    let closestDist = Infinity

    for (const feature of features.value) {
      const center = new THREE.Vector3(...feature.geometry.center)
      const dist = hitPoint.distanceTo(center)

      // 如果有 bounding box，检查是否在范围内
      if (feature.geometry.boundingBox) {
        const { min, max } = feature.geometry.boundingBox
        if (
          hitPoint.x >= min[0] && hitPoint.x <= max[0] &&
          hitPoint.y >= min[1] && hitPoint.y <= max[1] &&
          hitPoint.z >= min[2] && hitPoint.z <= max[2]
        ) {
          return feature
        }
      }

      if (dist < closestDist) {
        closestDist = dist
        closestFeature = feature
      }
    }

    // 距离阈值：只有距离特征中心足够近才算选中
    const threshold = 20
    return closestDist <= threshold ? closestFeature : null
  }

  // --- 聚焦到特征 ---
  function focusOnFeature(featureId: string) {
    const feature = features.value.find(f => f.id === featureId)
    const camera = options.camera?.value
    const controls = options.scene?.value // 需要外部提供 controls
    if (!feature || !camera) return

    const center = new THREE.Vector3(...feature.geometry.center)
    const offset = new THREE.Vector3(30, -20, 30)
    const targetPos = center.clone().add(offset)

    const startPos = camera.position.clone()
    const duration = 600
    const startTime = performance.now()

    function animate() {
      const elapsed = performance.now() - startTime
      const t = Math.min(elapsed / duration, 1.0)
      const ease = t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t

      camera.position.lerpVectors(startPos, targetPos, ease)
      camera.lookAt(center)

      if (t < 1.0) {
        requestAnimationFrame(animate)
      }
    }
    requestAnimationFrame(animate)
  }

  // --- 配置更新 ---
  function updateHighlightConfig(partial: Partial<HighlightConfig>) {
    highlightConfig.value = { ...highlightConfig.value, ...partial }
  }

  // --- 清理 ---
  function cleanup() {
    removeCurrentHighlight()
    if (syncChannel) {
      syncChannel.close()
      syncChannel = null
    }
    hoveredFeatureId.value = null
    selectedFeatureId.value = null
    hoverInfo.value = null
  }

  // 自动初始化同步通道
  initSyncChannel()

  return {
    // 状态
    selectedFeatureId,
    hoveredFeatureId,
    features,
    highlightConfig,
    hoverInfo,
    syncEnabled,

    // 计算属性
    selectedFeature,
    hoveredFeature,
    hasSelection,

    // 方法
    setFeatures,
    applyHighlight,
    clearHighlight,
    handleHover,
    updatePulseAnimation,
    pickFeatureAtScreen,
    focusOnFeature,
    updateHighlightConfig,
    cleanup,
  }
}
