<template>
  <div
    ref="containerRef"
    class="highlight-viewer"
    @mousemove="onMouseMove"
    @click="onClick"
  >
    <!-- 3D 场景容器 -->
    <div
      ref="canvasContainerRef"
      class="canvas-container"
    />

    <!-- 悬停信息提示框 -->
    <div
      v-if="hoverInfo && showTooltip"
      class="hover-tooltip"
      :style="{
        left: hoverInfo.screenPosition.x + 15 + 'px',
        top: hoverInfo.screenPosition.y + 15 + 'px',
      }"
    >
      <div class="tooltip-header">
        <span class="feature-name">{{ hoverInfo.feature.name }}</span>
        <span class="feature-type">{{ hoverInfo.feature.type }}</span>
      </div>
      <div class="tooltip-content">
        <div class="tooltip-row">
          <span class="label">{{ t('highlightViewer.labelDescription') }}:</span>
          <span class="value">{{ hoverInfo.feature.description }}</span>
        </div>
        <div
          v-if="hoverInfo.feature.aiInfo"
          class="tooltip-row"
        >
          <span class="label">{{ t('highlightViewer.labelAiImportance') }}:</span>
          <span class="value importance">{{ hoverInfo.feature.aiInfo.importance.toFixed(2) }}</span>
        </div>
        <div
          v-if="hoverInfo.feature.aiInfo?.reason"
          class="tooltip-row"
        >
          <span class="label">{{ t('highlightViewer.labelReason') }}:</span>
          <span class="value">{{ hoverInfo.feature.aiInfo.reason }}</span>
        </div>
        <div
          v-if="hoverInfo.feature.aiInfo?.category"
          class="tooltip-row"
        >
          <span class="label">{{ t('highlightViewer.labelCategory') }}:</span>
          <span class="value category">{{ hoverInfo.feature.aiInfo.category }}</span>
        </div>
      </div>
    </div>

    <!-- 特征列表面板 -->
    <div
      v-if="composableFeatures.length > 0 && showFeatureList"
      class="feature-list-panel"
    >
      <div class="panel-header">
        <h4>{{ t('highlightViewer.aiFeaturesTitle') }}</h4>
        <span class="feature-count">{{ composableFeatures.length }}</span>
      </div>
      <div class="feature-list">
        <div
          v-for="feature in composableFeatures"
          :key="feature.id"
          class="feature-item"
          :class="{
            selected: selectedFeatureId === feature.id,
            hovered: hoveredFeatureId === feature.id,
          }"
          @click.stop="selectFeature(feature.id)"
          @mouseenter="handleHover(feature.id)"
          @mouseleave="handleHover(null)"
        >
          <div class="feature-info">
            <div class="feature-name">
              {{ feature.name }}
            </div>
            <div class="feature-type">
              {{ feature.type }}
            </div>
          </div>
          <div
            v-if="feature.aiInfo"
            class="feature-importance"
            :style="{
              '--importance': feature.aiInfo.importance,
            }"
          >
            {{ (feature.aiInfo.importance * 100).toFixed(0) }}%
          </div>
        </div>
      </div>
    </div>

    <!-- 控制面板 -->
    <div class="control-panel">
      <div class="control-group">
        <label class="control-label">
          <input
            v-model="showTooltip"
            type="checkbox"
          >
          {{ t('highlightViewer.showTooltip') }}
        </label>
      </div>
      <div class="control-group">
        <label class="control-label">
          <input
            v-model="showFeatureList"
            type="checkbox"
          >
          {{ t('highlightViewer.showFeatureList') }}
        </label>
      </div>
      <div class="control-group">
        <label class="control-label">
          <input
            v-model="syncEnabled"
            type="checkbox"
          >
          {{ t('highlightViewer.syncEnabled') }}
        </label>
      </div>
      <div
        v-if="hasSelection"
        class="control-group"
      >
        <button
          class="clear-button"
          @click="clearSelection"
        >
          {{ t('highlightViewer.clearSelection') }}
        </button>
      </div>
    </div>

    <!-- 选中状态指示 -->
    <div
      v-if="selectedFeature"
      class="selection-indicator"
    >
      <div class="indicator-label">
        {{ t('highlightViewer.selected') }}: {{ selectedFeature.name }}
      </div>
      <div
        v-if="selectedFeature.aiInfo"
        class="indicator-details"
      >
        <span>{{ t('highlightViewer.importance') }}: {{ (selectedFeature.aiInfo.importance * 100).toFixed(0) }}%</span>
        <span v-if="selectedFeature.aiInfo.category"> | {{ selectedFeature.aiInfo.category }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, watch, computed } from 'vue'
import * as THREE from 'three'
import { useThreeScene } from '@/composables/useThreeScene'
import { useFeatureHighlight, type FeatureInfo } from '@/composables/useFeatureHighlight'
import { useI18n } from 'vue-i18n'

const props = defineProps<{
  modelUrl?: string
  features?: FeatureInfo[]
  backgroundColor?: string
  showGrid?: boolean
  initialShowTooltip?: boolean
  initialShowFeatureList?: boolean
  initialSyncEnabled?: boolean
}>()

const emit = defineEmits<{
  'feature-select': [feature: FeatureInfo]
  'feature-hover': [feature: FeatureInfo | null]
  'feature-clear': []
}>()

const containerRef = ref<HTMLElement>()
const canvasContainerRef = ref<HTMLElement>()
const { t } = useI18n()
const showTooltip = ref(props.initialShowTooltip ?? true)
const showFeatureList = ref(props.initialShowFeatureList ?? true)

let threeScene: ReturnType<typeof useThreeScene> | null = null
let modelGroup: THREE.Object3D | null = null
let lastFrameTime = performance.now()

// 创建组件级别的 features ref，确保响应性
// 直接使用 props.features 初始化，避免 watcher 时序问题
const localFeatures = ref<FeatureInfo[]>(props.features ?? [])

// 初始化特征高亮 composable，传入本地 ref
const {
  selectedFeatureId,
  hoveredFeatureId,
  features: composableFeatures,
  hoverInfo,
  syncEnabled,
  selectedFeature,
  hoveredFeature,
  hasSelection,
  setFeatures,
  applyHighlight,
  clearHighlight,
  handleHover,
  updatePulseAnimation,
  pickFeatureAtScreen,
  cleanup,
} = useFeatureHighlight({ featuresRef: localFeatures })

// 初始化同步设置
syncEnabled.value = props.initialSyncEnabled ?? true

// 监听 props.features 变化，同步到本地 ref
watch(
  () => props.features,
  (newFeatures) => {
    if (newFeatures) {
      localFeatures.value = newFeatures
    }
  },
  { deep: true }
)

onMounted(() => {
  initScene()
})

function initScene() {
  if (!canvasContainerRef.value) return

  threeScene = useThreeScene({
    container: canvasContainerRef.value,
    backgroundColor: props.backgroundColor ?? '#1a1a2e',
    fov: 60,
    cameraPosition: [0, 50, 100],
    enableDamping: true,
    dampingFactor: 0.05,
    showGrid: props.showGrid ?? true,
  })

  const { scene, addLight, startAnimation } = threeScene

  // 添加光源
  const ambient = new THREE.AmbientLight(0xffffff, 0.6)
  addLight(ambient)

  const dir1 = new THREE.DirectionalLight(0xffffff, 0.8)
  dir1.position.set(10, 10, 10)
  addLight(dir1)

  const dir2 = new THREE.DirectionalLight(0xffffff, 0.4)
  dir2.position.set(-10, 5, -10)
  addLight(dir2)

  // 创建模型组
  modelGroup = new THREE.Group()
  modelGroup.name = 'model-group'
  scene.add(modelGroup)

  // 加载模型（如果有）
  if (props.modelUrl) {
    loadModel(props.modelUrl)
  }

  // 启动动画循环
  startAnimation(() => {
    const now = performance.now()
    const deltaTime = (now - lastFrameTime) / 1000
    lastFrameTime = now

    // 更新脉冲动画
    updatePulseAnimation(deltaTime)
  })
}

async function loadModel(url: string) {
  if (!threeScene || !modelGroup) return

  try {
    // 清空现有模型
    while (modelGroup.children.length > 0) {
      modelGroup.remove(modelGroup.children[0])
    }

    // 根据文件扩展名选择加载器
    const lowerUrl = url.toLowerCase()
    let loadedModel: THREE.Object3D | null = null

    if (lowerUrl.endsWith('.gltf') || lowerUrl.endsWith('.glb')) {
      const { GLTFLoader } = await import('three/examples/jsm/loaders/GLTFLoader.js')
      const loader = new GLTFLoader()
      loadedModel = await new Promise((resolve, reject) => {
        loader.load(
          url,
          (gltf) => resolve(gltf.scene),
          undefined,
          reject
        )
      })
    } else if (lowerUrl.endsWith('.obj')) {
      const { OBJLoader } = await import('three/examples/jsm/loaders/OBJLoader.js')
      const loader = new OBJLoader()
      loadedModel = await new Promise((resolve, reject) => {
        loader.load(
          url,
          (obj) => resolve(obj),
          undefined,
          reject
        )
      })
    } else {
      // 不支持的模型格式，静默忽略
      return
    }

    if (loadedModel) {
      modelGroup.add(loadedModel)
      // 居中相机
      threeScene.camera.lookAt(modelGroup.position)
    }
  } catch {
    // 模型加载失败，静默处理
  }
}

function onMouseMove(event: MouseEvent) {
  if (!threeScene || !threeScene.renderer || !threeScene.camera) return

  const rect = threeScene.renderer.domElement.getBoundingClientRect()
  const x = event.clientX - rect.left
  const y = event.clientY - rect.top

  // 使用 raycasting 检测悬停的特征
  const feature = pickFeatureAtScreen(event.clientX, event.clientY)
  if (feature) {
    handleHover(feature.id, event.clientX, event.clientY)
    emit('feature-hover', feature)
  } else {
    handleHover(null)
    emit('feature-hover', null)
  }
}

function onClick(event: MouseEvent) {
  if (!threeScene || !threeScene.renderer || !threeScene.camera) return

  const feature = pickFeatureAtScreen(event.clientX, event.clientY)
  if (feature) {
    selectFeature(feature.id)
  } else {
    clearSelection()
  }
}

function selectFeature(featureId: string) {
  if (!threeScene || !modelGroup) return

  applyHighlight(featureId)
  const feature = composableFeatures.value.find(f => f.id === featureId)
  if (feature) {
    emit('feature-select', feature)
  }
}

function clearSelection() {
  clearHighlight()
  emit('feature-clear')
}

// 暴露方法给父组件
defineExpose({
  selectFeature,
  clearSelection,
  setFeatures,
})
</script>

<style lang="scss" scoped>
.highlight-viewer {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
  background: #1a1a2e;

  .canvas-container {
    width: 100%;
    height: 100%;
  }

  .hover-tooltip {
    position: absolute;
    z-index: 100;
    background: rgba(0, 0, 0, 0.9);
    border: 1px solid rgba(0, 255, 136, 0.5);
    border-radius: 6px;
    padding: 10px;
    min-width: 200px;
    max-width: 300px;
    color: #fff;
    font-size: 12px;
    pointer-events: none;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);

    .tooltip-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 8px;
      padding-bottom: 6px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.2);

      .feature-name {
        font-weight: 600;
        font-size: 13px;
        color: #00ff88;
      }

      .feature-type {
        font-size: 11px;
        color: rgba(255, 255, 255, 0.6);
        background: rgba(255, 255, 255, 0.1);
        padding: 2px 6px;
        border-radius: 3px;
      }
    }

    .tooltip-content {
      .tooltip-row {
        display: flex;
        justify-content: space-between;
        align-items: flex-start;
        margin-bottom: 4px;

        &:last-child {
          margin-bottom: 0;
        }

        .label {
          color: rgba(255, 255, 255, 0.6);
          font-size: 11px;
          flex-shrink: 0;
          margin-right: 8px;
        }

        .value {
          color: #fff;
          font-size: 11px;
          text-align: right;
          word-break: break-word;

          &.importance {
            color: #00ff88;
            font-weight: 600;
          }

          &.category {
            color: #448aff;
            background: rgba(68, 138, 255, 0.2);
            padding: 1px 4px;
            border-radius: 2px;
          }
        }
      }
    }
  }

  .feature-list-panel {
    position: absolute;
    top: 12px;
    left: 12px;
    width: 280px;
    max-height: calc(100% - 24px);
    background: rgba(0, 0, 0, 0.85);
    border-radius: 8px;
    padding: 12px;
    color: #fff;
    overflow-y: auto;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);

    .panel-header {
      display: flex;
      justify-content: space-between;
      align-items: center;
      margin-bottom: 12px;
      padding-bottom: 8px;
      border-bottom: 1px solid rgba(255, 255, 255, 0.2);

      h4 {
        margin: 0;
        font-size: 14px;
        font-weight: 600;
        color: #00ff88;
      }

      .feature-count {
        background: rgba(0, 255, 136, 0.2);
        color: #00ff88;
        padding: 2px 8px;
        border-radius: 10px;
        font-size: 12px;
        font-weight: 600;
      }
    }

    .feature-list {
      display: flex;
      flex-direction: column;
      gap: 6px;

      .feature-item {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 8px;
        background: rgba(255, 255, 255, 0.05);
        border: 1px solid rgba(255, 255, 255, 0.1);
        border-radius: 4px;
        cursor: pointer;
        transition: all 0.2s ease;

        &:hover {
          background: rgba(255, 255, 255, 0.1);
          border-color: rgba(0, 255, 136, 0.3);
        }

        &.selected {
          background: rgba(0, 255, 136, 0.15);
          border-color: #00ff88;
        }

        &.hovered {
          border-color: rgba(0, 255, 136, 0.5);
        }

        .feature-info {
          flex: 1;
          min-width: 0;

          .feature-name {
            font-size: 12px;
            font-weight: 500;
            color: #fff;
            margin-bottom: 2px;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
          }

          .feature-type {
            font-size: 10px;
            color: rgba(255, 255, 255, 0.5);
          }
        }

        .feature-importance {
          flex-shrink: 0;
          margin-left: 8px;
          padding: 2px 6px;
          background: rgba(0, 255, 136, calc(0.1 + var(--importance) * 0.3));
          color: #00ff88;
          border-radius: 3px;
          font-size: 11px;
          font-weight: 600;
        }
      }
    }
  }

  .control-panel {
    position: absolute;
    top: 12px;
    right: 12px;
    background: rgba(0, 0, 0, 0.85);
    border-radius: 8px;
    padding: 12px;
    color: #fff;
    font-size: 12px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);

    .control-group {
      margin-bottom: 8px;

      &:last-child {
        margin-bottom: 0;
      }

      .control-label {
        display: flex;
        align-items: center;
        gap: 6px;
        cursor: pointer;
        user-select: none;

        input[type='checkbox'] {
          cursor: pointer;
        }
      }

      .clear-button {
        width: 100%;
        padding: 6px 12px;
        background: rgba(255, 82, 82, 0.2);
        border: 1px solid rgba(255, 82, 82, 0.5);
        border-radius: 4px;
        color: #ff5252;
        font-size: 12px;
        cursor: pointer;
        transition: all 0.2s ease;

        &:hover {
          background: rgba(255, 82, 82, 0.3);
          border-color: #ff5252;
        }
      }
    }
  }

  .selection-indicator {
    position: absolute;
    bottom: 12px;
    left: 50%;
    transform: translateX(-50%);
    background: rgba(0, 255, 136, 0.15);
    border: 1px solid #00ff88;
    border-radius: 8px;
    padding: 10px 16px;
    color: #fff;
    text-align: center;
    box-shadow: 0 4px 12px rgba(0, 255, 136, 0.3);

    .indicator-label {
      font-size: 13px;
      font-weight: 600;
      color: #00ff88;
      margin-bottom: 4px;
    }

    .indicator-details {
      font-size: 11px;
      color: rgba(255, 255, 255, 0.8);
    }
  }
}
</style>
