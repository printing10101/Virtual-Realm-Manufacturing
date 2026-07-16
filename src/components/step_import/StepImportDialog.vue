<template>
  <el-dialog
    v-model="visible"
    :title="$t('stepImport.dialogTitle')"
    width="700px"
    :close-on-click-modal="false"
    @close="handleClose"
  >
    <el-tabs
      v-model="activeTab"
      @tab-change="onTabChange"
    >
      <el-tab-pane
        :label="$t('stepImport.importTab')"
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
                <UploadFilled />
              </el-icon>
              <div class="el-upload__text">
                {{ $t('stepImport.uploadHint') }} <em>{{ $t('stepImport.uploadClick') }}</em>
              </div>
              <template #tip>
                <div class="el-upload__tip">
                  {{ $t('stepImport.uploadTip') }}
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
                <el-form-item :label="$t('stepImport.outputFormat')">
                  <el-radio-group v-model="outputFormat">
                    <el-radio value="stl">
                      {{ $t('stepImport.stlFormat') }}
                    </el-radio>
                    <el-radio value="brep">
                      {{ $t('stepImport.brepFormat') }}
                    </el-radio>
                  </el-radio-group>
                </el-form-item>
                <el-form-item :label="$t('stepImport.precisionLevel')">
                  <el-select
                    v-model="precision"
                    style="width: 160px"
                  >
                    <el-option
                      :label="$t('stepImport.lowPrecision')"
                      value="low"
                    />
                    <el-option
                      :label="$t('stepImport.mediumPrecision')"
                      value="medium"
                    />
                    <el-option
                      :label="$t('stepImport.highPrecision')"
                      value="high"
                    />
                  </el-select>
                  <span class="precision-hint">
                    {{ $t(precisionHint) }}
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
                <Loading />
              </el-icon>
              <span>{{ store.isUploading ? $t('stepImport.uploading') : $t('stepImport.processing') }}</span>
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
              {{ $t('stepImport.processingDetail') }}
            </div>
          </div>

          <!-- 成功结果 -->
          <div
            v-if="store.isSuccess && store.currentResult"
            class="result-section"
          >
            <el-alert
              :title="store.warnings.length > 0 ? $t('stepImport.importSuccessWithWarning') : $t('stepImport.importSuccess')"
              :type="store.warnings.length > 0 ? 'warning' : 'success'"
              :closable="false"
              show-icon
            />

            <!-- 模型概览 -->
            <div class="model-overview">
              <h4>{{ $t('stepImport.modelOverview') }}</h4>
              <el-descriptions
                :column="2"
                border
                size="small"
              >
                <el-descriptions-item :label="$t('stepImport.fileName')">
                  {{ store.currentResult.file_name }}
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.fileSize')">
                  {{ formatFileSize(store.currentResult.file_size) }}
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.parseTime')">
                  {{ store.currentResult.parse_time_ms.toFixed(0) }} ms
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.conversionTime')">
                  {{ store.currentResult.conversion_time_ms.toFixed(0) }} ms
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.entityCount')">
                  {{ store.modelInfo?.entity_count ?? 0 }}
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.faceCount')">
                  {{ store.modelInfo?.face_count?.toLocaleString() ?? 0 }}
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.vertexCount')">
                  {{ store.modelInfo?.vertex_count?.toLocaleString() ?? 0 }}
                </el-descriptions-item>
                <el-descriptions-item :label="$t('stepImport.assembly')">
                  {{ store.currentResult.is_assembly ? $t('common.yes') : $t('common.no') }}
                </el-descriptions-item>
              </el-descriptions>
            </div>

            <!-- 包围盒尺寸 -->
            <div
              v-if="store.modelInfo?.bounding_box"
              class="model-dimensions"
            >
              <h4>{{ $t('stepImport.boundingBox') }}</h4>
              <div class="dimension-cards">
                <div class="dim-card">
                  <span class="dim-label">{{ $t('stepImport.lengthX') }}</span>
                  <span class="dim-value">{{ store.modelInfo.bounding_box.length.toFixed(2) }} mm</span>
                </div>
                <div class="dim-card">
                  <span class="dim-label">{{ $t('stepImport.widthY') }}</span>
                  <span class="dim-value">{{ store.modelInfo.bounding_box.width.toFixed(2) }} mm</span>
                </div>
                <div class="dim-card">
                  <span class="dim-label">{{ $t('stepImport.heightZ') }}</span>
                  <span class="dim-value">{{ store.modelInfo.bounding_box.height.toFixed(2) }} mm</span>
                </div>
              </div>
              <div
                v-if="store.modelInfo.volume > 0"
                class="dim-extra"
              >
                {{ $t('stepImport.volume') }}: {{ (store.modelInfo.volume / 1000).toFixed(2) }} {{ $t('stepImport.cubicCm') }} |
                {{ $t('stepImport.surfaceArea') }}: {{ (store.modelInfo.surface_area / 100).toFixed(2) }} {{ $t('stepImport.squareCm') }}
              </div>
            </div>

            <!-- 警告信息 -->
            <div
              v-if="store.warnings.length > 0"
              class="warning-section"
            >
              <!-- 动态字符串列表，无业务唯一 id，index 作为 key 可接受 -->
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
              <h4>{{ $t('stepImport.entitySelection', { count: store.activeStlFiles.length }) }}</h4>
              <el-radio-group
                v-model="entityIndex"
                size="small"
                @change="onEntityChange"
              >
                <!-- 动态列表，entity_name 可能重复且 radio 使用 index 作为 value，index 作为 key 可接受 -->
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
              <!-- 动态字符串列表，无业务唯一 id，index 作为 key 可接受 -->
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
              :title="$t('stepImport.importFailed')"
              :sub-title="store.errorMessage"
            >
              <template #extra>
                <el-button
                  type="primary"
                  @click="handleRetry"
                >
                  {{ $t('common.retry') }}
                </el-button>
              </template>
            </el-result>
          </div>
        </div>
      </el-tab-pane>

      <el-tab-pane
        :label="$t('stepImport.historyTab')"
        name="history"
      >
        <div class="history-container">
          <div
            v-if="historyLoading"
            style="text-align:center;padding:20px;"
          >
            <el-icon class="is-loading">
              <Loading />
            </el-icon> {{ $t('common.loading') }}
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
              :label="$t('stepImport.historyFile')"
              min-width="180"
              show-overflow-tooltip
            />
            <el-table-column
              :label="$t('stepImport.historySize')"
              width="90"
            >
              <template #default="{ row }">
                {{ formatFileSize(row.file_size) }}
              </template>
            </el-table-column>
            <el-table-column
              :label="$t('stepImport.historyTime')"
              width="170"
            >
              <template #default="{ row }">
                {{ formatSecondsTimestamp(row.created_at) }}
              </template>
            </el-table-column>
            <el-table-column
              :label="$t('stepImport.historyActions')"
              width="160"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  text
                  type="primary"
                  @click="handlePreviewHistory(row as ImportHistoryEntry)"
                >
                  {{ $t('stepImport.historyView') }}
                </el-button>
                <el-button
                  size="small"
                  text
                  type="danger"
                  @click="handleDeleteHistory(row as ImportHistoryEntry)"
                >
                  {{ $t('stepImport.historyDelete') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
          <el-empty
            v-else
            :description="$t('stepImport.noHistory')"
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
          {{ $t('stepImport.startImport') }}
        </el-button>
        <el-button
          v-if="store.isSuccess && activeTab === 'import'"
          type="primary"
          @click="handleLoadInViewer"
        >
          {{ $t('stepImport.loadToViewer') }}
        </el-button>
        <el-button @click="handleClose">
          {{ store.isSuccess ? $t('common.done') : $t('common.cancel') }}
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
import { UploadFilled, Loading } from '@element-plus/icons-vue'
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
    case 'low': return 'stepImport.lowPrecisionHint'
    case 'medium': return 'stepImport.mediumPrecisionHint'
    case 'high': return 'stepImport.highPrecisionHint'
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
.step-import-container { min-height: 200px; }
.step-uploader { width: 100%; }
.import-options { margin-top: 16px; padding: 12px; background: var(--bg-secondary); border-radius: 6px; }
.precision-hint { margin-left: 12px; font-size: 12px; color: var(--text-tertiary); }
.progress-section { padding: 24px 0; text-align: center; }
.progress-status { margin-bottom: 16px; font-size: 14px; color: var(--text-secondary); display: flex; align-items: center; justify-content: center; gap: 8px; }
.progress-detail { margin-top: 12px; font-size: 12px; color: var(--text-tertiary); }
.result-section { max-height: 50vh; overflow-y: auto; }
.model-overview { margin-top: 16px; }
.model-overview h4,.model-dimensions h4,.entity-selector h4 { margin: 12px 0 8px; font-size: 14px; font-weight: 600; color: var(--text-primary); }
.dimension-cards { display: flex; gap: 12px; }
.dim-card { flex: 1; padding: 12px; background: var(--bg-tertiary); border-radius: 6px; text-align: center; }
.dim-label { display: block; font-size: 12px; color: var(--text-tertiary); margin-bottom: 4px; }
.dim-value { font-size: 16px; font-weight: 600; color: var(--text-primary); }
.dim-extra { margin-top: 8px; font-size: 12px; color: var(--text-secondary); text-align: center; }
.warning-section { margin-top: 12px; }
.entity-selector { margin-top: 16px; }
.error-section { padding: 24px 0; }
.error-detail { margin-top: 12px; }
.history-container { min-height: 200px; }
.dialog-footer { display: flex; justify-content: flex-end; gap: 8px; }
</style>
