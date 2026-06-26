<!--
  DXF 文件导入对话框
  - 支持拖拽和点击两种方式选择 .dxf 文件
  - 上传进度可视化
  - 解析结果统计展示（线段、圆弧、圆、特征）
  - 内置 2D/3D 预览（基于 Three.js 在 XY 平面渲染几何）
  - 解析成功后可一键导入到当前工程
-->
<template>
  <el-dialog
    v-model="visible"
    :title="$t('dxfImport.dialogTitle')"
    width="900px"
    top="4vh"
    :close-on-click-modal="false"
    destroy-on-close
    @close="handleClose"
  >
    <div class="dxf-import-container">
      <!-- 阶段 1：文件选择区（仅 idle / error 阶段显示） -->
      <div
        v-if="store.isIdle || store.isError"
        class="upload-section"
      >
        <div
          class="drop-zone"
          :class="{ 'is-dragover': isDragOver, 'is-disabled': false }"
          @click="triggerFilePicker"
          @dragenter.prevent="isDragOver = true"
          @dragover.prevent="isDragOver = true"
          @dragleave.prevent="isDragOver = false"
          @drop.prevent="onFileDrop"
        >
          <el-icon class="upload-icon">
            <upload-filled />
          </el-icon>
          <div class="drop-text">
            <span class="primary-text">{{ $t('dxfImport.uploadHint') }}</span>
            <span class="em-text">{{ $t('dxfImport.uploadClick') }}</span>
          </div>
          <div class="drop-tip">
            {{ $t('dxfImport.uploadTip') }}
          </div>
        </div>

        <input
          ref="fileInputRef"
          type="file"
          accept=".dxf"
          style="display: none;"
          @change="onFileInputChange"
        >

        <el-alert
          v-if="localFormatError"
          :title="localFormatError"
          type="error"
          :closable="false"
          show-icon
          style="margin-top: 12px;"
        />
      </div>

      <!-- 阶段 2：上传 / 解析进度 -->
      <div
        v-else-if="store.isActive"
        class="progress-section"
      >
        <div class="progress-status">
          <el-icon class="is-loading">
            <loading />
          </el-icon>
          <span>
            <template v-if="store.isUploading">
              {{ $t('dxfImport.uploading') }}
            </template>
            <template v-else>
              {{ $t('dxfImport.parsing') }}
            </template>
          </span>
          <span class="file-name-inline">{{ store.currentFileName }}</span>
        </div>

        <el-progress
          :percentage="store.overallProgress"
          :status="store.isError ? 'exception' : undefined"
          :stroke-width="10"
          striped
          striped-flow
        />

        <div class="progress-detail">
          <span v-if="store.isUploading">
            {{ $t('dxfImport.uploadProgress', { pct: store.uploadProgress }) }}
          </span>
          <span v-else>
            {{ $t('dxfImport.parseProgress', { pct: store.parseProgress }) }}
          </span>
        </div>
      </div>

      <!-- 阶段 3：解析成功 + 结果展示 -->
      <div
        v-else-if="store.isSuccess && store.parseResult"
        class="result-section"
      >
        <el-alert
          :title="$t('dxfImport.importSuccess')"
          type="success"
          :closable="false"
          show-icon
        />

        <!-- 解析统计卡片 -->
        <div class="stats-section">
          <h4>{{ $t('dxfImport.statistics') }}</h4>
          <div class="stat-grid">
            <div class="stat-card">
              <div class="stat-label">{{ $t('dxfImport.linesCount') }}</div>
              <div class="stat-value">
                {{ store.parseResult.lines_count.toLocaleString() }}
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-label">{{ $t('dxfImport.arcsCount') }}</div>
              <div class="stat-value">
                {{ store.parseResult.arcs_count.toLocaleString() }}
              </div>
            </div>
            <div class="stat-card">
              <div class="stat-label">{{ $t('dxfImport.circlesCount') }}</div>
              <div class="stat-value">
                {{ store.parseResult.circles_count.toLocaleString() }}
              </div>
            </div>
            <div class="stat-card highlight">
              <div class="stat-label">{{ $t('dxfImport.featuresCount') }}</div>
              <div class="stat-value">{{ featuresCount.toLocaleString() }}</div>
            </div>
          </div>

          <el-descriptions
            :column="2"
            border
            size="small"
            class="meta-descriptions"
          >
            <el-descriptions-item :label="$t('dxfImport.fileName')">
              {{ store.parseResult.file_name }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('dxfImport.fileSize')">
              {{ formatFileSize(store.parseResult.file_size) }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('dxfImport.dxfVersion')">
              {{ store.parseResult.dxf_version || '-' }}
            </el-descriptions-item>
            <el-descriptions-item :label="$t('dxfImport.parseTime')">
              {{ store.parseResult.parse_time_ms.toFixed(0) }} ms
            </el-descriptions-item>
            <el-descriptions-item
              :label="$t('dxfImport.totalEntities')"
              :span="2"
            >
              {{ store.parseResult.total_entities.toLocaleString() }}
            </el-descriptions-item>
          </el-descriptions>
        </div>

        <!-- 2D/3D 预览 -->
        <div class="preview-section">
          <div class="preview-header">
            <h4>{{ $t('dxfImport.preview') }}</h4>
            <el-button-group size="small">
              <el-button @click="resetView">
                <el-icon><aim /></el-icon>{{ $t('dxfImport.viewFit') }}
              </el-button>
              <el-button @click="viewTop">{{ $t('dxfImport.viewTop') }}</el-button>
              <el-button @click="view3D">{{ $t('dxfImport.viewIso') }}</el-button>
              <el-button @click="toggleWireframe">
                {{ wireframe ? $t('dxfImport.viewSolid') : $t('dxfImport.viewWire') }}
              </el-button>
            </el-button-group>
          </div>
          <div
            ref="previewContainer"
            class="preview-canvas"
          />
          <div
            v-if="previewLoading"
            class="preview-loading"
          >
            <el-icon class="is-loading">
              <loading />
            </el-icon>
            <span>{{ $t('viewer.loading') }}</span>
          </div>
        </div>

        <!-- 警告信息 -->
        <div
          v-if="store.parseResult.warnings && store.parseResult.warnings.length > 0"
          class="warning-section"
        >
          <el-alert
            v-for="(w, i) in store.parseResult.warnings"
            :key="i"
            :title="w"
            type="warning"
            :closable="false"
            show-icon
            style="margin-bottom: 4px;"
          />
        </div>
      </div>

      <!-- 错误状态（result 区域下） -->
      <div
        v-else-if="store.isError"
        class="error-section"
      >
        <el-result
          icon="error"
          :title="$t('dxfImport.importFailed')"
          :sub-title="store.errorMessage"
        />
      </div>
    </div>

    <template #footer>
      <div class="dialog-footer">
        <!-- 空闲或错误：关闭按钮 -->
        <el-button
          v-if="store.isIdle || store.isError"
          @click="handleClose"
        >
          {{ $t('common.cancel') }}
        </el-button>

        <!-- 错误：重试 -->
        <el-button
          v-if="store.isError"
          type="primary"
          @click="handleRetry"
        >
          {{ $t('common.retry') }}
        </el-button>

        <!-- 上传/解析中：只能关闭（但通常禁用） -->
        <el-button
          v-if="store.isActive"
          :disabled="true"
        >
          {{ $t('common.loading') }}
        </el-button>

        <!-- 成功：导入到项目 + 关闭 -->
        <template v-if="store.isSuccess">
          <el-button @click="handleClose">
            {{ $t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            :loading="importing"
            @click="handleImportToProject"
          >
            {{ $t('dxfImport.importToProject') }}
          </el-button>
        </template>
      </div>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
/**
 * DXF 文件导入对话框
 * 组合 dxfImport store 与 Three.js 2D 预览。
 */
import { ref, computed, watch, nextTick, onBeforeUnmount } from 'vue'
import * as THREE from 'three'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { useDxfImportStore } from '@/stores/dxfImport'
import { formatFileSize } from '@/utils/formatters'
import { useThreeScene } from '@/composables/useThreeScene'
import type { DxfParseResponse } from '@/types'

// 预览场景常量
const PREVIEW_CAMERA_FOV = 45
const PREVIEW_CAMERA_POSITION: [number, number, number] = [0, -200, 200]
const PREVIEW_GRID_SIZE = 500
const PREVIEW_GRID_DIVISIONS = 25
const PREVIEW_AXES_SIZE = 50

const { t } = useI18n()

const store = useDxfImportStore()

const visible = computed({
  get: () => store.showDialog,
  set: (v: boolean) => {
    store.showDialog = v
  },
})

/** 本地文件格式错误（仅在选择文件时立即校验） */
const localFormatError = ref('')
/** 拖拽态 */
const isDragOver = ref(false)
/** 文件 input ref */
const fileInputRef = ref<HTMLInputElement | null>(null)
/** 预览画布 ref */
const previewContainer = ref<HTMLDivElement | null>(null)
/** 预览加载态 */
const previewLoading = ref(false)
/** 正在导入到工程 */
const importing = ref(false)
/** 线框模式 */
const wireframe = ref(false)

/** 识别到的特征数量（孔+平面+其他） */
const featuresCount = computed(() => {
  const f = store.featureResult
  if (!f) return 0
  return (f.hole_count ?? 0) + (f.plane_count ?? 0)
})

// —— Three.js 资源（统一管理生命周期） ——
let threeScene: ReturnType<typeof useThreeScene> | null = null
let contentGroup: THREE.Group | null = null

watch(() => store.showDialog, (val) => {
  if (val) {
    // 打开时清理本地状态
    localFormatError.value = ''
  } else {
    // 关闭时释放预览资源
    disposePreview()
  }
})

// 解析成功时初始化预览
watch(
  () => [store.isSuccess, store.parseResult] as const,
  async ([success, result]) => {
    if (success && result) {
      await nextTick()
      initPreview(result)
    } else {
      disposePreview()
    }
  },
  { deep: true },
)

onBeforeUnmount(() => {
  disposePreview()
})

// ============= 文件选择 =============

function triggerFilePicker() {
  fileInputRef.value?.click()
}

function onFileInputChange(e: Event) {
  const target = e.target as HTMLInputElement
  const file = target.files?.[0]
  if (file) {
    handleFileSelected(file)
  }
  // 重置 input，允许选择同名文件
  if (target) target.value = ''
}

function onFileDrop(e: DragEvent) {
  isDragOver.value = false
  const file = e.dataTransfer?.files?.[0]
  if (file) {
    handleFileSelected(file)
  }
}

async function handleFileSelected(file: File) {
  localFormatError.value = ''

  // 1. 文件格式校验
  const ext = (file.name.split('.').pop() || '').toLowerCase()
  if (ext !== 'dxf') {
    const msg = t('dxfImport.invalidFormat')
    ElMessage.error(msg)
    localFormatError.value = msg
    return
  }

  // 2. 大文件提示（>50MB 时给出友好提示，但不阻止）
  if (file.size > 50 * 1024 * 1024) {
    ElMessage.warning(t('dxfImport.largeFileWarning'))
  }

  // 3. 触发完整流程
  const ok = await store.importDxfFile(file)
  if (!ok) {
    ElMessage.error(store.errorMessage || t('dxfImport.dxfImportFailed'))
  }
}

// ============= 预览 =============

function initPreview(result: DxfParseResponse) {
  if (!previewContainer.value) return
  previewLoading.value = true

  try {
    // 释放旧资源
    disposePreview()

    // 使用 useThreeScene composable
    threeScene = useThreeScene({
      container: previewContainer.value,
      backgroundColor: '#0e1525',
      fov: PREVIEW_CAMERA_FOV,
      cameraPosition: PREVIEW_CAMERA_POSITION,
      enableDamping: true,
      dampingFactor: 0.08,
      showGrid: true,
      gridSize: PREVIEW_GRID_SIZE,
      gridDivisions: PREVIEW_GRID_DIVISIONS,
    })

    const { scene, camera, renderer, controls, addLight } = threeScene

    // Z 轴向上，更符合工程图习惯
    camera.up.set(0, 0, 1)
    camera.updateProjectionMatrix()

    // 灯光
    addLight(new THREE.AmbientLight(0xffffff, 0.7))
    const dir = new THREE.DirectionalLight(0xffffff, 0.7)
    dir.position.set(50, 50, 100)
    addLight(dir)

    // 网格旋转到 XY 平面
    const grid = scene.children.find((c) => c instanceof THREE.GridHelper) as THREE.GridHelper
    if (grid) {
      grid.rotation.x = Math.PI / 2
    }

    // 坐标轴
    const axes = new THREE.AxesHelper(PREVIEW_AXES_SIZE)
    scene.add(axes)

    // 创建几何
    contentGroup = createDxfGroup(result)
    scene.add(contentGroup)

    // 缩放到合适视角
    resetView()

    // 启动渲染循环
    threeScene.startAnimation()
  } finally {
    previewLoading.value = false
  }
}

function createDxfGroup(result: DxfParseResponse): THREE.Group {
  const group = new THREE.Group()
  const lineColor = 0x5b9bd5
  const lineMat = new THREE.LineBasicMaterial({
    color: lineColor,
    linewidth: 1,
  })

  // 计算缩放与中心
  const ext = result.extents || {}
  const cx = ((ext.min_x ?? 0) + (ext.max_x ?? 0)) / 2
  const cy = ((ext.min_y ?? 0) + (ext.max_y ?? 0)) / 2
  const rangeX = Math.max((ext.max_x ?? 0) - (ext.min_x ?? 0), 1)
  const rangeY = Math.max((ext.max_y ?? 0) - (ext.min_y ?? 0), 1)
  const range = Math.max(rangeX, rangeY, 1)
  const scale = 100 / range // 把外接盒归一到 ~100 单位

  // 1) 线段
  if (result.lines && result.lines.length > 0) {
    const maxLines = 5000 // 防止极端情况下卡顿
    const lines = result.lines.slice(0, maxLines)
    const positions: number[] = []
    for (const ln of lines) {
      const [sx, sy] = ln.start
      const [ex, ey] = ln.end
      positions.push(
        (sx - cx) * scale, (sy - cy) * scale, 0,
        (ex - cx) * scale, (ey - cy) * scale, 0,
      )
    }
    const geo = new THREE.BufferGeometry()
    geo.setAttribute(
      'position',
      new THREE.Float32BufferAttribute(positions, 3),
    )
    const segs = new THREE.LineSegments(geo, lineMat)
    group.add(segs)
  }

  // 2) 圆（线框形式）
  if (result.circles && result.circles.length > 0) {
    const maxCircles = 2000
    const circles = result.circles.slice(0, maxCircles)
    for (const c of circles) {
      const [ccx, ccy] = c.center
      const r = (c.radius ?? 0) * scale
      if (r <= 0) continue
      const segs = 48
      const pts: number[] = []
      for (let i = 0; i <= segs; i++) {
        const a = (i / segs) * Math.PI * 2
        pts.push(
          (ccx - cx) * scale + Math.cos(a) * r,
          (ccy - cy) * scale + Math.sin(a) * r,
          0,
        )
      }
      const geo = new THREE.BufferGeometry()
      geo.setAttribute(
        'position',
        new THREE.Float32BufferAttribute(pts, 3),
      )
      const ring = new THREE.Line(geo, lineMat)
      group.add(ring)
    }
  }

  return group
}

function animate() {
  if (!threeScene) return
  // Animation is handled by threeScene.startAnimation(), this function is kept for potential future use
  const { scene, camera, renderer, controls } = threeScene
  controls?.update()
  if (renderer && scene && camera) {
    renderer.render(scene, camera)
  }
}

function onPreviewResize() {
  if (!previewContainer.value || !threeScene) return
  const { renderer, camera } = threeScene
  if (!renderer || !camera) return
  const w = previewContainer.value.clientWidth
  const h = previewContainer.value.clientHeight
  if (w === 0 || h === 0) return
  renderer.setSize(w, h)
  camera.aspect = w / h
  camera.updateProjectionMatrix()
}

function resetView() {
  if (!threeScene || !contentGroup) return
  const { camera, controls } = threeScene
  const box = new THREE.Box3().setFromObject(contentGroup)
  if (box.isEmpty()) {
    camera.position.set(0, -200, 200)
    controls.target.set(0, 0, 0)
  } else {
    const center = box.getCenter(new THREE.Vector3())
    const size = box.getSize(new THREE.Vector3())
    const maxDim = Math.max(size.x, size.y, 1)
    const fov = camera.fov * (Math.PI / 180)
    const dist = (maxDim / (2 * Math.tan(fov / 2))) * 1.8
    camera.position.set(center.x, center.y - dist, center.z + dist * 0.4)
    controls.target.copy(center)
  }
  controls.update()
}

function viewTop() {
  if (!threeScene) return
  const { camera, controls } = threeScene
  const target = controls.target.clone()
  camera.position.set(target.x, target.y, target.z + 200)
  camera.up.set(0, 1, 0)
  controls.update()
}

function view3D() {
  if (!threeScene) return
  const { camera, controls } = threeScene
  const target = controls.target.clone()
  const d = 200
  camera.position.set(target.x + d, target.y - d, target.z + d)
  camera.up.set(0, 0, 1)
  controls.update()
}

function toggleWireframe() {
  wireframe.value = !wireframe.value
  if (!contentGroup) return
  contentGroup.traverse((obj) => {
    if (obj instanceof THREE.LineSegments || obj instanceof THREE.Line) {
      const mat = obj.material as THREE.LineBasicMaterial
      if (mat) mat.color.set(wireframe.value ? 0xffd166 : 0x5b9bd5)
    }
  })
}

function disposePreview() {
  if (contentGroup) {
    contentGroup.traverse((obj) => {
      if (obj instanceof THREE.LineSegments || obj instanceof THREE.Line) {
        obj.geometry?.dispose()
        if (Array.isArray(obj.material)) {
          obj.material.forEach((m) => m.dispose())
        } else {
          (obj.material as THREE.Material)?.dispose()
        }
      }
    })
    contentGroup = null
  }
  if (threeScene) {
    threeScene.cleanup()
    threeScene = null
  }
}

// ============= 业务操作 =============

function handleRetry() {
  store.reset()
  localFormatError.value = ''
}

function handleClose() {
  store.closeDialog()
}

async function handleImportToProject() {
  importing.value = true
  try {
    // 简化处理：将解析后的几何附加到当前工程的资源列表中。
    // 由于后端尚未提供专用 endpoint，这里走通用资源上传。
    // 若后端已提供专用 /api/dxf/import-project 接口，可在此替换。
    const { useProjectStore } = await import('@/stores/project')
    const projectStore = useProjectStore()
    if (!projectStore.manifest) {
      ElMessage.error(t('dxfImport.noOpenProject'))
      return
    }
    // 直接在工程清单中追加一条 DXF 资源记录
    const parseResult = store.parseResult
    if (parseResult) {
      projectStore.manifest.resources.push({
        id: store.currentFileId || `dxf-${Date.now()}`,
        type: 'drawing',
        path: `dxf/${parseResult.file_name}`,
        original_name: parseResult.file_name,
        mime_type: 'application/dxf',
        added_at: new Date().toISOString(),
        metadata: {
          source: 'dxf-import',
          file_id: store.currentFileId,
          lines_count: parseResult.lines_count,
          arcs_count: parseResult.arcs_count,
          circles_count: parseResult.circles_count,
          features_count: featuresCount.value,
        },
      })
      // 触发响应式更新
      projectStore.markModified?.()
    }
   ElMessage.success(t('dxfImport.importToProjectSuccess'))
    store.closeDialog()
  } catch {
    ElMessage.error(t('dxfImport.importToProjectFailed'))
  } finally {
    importing.value = false
  }}
</script>

<style scoped>
.dxf-import-container {
  min-height: 320px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

/* 拖拽区 */
.upload-section {
  padding: 24px 0;
}

.drop-zone {
  border: 2px dashed var(--border-light);
  border-radius: 8px;
  padding: 48px 16px;
  text-align: center;
  cursor: pointer;
  background: var(--bg-secondary);
  transition: all 0.2s ease;
  user-select: none;
}

.drop-zone:hover,
.drop-zone.is-dragover {
  border-color: var(--accent-primary);
  background: rgba(139, 125, 107, 0.1);
}

.upload-icon {
  font-size: 48px;
  color: var(--accent-primary);
  margin-bottom: 12px;
}

.drop-text {
  display: flex;
  flex-direction: column;
  gap: 4px;
  font-size: 14px;
  color: var(--text-secondary);
}

.drop-text .em-text {
  color: var(--accent-primary);
  font-style: normal;
}

.drop-tip {
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 进度区 */
.progress-section {
  padding: 32px 0;
}

.progress-status {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  font-size: 14px;
  color: var(--text-secondary);
  margin-bottom: 16px;
}

.file-name-inline {
  color: var(--text-tertiary);
  font-size: 12px;
  margin-left: 8px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.progress-detail {
  margin-top: 12px;
  text-align: center;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* 结果区 */
.result-section {
  max-height: 60vh;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stats-section h4,
.preview-section h4 {
  margin: 8px 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 8px;
  margin-bottom: 12px;
}

.stat-card {
  padding: 12px;
  background: var(--bg-tertiary);
  border-radius: 6px;
  text-align: center;
  transition: transform 0.15s ease;
}

.stat-card:hover {
  transform: translateY(-2px);
}

.stat-card.highlight {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: white;
}

.stat-label {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-bottom: 4px;
}

.stat-card.highlight .stat-label {
  color: rgba(255, 255, 255, 0.9);
}

.stat-value {
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-card.highlight .stat-value {
  color: white;
}

.meta-descriptions {
  margin-top: 8px;
}

/* 预览区 */
.preview-section {
  margin-top: 8px;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.preview-header h4 {
  margin: 0;
}

.preview-canvas {
  width: 100%;
  height: 360px;
  border-radius: 6px;
  overflow: hidden;
  background: #0e1525;
  position: relative;
}

.preview-loading {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  display: flex;
  align-items: center;
  gap: 8px;
  color: var(--bg-card);
  font-size: 14px;
  background: rgba(0, 0, 0, 0.4);
  padding: 8px 16px;
  border-radius: 4px;
}

.warning-section {
  margin-top: 4px;
}

.error-section {
  padding: 24px 0;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
