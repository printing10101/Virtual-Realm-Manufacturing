<template>
  <div class="document-view">
    <el-card class="view-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('document.title') }}</h2>
          <el-button
            size="small"
            @click="goBack"
          >
            <el-icon><Back /></el-icon>
            {{ t('document.back') }}
          </el-button>
        </div>
      </template>

      <el-alert
        v-if="selectedPlanId"
        :title="t('document.selectedPlan') + ': ' + selectedPlanId"
        type="info"
        :closable="false"
        show-icon
        style="margin-bottom: 20px"
      />

      <div
        v-if="!currentDocId"
        class="template-selection"
      >
        <h3>{{ t('document.selectTemplate') }}</h3>
        <el-row
          :gutter="20"
          class="template-cards"
        >
          <el-col
            v-for="template in templates"
            :key="template.id"
            :span="8"
          >
            <el-card
              :class="['template-card', { active: selectedTemplate === template.id }]"
              shadow="hover"
              @click="selectedTemplate = template.id"
            >
              <div class="template-content">
                <el-icon
                  class="template-icon"
                  :size="40"
                >
                  <component :is="getTemplateIcon(template.id)" />
                </el-icon>
                <h4>{{ template.name }}</h4>
                <p>{{ template.description }}</p>
                <el-tag
                  size="small"
                  type="info"
                >
                  {{ template.metadata?.layout }}
                </el-tag>
              </div>
            </el-card>
          </el-col>
        </el-row>

        <div class="action-buttons">
          <el-button
            type="primary"
            size="large"
            :loading="isGenerating"
            :disabled="!selectedTemplate"
            @click="handleGenerate"
          >
            {{ isGenerating ? t('document.generating') : t('document.generate') }}
          </el-button>
          <el-button
            type="success"
            size="large"
            :loading="isGeneratingAll"
            :disabled="!selectedPlanId"
            @click="handleGenerateAll"
          >
            {{ t('document.generateAll') }}
          </el-button>
        </div>
      </div>

      <div
        v-if="currentDocId && documentContent"
        class="document-preview"
      >
        <div class="preview-toolbar">
          <el-button-group>
            <el-button
              :icon="Back"
              @click="currentDocId = ''"
            >
              {{ t('document.selectTemplate') }}
            </el-button>
            <el-button
              :type="isEditing ? 'success' : ''"
              @click="isEditing = !isEditing"
            >
              {{ isEditing ? t('document.viewMode') : t('document.editMode') }}
            </el-button>
          </el-button-group>

          <el-button-group>
            <el-button
              :loading="exporting === 'pdf'"
              @click="handleExport('pdf')"
            >
              <el-icon><Download /></el-icon>
              {{ t('document.exportPDF') }}
            </el-button>
            <el-button
              :loading="exporting === 'docx'"
              @click="handleExport('docx')"
            >
              <el-icon><Download /></el-icon>
              {{ t('document.exportDOCX') }}
            </el-button>
          </el-button-group>

          <el-button-group v-if="isEditing">
            <el-button
              type="primary"
              :loading="isSaving"
              @click="handleSave"
            >
              {{ t('document.save') }}
            </el-button>
            <el-button @click="handleCancelEdit">
              {{ t('document.cancel') }}
            </el-button>
          </el-button-group>
        </div>

        <el-row
          :gutter="20"
          class="preview-content"
        >
          <el-col :span="18">
            <el-card
              class="markdown-card"
              shadow="never"
            >
              <template #header>
                <div class="card-title">
                  <span>{{ documentTitle }}</span>
                  <el-tag
                    v-if="isModified"
                    type="warning"
                  >
                    {{ t('document.modified') }}
                  </el-tag>
                </div>
              </template>

              <div
                v-if="isEditing"
                class="editor-area"
              >
                <el-input
                  v-model="editingContent"
                  type="textarea"
                  :rows="30"
                  :placeholder="t('document.editPlaceholder')"
                />
              </div>
              <div
                v-else
                class="markdown-body"
                v-html="renderedMarkdown"
              />
            </el-card>
          </el-col>

          <el-col :span="6">
            <el-card
              class="meta-card"
              shadow="never"
            >
              <template #header>
                <h4>{{ t('document.metaInfo') }}</h4>
              </template>
              <el-descriptions
                :column="1"
                border
                size="small"
              >
                <el-descriptions-item :label="t('document.templateName')">
                  {{ templateName }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('document.createdAt')">
                  {{ createdAt }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('document.updatedAt')">
                  {{ updatedAt }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('document.version')">
                  V{{ version }}
                </el-descriptions-item>
                <el-descriptions-item :label="t('document.planId')">
                  {{ planId }}
                </el-descriptions-item>
              </el-descriptions>
            </el-card>

            <el-card
              class="history-card"
              shadow="never"
              style="margin-top: 16px"
            >
              <template #header>
                <div class="history-header">
                  <h4>{{ t('document.history') }}</h4>
                  <el-button
                    size="small"
                    @click="loadHistory"
                  >
                    <el-icon><Refresh /></el-icon>
                  </el-button>
                </div>
              </template>
              <el-timeline>
                <el-timeline-item
                  v-for="item in historyList"
                  :key="item.doc_id"
                  :timestamp="item.created_at?.slice(0, 19)"
                  placement="top"
                >
                  <el-card
                    shadow="never"
                    class="history-item"
                  >
                    <h5>{{ item.title }}</h5>
                    <p>{{ item.template_name }} - V{{ item.version }}</p>
                    <el-tag
                      v-if="item.is_modified"
                      type="warning"
                      size="small"
                    >
                      {{ t('document.modified') }}
                    </el-tag>
                    <div class="history-actions">
                      <el-button
                        size="small"
                        @click="viewHistory(item.doc_id)"
                      >
                        {{ t('document.preview') }}
                      </el-button>
                      <el-button
                        size="small"
                        @click="createFromHistory(item.doc_id)"
                      >
                        {{ t('document.createFromHistory') }}
                      </el-button>
                    </div>
                  </el-card>
                </el-timeline-item>
              </el-timeline>
            </el-card>
          </el-col>
        </el-row>
      </div>

      <div
        v-if="!currentDocId && !templates.length"
        class="empty-result"
      >
        <el-skeleton
          :rows="3"
          animated
        />
      </div>
    </el-card>

    <el-dialog
      v-model="showExportConfirm"
      :title="t('document.exportTitle')"
      width="400px"
    >
      <p>{{ t('document.exportConfirm', { format: exportFormat.toUpperCase() }) }}</p>
      <template #footer>
        <el-button @click="showExportConfirm = false">
          {{ t('document.cancel') }}
        </el-button>
        <el-button
          type="primary"
          @click="confirmExport"
        >
          {{ t('document.confirm') }}
        </el-button>
      </template>
    </el-dialog>

    <el-dialog
      v-model="showDiffDialog"
      :title="t('document.diffTitle')"
      width="80%"
    >
      <el-row :gutter="20">
        <el-col :span="12">
          <h4>{{ t('document.original') }}</h4>
          <pre class="diff-content">{{ originalContent }}</pre>
        </el-col>
        <el-col :span="12">
          <h4>{{ t('document.modified_content') }}</h4>
          <pre class="diff-content">{{ modifiedContent }}</pre>
        </el-col>
      </el-row>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Back, Download, Refresh, Document, Tickets, FolderChecked } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import { buildApiUrl } from '@/utils/api'
import { useSettingsStore } from '@/stores/settingsStore'
import axios from 'axios'
import MarkdownIt from 'markdown-it'

const { t } = useI18n()
const route = useRoute()
const router = useRouter()
const settingsStore = useSettingsStore()

const md = new MarkdownIt({ html: true, breaks: true, linkify: true })

interface Template {
  id: string
  name: string
  description: string
  metadata?: { layout?: string }
}

interface HistoryItem {
  doc_id: string
  title: string
  template_name: string
  created_at: string
  version: number
  is_modified: boolean
}

const templates = ref<Template[]>([])
const selectedTemplate = ref<string>('')
const currentDocId = ref<string>('')
const documentContent = ref<string>('')
const documentTitle = ref<string>('')
const isGenerating = ref(false)
const isGeneratingAll = ref(false)
const isEditing = ref(false)
const isSaving = ref(false)
const editingContent = ref<string>('')
const originalContent = ref<string>('')
const isModified = ref(false)
const exporting = ref<string>('')
const showExportConfirm = ref(false)
const exportFormat = ref<string>('')
const historyList = ref<HistoryItem[]>([])
const showDiffDialog = ref(false)
const modifiedContent = ref('')

const templateName = computed(() => {
  const t = templates.value.find(t => t.id === selectedTemplate.value)
  return t?.name || ''
})

const createdAt = computed(() => {
  return documentContent.value ? documentContent.value.slice(0, 19) : ''
})

const updatedAt = computed(() => {
  return documentContent.value ? documentContent.value.slice(0, 19) : ''
})

const version = computed(() => {
  return 1
})

const planId = computed(() => {
  return selectedPlanId.value || ''
})

const selectedPlanId = ref<string>(route.query.process_plan_id as string || '')

const renderedMarkdown = computed(() => {
  return md.render(isEditing.value ? editingContent.value : documentContent.value)
})

const getTemplateIcon = (id: string) => {
  const icons: Record<string, any> = {
    process_card: Document,
    work_instruction: Tickets,
    inspection_standard: FolderChecked
  }
  return icons[id] || Document
}

const loadTemplates = async () => {
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.get(buildApiUrl('/api/v1/documents/templates', pythonBackendUrl))
    if (response.data.code === 0) {
      templates.value = response.data.data
    }
  } catch (error) {
    console.error('Failed to load templates:', error)
  }
}

const handleGenerate = async () => {
  if (!selectedTemplate.value) {
    ElMessage.warning(t('document.selectTemplateFirst'))
    return
  }

  isGenerating.value = true
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.post(buildApiUrl('/api/v1/documents/generate', pythonBackendUrl), {
      template_id: selectedTemplate.value,
      process_plan_id: selectedPlanId.value || 'default_plan',
      user_id: 'current_user'
    })

    if (response.data.code === 0) {
      currentDocId.value = response.data.data.doc_id
      await loadDocument(currentDocId.value)
      ElMessage.success(t('document.generateSuccess'))
    } else {
      ElMessage.error(response.data.message || t('document.generateFailed'))
    }
  } catch (error) {
    ElMessage.error(t('document.generateError'))
    console.error(error)
  } finally {
    isGenerating.value = false
  }
}

const handleGenerateAll = async () => {
  if (!selectedPlanId.value) {
    ElMessage.warning(t('document.selectPlanFirst'))
    return
  }

  isGeneratingAll.value = true
  try {
    const templateIds = ['process_card', 'work_instruction', 'inspection_standard']
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'

    for (const templateId of templateIds) {
      await axios.post(buildApiUrl('/api/v1/documents/generate', pythonBackendUrl), {
        template_id: templateId,
        process_plan_id: selectedPlanId.value,
        user_id: 'current_user'
      })
    }

    selectedTemplate.value = 'process_card'
    currentDocId.value = ''
    await handleGenerate()
    ElMessage.success(t('document.generateAllSuccess'))
  } catch (error) {
    ElMessage.error(t('document.generateError'))
    console.error(error)
  } finally {
    isGeneratingAll.value = false
  }
}

const loadDocument = async (docId: string) => {
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.get(buildApiUrl(`/api/v1/documents/${docId}`, pythonBackendUrl))

    if (response.data.code === 0) {
      const data = response.data.data
      documentContent.value = data.content
      documentTitle.value = data.title
      isModified.value = data.is_modified || false
      await loadHistory()
    }
  } catch (error) {
    ElMessage.error(t('document.loadFailed'))
    console.error(error)
  }
}

const loadHistory = async () => {
  if (!currentDocId.value) return

  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.get(buildApiUrl(`/api/v1/documents/${currentDocId.value}/history`, pythonBackendUrl))

    if (response.data.code === 0) {
      historyList.value = response.data.data
    }
  } catch (error) {
    console.error('Failed to load history:', error)
  }
}

const handleExport = async (format: string) => {
  exportFormat.value = format
  showExportConfirm.value = true
}

const confirmExport = async () => {
  showExportConfirm.value = false
  exporting.value = exportFormat.value

  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const url = buildApiUrl(`/api/v1/documents/${currentDocId.value}/${exportFormat.value}`, pythonBackendUrl)

    const response = await axios.get(url, { responseType: 'blob' })

    const blob = new Blob([response.data])
    const downloadUrl = window.URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = downloadUrl
    link.download = `${documentTitle.value}.${exportFormat.value}`
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
    window.URL.revokeObjectURL(downloadUrl)

    ElMessage.success(t('document.exportSuccess', { format: exportFormat.value.toUpperCase() }))
  } catch (error) {
    ElMessage.error(t('document.exportFailed', { format: exportFormat.value.toUpperCase() }))
    console.error(error)
  } finally {
    exporting.value = ''
  }
}

const handleSave = async () => {
  isSaving.value = true
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.put(buildApiUrl(`/api/v1/documents/${currentDocId.value}/update`, pythonBackendUrl), {
      content: editingContent.value
    })

    if (response.data.code === 0) {
      documentContent.value = editingContent.value
      isModified.value = true
      isEditing.value = false
      ElMessage.success(t('document.saveSuccess'))
    } else {
      ElMessage.error(response.data.message || t('document.saveFailed'))
    }
  } catch (error) {
    ElMessage.error(t('document.saveError'))
    console.error(error)
  } finally {
    isSaving.value = false
  }
}

const handleCancelEdit = () => {
  editingContent.value = documentContent.value
  isEditing.value = false
}

const viewHistory = async (docId: string) => {
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.get(buildApiUrl(`/api/v1/documents/${docId}`, pythonBackendUrl))

    if (response.data.code === 0) {
      originalContent.value = response.data.data.content
      modifiedContent.value = documentContent.value
      showDiffDialog.value = true
    }
  } catch (error) {
    ElMessage.error(t('document.loadFailed'))
    console.error(error)
  }
}

const createFromHistory = async (docId: string) => {
  try {
    const pythonBackendUrl = settingsStore.pythonBackendUrl || 'http://localhost:8765'
    const response = await axios.post(buildApiUrl(`/api/v1/documents/${docId}/duplicate`, pythonBackendUrl))

    if (response.data.code === 0) {
      currentDocId.value = response.data.data.doc_id
      await loadDocument(currentDocId.value)
      ElMessage.success(t('document.createFromHistorySuccess'))
    }
  } catch (error) {
    ElMessage.error(t('document.createFromHistoryFailed'))
    console.error(error)
  }
}

const goBack = () => {
  router.push('/comparison')
}

onMounted(() => {
  loadTemplates()

  if (route.query.process_plan_id) {
    selectedPlanId.value = route.query.process_plan_id as string
  }

  if (route.query.template_id) {
    selectedTemplate.value = route.query.template_id as string
    handleGenerate()
  }
})
</script>

<style scoped lang="scss">
.document-view {
  .view-card {
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

    .template-selection {
      h3 {
        margin-bottom: 20px;
        font-size: 16px;
        color: #303133;
      }

      .template-cards {
        margin-bottom: 24px;
      }

      .template-card {
        cursor: pointer;
        transition: all 0.3s;
        border: 2px solid transparent;

        &:hover {
          transform: translateY(-4px);
        }

        &.active {
          border-color: #409EFF;
          background: #ecf5ff;
        }

        .template-content {
          text-align: center;
          padding: 16px;

          .template-icon {
            margin-bottom: 12px;
            color: #409EFF;
          }

          h4 {
            margin: 12px 0;
            font-size: 18px;
            color: #303133;
          }

          p {
            margin: 0 0 12px;
            font-size: 13px;
            color: #909399;
            line-height: 1.5;
          }
        }
      }

      .action-buttons {
        display: flex;
        gap: 12px;
        justify-content: center;
        margin-top: 24px;
      }
    }

    .document-preview {
      .preview-toolbar {
        display: flex;
        justify-content: space-between;
        margin-bottom: 20px;
        flex-wrap: wrap;
        gap: 12px;
      }

      .preview-content {
        .markdown-card {
          min-height: 600px;

          .card-title {
            display: flex;
            justify-content: space-between;
            align-items: center;

            span {
              font-size: 16px;
              font-weight: bold;
              color: #303133;
            }
          }

          .editor-area {
            textarea {
              font-family: 'Consolas', 'Monaco', monospace;
              font-size: 13px;
              line-height: 1.6;
            }
          }

          .markdown-body {
            font-size: 14px;
            line-height: 1.8;
            color: #303133;

            :deep(h1), :deep(h2), :deep(h3) {
              color: #409EFF;
              margin-top: 24px;
              margin-bottom: 12px;
            }

            :deep(table) {
              width: 100%;
              border-collapse: collapse;
              margin: 16px 0;

              th, td {
                border: 1px solid #dcdfe6;
                padding: 8px 12px;
                text-align: left;
              }

              th {
                background-color: #409EFF;
                color: white;
                font-weight: bold;
              }

              tr:nth-child(even) {
                background-color: #f5f7fa;
              }
            }

            :deep(code) {
              background-color: #f5f7fa;
              padding: 2px 6px;
              border-radius: 4px;
              font-family: 'Consolas', 'Monaco', monospace;
            }

            :deep(pre) {
              background-color: #f5f7fa;
              padding: 12px;
              border-radius: 4px;
              overflow-x: auto;
            }
          }
        }

        .meta-card, .history-card {
          :deep(.el-descriptions__label) {
            font-weight: bold;
          }
        }

        .history-card {
          .history-header {
            display: flex;
            justify-content: space-between;
            align-items: center;

            h4 {
              margin: 0;
            }
          }

          .history-item {
            h5 {
              margin: 0 0 8px;
              font-size: 14px;
              color: #303133;
            }

            p {
              margin: 0 0 8px;
              font-size: 12px;
              color: #909399;
            }

            .history-actions {
              display: flex;
              gap: 8px;
              margin-top: 8px;
            }
          }
        }
      }
    }

    .empty-result {
      margin-top: 40px;
      min-height: 200px;
    }
  }
}

.diff-content {
  background: #f5f7fa;
  padding: 12px;
  border-radius: 4px;
  max-height: 400px;
  overflow-y: auto;
  white-space: pre-wrap;
  word-wrap: break-word;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

@media (max-width: 768px) {
  .document-view {
    .view-card {
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
      }

      .template-selection {
        .template-cards {
          .el-col {
            margin-bottom: 12px;
          }
        }

        .action-buttons {
          flex-direction: column;
        }
      }

      .document-preview {
        .preview-toolbar {
          flex-direction: column;
        }
      }
    }
  }
}
</style>
