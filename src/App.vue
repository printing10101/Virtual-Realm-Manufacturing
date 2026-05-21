<template>
  <div id="app">
    <el-config-provider :locale="elLocale">
      <el-container class="app-container">
        <el-header class="app-header">
          <div class="header-left">
            <h1 class="app-title">
              {{ title }}
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
              <el-menu-item
                v-permission="'system:config'"
                index="/settings"
              >
                {{ $t('navigation.settings') }}
              </el-menu-item>
              <el-menu-item index="/about">
                {{ $t('navigation.about') }}
              </el-menu-item>
              <el-menu-item
                v-permission="'rule:edit'"
                index="/rule-editor"
              >
                <el-icon><Setting /></el-icon>工艺规则
              </el-menu-item>
              <el-menu-item
                v-permission="'toolpath:edit'"
                index="/toolpath-editor"
              >
                <el-icon><EditPen /></el-icon>刀路编辑
              </el-menu-item>
              <el-menu-item
                v-permission="'user:manage'"
                index="/admin/users"
              >
                <el-icon><UserFilled /></el-icon>用户管理
              </el-menu-item>
            </el-menu>
          </div>

          <div class="header-right">
            <el-dropdown
              trigger="click"
              @command="handleFileCommand"
            >
              <el-button
                type="default"
                size="small"
              >
                文件
                <el-icon class="el-icon--right">
                  <arrow-down />
                </el-icon>
              </el-button>
              <template #dropdown>
                <el-dropdown-menu>
                  <el-dropdown-item command="new">
                    <el-icon><document-add /></el-icon>新建工程
                  </el-dropdown-item>
                  <el-dropdown-item command="open">
                    <el-icon><folder-opened /></el-icon>打开工程
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="save"
                  >
                    <el-icon><disk /></el-icon>保存
                  </el-dropdown-item>
                  <el-dropdown-item command="save-as">
                    <el-icon><copy-document /></el-icon>另存为...
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="download"
                  >
                    <el-icon><download /></el-icon>下载工程文件
                  </el-dropdown-item>
                  <el-dropdown-item
                    divided
                    command="import-step"
                  >
                    <el-icon><upload /></el-icon>导入STEP
                  </el-dropdown-item>
                </el-dropdown-menu>
              </template>
            </el-dropdown>

            <span
              v-if="projectStore.projectName !== '未命名工程'"
              class="project-indicator"
            >
              {{ projectStore.projectName }}
              <el-tag
                v-if="projectStore.isModified"
                size="small"
                type="warning"
                effect="plain"
              >已修改</el-tag>
            </span>
          </div>
        </el-header>

        <el-main class="app-main">
          <router-view />
        </el-main>
      </el-container>

      <!-- ==================== 新建工程对话框 ==================== -->
      <el-dialog
        v-model="showNewDialog"
        title="新建工程"
        width="480px"
        :close-on-click-modal="false"
      >
        <el-form
          :model="newForm"
          label-width="80px"
        >
          <el-form-item
            label="工程名称"
            required
          >
            <el-input
              v-model="newForm.name"
              maxlength="128"
              placeholder="输入工程名称"
            />
          </el-form-item>
          <el-form-item label="作者">
            <el-input
              v-model="newForm.author"
              maxlength="64"
              placeholder="输入您的姓名"
            />
          </el-form-item>
          <el-form-item label="描述">
            <el-input
              v-model="newForm.description"
              type="textarea"
              :rows="3"
              maxlength="512"
              placeholder="可选：输入工程描述"
            />
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showNewDialog = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="creating"
            @click="handleCreate"
          >
            创建工程
          </el-button>
        </template>
      </el-dialog>

      <!-- ==================== 打开工程对话框 ==================== -->
      <el-dialog
        v-model="showOpenDialog"
        title="打开工程"
        width="600px"
        :close-on-click-modal="false"
      >
        <el-tabs v-model="openTab">
          <el-tab-pane
            label="本地工程"
            name="local"
          >
            <div
              v-if="openListLoading"
              style="text-align:center;padding:20px;"
            >
              <el-icon class="is-loading">
                <loading />
              </el-icon> 加载中...
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
                label="工程名称"
                min-width="150"
              />
              <el-table-column
                label="修改时间"
                width="170"
              >
                <template #default="{ row }">
                  {{ formatDate(row.modified_at) }}
                </template>
              </el-table-column>
              <el-table-column
                label="大小"
                width="90"
              >
                <template #default="{ row }">
                  {{ formatSize(row.file_size) }}
                </template>
              </el-table-column>
              <el-table-column
                label="资源"
                width="60"
              >
                <template #default="{ row }">
                  {{ row.resource_count }}
                </template>
              </el-table-column>
              <el-table-column
                label="操作"
                width="120"
              >
                <template #default="{ row }">
                  <el-button
                    size="small"
                    text
                    type="primary"
                    @click="handleOpenFromList(row)"
                  >
                    打开
                  </el-button>
                  <el-button
                    size="small"
                    text
                    type="danger"
                    @click="handleDeleteProject(row)"
                  >
                    删除
                  </el-button>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>
          <el-tab-pane
            label="从文件导入"
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
                拖拽 .vrm 文件到此处或 <em>点击选择文件</em>
              </div>
            </el-upload>
          </el-tab-pane>
        </el-tabs>
        <template #footer>
          <el-button @click="showOpenDialog = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="opening"
            :disabled="!canOpen"
            @click="handleOpen"
          >
            打开工程
          </el-button>
        </template>
      </el-dialog>

      <!-- ==================== 另存为对话框 ==================== -->
      <el-dialog
        v-model="showSaveAsDialog"
        title="另存为工程"
        width="420px"
        :close-on-click-modal="false"
      >
        <el-form
          :model="saveAsForm"
          label-width="80px"
        >
          <el-form-item
            label="文件名"
            required
          >
            <el-input
              v-model="saveAsForm.outputName"
              maxlength="128"
              placeholder="输入文件名（不含扩展名）"
            >
              <template #append>
                .vrm
              </template>
            </el-input>
          </el-form-item>
        </el-form>
        <template #footer>
          <el-button @click="showSaveAsDialog = false">
            取消
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="handleSaveAs"
          >
            另存为
          </el-button>
        </template>
      </el-dialog>

      <!-- ==================== 未保存提示对话框 ==================== -->
      <el-dialog
        v-model="showUnsavedDialog"
        title="未保存的更改"
        width="400px"
      >
        <p>当前工程有未保存的更改。是否保存后再继续？</p>
        <template #footer>
          <el-button @click="discardAndProceed">
            不保存
          </el-button>
          <el-button
            type="primary"
            :loading="saving"
            @click="saveAndProceed"
          >
            保存并继续
          </el-button>
          <el-button @click="cancelProceed">
            取消
          </el-button>
        </template>
      </el-dialog>

      <StepImportDialog />
      <ErrorConflictDialog />
    </el-config-provider>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, inject, ref, reactive, type Ref } from 'vue'
import { useRoute } from 'vue-router'
import { useVersionStore } from '@/stores/version'
import { useProjectStore } from '@/stores/project'
import { useStepImportStore } from '@/stores/stepImport'
import StepImportDialog from '@/components/step_import/StepImportDialog.vue'
import ErrorConflictDialog from '@/components/ErrorConflictDialog.vue'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import en from 'element-plus/es/locale/lang/en'
import type { ProjectSummary } from '@/types'

const title = '灵境制造 V4'
const route = useRoute()
const activeRoute = computed(() => route.path)

const elLocaleRef = inject<Ref<typeof zhCn>>('locale', ref(zhCn))
const elLocale = computed(() => elLocaleRef.value)

const versionStore = useVersionStore()
const frontendVersion = computed(() => versionStore.frontendVersion)
const projectStore = useProjectStore()
const stepImportStore = useStepImportStore()

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
const importFileList = ref<Array<{ raw?: File }>>([])
const selectedSummary = ref<ProjectSummary | null>(null)
const pendingFileCommand = ref('')

const canOpen = computed(() => {
  if (openTab.value === 'local') return selectedSummary.value !== null
  return importFileList.value.length > 0
})

onMounted(async () => {
  await versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
})

function formatDate(iso: string) {
  if (!iso) return '-'
  const d = new Date(iso)
  return d.toLocaleString('zh-CN', { hour12: false })
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

function handleFileSelected(file: any) {
  importFileList.value = [{ raw: file.raw }]
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
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  color: #2c3e50;
}

.app-container {
  min-height: 100vh;
}

.app-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e4e7ed;
  gap: 16px;
  padding: 0 20px;
}

.app-title {
  margin: 0;
  font-size: 1.25rem;
  white-space: nowrap;
}

.header-left {
  display: flex;
  align-items: baseline;
  gap: 8px;
  flex-shrink: 0;
}

.app-version {
  font-size: 0.75rem;
  color: #909399;
  white-space: nowrap;
}

.header-center {
  flex: 1;
  display: flex;
  justify-content: center;
}

.header-menu {
  border-bottom: none;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-shrink: 0;
}

.project-indicator {
  font-size: 13px;
  color: #606266;
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
}
</style>
