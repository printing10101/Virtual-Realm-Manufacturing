<template>
  <div class="settings-view">
    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('settings.title') }}</h2>
          <el-button :loading="isSaving" @click="handleSaveAll">
            {{ t('settings.save') }}
          </el-button>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('settings.aiMode')" name="ai">
          <el-form :model="aiForm" label-width="140px" class="ai-form">
            <el-form-item :label="t('settings.aiMode')">
              <el-radio-group v-model="aiForm.mode">
                <el-radio-button value="local">{{ t('settings.localModel') }}</el-radio-button>
                <el-radio-button value="cloud">{{ t('settings.cloudModel') }}</el-radio-button>
                <el-radio-button value="rule">{{ t('settings.offlineMode') }}</el-radio-button>
              </el-radio-group>
            </el-form-item>

            <div v-if="aiForm.mode === 'local'">
              <el-divider>{{ t('settings.localModelSettings') }}</el-divider>

              <el-alert
                v-if="ollamaStatus"
                :type="ollamaStatus.available ? 'success' : 'error'"
                :title="ollamaStatus.available ? t('settings.ollamaRunning') : t('settings.ollamaNotRunning')"
                :description="ollamaStatus.available
                  ? `${t('settings.ollamaVersion')}: ${ollamaStatus.version} | ${t('settings.ollamaUrl')}: ${ollamaStatus.base_url}`
                  : t('settings.ollamaNotRunningDesc')"
                show-icon
                :closable="false"
                class="status-alert"
              />

              <el-form-item :label="t('settings.installedModels')">
                <el-table :data="installedModels" style="width: 100%" :empty-text="t('settings.noInstalledModels')">
                  <el-table-column prop="name" :label="t('settings.modelName')" />
                  <el-table-column prop="size" :label="t('settings.modelSize')" width="120" />
                  <el-table-column :label="t('settings.actions')" width="120">
                    <template #default="scope">
                      <el-popconfirm
                        :title="`${t('settings.confirmDelete')} ${scope.row.name}?`"
                        @confirm="handleDeleteModel(scope.row.name)"
                      >
                        <template #reference>
                          <el-button type="danger" size="small" :disabled="isDeleting">{{ t('settings.delete') }}</el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </el-table-column>
                </el-table>
              </el-form-item>

              <el-form-item :label="t('settings.recommendedModels')">
                <el-table :data="recommendedModels" style="width: 100%" :empty-text="t('settings.noRecommendedModels')">
                  <el-table-column prop="name" :label="t('settings.modelName')" />
                  <el-table-column prop="size" :label="t('settings.modelSize')" width="120" />
                  <el-table-column prop="category" :label="t('settings.modelCategory')" width="100" />
                  <el-table-column :label="t('settings.actions')" width="140">
                    <template #default="scope">
                      <el-button
                        type="primary"
                        size="small"
                        :disabled="isModelInstalled(scope.row.name) || downloadingModel === scope.row.name"
                        @click="handlePullModel(scope.row.name)"
                      >
                        {{ downloadingModel === scope.row.name ? t('settings.downloading') : t('settings.download') }}
                      </el-button>
                    </template>
                  </el-table-column>
                </el-table>
              </el-form-item>

              <div v-if="downloadProgress !== null" class="download-progress">
                <el-progress
                  :percentage="Math.min(100, Math.round((downloadProgress ?? 0) * 100))"
                  :status="downloadProgress >= 1 ? 'success' : undefined"
                />
                <span class="progress-text">{{ downloadStatusText }}</span>
              </div>

              <el-divider>{{ t('settings.gpuInfo') }}</el-divider>

              <el-form-item :label="t('settings.gpuInfo')">
                <div v-if="gpuInfo" class="gpu-info">
                  <el-tag>{{ t('settings.ollamaVersion') }}: {{ gpuInfo.ollama_version }}</el-tag>
                  <el-tag>{{ t('settings.gpuCount') }}: {{ gpuInfo.gpu_count }}</el-tag>
                  <el-table :data="gpuInfo.gpus" style="width: 100%; margin-top: 10px" :empty-text="t('settings.noGpuDetected')">
                    <el-table-column prop="index" :label="t('settings.gpuIndex')" width="80" />
                    <el-table-column prop="name" :label="t('settings.gpuName')" />
                    <el-table-column prop="memory_total" :label="t('settings.gpuMemoryTotal')" width="140" />
                    <el-table-column prop="memory_free" :label="t('settings.gpuMemoryFree')" width="140" />
                  </el-table>
                </div>
                <el-button @click="loadGpuInfo" :loading="isLoadingGpu">{{ t('settings.refreshGpuInfo') }}</el-button>
              </el-form-item>
            </div>

            <div v-if="aiForm.mode === 'cloud'">
              <el-divider>{{ t('settings.cloudApiSettings') }}</el-divider>

              <el-form-item :label="t('settings.cloudApiKey')">
                <el-input
                  v-model="aiForm.cloud_api_key"
                  type="password"
                  show-password
                  :placeholder="t('settings.cloudApiKeyPlaceholder')"
                />
              </el-form-item>

              <el-form-item :label="t('settings.cloudApiBaseUrl')">
                <el-input
                  v-model="aiForm.cloud_base_url"
                  :placeholder="t('settings.cloudApiUrlPlaceholder')"
                />
              </el-form-item>

              <el-form-item :label="t('settings.cloudModel')">
                <el-input
                  v-model="aiForm.cloud_model"
                  :placeholder="t('settings.cloudModelPlaceholder')"
                />
              </el-form-item>
            </div>

            <div v-if="aiForm.mode === 'rule'">
              <el-alert
                type="info"
                :title="t('settings.ruleModeInfo')"
                :closable="false"
                show-icon
              />
            </div>
          </el-form>
        </el-tab-pane>

        <el-tab-pane :label="t('settings.generalSettings')" name="general">
          <el-form :model="settingsForm" label-width="140px" class="general-form">
            <el-form-item :label="t('settings.language')">
              <el-select v-model="settingsForm.language" @change="handleLanguageChange">
                <el-option label="中文" value="zh-CN" />
                <el-option label="English" value="en-US" />
              </el-select>
            </el-form-item>

            <el-form-item :label="t('settings.theme')">
              <el-switch
                v-model="settingsForm.darkMode"
                :active-text="t('settings.darkMode')"
                :inactive-text="t('settings.lightMode')"
                @change="handleThemeChange"
              />
            </el-form-item>

            <el-form-item :label="t('settings.pythonBackendUrl')">
              <el-input
                v-model="settingsForm.pythonBackendUrl"
                @blur="handlePythonBackendUrlChange"
              />
            </el-form-item>

            <el-form-item :label="t('settings.ollamaUrl')">
              <el-input
                v-model="settingsForm.ollamaUrl"
                @blur="handleOllamaUrlChange"
              />
            </el-form-item>

            <el-form-item :label="t('settings.autoSave')">
              <el-switch v-model="settingsForm.autoSave" @change="handleAutoSaveChange" />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '@/stores/settingsStore'
import { ElMessage } from 'element-plus'
import * as ollama from '@/services/ollama'
import { DEFAULT_SETTINGS } from '@/constants'
import { handleError } from '@/utils/errorHandler'

const { t, locale } = useI18n()
const settingsStore = useSettingsStore()

const activeTab = ref('ai')
const isSaving = ref(false)
const isDeleting = ref(false)
const isLoadingGpu = ref(false)

interface SettingsForm {
  language: string
  darkMode: boolean
  autoSave: boolean
  pythonBackendUrl: string
  ollamaUrl: string
}

const settingsForm = reactive<SettingsForm>({
  language: DEFAULT_SETTINGS.LANGUAGE,
  darkMode: DEFAULT_SETTINGS.THEME === 'dark',
  autoSave: DEFAULT_SETTINGS.AUTO_SAVE,
  pythonBackendUrl: DEFAULT_SETTINGS.PYTHON_BACKEND_URL,
  ollamaUrl: DEFAULT_SETTINGS.OLLAMA_URL
})

interface AiForm {
  mode: 'local' | 'cloud' | 'rule'
  cloud_api_key: string
  cloud_base_url: string
  cloud_model: string
}

const aiForm = reactive<AiForm>({
  mode: 'local',
  cloud_api_key: '',
  cloud_base_url: DEFAULT_SETTINGS.CLOUD_BASE_URL,
  cloud_model: DEFAULT_SETTINGS.CLOUD_MODEL,
})

const ollamaStatus = ref<ollama.OllamaStatus | null>(null)
const installedModels = ref<ollama.OllamaModel[]>([])
const recommendedModels = ref<ollama.RecommendedModel[]>([])
const gpuInfo = ref<ollama.GpuInfo | null>(null)
const downloadingModel = ref<string | null>(null)
const downloadProgress = ref<number | null>(null)
const downloadStatusText = ref('')

onMounted(async () => {
  await loadSettingsToForm()
  await Promise.allSettled([
    loadOllamaStatus(),
    loadInstalledModels(),
    loadRecommendedModels(),
  ])
})

async function loadSettingsToForm() {
  await settingsStore.loadSettings()
  settingsForm.language = settingsStore.settings.language
  settingsForm.darkMode = settingsStore.settings.theme === 'dark'
  settingsForm.autoSave = settingsStore.settings.auto_save
  settingsForm.pythonBackendUrl = settingsStore.settings.python_backend_url
  settingsForm.ollamaUrl = settingsStore.settings.ollama_url
}

const isModelInstalled = (modelName: string): boolean => {
  return installedModels.value.some(m => m.name === modelName || m.name.startsWith(`${modelName}:`))
}

const handleLanguageChange = (lang: string) => {
  locale.value = lang
  settingsStore.updateSetting('language', lang)
}

const handleThemeChange = (darkMode: boolean) => {
  settingsStore.updateSetting('theme', darkMode ? 'dark' : 'light')
}

const handleAutoSaveChange = (autoSave: boolean) => {
  settingsStore.updateSetting('auto_save', autoSave)
}

const handlePythonBackendUrlChange = () => {
  settingsStore.updateSetting('python_backend_url', settingsForm.pythonBackendUrl)
}

const handleOllamaUrlChange = async () => {
  settingsStore.updateSetting('ollama_url', settingsForm.ollamaUrl)
  await loadOllamaStatus()
}

const loadOllamaStatus = async () => {
  try {
    ollamaStatus.value = await ollama.getOllamaStatus()
  } catch {
    ollamaStatus.value = null
  }
}

const loadInstalledModels = async () => {
  try {
    const result = await ollama.listModels()
    installedModels.value = result.models
  } catch {
    installedModels.value = []
  }
}

const loadRecommendedModels = async () => {
  try {
    const result = await ollama.getRecommendedModels()
    recommendedModels.value = result.models
  } catch {
    recommendedModels.value = []
  }
}

const loadGpuInfo = async () => {
  isLoadingGpu.value = true
  try {
    gpuInfo.value = await ollama.getGpuInfo()
  } catch (error) {
    gpuInfo.value = null
    handleError(error)
  } finally {
    isLoadingGpu.value = false
  }
}

const handlePullModel = async (modelName: string) => {
  downloadingModel.value = modelName
  downloadProgress.value = 0
  downloadStatusText.value = t('settings.startingDownload')
  try {
    await ollama.pullModel(modelName, (progress) => {
      if (progress.progress !== null) {
        downloadProgress.value = progress.progress
      }
      downloadStatusText.value = progress.status
      if (progress.progress !== null && progress.progress >= 1) {
        downloadProgress.value = 1
        downloadStatusText.value = t('settings.downloadComplete')
      }
    })
    ElMessage.success(`${modelName} ${t('settings.downloadSuccess')}`)
    await Promise.allSettled([loadInstalledModels(), loadRecommendedModels()])
  } catch (error) {
    handleError(error)
  } finally {
    downloadingModel.value = null
    downloadProgress.value = null
    downloadStatusText.value = ''
  }
}

const handleDeleteModel = async (modelName: string) => {
  isDeleting.value = true
  try {
    await ollama.deleteModel(modelName)
    ElMessage.success(`${modelName} ${t('settings.deleteSuccess')}`)
    await Promise.allSettled([loadInstalledModels(), loadRecommendedModels()])
  } catch (error) {
    handleError(error)
  } finally {
    isDeleting.value = false
  }
}

const handleSaveAll = async () => {
  isSaving.value = true
  try {
    await settingsStore.saveSettings()
    ElMessage.success(t('settings.settingsSaved'))
  } catch (error) {
    handleError(error)
  } finally {
    isSaving.value = false
  }
}
</script>

<style scoped lang="scss">
.settings-view {
  .settings-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h2 {
        margin: 0;
        font-size: 20px;
        color: #303133;
      }
    }
  }

  .ai-form, .general-form {
    max-width: 800px;
  }

  .status-alert {
    margin-bottom: 20px;
  }

  .download-progress {
    margin: 16px 0;
    padding: 12px;
    background-color: #f5f7fa;
    border-radius: 8px;

    .progress-text {
      display: block;
      margin-top: 8px;
      font-size: 12px;
      color: #909399;
    }
  }

  .gpu-info {
    .el-tag {
      margin-right: 8px;
      margin-bottom: 8px;
    }
  }
}

@media (max-width: 768px) {
  .settings-view {
    .settings-card {
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
      }
    }
  }
}
</style>
