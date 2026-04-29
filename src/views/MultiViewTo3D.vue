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
        <el-col :xs="24" :sm="8">
          <div class="upload-section">
            <h3>{{ t('multiView.frontView') }}</h3>
            <el-upload
              class="upload-area"
              drag
              accept="image/*"
              :auto-upload="false"
              :on-change="(file: any) => handleFileChange(file, 'front')"
              :show-file-list="false"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ t('multiView.dragOrClick') }}<em>{{ t('multiView.clickToUpload') }}</em>
              </div>
            </el-upload>
            <img v-if="previewUrls.front" :src="previewUrls.front" class="preview-img" />
          </div>
        </el-col>
        <el-col :xs="24" :sm="8">
          <div class="upload-section">
            <h3>{{ t('multiView.topView') }}</h3>
            <el-upload
              class="upload-area"
              drag
              accept="image/*"
              :auto-upload="false"
              :on-change="(file: any) => handleFileChange(file, 'top')"
              :show-file-list="false"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ t('multiView.dragOrClick') }}<em>{{ t('multiView.clickToUpload') }}</em>
              </div>
            </el-upload>
            <img v-if="previewUrls.top" :src="previewUrls.top" class="preview-img" />
          </div>
        </el-col>
        <el-col :xs="24" :sm="8">
          <div class="upload-section">
            <h3>{{ t('multiView.leftView') }}</h3>
            <el-upload
              class="upload-area"
              drag
              accept="image/*"
              :auto-upload="false"
              :on-change="(file: any) => handleFileChange(file, 'left')"
              :show-file-list="false"
            >
              <el-icon class="el-icon--upload"><UploadFilled /></el-icon>
              <div class="el-upload__text">
                {{ t('multiView.dragOrClick') }}<em>{{ t('multiView.clickToUpload') }}</em>
              </div>
            </el-upload>
            <img v-if="previewUrls.left" :src="previewUrls.left" class="preview-img" />
          </div>
        </el-col>
      </el-row>

      <div class="actions">
        <el-select v-model="outputFormat" :placeholder="t('multiView.outputFormat')" style="width: 150px; margin-right: 16px;">
          <el-option label="STL" value="stl" />
          <el-option label="OBJ" value="obj" />
          <el-option label="GLTF" value="gltf" />
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
import ThreeViewer from '@/components/three/ThreeViewer.vue'
import axios from 'axios'

const { t } = useI18n()

const frontFile = ref<File | null>(null)
const topFile = ref<File | null>(null)
const leftFile = ref<File | null>(null)

const previewUrls = ref({
  front: '',
  top: '',
  left: ''
})

const outputFormat = ref('stl')
const isGenerating = ref(false)
const taskStatus = ref<string | null>(null)
const taskId = ref<string | null>(null)
const progress = ref(0)
const modelUrl = ref<string | null>(null)
const errorMessage = ref('')

let pollingTimer: number | null = null

const canGenerate = computed(() => {
  return frontFile.value && topFile.value && leftFile.value
})

const progressStatus = computed(() => {
  if (taskStatus.value === 'completed') return 'success'
  if (taskStatus.value === 'failed') return 'exception'
  return undefined
})

function handleFileChange(file: any, view: 'front' | 'top' | 'left') {
  const rawFile = file.raw as File
  if (!rawFile) return

  if (view === 'front') frontFile.value = rawFile
  else if (view === 'top') topFile.value = rawFile
  else leftFile.value = rawFile

  const reader = new FileReader()
  reader.onload = (e) => {
    previewUrls.value[view] = e.target?.result as string
  }
  reader.readAsDataURL(rawFile)
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
    formData.append('front_view', frontFile.value!)
    formData.append('top_view', topFile.value!)
    formData.append('left_view', leftFile.value!)
    formData.append('output_format', outputFormat.value)

    const response = await axios.post('/api/cad/three-view-to-3d', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })

    if (response.data.code === 0) {
      taskId.value = response.data.data.task_id
      ElMessage.success(t('multiView.taskCreated'))
      startPolling()
    } else {
      throw new Error(response.data.message)
    }
  } catch (error: any) {
    ElMessage.error(`${t('multiView.taskFailed')}: ${error.message}`)
    isGenerating.value = false
  }
}

function startPolling() {
  if (pollingTimer) clearInterval(pollingTimer)
  
  pollingTimer = window.setInterval(async () => {
    if (!taskId.value) return

    try {
      const response = await axios.get(`/api/cad/tasks/${taskId.value}`)
      
      if (response.data.code === 0) {
        const data = response.data.data
        taskStatus.value = data.status
        progress.value = Math.round(data.progress)

        if (data.status === 'completed') {
          stopPolling()
          isGenerating.value = false
          modelUrl.value = `/api/cad/models/${taskId.value}/download`
          ElMessage.success(t('multiView.generateSuccess'))
        } else if (data.status === 'failed') {
          stopPolling()
          isGenerating.value = false
          errorMessage.value = data.error_message || t('multiView.generateFailed')
          ElMessage.error(errorMessage.value)
        }
      }
    } catch (error) {
      console.error('Polling failed:', error)
    }
  }, 2000)
}

function stopPolling() {
  if (pollingTimer) {
    clearInterval(pollingTimer)
    pollingTimer = null
  }
}

function downloadModel() {
  if (!taskId.value) return
  const url = `/api/cad/models/${taskId.value}/download`
  const a = document.createElement('a')
  a.href = url
  a.download = `model_${taskId.value}.${outputFormat.value}`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
}

onUnmounted(() => {
  stopPolling()
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
