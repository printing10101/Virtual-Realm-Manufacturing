<template>
  <div class="multi-view-to-3d">
    <el-card class="view-card">
      <template #header>
        <div class="card-header">
          <div class="header-left">
            <h2>{{ t('multiView.title') }}</h2>
            <el-tag type="info" effect="plain">{{ t('multiView.layoutTip') }}</el-tag>
          </div>
        </div>
      </template>
      
      <el-row :gutter="20">
        <el-col v-for="view in (['front', 'top', 'left'] as const)" :key="view" :xs="24" :sm="8">
          <div class="upload-section">
            <h3>{{ t(viewLabels[view]) }}</h3>
            <el-upload
              class="upload-area"
              drag
              accept="image/*"
              :auto-upload="false"
              :on-change="(file: { raw: File }) => handleFileChange(file, view)"
              :show-file-list="false"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ t('multiView.dragOrClick') }}<em>{{ t('multiView.clickToUpload') }}</em>
              </div>
            </el-upload>
            <img v-if="previewUrls[view]" :src="previewUrls[view]" class="preview-img" />
          </div>
        </el-col>
      </el-row>

      <div class="actions">
        <el-select v-model="outputFormat" :placeholder="t('multiView.outputFormat')" style="width: 150px; margin-right: 16px;">
          <el-option v-for="fmt in supportedFormats" :key="fmt" :label="fmt.toUpperCase()" :value="fmt" />
        </el-select>
        <el-button 
          type="primary" 
          :loading="isGenerating" 
          :disabled="!canGenerate"
          @click="startGeneration"
        >
          {{ isGenerating ? t('multiView.generating') : t('multiView.generate3D') }}
        </el-button>
      </div>

      <el-progress 
        v-if="isGenerating || taskStatus"
        :percentage="progress" 
        :status="progressStatus"
        style="margin-top: 20px;"
      />

      <div v-if="taskStatus === 'completed' && modelUrl" class="preview-area">
        <h3>{{ t('multiView.preview3D') }}</h3>
        <ThreeViewer :model-url="modelUrl" :auto-rotate="true" />
        <div class="download-actions">
          <el-button type="success" @click="downloadModel">
            <el-icon><Download /></el-icon>
            {{ t('multiView.downloadModel') }}
          </el-button>
        </div>
      </div>

      <div v-if="taskStatus === 'failed'" class="error-area">
        <el-alert type="error" :title="errorMessage" show-icon :closable="false" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onUnmounted } from 'vue'
import { UploadFilled, Download } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { useI18n } from 'vue-i18n'
import { API_ENDPOINTS, POLLING_CONFIG, DEFAULT_SETTINGS } from '@/constants'
import { buildApiUrl, createTaskPoller } from '@/utils/api'
import ThreeViewer from '@/components/three/ThreeViewer.vue'
import axios from 'axios'
import { handleError } from '@/utils/errorHandler'
import { useSettingsStore } from '@/stores/settingsStore'

const settingsStore = useSettingsStore()

type ViewType = 'front' | 'top' | 'left'

const { t } = useI18n()

const supportedFormats = ['stl', 'obj', 'gltf'] as const

const viewLabels: Record<string, string> = {
  front: 'multiView.frontView',
  top: 'multiView.topView',
  left: 'multiView.leftView',
}

interface ViewFiles {
  front: File | null
  top: File | null
  left: File | null
}

interface PreviewUrls {
  front: string
  top: string
  left: string
}

const uploadedFiles = ref<ViewFiles>({ front: null, top: null, left: null })
const previewUrls = ref<PreviewUrls>({ front: '', top: '', left: '' })
const outputFormat = ref<string>('stl')
const isGenerating = ref(false)
const taskStatus = ref<string | null>(null)
const taskId = ref<string | null>(null)
const progress = ref(0)
const modelUrl = ref<string | null>(null)
const errorMessage = ref('')

let pollerCleanup: (() => void) | null = null

const canGenerate = computed(() => {
  return uploadedFiles.value.front && uploadedFiles.value.top && uploadedFiles.value.left
})

const progressStatus = computed(() => {
  if (taskStatus.value === 'completed') return 'success'
  if (taskStatus.value === 'failed') return 'exception'
  return undefined
})

function handleFileChange(file: { raw: File }, view: ViewType) {
  if (!file.raw) return

  uploadedFiles.value[view] = file.raw

  const reader = new FileReader()
  reader.onload = (e) => {
    previewUrls.value[view] = e.target?.result as string
  }
  reader.readAsDataURL(file.raw)
}

function getPythonBaseUrl(): string {
  return settingsStore.settings.python_backend_url || DEFAULT_SETTINGS.PYTHON_BACKEND_URL
}

async function startGeneration() {
  if (!canGenerate.value) {
    ElMessage.warning(t('multiView.uploadAllViews'))
    return
  }

  isGenerating.value = true
  taskStatus.value = null
  progress.value = 0
  modelUrl.value = null
  errorMessage.value = ''

  try {
    const formData = new FormData()
    formData.append('front_view', uploadedFiles.value.front!)
    formData.append('top_view', uploadedFiles.value.top!)
    formData.append('left_view', uploadedFiles.value.left!)
    formData.append('output_format', outputFormat.value)

    const response = await axios.post(
      buildApiUrl(API_ENDPOINTS.CAD.THREE_VIEW_TO_3D, getPythonBaseUrl()),
      formData,
      { headers: { 'Content-Type': 'multipart/form-data' } }
    )

    if (response.data.code === 0) {
      taskId.value = response.data.data.task_id
      ElMessage.success(t('multiView.taskCreated'))
      startPolling(response.data.data.task_id)
    } else {
      throw new Error(response.data.message)
    }
  } catch (error) {
    handleError(error)
    isGenerating.value = false
  }
}

function startPolling(id: string) {
  const cleanup = createTaskPoller(id, {
    onProgress: (data) => {
      taskStatus.value = data.status
      progress.value = Math.round(data.progress)
    },
    onComplete: (data) => {
      taskStatus.value = 'completed'
      progress.value = 100
      isGenerating.value = false
      modelUrl.value = buildApiUrl(API_ENDPOINTS.CAD.MODEL_DOWNLOAD(id), getPythonBaseUrl())
      ElMessage.success(t('multiView.generateSuccess'))
    },
    onFailed: (data) => {
      taskStatus.value = 'failed'
      isGenerating.value = false
      errorMessage.value = data.error_message || t('multiView.generateFailed')
      ElMessage.error(errorMessage.value)
    },
    onError: () => {},
    intervalMs: POLLING_CONFIG.INTERVAL_MS,
    timeoutMs: POLLING_CONFIG.TIMEOUT_MS,
  }, getPythonBaseUrl())
  pollerCleanup = cleanup
}

function downloadModel() {
  if (!taskId.value) return
  const url = buildApiUrl(API_ENDPOINTS.CAD.MODEL_DOWNLOAD(taskId.value), getPythonBaseUrl())
  const a = document.createElement('a')
  a.href = url
  a.download = `model_${taskId.value}.${outputFormat.value}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

onUnmounted(() => {
  pollerCleanup?.()
})
</script>

<style scoped lang="scss">
.multi-view-to-3d {
  .view-card {
    .card-header {
      .header-left {
        display: flex;
        align-items: center;
        gap: 16px;
        
        h2 {
          margin: 0;
          font-size: 20px;
          color: #303133;
        }
      }
    }
    
    .upload-section {
      h3 {
        margin: 0 0 12px 0;
        font-size: 16px;
        color: #303133;
      }
      
      .upload-area {
        margin-bottom: 12px;
      }
      
      .preview-img {
        width: 100%;
        max-height: 200px;
        object-fit: contain;
        border-radius: 8px;
        border: 1px solid #ebeef5;
        margin-top: 12px;
      }
    }
    
    .actions {
      margin-top: 24px;
      display: flex;
      align-items: center;
    }
    
    .preview-area {
      margin-top: 30px;
      
      h3 {
        margin-bottom: 15px;
        font-size: 18px;
        color: #303133;
      }
      
      .download-actions {
        margin-top: 16px;
        text-align: center;
      }
    }
    
    .error-area {
      margin-top: 20px;
    }
  }
}

@media (max-width: 768px) {
  .multi-view-to-3d {
    .view-card {
      .card-header {
        .header-left {
          flex-direction: column;
          align-items: flex-start;
          gap: 8px;
        }
      }
      
      .actions {
        flex-direction: column;
        gap: 12px;
        
        .el-select {
          width: 100% !important;
          margin-right: 0 !important;
        }
      }
    }
  }
}
</style>
