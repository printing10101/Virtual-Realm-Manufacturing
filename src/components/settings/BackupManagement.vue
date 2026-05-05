<template>
  <div class="backup-management">
    <el-card class="box-card">
      <template #header>
        <div class="card-header">
          <span>{{ t('backup.title') }}</span>
          <div>
            <el-button
              type="primary"
              @click="handleExport"
            >
              <el-icon><Download /></el-icon>
              {{ t('backup.export') }}
            </el-button>
            <el-button @click="handleAutoBackup">
              <el-icon><RefreshRight /></el-icon>
              {{ t('backup.autoBackup') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item :label="t('backup.totalBackups')">
          {{ status.total_backups || 0 }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('backup.totalSize')">
          {{ status.total_size_mb || 0 }} MB
        </el-descriptions-item>
        <el-descriptions-item :label="t('backup.latestBackup')">
          {{ status.latest_backup || t('backup.none') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('backup.retentionDays')">
          {{ status.retention_days || 7 }} {{ t('backup.days') }}
        </el-descriptions-item>
      </el-descriptions>

      <el-divider />

      <h3>{{ t('backup.backupList') }}</h3>
      <el-table
        :data="backups"
        stripe
      >
        <el-table-column
          prop="name"
          :label="t('backup.name')"
        />
        <el-table-column
          prop="size"
          :label="t('backup.size')"
          width="120"
        >
          <template #default="{ row }">
            {{ formatSize(row.size) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="created_at"
          :label="t('backup.createdAt')"
          width="180"
        />
        <el-table-column
          :label="t('backup.actions')"
          width="200"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              @click="handleImport(row.path)"
            >
              {{ t('backup.import') }}
            </el-button>
            <el-button
              size="small"
              type="danger"
              @click="handleDelete(row.path)"
            >
              {{ t('backup.delete') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog
      v-model="importDialogVisible"
      :title="t('backup.import')"
      width="500px"
    >
      <el-form
        :model="importForm"
        label-width="100px"
      >
        <el-form-item :label="t('backup.selectiveRestore')">
          <el-switch v-model="importForm.selective" />
        </el-form-item>
        <el-form-item
          v-if="importForm.selective"
          :label="t('backup.includeItems')"
        >
          <el-checkbox-group v-model="importForm.include_items">
            <el-checkbox label="database">
              {{ t('backup.database') }}
            </el-checkbox>
            <el-checkbox label="vector_db">
              {{ t('backup.vectorDb') }}
            </el-checkbox>
            <el-checkbox label="config">
              {{ t('backup.config') }}
            </el-checkbox>
          </el-checkbox-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">
          {{ t('common.cancel') }}
        </el-button>
        <el-button
          type="primary"
          @click="confirmImport"
        >
          {{ t('common.confirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Download, RefreshRight } from '@element-plus/icons-vue'
import axios from 'axios'

const { t } = useI18n()

interface BackupInfo {
  path: string
  size: number
  created_at: string
  name: string
}

interface BackupStatus {
  total_backups: number
  total_size_mb: number
  latest_backup: string | null
  oldest_backup: string | null
  retention_days: number
}

const backups = ref<BackupInfo[]>([])
const status = ref<BackupStatus>({
  total_backups: 0,
  total_size_mb: 0,
  latest_backup: null,
  oldest_backup: null,
  retention_days: 7
})

const importDialogVisible = ref(false)
const importForm = ref({
  backup_path: '',
  selective: false,
  include_items: ['database', 'vector_db', 'config']
})

const pythonBackendUrl = 'http://localhost:8765'

function buildApiUrl(path: string, baseUrl: string): string {
  return `${baseUrl}${path}`
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`
}

async function loadBackups() {
  try {
    const response = await axios.get(buildApiUrl('/api/v1/backup/list', pythonBackendUrl))
    if (response.data.code === 0) {
      backups.value = response.data.data.backups
    }
  } catch {
    ElMessage.error(t('backup.loadFailed'))
  }
}

async function loadStatus() {
  try {
    const response = await axios.get(buildApiUrl('/api/v1/backup/status', pythonBackendUrl))
    if (response.data.code === 0) {
      status.value = response.data.data
    }
  } catch {
    // 静默失败
  }
}

async function handleExport() {
  try {
    const response = await axios.post(buildApiUrl('/api/v1/backup/export', pythonBackendUrl))
    if (response.data.code === 0) {
      ElMessage.success(t('backup.exportSuccess'))
      await loadBackups()
      await loadStatus()
    }
  } catch {
    ElMessage.error(t('backup.exportFailed'))
  }
}

async function handleAutoBackup() {
  try {
    const response = await axios.post(buildApiUrl('/api/v1/backup/auto-backup', pythonBackendUrl))
    if (response.data.code === 0) {
      ElMessage.success(t('backup.autoBackupSuccess'))
      await loadBackups()
      await loadStatus()
    }
  } catch {
    ElMessage.error(t('backup.autoBackupFailed'))
  }
}

function handleImport(path: string) {
  importForm.value.backup_path = path
  importDialogVisible.value = true
}

async function confirmImport() {
  try {
    const response = await axios.post(
      buildApiUrl('/api/v1/backup/import', pythonBackendUrl),
      importForm.value
    )
    if (response.data.code === 0) {
      ElMessage.success(t('backup.importSuccess'))
      importDialogVisible.value = false
    }
  } catch {
    ElMessage.error(t('backup.importFailed'))
  }
}

async function handleDelete(path: string) {
  try {
    await ElMessageBox.confirm(t('backup.confirmDelete'), t('common.warning'), {
      type: 'warning'
    })
    const response = await axios.delete(buildApiUrl('/api/v1/backup/delete', pythonBackendUrl), {
      data: { backup_path: path }
    })
    if (response.data.code === 0) {
      ElMessage.success(t('backup.deleteSuccess'))
      await loadBackups()
      await loadStatus()
    }
  } catch {
    // 用户取消或请求失败
  }
}

onMounted(() => {
  loadBackups()
  loadStatus()
})
</script>

<style scoped>
.backup-management {
  padding: 20px;
}
.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}
</style>
