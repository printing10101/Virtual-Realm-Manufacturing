<template>
  <el-dialog
    v-model="visible"
    title="导入 STEP 模型"
    width="700px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-tabs
      v-model="activeTab"
      @tab-change="onTabChange"
    >
      <el-tab-pane
        label="导入模型"
        name="import"
      >
        <div class="step-import-container">
          <!-- 导入前：文件选择区 -->
          <div
            v-if="!store.isSuccess && !store.isError"
            class="upload-section"
          >
            <el-upload
              ref="uploadRef"
              class="step-uploader"
              drag
              :auto-upload="false"
              :limit="1"
              accept=".step,.stp"
              :on-change="handleFileChange"
              :on-remove="handleFileRemove"
              :file-list="fileList"
            >
              <el-icon class="el-icon--upload">
                <upload-filled />
              </el-icon>
              <div class="el-upload__text">
                拖拽 STEP 文件到此处或 <em>点击选择文件</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  支持 .step / .stp 格式，单个文件最大 50MB
                </div>
              </template>
            </el-upload>

            <div
              v-if="selectedFile"
              class="import-options"
            >
              <el-form
                label-width="80px"
                size="small"
              >
                <el-form-item label="输出格式">
                  <el-radio-group v-model="outputFormat">
                    <el-radio value="stl">
                      STL (三角网格)
                    </el-radio>
                    <el-radio value="brep">
                      BREP (边界表示)
                    </el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item label="精度级别">
                  <el-select
                    v-model="precision"
                    style="width: 160px"
                  >
                    <el-option
                      label="低精度 (快速)"
                      value="low"
                    />
                    <el-option
                      label="中精度 (平衡)"
                      value="medium"
                    />
                    <el-option
                      label="高精度 (精细)"
                      value="high"
                    />
                  </el-select>
                  <span class="precision-hint">
                    {{ precisionHint }}
                  </span>
                </el-form-item>
              </el-form>
            </div>
          </div>

          <!-- 上传/处理进度 -->
          <div
            v-if="store.isActive"
            class="progress-section"
          >
            <div class="progress-status">
              <el-icon
                v-if="store.isUploading"
                class="is-loading"
              >
                <loading />
              </el-icon>
              <span>{{ store.isUploading ? '正在上传文件...' : '正在解析和处理模型...' }}</span>
            </div>
            <el-progress
              :percentage="store.isUploading ? store.uploadProgress : undefined"
              :indeterminate="store.isProcessing"
              :status="store.isSuccess ? 'success' : store.isError ? 'exception' : undefined"
              :stroke-width="8"
            />
            <div
              v-if="store.isProcessing"
              class="progress-detail"
            >
              正在解析STEP几何数据并生成三角网格，请耐心等待...
            </div>
          </div>

          <!-- 成功结果 -->
          <div
            v-if="store.isSuccess && store.currentResult"
            class="result-section"
          >
            <el-alert
              :title="store.warnings.length > 0 ? '导入成功 (含警告)' : '导入成功'"
              :type="store.warnings.length > 0 ? 'warning' : 'success'"
              :closable="false"
              show-icon
            />

            <!-- 模型概览 -->
            <div class="model-overview">
              <h4>模型概览</h4>
              <el-descriptions
                :column="2"
                border
                size="small"
              >
                <el-descriptions-item label="文件名">
                  {{ store.currentResult.file_name }}
                </el-descriptions-item>
                <el-descriptions-item label="文件大小">
                  {{ formatFileSize(store.currentResult.file_size) }}
                </el-descriptions-item>
                <el-descriptions-item label="解析耗时">
                  {{ store.currentResult.parse_time_ms.toFixed(0) }} ms
                </el-descriptions-item>
                <el-descriptions-item label="转换耗时">
                  {{ store.currentResult.conversion_time_ms.toFixed(0) }} ms
                </el-descriptions-item>
                <el-descriptions-item label="实体数">
                  {{ store.modelInfo?.entity_count ?? 0 }}
                </el-descriptions-item>
                <el-descriptions-item label="面数">
                  {{ store.modelInfo?.face_count?.toLocaleString() ?? 0 }}
                </el-descriptions-item>
                <el-descriptions-item label="顶点数">
                  {{ store.modelInfo?.vertex_count?.toLocaleString() ?? 0 }}
                </el-descriptions-item>
                <el-descriptions-item label="装配体">
                  {{ store.currentResult.is_assembly ? '是' : '否' }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 包围盒尺寸 -->
            <div
              v-if="store.modelInfo?.bounding_box"
              class="model-dimensions"
            >
              <h4>包围盒尺寸</h4>
              <div class="dimension-cards">
                <div class="dim-card">
                  <span class="dim-label">长 (X)</span>
                  <span class="dim-value">{{ store.modelInfo.bounding_box.length.toFixed(2) }} mm</span>
                </div>
                <div class="dim-card">
                  <span class="dim-label">宽 (Y)</span>
                  <span class="dim-value">{{ store.modelInfo.bounding_box.width.toFixed(2) }} mm</span>
                </div>
                <div class="dim-card">
                  <span class="dim-label">高 (Z)</span>
                  <span class="dim-value">{{ store.modelInfo.bounding_box.height.toFixed(2) }} mm</span>
                </div>
              </div>
              <div
                v-if="store.modelInfo.volume > 0"
                class="dim-extra"
              >
                体积: {{ (store.modelInfo.volume / 1000).toFixed(2) }} cm³ |
                表面积: {{ (store.modelInfo.surface_area / 100).toFixed(2) }} cm²
              </div>
            </div>

            <!-- 警告信息 -->
            <div
              v-if="store.warnings.length > 0"
              class="warning-section"
            >
              <el-alert
                v-for="(w, i) in store.warnings"
                :key="i"
                :title="w"
                type="warning"
                :closable="false"
                show-icon
                style="margin-bottom: 4px;"
              />
            </div>

            <!-- 多实体选择 -->
            <div
              v-if="store.hasStlFiles && store.activeStlFiles.length > 1"
              class="entity-selector"
            >
              <h4>实体选择 ({{ store.activeStlFiles.length }} 个实体)</h4>
              <el-radio-group
                v-model="entityIndex"
                size="small"
                @change="onEntityChange"
              >
                <el-radio-button
                  v-for="(f, i) in store.activeStlFiles"
                  :key="i"
                  :value="i"
                >
                  {{ f.entity_name }}
                </el-radio-button>
              </el-radio-group>
            </div>

            <!-- 转换错误 -->
            <div
              v-if="store.currentResult.status.errors.length > 0"
              class="error-detail"
            >
              <el-alert
                v-for="(e, i) in store.currentResult.status.errors"
                :key="i"
                :title="e"
                type="error"
                :closable="false"
                show-icon
                style="margin-bottom: 4px;"
              />
            </div>
          </div>

          <!-- 错误状态 -->
          <div
            v-if="store.isError"
            class="error-section"
          >
            <el-result
              icon="error"
              title="导入失败"
              :sub-title="store.errorMessage"
            >
              <template #extra>
                <el-button
                  type="primary"
                  @click="handleRetry"
                >
                  重试
                </el-button>
              </template>
            </el-result>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane
        label="导入历史"
        name="history"
      >
        <div class="history-container">
          <div
            v-if="historyLoading"
            style="text-align:center;padding:20px;"
          >
            <el-icon class="is-loading">
              <loading />
            </el-icon> 加载中...
          </div>
          <el-table
            v-else-if="store.importHistory.length > 0"
            :data="store.importHistory"
            height="350"
            stripe
            size="small"
          >
            <el-table-column
              prop="original_name"
              label="原始文件"
              min-width="180"
              show-overflow-tooltip
            />
            <el-table-column
              label="大小"
              width="90"
            >
              <template #default="{ row }">
                {{ formatFileSize(row.file_size) }}
              </template>
            </el-table-column>
            <el-table-column
              label="导入时间"
              width="170"
            >
              <template #default="{ row }">
                {{ formatSecondsTimestamp(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column
              label="操作"
              width="160"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  text
                  type="primary"
                  @click="handlePreviewHistory(row)"
                >
                  查看
                </el-button>
                <el-button
                  size="small"
                  text
                  type="danger"
                  @click="handleDeleteHistory(row)"
                >
                  删除
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-else
            description="暂无导入记录"
            :image-size="80"
          />
        </div>
      </el-tab-pane>
    </el-tabs>

    <template #footer>
      <div class="dialog-footer">
        <el-button
          v-if="!store.isSuccess && !store.isError && selectedFile && activeTab === 'import'"
          type="primary"
          :loading="store.isActive"
          :disabled="!selectedFile"
          @click="handleImport"
        >
          开始导入
        </el-button>
        <el-button
          v-if="store.isSuccess && activeTab === 'import'"
          type="primary"
          @click="handleLoadInViewer"
        >
          加载到3D视图
        </el-button>
        <el-button @click="handleClose">
          {{ store.isSuccess ? '完成' : '取消' }}
        </el-button>
      </div>
    </template>
  </el-dialog>

  <StepModelViewer
    v-model="showViewer"
    :model-url="viewerModelUrl"
    :model-name="viewerModelName"
    :face-count="viewerFaceCount"
    :vertex-count="viewerVertexCount"
    :file-size="viewerFileSize"
    @close="showViewer = false"
  />
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { useStepImportStore } from '@/stores/stepImport'
import StepModelViewer from '@/components/step_import/StepModelViewer.vue'
import type { UploadFile, UploadInstance } from 'element-plus'
import type { ImportHistoryEntry } from '@/types'
import { formatFileSize, formatSecondsTimestamp } from '@/utils/formatters'

const store = useStepImportStore()

const visible = computed({
  get: () => store.showDialog,
  set: (val: boolean) => { store.showDialog = val },
})

const uploadRef = ref<UploadInstance>()
const fileList = ref<UploadFile[]>([])
const selectedFile = ref<File | null>(null)
const outputFormat = ref('stl')
const precision = ref('medium')
const entityIndex = ref(0)
const activeTab = ref('import')
const historyLoading = ref(false)

const showViewer = ref(false)
const viewerModelUrl = ref('')
const viewerModelName = ref('')
const viewerFaceCount = ref(0)
const viewerVertexCount = ref(0)
const viewerFileSize = ref(0)

const precisionHint = computed(() => {
  switch (precision.value) {
    case 'low': return '适用于大型装配体，面数较少，加载快'
    case 'medium': return '默认选项，平衡精度与性能'
    case 'high': return '适用于精密零件，面数较多，文件更大'
    default: return ''
  }
})

watch(() => store.showDialog, (val) => {
  if (val) {
    resetLocalState()
    store.fetchImportHistory()
  }
})

function resetLocalState() {
  fileList.value = []
  selectedFile.value = null
  outputFormat.value = 'stl'
  precision.value = 'medium'
  entityIndex.value = 0
}

function handleFileChange(file: UploadFile) {
  if (file.raw) {
    const ext = file.name.split('.').pop()?.toLowerCase()
    if (ext !== 'step' && ext !== 'stp') {
      fileList.value = []
      return
    }
    if (file.raw.size > 50 * 1024 * 1024) {
      fileList.value = []
      return
    }
    selectedFile.value = file.raw
  }
  fileList.value = [file]
}

function handleFileRemove() {
  selectedFile.value = null
  fileList.value = []
}

async function handleImport() {
  if (!selectedFile.value) return
  await store.importStepFile(selectedFile.value, precision.value, outputFormat.value)
}

function onEntityChange(index: string | number | boolean | undefined) {
  const idx = typeof index === 'number' ? index : parseInt(String(index), 10)
  if (!isNaN(idx)) store.selectEntity(idx)
}

function handleLoadInViewer() {
  viewerModelUrl.value = store.activeStlUrl
  viewerModelName.value = store.currentResult?.file_name ?? ''
  viewerFaceCount.value = store.modelInfo?.face_count ?? 0
  viewerVertexCount.value = store.modelInfo?.vertex_count ?? 0
  viewerFileSize.value = store.currentResult?.file_size ?? 0
  showViewer.value = true
}

function handleRetry() {
  store.reset()
  resetLocalState()
}

function handleClose() {
  visible.value = false
}

function onTabChange(tabName: string | number) {
  if (tabName === 'history') {
    historyLoading.value = true
    store.fetchImportHistory().finally(() => { historyLoading.value = false })
  }
}

function handlePreviewHistory(row: ImportHistoryEntry) {
  viewerModelUrl.value = row.stl_url
  viewerModelName.value = row.original_name
  viewerFaceCount.value = 0
  viewerVertexCount.value = 0
  viewerFileSize.value = row.file_size
  showViewer.value = true
}

async function handleDeleteHistory(row: ImportHistoryEntry) {
  await store.deleteHistoryFile(row.file_name)
}

</script>

<style scoped>
.step-import-container {
  min-height: 200px;
}

.step-uploader {
  width: 100%;
}

.import-options {
  margin-top: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 6px;
}

.precision-hint {
  margin-left: 12px;
  font-size: 12px;
  color: #909399;
}

.progress-section {
  padding: 24px 0;
  text-align: center;
}

.progress-status {
  margin-bottom: 16px;
  font-size: 14px;
  color: #606266;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.progress-detail {
  margin-top: 12px;
  font-size: 12px;
  color: #909399;
}

.result-section {
  max-height: 50vh;
  overflow-y: auto;
}

.model-overview {
  margin-top: 16px;
}

.model-overview h4,
.model-dimensions h4,
.entity-selector h4 {
  margin: 12px 0 8px;
  font-size: 14px;
  font-weight: 600;
  color: #303133;
}

.dimension-cards {
  display: flex;
  gap: 12px;
}

.dim-card {
  flex: 1;
  padding: 12px;
  background: #f5f7fa;
  border-radius: 6px;
  text-align: center;
}

.dim-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.dim-value {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.dim-extra {
  margin-top: 8px;
  font-size: 12px;
  color: #606266;
  text-align: center;
}

.warning-section {
  margin-top: 12px;
}

.entity-selector {
  margin-top: 16px;
}

.error-section {
  padding: 24px 0;
}

.error-detail {
  margin-top: 12px;
}

.history-container {
  min-height: 200px;
}

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
