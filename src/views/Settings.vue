<template>
  <div class="settings-view">
    <el-card class="settings-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('settings.title') }}</h2>
        </div>
      </template>

      <el-tabs v-model="activeTab">
        <el-tab-pane :label="t('settings.aiMode')" name="ai">
          <el-form :model="aiForm" label-width="140px" class="ai-form">
            <el-form-item :label="t('settings.aiMode')">
              <el-radio-group v-model="aiForm.mode" @change="handleAiModeChange">
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
                <el-table :data="installedModels" style="width: 100%" empty-text="暂无已安装模型">
                  <el-table-column prop="name" :label="t('settings.modelName')" />
                  <el-table-column prop="size" :label="t('settings.modelSize')" width="120" />
                  <el-table-column :label="t('settings.actions')" width="120">
                    <template #default="scope">
                      <el-popconfirm
                        :title="`${t('settings.confirmDelete')}${scope.row.name}?`"
                        @confirm="handleDeleteModel(scope.row.name)"
                      >
                        <template #reference>
                          <el-button type="danger" size="small">{{ t('settings.delete') }}</el-button>
                        </template>
                      </el-popconfirm>
                    </template>
                  </el-table-column>
                </el-table>
              </el-form-item>

              <el-form-item :label="t('settings.recommendedModels')">
                <el-table :data="recommendedModels" style="width: 100%" empty-text="暂无推荐模型">
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
                  :percentage="Math.round(downloadProgress * 100)"
                  :status="downloadProgress >= 1 ? 'success' : undefined"
                />
                <span class="progress-text">{{ downloadStatusText }}</span>
              </div>

              <el-divider>{{ t('settings.gpuInfo') }}</el-divider>

              <el-form-item :label="t('settings.gpuInfo')">
                <div v-if="gpuInfo" class="gpu-info">
                  <el-tag>{{ t('settings.ollamaVersion') }}: {{ gpuInfo.ollama_version }}</el-tag>
                  <el-tag>{{ t('settings.gpuCount') }}: {{ gpuInfo.gpu_count }}</el-tag>
                  <el-table :data="gpuInfo.gpus" style="width: 100%; margin-top: 10px" empty-text="未检测到 GPU">
                    <el-table-column prop="index" :label="t('settings.gpuIndex')" width="80" />
                    <el-table-column prop="name" :label="t('settings.gpuName')" />
                    <el-table-column prop="memory_total" :label="t('settings.gpuMemoryTotal')" width="140" />
                    <el-table-column prop="memory_free" :label="t('settings.gpuMemoryFree')" width="140" />
                  </el-table>
                </div>
                <el-button @click="loadGpuInfo">{{ t('settings.refreshGpuInfo') }}</el-button>
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

            <el-form-item>
              <el-button type="primary" @click="handleSaveAiSettings">{{ t('settings.save') }}</el-button>
            </el-form-item>
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
              />
            </el-form-item>
          </el-form>
        </el-tab-pane>
      </el-tabs>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, watch } from 'vue'
import { useI18n } from 'vue-i18n'
import { useAppStore } from '@/stores/app'
import { useSettingsStore } from '@/stores/settingsStore'
import { ElMessage } from 'element-plus'
import * as ollama from '@/services/ollama'

const { t, locale } = useI18n()
const appStore = useAppStore()
const settingsStore = useSettingsStore()

const activeTab = ref('ai')

const settingsForm = reactive({
  language: 'zh-CN',
  darkMode: false,
  autoSave: true,
  pythonBackendUrl: 'http://localhost:8000',
  ollamaUrl: 'http://localhost:11434',
  defaultModel: 'qwen2.5-coder:7b'
})

watch(() => settingsStore.settings, (newSettings) => {
  settingsForm.language = newSettings.language
  settingsForm.darkMode = newSettings.theme === 'dark'
  settingsForm.autoSave = newSettings.auto_save
  settingsForm.pythonBackendUrl = newSettings.python_backend_url
  settingsForm.ollamaUrl = newSettings.ollama_url
  settingsForm.defaultModel = newSettings.default_model
}, { deep: true, immediate: true })

const aiForm = reactive({
  mode: 'local',
  cloud_api_key: '',
  cloud_base_url: 'https://api.openai.com/v1',
  cloud_model: 'gpt-3.5-turbo',
})

const ollamaStatus = ref<ollama.OllamaStatus | null>(null)
const installedModels = ref<ollama.OllamaModel[]>([])
const recommendedModels = ref<ollama.RecommendedModel[]>([])
const gpuInfo = ref<ollama.GpuInfo | null>(null)
const downloadingModel = ref<string | null>(null)
const downloadProgress = ref<number | null>(null)
const downloadStatusText = ref('')

const isModelInstalled = (modelName: string) => {
  return installedModels.value.some(m => m.name === modelName)
}

const handleLanguageChange = (lang: string) => {
  locale.value = lang
  appStore.setLanguage(lang)
  settingsStore.updateSetting('language', lang)
}

const handleThemeChange = (darkMode: boolean) => {
  appStore.currentTheme = darkMode ? 'dark' : 'light'
  settingsStore.updateSetting('theme', darkMode ? 'dark' : 'light')
}

const handleAutoSaveChange = (autoSave: boolean) => {
  settingsStore.updateSetting('auto_save', autoSave)
}

const handlePythonBackendUrlChange = (url: string) => {
  settingsStore.updateSetting('python_backend_url', url)
}

const handleOllamaUrlChange = (url: string) => {
  settingsStore.updateSetting('ollama_url', url)
}

const handleDefaultModelChange = (model: string) => {
  settingsStore.updateSetting('default_model', model)
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
  try {
    gpuInfo.value = await ollama.getGpuInfo()
  } catch {
    gpuInfo.value = null
    ElMessage.error(t('settings.gpuInfoLoadFailed'))
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
    await loadInstalledModels()
  } catch (e: any) {
    ElMessage.error(`${t('settings.downloadFailed')}: ${e.message}`)
  } finally {
    downloadingModel.value = null
    downloadProgress.value = null
    downloadStatusText.value = ''
  }
}

const handleDeleteModel = async (modelName: string) => {
  try {
    await ollama.deleteModel(modelName)
    ElMessage.success(`${modelName} ${t('settings.deleteSuccess')}`)
    await loadInstalledModels()
  } catch (e: any) {
    ElMessage.error(`${t('settings.deleteFailed')}: ${e.message}`)
  }
}

const handleAiModeChange = () => {
}

const handleSaveAiSettings = () => {
  ElMessage.success(t('settings.settingsSaved'))
}

onMounted(async () => {
  await settingsStore.loadSettings()
  await loadOllamaStatus()
  await loadInstalledModels()
  await loadRecommendedModels()
  await loadGpuInfo()
})
</script>

<style scoped lang="scss">
.settings-view {
  .settings-card {
    .card-header {
      h2 {
        margin: 0;
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
    border-radius: 4px;

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
</style>
