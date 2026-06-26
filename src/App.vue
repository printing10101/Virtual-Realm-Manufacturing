<template>
  <div id="app">
    <SplashScreen v-if="showSplash" @complete="showSplash = false" />
    <el-config-provider :locale="elLocale">
      <el-container class="app-container">
        <el-header class="app-header">
          <div class="header-left">
            <h1 class="app-title">
              {{ $t('app.title') }}
            </h1>
            <span class="app-version">v{{ frontendVersion }}</span>
          </div>

          <div class="header-center">
            <el-menu
              :default-active="activeRoute"
              mode="horizontal"
              router
              class="header-menu"
            >
              <el-menu-item index="/">
                {{ $t('navigation.home') }}
              </el-menu-item>
              <el-menu-item index="/workspace">
                {{ $t('navigation.workspace') }}
              </el-menu-item>
              <el-menu-item index="/settings">
                {{ $t('navigation.settings') }}
              </el-menu-item>
              <el-menu-item index="/about">
                {{ $t('navigation.about') }}
              </el-menu-item>
              <el-menu-item index="/rule-editor">
                <el-icon><Setting /></el-icon>{{ $t('navigation.processRules') }}
              </el-menu-item>
              <el-menu-item index="/toolpath-editor">
                <el-icon><EditPen /></el-icon>{{ $t('navigation.toolpathEdit') }}
              </el-menu-item>
              <el-menu-item index="/process-planning">
                <el-icon><SetUp /></el-icon>{{ $t('navigation.processPlanning') }}
              </el-menu-item>
            </el-menu>
          </div>

          <div class="header-right">
            <BackendStatusIndicator />
            <el-dropdown
              trigger="click"
              @command="handleFileCommand"
            >
              <el-button
                type="default"
                size="small"
              >
                {{ $t('app.fileMenu') }}
                <el-icon class="el-icon--right">
                  <arrow-down />
                </el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="new">
                    <el-icon><document-add /></el-icon>{{ $t('app.newProject') }}
                  </el-dropdown-item>
                  <el-dropdown-item command="open">
                    <el-icon><folder-opened /></el-icon>{{ $t('app.openProject') }}
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="save"
                  >
                    <el-icon><disk /></el-icon>{{ $t('common.save') }}
                  </el-dropdown-item>
                  <el-dropdown-item command="save-as">
                    <el-icon><copy-document /></el-icon>{{ $t('app.saveAs') }}
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="download"
                  >
                    <el-icon><download /></el-icon>{{ $t('app.downloadProject') }}
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="import-step"
                  >
                    <el-icon><upload /></el-icon>{{ $t('app.importStep') }}
                  </el-dropdown-item>
                  <el-dropdown-item command="import-dxf">
                    <el-icon><document-copy /></el-icon>{{ $t('app.importDxf') }}
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>

            <span
              v-if="projectStore.projectName !== $t('app.defaultProjectName')"
              class="project-indicator"
            >
              {{ projectStore.projectName }}
              <el-tag
                v-if="projectStore.isModified"
                size="small"
                type="warning"
                effect="plain"
              >{{ $t('app.modified') }}</el-tag>
            </span>
          </div>
        </el-header>

        <el-main class="app-main">
          <div v-if="!appReady" class="app-initializing">
            <el-icon class="is-loading" :size="28"><loading /></el-icon>
            <span>正在初始化...</span>
          </div>
          <router-view v-else />
        </el-main>
      </el-container>

      <!-- ==================== 新建工程对话框 ==================== -->
      <el-dialog
        v-model="showNewDialog"
        :title="$t('app.newDialogTitle')"
        width="480px"
        :close-on-click-modal="false"
      >
        <el-form
          :model="newForm"
          label-width="80px"
        >
          <el-form-item
            :label="$t('app.projectName')"
            required
          >
            <el-input
              v-model="newForm.name"
              maxlength="128"
              :placeholder="$t('app.projectNamePlaceholder')"
            />
          </el-form-item>
          <el-form-item :label="$t('common.author')">
            <el-input
              v-model="newForm.author"
              maxlength="64"
              :placeholder="$t('app.authorPlaceholder')"
            />
          </el-form-item>
          <el-form-item :label="$t('common.description')">
            <el-input
              v-model="newForm.description"
              type="textarea"
              :rows="3"
              maxlength="512"
              :placeholder="$t('app.descriptionPlaceholder')"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showNewDialog = false">
            {{ $t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            :loading="creating"
            @click="handleCreate"
          >
            {{ $t('app.createProject') }}
          </el-button>
        </template>
      </el-dialog>

      <!-- ==================== 打开工程对话框 ==================== -->
      <el-dialog
        v-model="showOpenDialog"
        :title="$t('app.openDialogTitle')"
        width="600px"
        :close-on-click-modal="false"
      >
        <el-tabs v-model="openTab">
          <el-tab-pane
            :label="$t('app.localTab')"
            name="local"
          >
            <div
              v-if="openListLoading"
              style="text-align:center;padding:20px;"
            >
              <el-icon class="is-loading">
                <loading />
              </el-icon> {{ $t('common.loading') }}
            </div>
            <el-table
              v-else
              :data="projectStore.projectList"
              height="300"
              highlight-current-row
              stripe
              size="small"
              @row-dblclick="handleOpenFromList"
              @current-change="onOpenSelectChange"
            >
              <el-table-column
                prop="name"
                :label="$t('app.projectNameCol')"
                min-width="150"
              />
              <el-table-column
                :label="$t('app.modifiedTimeCol')"
                width="170"
              >
                <template #default="{ row }">
                  {{ formatDate(row.modified_at) }}
                </template>
              </el-table-column>
              <el-table-column
                :label="$t('app.sizeCol')"
                width="90"
              >
                <template #default="{ row }">
                  {{ formatSize(row.file_size) }}
                </template>
              </el-table-column>
              <el-table-column
                :label="$t('app.resourceCol')"
                width="60"
              >
                <template #default="{ row }">
                  {{ row.resource_count }}
                </template>
              </el-table-column>
              <el-table-column
                :label="$t('common.operation')"
                width="120"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    text
                    type="primary"
                    @click="handleOpenFromList(row as ProjectSummary)"
                  >
                    {{ $t('app.open') }}
                  </el-button>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    @click="handleDeleteProject(row as ProjectSummary)"
                  >
                    {{ $t('common.delete') }}
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane
            :label="$t('app.importTab')"
            name="import"
          >
            <el-upload
              drag
              :auto-upload="false"
              :limit="1"
              accept=".vrm"
              :on-change="handleFileSelected"
              :file-list="importFileList"
            >
              <el-icon class="el-icon--upload">
                <upload-filled />
              </el-icon>
              <div class="el-upload__text">
                {{ $t('app.importVrmHint') }} <em>{{ $t('app.importVrmClick') }}</em>
              </div>
            </el-upload>
          </el-tab-pane>
        </el-tabs>
        <template #footer>
          <el-button @click="showOpenDialog = false">
            {{ $t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            :loading="opening"
            :disabled="!canOpen"
            @click="handleOpen"
          >
            {{ $t('app.openProject') }}
          </el-button>
        </template>
      </el-dialog>

      <!-- ==================== 另存为对话框 ==================== -->
      <el-dialog
        v-model="showSaveAsDialog"
        :title="$t('app.saveAsDialogTitle')"
        width="420px"
        :close-on-click-modal="false"
      >
        <el-form
          :model="saveAsForm"
          label-width="80px"
        >
          <el-form-item
            :label="$t('app.fileName')"
            required
          >
            <el-input
              v-model="saveAsForm.outputName"
              maxlength="128"
              :placeholder="$t('app.fileNamePlaceholder')"
            >
              <template #append>
                .vrm
              </template>
            </el-input>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showSaveAsDialog = false">
            {{ $t('common.cancel') }}
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="handleSaveAs"
          >
            {{ $t('app.saveAsBtn') }}
          </el-button>
        </template>
      </el-dialog>

      <!-- ==================== 未保存提示对话框 ==================== -->
      <el-dialog
        v-model="showUnsavedDialog"
        :title="$t('app.unsavedTitle')"
        width="400px"
      >
        <p>{{ $t('app.unsavedMessage') }}</p>
        <template #footer>
          <el-button @click="discardAndProceed">
            {{ $t('common.discard') }}
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="saveAndProceed"
          >
            {{ $t('common.saveAndContinue') }}
          </el-button>
          <el-button @click="cancelProceed">
            {{ $t('common.cancel') }}
          </el-button>
        </template>
      </el-dialog>

      <StepImportDialog />
      <DxfImportDialog />
      <ErrorConflictDialog />
      <BackendStartupDialog v-if="showStartupDialog" v-model="showStartupDialog" />
    </el-config-provider>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, inject, ref, reactive, watch, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useVersionStore } from '@/stores/version'
import { useProjectStore } from '@/stores/project'
import { useAuthStore } from '@/stores/auth'
import { useStepImportStore } from '@/stores/stepImport'
import { useDxfImportStore } from '@/stores/dxfImport'
import StepImportDialog from '@/components/step_import/StepImportDialog.vue'
import DxfImportDialog from '@/components/dxf_import/DxfImportDialog.vue'
import ErrorConflictDialog from '@/components/ErrorConflictDialog.vue'
import BackendStatusIndicator from '@/components/BackendStatusIndicator.vue'
import BackendStartupDialog from '@/components/BackendStartupDialog.vue'
import SplashScreen from '@/components/SplashScreen.vue'
import { useBackendStatus } from '@/composables/useBackendStatus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import type { ProjectSummary } from '@/types'

const route = useRoute()
const activeRoute = computed(() => route.path)
const authStore = useAuthStore()

const elLocaleRef = inject<Ref<typeof zhCn>>('locale', ref(zhCn))
const elLocale = computed(() => elLocaleRef.value)

const versionStore = useVersionStore()
const frontendVersion = computed(() => versionStore.frontendVersion)
const projectStore = useProjectStore()
const stepImportStore = useStepImportStore()
const dxfImportStore = useDxfImportStore()

// 启动动画
const showSplash = ref(true)
// 应用初始化完成标志（auto-login 完成后才渲染路由页面）
const appReady = ref(false)

// 后端进程状态监听
const { state: backendState, tauriMode } = useBackendStatus()
const showStartupDialog = ref(false)

watch(
  () => backendState.status,
  (status) => {
    if (!tauriMode.value) return
    if (status === 'starting' || status === 'failed' || status === 'crashed') {
      showStartupDialog.value = true
    } else if (status === 'running' || status === 'stopped') {
      showStartupDialog.value = false
    }
  },
  { immediate: true },
)

const showNewDialog = ref(false)
const showOpenDialog = ref(false)
const showSaveAsDialog = ref(false)
const showUnsavedDialog = ref(false)
const creating = ref(false)
const opening = ref(false)
const saving = ref(false)
const openListLoading = ref(false)
const openTab = ref('local')

const newForm = reactive({ name: '', author: '', description: '' })
const saveAsForm = reactive({ outputName: '' })
const importFileList = ref<any[]>([])
const selectedSummary = ref<ProjectSummary | null>(null)
const pendingFileCommand = ref('')

const canOpen = computed(() => {
  if (openTab.value === 'local') return selectedSummary.value !== null
  return importFileList.value.length > 0
})

onMounted(async () => {
  // 自动登录：桌面应用启动时自动获取 token（每次都重新登录确保 token 有效）
  try {
    await authStore.login('admin', 'admin123')
  } catch {
    // 登录失败不影响应用启动
  }
  appReady.value = true
  await versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
})

function formatDate(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  const locale = localStorage.getItem('app_locale') || 'zh-CN'
  return d.toLocaleString(locale === 'en' ? 'en-US' : 'zh-CN', { hour12: false })
}

function formatSize(bytes: number) {
  if (!bytes) return '0 B'
  const units = ['B', 'KB', 'MB', 'GB']
  let i = 0
  let s = bytes
  while (s >= 1024 && i < units.length - 1) { s /= 1024; i++ }
  return s.toFixed(i > 0 ? 1 : 0) + ' ' + units[i]
}

function handleFileCommand(cmd: string) {
  if (projectStore.isModified && (cmd === 'new' || cmd === 'open')) {
    pendingFileCommand.value = cmd
    showUnsavedDialog.value = true
    return
  }
  executeCommand(cmd)
}

function executeCommand(cmd: string) {
  switch (cmd) {
    case 'new':
      newForm.name = ''; newForm.author = ''; newForm.description = ''
      showNewDialog.value = true
      break
    case 'open':
      openTab.value = 'local'
      selectedSummary.value = null
      importFileList.value = []
      openListLoading.value = true
      projectStore.fetchProjectList().finally(() => { openListLoading.value = false })
      showOpenDialog.value = true
      break
    case 'save':
      saving.value = true
      projectStore.saveProject().finally(() => { saving.value = false })
      break
    case 'save-as':
      saveAsForm.outputName = projectStore.projectName
      showSaveAsDialog.value = true
      break
    case 'download':
      if (projectStore.currentFilePath) {
        projectStore.downloadProject(
          projectStore.currentFilePath.split('/').pop() ||
          projectStore.currentFilePath.split('\\').pop() || 'project.vrm'
        )
      }
      break
    case 'import-step':
      stepImportStore.showDialog = true
      break
    case 'import-dxf':
      dxfImportStore.openDialog()
      break
  }
}

async function handleCreate() {
  if (!newForm.name.trim()) return
  creating.value = true
  const ok = await projectStore.createProject({
    name: newForm.name.trim(),
    author: newForm.author.trim(),
    description: newForm.description.trim(),
  })
  creating.value = false
  if (ok) showNewDialog.value = false
}

function onOpenSelectChange(row: ProjectSummary | null) {
  selectedSummary.value = row
}

async function handleOpenFromList(row: ProjectSummary) {
  opening.value = true
  const ok = await projectStore.openProject(row.path)
  opening.value = false
  if (ok) showOpenDialog.value = false
}

function handleFileSelected(file: { raw?: File }) {
  importFileList.value = [{ raw: file.raw }] as Array<{ raw?: File }>
}

async function handleOpen() {
  if (openTab.value === 'local' && selectedSummary.value) {
    opening.value = true
    const ok = await projectStore.openProject(selectedSummary.value.path)
    opening.value = false
    if (ok) showOpenDialog.value = false
  } else if (openTab.value === 'import' && importFileList.value[0]?.raw) {
    opening.value = true
    const file = importFileList.value[0].raw
    const reader = new FileReader()
    reader.onload = async () => {
      const base64 = (reader.result as string).split(',')[1]
      const ok = await projectStore.openProject(undefined, base64)
      opening.value = false
      if (ok) showOpenDialog.value = false
    }
    reader.readAsDataURL(file)
  }
}

async function handleSaveAs() {
  if (!saveAsForm.outputName.trim()) return
  saving.value = true
  const ok = await projectStore.saveAsProject(saveAsForm.outputName.trim() + '.vrm')
  saving.value = false
  if (ok) showSaveAsDialog.value = false
}

async function handleDeleteProject(row: ProjectSummary) {
  await projectStore.deleteProject(row.name + '.vrm')
  await projectStore.fetchProjectList()
}

function discardAndProceed() {
  projectStore.isModified = false
  showUnsavedDialog.value = false
  executeCommand(pendingFileCommand.value)
}

async function saveAndProceed() {
  saving.value = true
  await projectStore.saveProject()
  saving.value = false
  showUnsavedDialog.value = false
  executeCommand(pendingFileCommand.value)
}

function cancelProceed() {
  showUnsavedDialog.value = false
  pendingFileCommand.value = ''
}
</script>

<style>
#app {
  font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-primary);
  background-color: var(--bg-primary);
}

.app-container {
  min-height: 100vh;
  background-color: var(--bg-primary);
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--border-light);
  background-color: var(--bg-card);
  gap: 16px;
  padding: 0 24px;
  height: 60px;
  box-shadow: var(--shadow-sm);
}

.app-title {
  margin: 0;
  font-size: 1.25rem;
  font-weight: 600;
  white-space: nowrap;
  color: var(--text-primary);
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-shrink: 0;
}

.app-version {
  font-size: 0.75rem;
  color: var(--text-tertiary);
  white-space: nowrap;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.header-menu {
  border-bottom: none;
  background: transparent;
}

.header-menu .el-menu-item {
  font-weight: 500;
  transition: all var(--transition-fast);
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.project-indicator {
  font-size: 13px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: 6px;
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.app-main {
  padding: 24px;
  background-color: var(--bg-primary);
}

.app-initializing {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 300px;
  gap: 16px;
  color: var(--text-tertiary);
  font-size: 14px;
}
</style>
