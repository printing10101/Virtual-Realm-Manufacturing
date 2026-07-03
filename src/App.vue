<template>
  <div id="app">
    <ErrorBoundary>
      <SplashScreen
        v-if="showSplash"
        @complete="showSplash = false"
      />
      <el-config-provider :locale="elLocale">
        <div
          v-if="!appReady"
          class="app-initializing"
        >
          <el-icon
            class="is-loading"
            :size="28"
          >
            <Loading />
          </el-icon>
          <span>{{ $t('splashScreen.statusInit') }}</span>
        </div>
        <AppLayout
          v-else
          :project-name="projectStore.projectName"
          :is-modified="projectStore.isModified"
          @file-command="handleFileCommand"
          @refresh="handleRefresh"
        /><!-- ==================== 新建工程对话框 ==================== -->
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
                  <Loading />
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
                  <UploadFilled />
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
        <BackendStartupDialog
          v-if="showStartupDialog"
          v-model="showStartupDialog"
        />
      </el-config-provider>
    </ErrorBoundary>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, inject, ref, reactive, watch, type Ref } from 'vue'
import { useRouter } from 'vue-router'
import { useVersionStore } from '@/stores/version'
import { useProjectStore } from '@/stores/project'
import { useAuthStore } from '@/stores/auth'
import { useStepImportStore } from '@/stores/stepImport'
import { useDxfImportStore } from '@/stores/dxfImport'
import StepImportDialog from '@/components/step_import/StepImportDialog.vue'
import DxfImportDialog from '@/components/dxf_import/DxfImportDialog.vue'
import ErrorConflictDialog from '@/components/ErrorConflictDialog.vue'
import BackendStartupDialog from '@/components/BackendStartupDialog.vue'
import SplashScreen from '@/components/SplashScreen.vue'
import AppLayout from '@/components/AppLayout.vue'
import { useBackendStatus } from '@/composables/useBackendStatus'
import { Loading, UploadFilled } from '@element-plus/icons-vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import type { ProjectSummary } from '@/types'
import type { UploadUserFile } from 'element-plus'

const router = useRouter()
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
const importFileList = ref<UploadUserFile[]>([])
const selectedSummary = ref<ProjectSummary | null>(null)
const pendingFileCommand = ref('')

const canOpen = computed(() => {
  if (openTab.value === 'local') return selectedSummary.value !== null
  return importFileList.value.length > 0
})

onMounted(async () => {
  // 安全修复 [B7]：删除硬编码凭据 admin/admin123 自动登录。
  // 改为检查已有 token；未登录时由路由守卫引导至登录页，用户手动完成认证。
  // 桌面应用可通过 Tauri sidecar 预置 token，Web 端需用户手动登录。
  try {
    if (!authStore.isAuthenticated) {
      console.info('[App] 未检测到登录态，请通过登录页面完成认证')
    }
  } catch {
    // 检查登录态失败不阻塞应用启动
  }
  appReady.value = true
  // 版本检查不阻塞 UI 渲染，后台静默执行
  versionStore.fetchVersionInfo().catch(() => {})
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

function handleRefresh() {
  // 刷新操作：重新获取版本信息并检查一致性
  versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
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

function handleFileSelected(file: { raw?: File; name?: string }) {
  if (!file.raw) {
    importFileList.value = []
    return
  }
  importFileList.value = [{
    name: file.name ?? file.raw.name,
    raw: file.raw,
  }] as UploadUserFile[]
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
  font-family: inherit;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: var(--text-primary);
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
