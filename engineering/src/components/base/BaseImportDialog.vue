<!--
  BaseImportDialog - 通用的文件导入对话框基础组件
  
  提供导入流程的基础实现，支持：
  - 文件上传（拖放/点击）
  - 上传/解析进度显示
  - 解析结果展示
  - 错误处理和重试
  - 历史导入记录
  
  ## 使用示例
  ```vue
  <BaseImportDialog
    v-model="visible"
    :accept=".dxf,.step,.stp"
    :upload-api="/api/import"
    :parse-api="/api/parse"
    @success="handleImportSuccess"
    @error="handleImportError"
  >
    <template #preview="props">
      <DivPreview v-bind="props" />
    </template>
  </BaseImportDialog>
  ```
-->
<template>
  <el-dialog
    v-model="internalVisible"
    :title="dialogTitle"
    :width="dialogWidth"
    :close-on-click-modal="false"
    destroy-on-close
    @close="handleClose"
  >
    <!-- 阶段 1：文件上传 -->
    <div
      v-if="isIdle || isError"
      class="import-section"
    >
      <slot name="upload" :on-file-selected="handleFileSelected">
        <el-upload
          drag
          :auto-upload="false"
          :accept="accept"
          :on-change="handleFileChange"
          :on-remove="handleFileRemove"
          :disabled="isSelecting"
        >
          <el-icon class="el-icon--upload">
            <FolderOpened />
          </el-icon>
          <div class="el-upload__text">
            {{ uploadText }}
          </div>
          <template #tip>
            <div class="el-upload__tip">
              {{ uploadTip }}
            </div>
          </template>
        </el-upload>
      </slot>
    </div>

    <!-- 阶段 2：上传/解析进度 -->
    <div
      v-if="isActive"
      class="progress-section"
    >
      <slot name="progress" :progress="progress">
        <el-progress
          :percentage="progress"
          :status="isError ? 'exception' : isUploading ? undefined : 'success'"
          :stroke-width="8"
        />
        <div class="progress-text">
          {{ progressText }}
        </div>
      </slot>
    </div>

    <!-- 阶段 3：解析结果 -->
    <div
      v-if="isSuccess && parseResult"
      class="result-section"
    >
      <el-alert
        :title="successMessage"
        type="success"
        :closable="false"
        show-icon
      />

      <!-- 预览插槽（必需） -->
      <slot
        name="preview"
        :parse-result="parseResult"
        :feature-result="featureResult"
      />

      <!-- 警告信息 -->
      <div
        v-if="warnings?.length"
        class="warning-section"
      >
        <el-alert
          v-for="(w, i) in warnings"
          :key="`warn-${i}`"
          :title="w"
          type="warning"
          :closable="true"
        />
      </div>
    </div>

    <!-- 错误状态 -->
    <div
      v-if="isError"
      class="error-section"
    >
      <el-result
        icon="error"
        :title="errorMessage"
        :sub-title="parseError"
      >
        <template #extra>
          <slot name="error-actions" :retry="handleRetry">
            <el-button type="primary" @click="handleRetry">
              {{ $t('common.retry') }}
            </el-button>
          </slot>
        </template>
      </el-result>
    </div>

    <!-- 底部操作 -->
    <template #footer>
      <slot name="footer" :state="importState">
        <div class="footer-actions">
          <el-button
            v-if="isIdle || isError"
            @click="handleClose"
          >
            {{ cancelText }}
          </el-button>
          <el-button
            v-if="isActive"
            :loading="true"
            :disabled="true"
          >
            {{ loadingText }}
          </el-button>
          <template v-if="isSuccess">
            <slot name="success-actions" :import="handleImport">
              <el-button
                type="primary"
                @click="handleImport"
              >
                {{ importText }}
              </el-button>
            </slot>
            <el-button @click="handleClose">
              {{ doneText }}
            </el-button>
          </template>
        </div>
      </slot>
    </template>
  </el-dialog>
</template>

<script setup lang="ts">
import { ref, computed, watch } from 'vue'
import { FolderOpened } from '@element-plus/icons-vue'
import type { UploadFile } from 'element-plus'

interface Props {
  /** 对话框是否可见 */
  modelValue?: boolean
  /** 文件类型（accept 属性） */
  accept?: string
  /** 支持的最大文件大小（字节） */
  maxFileSize?: number
  /** 上传 API 端点 */
  uploadApi?: string
  /** 解析 API 端点 */
  parseApi?: string
  /** 是否自动上传 */
  autoUpload?: boolean
  /** 自定义标题 */
  dialogTitle?: string
  /** 对话框宽度 */
  dialogWidth?: string | number
  /** 成功消息 */
  successMessage?: string
  /** 错误消息 */
  errorMessage?: string
  /** 上传文本 */
  uploadText?: string
  /** 上传提示文本 */
  uploadTip?: string
  /** 取消按钮文本 */
  cancelText?: string
  /** 导入按钮文本 */
  importText?: string
  /** 完成按钮文本 */
  doneText?: string
  /** 加载中文本 */
  loadingText?: string
  /** 进度文本 */
  progressText?: string
}

const props = withDefaults(defineProps<Props>(), {
  accept: '.stl,.step,.stp,.dxf',
  maxFileSize: 100 * 1024 * 1024, // 100MB
  uploadText: '拖拽文件到此处或点击上传',
  uploadTip: '支持 .stl, .step, .stp, .dxf 格式',
  dialogTitle: '文件导入',
  dialogWidth: '900px',
  successMessage: '导入成功',
  errorMessage: '导入失败',
  cancelText: '取消',
  importText: '导入到项目',
  doneText: '完成',
  loadingText: '上传/解析中...',
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: boolean): void
  (e: 'file-selected', file: File): void
  (e: 'success', parseResult: unknown): void
  (e: 'error', error: Error): void
  (e: 'import', parseResult: unknown): void
}>()

const internalVisible = ref(props.modelValue ?? false)
const selectedFile = ref<File | null>(null)
const parseResult = ref<unknown>(null)
const featureResult = ref<unknown>(null)
const warnings = ref<string[]>([])
const errors = ref<string[]>([])

/** 导入状态机 */
const importState = computed(() => {
  if (internalVisible.value === false) return 'closed'
  if (!selectedFile.value) return 'idle'
  if (isUploading.value) return 'uploading'
  if (isParsing.value) return 'parsing'
  if (isSuccess.value) return 'success'
  if (isError.value) return 'error'
  return 'idle'
})

/** 状态计算 */
const isIdle = computed(() => importState.value === 'idle' || importState.value === 'closed')
const isActive = computed(() => importState.value === 'uploading' || importState.value === 'parsing')
const isUploading = ref(false)
const isParsing = ref(false)
const isSuccess = ref(false)
const isError = ref(false)
const isSelecting = computed(() => isUploading.value || isParsing.value)
const progress = computed(() => {
  if (isUploading.value) return 50
  if (isParsing.value) return 75
  if (isSuccess.value) return 100
  return 0
})

/** 解析错误详情（用于结果区域副标题） */
const parseError = computed(() => errors.value[errors.value.length - 1] ?? props.errorMessage)

/** 监听外部 visible */
watch(
  () => props.modelValue,
  (v) => {
    if (v !== undefined) internalVisible.value = v
  },
)

/** 处理文件选择 */
function handleFileChange(uploadFile: UploadFile) {
  const file = uploadFile.raw
  if (!file) return
  // 文件验证
  if (props.maxFileSize && file.size > props.maxFileSize) {
    errors.value.push(`文件大小超过 ${props.maxFileSize / 1024 / 1024}MB`)
    isError.value = true
    return
  }

  selectedFile.value = file
  emit('file-selected', file)
}

function handleFileRemove() {
  selectedFile.value = null
  resetState()
}

/** 处理文件导入 */
async function handleFileSelected(file: File) {
  selectedFile.value = file
  emit('file-selected', file)

  // 开始导入流程
  await startImportProcess(file)
}

/** 开始导入流程 */
async function startImportProcess(file: File) {
  isError.value = false
  isSuccess.value = false

  try {
    // 1. 上传文件
    if (props.uploadApi) {
      isUploading.value = true
      const uploadData = await uploadFile(file)
      // 2. 解析文件
      isParsing.value = true
      const result = await parseUploadedFile(uploadData)
      // 3. 结果处理
      parseResult.value = result
      featureResult.value = result
      isSuccess.value = true
      emit('success', result)
    } else {
      // 本地模式：直接解析文件
      await resolveLocalFile(file)
      isSuccess.value = true
      emit('success', parseResult.value)
    }
  } catch (err) {
    isError.value = true
    errors.value.push(err instanceof Error ? err.message : '未知错误')
    emit('error', err instanceof Error ? err : new Error('未知错误'))
  } finally {
    isUploading.value = false
    isParsing.value = false
  }
}

/** 上传文件 */
async function uploadFile(file: File): Promise<{ file_id: string; file_name: string }> {
  // 模拟上传，实际实现需要根据后端 API
  return {
    file_id: `file-${Date.now()}`,
    file_name: file.name,
  }
}

/** 解析文件 */
async function parseUploadedFile(uploadData: { file_id: string; file_name: string }): Promise<unknown> {
  // 模拟解析，实际实现需要根据后端 API
  return {
    file_name: uploadData.file_name,
    lines_count: 0,
    arcs_count: 0,
    circles_count: 0,
    warnings: warnings.value,
  }
}

/** 本地模式解析 */
async function resolveLocalFile(file: File) {
  // 使用 FileReader 读取文件内容
  const text = await readFileAsText(file)
  // 根据文件类型和格式进行解析
  // 此处为伪代码
  parseResult.value = {
    file_name: file.name,
    file_size: file.size,
    lines_count: text.split('\n').length,
  }
}

/** 读取文件为文本 */
function readFileAsText(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = (e) => resolve(e.target?.result as string)
    reader.onerror = (e) => reject(e)
    reader.readAsText(file)
  })
}

/** 执行导入操作 */
async function handleImport() {
  if (!parseResult.value) return
  emit('import', parseResult.value)
  resetState()
}

/** 重试 */
function handleRetry() {
  resetState()
  if (selectedFile.value) {
    void startImportProcess(selectedFile.value)
  }
}

/** 关闭对话框 */
function handleClose() {
  internalVisible.value = false
  emit('update:modelValue', false)
  resetState()
}

/** 重置状态 */
function resetState() {
  isSuccess.value = false
  isError.value = false
  parseResult.value = null
  featureResult.value = null
  warnings.value = []
  errors.value = []
}
</script>

<style scoped>
.import-section {
  min-height: 200px;
  padding: 20px;
}

.progress-section {
  padding: 32px 20px;
  text-align: center;
}

.progress-text {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-secondary);
}

.result-section {
  max-height: 60vh;
  overflow-y: auto;
  padding: 0 20px;
}

.warning-section {
  margin-top: 12px;
}

.error-section {
  padding: 32px 20px;
  text-align: center;
}

.footer-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
