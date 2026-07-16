<template>
  <div class="snapshot-panel-page">
    <!-- ===== Page Header ===== -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('snapshotPanel.pageTitle') }}</h1>
        <span class="page-header__subtitle">
          {{ t('snapshotPanel.pageSubtitle') }}
        </span>
      </div>
      <div class="page-header__actions">
        <el-button
          size="small"
          :icon="Refresh"
          :loading="loading"
          @click="handleRefresh"
        >
          {{ t('snapshotPanel.btnRefresh') }}
        </el-button>
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="openCreateDialog"
        >
          {{ t('snapshotPanel.btnCreate') }}
        </el-button>
      </div>
    </div>

    <!-- ===== Main Layout: List | Detail ===== -->
    <div class="snapshot-main">
      <!-- ===== Left: Snapshot List ===== -->
      <div class="snapshot-list-panel">
        <div class="panel-header">
          <span class="panel-title">{{ t('snapshotPanel.listTitle') }}</span>
          <el-button
            size="small"
            link
            @click="handleResetFilters"
          >
            {{ t('snapshotPanel.btnResetFilters') }}
          </el-button>
        </div>

        <div class="panel-filters">
          <el-input
            v-model="filterCreatedBy"
            size="small"
            :placeholder="t('snapshotPanel.filterCreatedBy')"
            clearable
            @change="handleFilterChange"
          />
          <el-input
            v-model="filterGitSha"
            size="small"
            :placeholder="t('snapshotPanel.filterGitSha')"
            clearable
            @change="handleFilterChange"
          />
          <el-input
            v-model="filterModelUri"
            size="small"
            :placeholder="t('snapshotPanel.filterModelUri')"
            clearable
            @change="handleFilterChange"
          />
        </div>

        <div
          v-loading="loading"
          class="snapshot-list-body"
        >
          <el-empty
            v-if="!loading && snapshots.length === 0"
            :description="t('snapshotPanel.emptyNoSnapshots')"
            :image-size="60"
          />
          <div
            v-for="snap in snapshots"
            :key="snap.snapshot_id"
            class="snapshot-card"
            :class="{ active: snap.snapshot_id === currentSnapshot?.snapshot_id }"
            @click="handleSelectSnapshot(snap.snapshot_id)"
          >
            <div class="snapshot-card-header">
              <span class="snapshot-id">{{ snap.snapshot_id.substring(0, 8) }}</span>
              <el-tag
                size="small"
                :type="snap.code_dirty ? 'warning' : 'success'"
              >
                {{ snap.code_dirty
                  ? t('snapshotPanel.dirtyDirty')
                  : t('snapshotPanel.dirtyClean') }}
              </el-tag>
            </div>
            <div class="snapshot-card-meta">
              <div class="meta-row">
                <span class="meta-label">{{ t('snapshotPanel.colCreatedBy') }}:</span>
                <span class="meta-value">{{ snap.created_by }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">{{ t('snapshotPanel.colGitSha') }}:</span>
                <span class="meta-value mono">{{ shortSha(snap.git_sha) }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">{{ t('snapshotPanel.colModelUri') }}:</span>
                <span class="meta-value mono">{{ snap.model_uri }}</span>
              </div>
              <div class="meta-row">
                <span class="meta-label">{{ t('snapshotPanel.colCreatedAt') }}:</span>
                <span class="meta-value">{{ formatTime(snap.created_at) }}</span>
              </div>
            </div>
          </div>
        </div>

        <div class="panel-pagination">
          <el-pagination
            v-model:current-page="currentPage"
            :page-size="pageSize"
            :total="totalCount"
            layout="prev, pager, next"
            small
            @current-change="handlePageChange"
          />
        </div>
      </div>

      <!-- ===== Right: Snapshot Detail ===== -->
      <div class="snapshot-detail-panel">
        <div class="panel-header">
          <span class="panel-title">{{ t('snapshotPanel.detailTitle') }}</span>
          <div
            v-if="currentSnapshot"
            class="panel-header-actions"
          >
            <el-button
              size="small"
              type="primary"
              :icon="VideoPlay"
              :loading="reproducing"
              @click="handleReproduce"
            >
              {{ t('snapshotPanel.btnReproduce') }}
            </el-button>
            <el-button
              size="small"
              :icon="Close"
              @click="handleCloseDetail"
            >
              {{ t('snapshotPanel.btnCloseDetail') }}
            </el-button>
          </div>
        </div>

        <div
          v-loading="currentLoading"
          class="snapshot-detail-body"
        >
          <el-empty
            v-if="!currentLoading && !currentSnapshot"
            :description="t('snapshotPanel.emptyNoSnapshots')"
            :image-size="80"
          />
          <div
            v-if="currentSnapshot"
            class="snapshot-detail-content"
          >
            <el-descriptions :column="1" border>
              <el-descriptions-item :label="t('snapshotPanel.colId')">
                <span class="mono">{{ currentSnapshot.snapshot_id }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailCreatedAt')">
                {{ formatTime(currentSnapshot.created_at) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailCreatedBy')">
                {{ currentSnapshot.created_by }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailGitSha')">
                <span class="mono">{{ currentSnapshot.git_sha }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailCodeStatus')">
                <el-tag
                  size="small"
                  :type="currentSnapshot.code_dirty ? 'warning' : 'success'"
                >
                  {{ currentSnapshot.code_dirty
                    ? t('snapshotPanel.dirtyDirty')
                    : t('snapshotPanel.dirtyClean') }}
                </el-tag>
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailModelUri')">
                <span class="mono">{{ currentSnapshot.model_uri }}</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailDatasetVersions')">
                <div
                  v-if="currentSnapshot.dataset_versions.length > 0"
                  class="uri-list"
                >
                  <div
                    v-for="(uri, idx) in currentSnapshot.dataset_versions"
                    :key="idx"
                    class="uri-item mono"
                  >
                    {{ uri }}
                  </div>
                </div>
                <span v-else>-</span>
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailMetrics')">
                <pre class="json-block">{{ JSON.stringify(currentSnapshot.metrics, null, 2) }}</pre>
              </el-descriptions-item>
              <el-descriptions-item :label="t('snapshotPanel.detailEnvironment')">
                <pre class="json-block">{{ JSON.stringify(currentSnapshot.environment, null, 2) }}</pre>
              </el-descriptions-item>
              <el-descriptions-item
                v-if="currentSnapshot.lineage_record_id"
                :label="t('snapshotPanel.detailLineageRecord')"
              >
                <span class="mono">{{ currentSnapshot.lineage_record_id }}</span>
              </el-descriptions-item>
              <el-descriptions-item
                v-if="currentSnapshot.mlflow_run_id"
                :label="t('snapshotPanel.detailMlflowRunId')"
              >
                <span class="mono">{{ currentSnapshot.mlflow_run_id }}</span>
              </el-descriptions-item>
              <el-descriptions-item
                v-if="currentSnapshot.notes"
                :label="t('snapshotPanel.detailNotes')"
              >
                {{ currentSnapshot.notes }}
              </el-descriptions-item>
            </el-descriptions>

            <div class="config-section">
              <div class="config-section__title">
                {{ t('snapshotPanel.detailConfig') }}
              </div>
              <pre class="json-block json-block--large">{{ JSON.stringify(currentSnapshot.config, null, 2) }}</pre>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- ===== Create Snapshot Dialog ===== -->
    <el-dialog
      v-model="createDialogVisible"
      :title="t('snapshotPanel.createDialogTitle')"
      width="640px"
      :close-on-click-modal="false"
    >
      <el-form
        ref="createFormRef"
        :model="createForm"
        label-width="140px"
        label-position="left"
      >
        <el-form-item :label="t('snapshotPanel.formConfig')">
          <el-input
            v-model="createForm.configStr"
            type="textarea"
            :rows="6"
            :placeholder="t('snapshotPanel.formConfigPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('snapshotPanel.formDatasetVersions')">
          <el-input
            v-model="createForm.datasetVersionsStr"
            type="textarea"
            :rows="3"
            :placeholder="t('snapshotPanel.formDatasetVersionsPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('snapshotPanel.formModelUri')">
          <el-input
            v-model="createForm.modelUri"
            :placeholder="t('snapshotPanel.formModelUriPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('snapshotPanel.formMetrics')">
          <el-input
            v-model="createForm.metricsStr"
            type="textarea"
            :rows="3"
            :placeholder="t('snapshotPanel.formMetricsPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('snapshotPanel.formCreatedBy')">
          <el-input
            v-model="createForm.createdBy"
            :placeholder="t('snapshotPanel.formCreatedByPlaceholder')"
          />
        </el-form-item>
        <el-form-item :label="t('snapshotPanel.formNotes')">
          <el-input
            v-model="createForm.notes"
            type="textarea"
            :rows="2"
            :placeholder="t('snapshotPanel.formNotesPlaceholder')"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button
          @click="createDialogVisible = false"
        >
          {{ t('snapshotPanel.btnCancelDialog') }}
        </el-button>
        <el-button
          type="primary"
          :loading="creating"
          @click="handleCreateConfirm"
        >
          {{ t('snapshotPanel.btnCreateConfirm') }}
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Plus,
  VideoPlay,
  Close,
} from '@element-plus/icons-vue'
import { useSnapshots } from '@/composables/useSnapshots'
import type { CreateSnapshotRequest } from '@/composables/useSnapshots'

const { t } = useI18n()

// ---------------------------------------------------------------------------
// useSnapshots composable 接入
// ---------------------------------------------------------------------------
const {
  snapshots,
  loading,
  totalCount,
  currentPage,
  pageSize,
  filterCreatedBy,
  filterGitSha,
  filterModelUri,
  loadSnapshots,
  resetFilters,
  currentSnapshot,
  currentLoading,
  selectSnapshot,
  clearCurrent,
  creating,
  reproducing,
  submitSnapshot,
  reproduce,
} = useSnapshots()

// ---------------------------------------------------------------------------
// 工具函数
// ---------------------------------------------------------------------------

function shortSha(sha?: string): string {
  if (!sha) return '-'
  return sha.length > 8 ? sha.substring(0, 8) : sha
}

function formatTime(iso?: string): string {
  if (!iso) return '-'
  try {
    const d = new Date(iso)
    return d.toLocaleString()
  } catch {
    return iso
  }
}

// ---------------------------------------------------------------------------
// 事件处理
// ---------------------------------------------------------------------------

async function handleRefresh(): Promise<void> {
  await loadSnapshots()
}

async function handleFilterChange(): Promise<void> {
  currentPage.value = 1
  await loadSnapshots()
}

async function handleResetFilters(): Promise<void> {
  await resetFilters()
}

async function handlePageChange(): Promise<void> {
  await loadSnapshots()
}

async function handleSelectSnapshot(snapshotId: string): Promise<void> {
  await selectSnapshot(snapshotId)
}

function handleCloseDetail(): void {
  clearCurrent()
}

async function handleReproduce(): Promise<void> {
  if (!currentSnapshot.value) return
  try {
    await ElMessageBox.confirm(
      t('snapshotPanel.confirmReproduce'),
      t('snapshotPanel.warning'),
      { type: 'warning' },
    )
  } catch {
    // 用户取消
    return
  }

  try {
    const workflowRunId = await reproduce(currentSnapshot.value.snapshot_id)
    ElMessage.success(
      t('snapshotPanel.msgReproduceSuccess', { id: workflowRunId }),
    )
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    const msg = err?.response?.data?.message ?? String(e)
    // 后端返回 INVALID_REQUEST + "该快照不支持一键复现" 时给友好提示
    if (msg.includes('不支持一键复现') || msg.includes('workflow_spec')) {
      ElMessage.warning(t('snapshotPanel.msgReproduceNotSupported'))
    } else {
      ElMessage.error(t('snapshotPanel.msgReproduceFailed', { error: msg }))
    }
  }
}

// ---------------------------------------------------------------------------
// 创建快照对话框
// ---------------------------------------------------------------------------

const createDialogVisible = ref(false)
const createFormRef = ref()

interface CreateForm {
  configStr: string
  datasetVersionsStr: string
  modelUri: string
  metricsStr: string
  createdBy: string
  notes: string
}

const createForm = reactive<CreateForm>({
  configStr: '',
  datasetVersionsStr: '',
  modelUri: '',
  metricsStr: '',
  createdBy: '',
  notes: '',
})

function openCreateDialog(): void {
  createForm.configStr = ''
  createForm.datasetVersionsStr = ''
  createForm.modelUri = ''
  createForm.metricsStr = '{}'
  createForm.createdBy = ''
  createForm.notes = ''
  createDialogVisible.value = true
}

async function handleCreateConfirm(): Promise<void> {
  // 校验 config
  if (!createForm.configStr.trim()) {
    ElMessage.warning(t('snapshotPanel.msgConfigEmpty'))
    return
  }
  let config: Record<string, unknown>
  try {
    config = JSON.parse(createForm.configStr)
  } catch {
    ElMessage.warning(t('snapshotPanel.msgConfigInvalid'))
    return
  }

  // 校验 metrics（可选，默认 {}）
  let metrics: Record<string, number>
  try {
    metrics = JSON.parse(createForm.metricsStr || '{}')
  } catch {
    ElMessage.warning(t('snapshotPanel.msgMetricsInvalid'))
    return
  }

  // 解析 dataset_versions（每行一个 URI）
  const datasetVersions = createForm.datasetVersionsStr
    .split('\n')
    .map(s => s.trim())
    .filter(s => s.length > 0)
  if (datasetVersions.length === 0) {
    ElMessage.warning(t('snapshotPanel.msgDatasetVersionsEmpty'))
    return
  }

  const body: CreateSnapshotRequest = {
    config,
    dataset_versions: datasetVersions,
    model_uri: createForm.modelUri.trim() || 'model://unknown',
    metrics,
    created_by: createForm.createdBy.trim() || 'system:user',
    notes: createForm.notes.trim() || undefined,
  }

  try {
    const snapshotId = await submitSnapshot(body)
    ElMessage.success(
      t('snapshotPanel.msgCreateSuccess', { id: snapshotId }),
    )
    createDialogVisible.value = false
    // 自动选中新创建的快照
    await selectSnapshot(snapshotId)
  } catch (e: unknown) {
    const err = e as { response?: { data?: { message?: string } } }
    const msg = err?.response?.data?.message ?? String(e)
    ElMessage.error(msg)
  }
}

// ---------------------------------------------------------------------------
// 初始化
// ---------------------------------------------------------------------------

onMounted(() => {
  void loadSnapshots()
})
</script>

<style scoped>
.snapshot-panel-page {
  display: flex;
  flex-direction: column;
  height: 100%;
  padding: 16px;
  gap: 12px;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  padding: 8px 4px;
}

.page-header__title h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
}

.page-header__subtitle {
  color: var(--el-text-color-secondary);
  font-size: 13px;
}

.page-header__actions {
  display: flex;
  gap: 8px;
}

.snapshot-main {
  display: grid;
  grid-template-columns: 380px 1fr;
  gap: 12px;
  flex: 1;
  min-height: 0;
}

.snapshot-list-panel,
.snapshot-detail-panel {
  display: flex;
  flex-direction: column;
  background: var(--el-bg-color);
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 6px;
  overflow: hidden;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
  background: var(--el-fill-color-light);
}

.panel-title {
  font-weight: 600;
  font-size: 14px;
}

.panel-header-actions {
  display: flex;
  gap: 8px;
}

.panel-filters {
  display: flex;
  flex-direction: column;
  gap: 6px;
  padding: 10px 12px;
  border-bottom: 1px solid var(--el-border-color-lighter);
}

.snapshot-list-body {
  flex: 1;
  overflow-y: auto;
  padding: 8px;
}

.snapshot-card {
  padding: 10px 12px;
  margin-bottom: 8px;
  border: 1px solid var(--el-border-color-lighter);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.snapshot-card:hover {
  border-color: var(--el-color-primary);
  background: var(--el-fill-color-light);
}

.snapshot-card.active {
  border-color: var(--el-color-primary);
  background: var(--el-color-primary-light-9);
}

.snapshot-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.snapshot-id {
  font-weight: 600;
  font-size: 13px;
  font-family: 'Consolas', 'Monaco', monospace;
}

.snapshot-card-meta {
  font-size: 12px;
}

.meta-row {
  display: flex;
  margin-bottom: 2px;
}

.meta-label {
  color: var(--el-text-color-secondary);
  width: 80px;
  flex-shrink: 0;
}

.meta-value {
  color: var(--el-text-color-primary);
  word-break: break-all;
}

.mono {
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
}

.panel-pagination {
  padding: 8px 12px;
  border-top: 1px solid var(--el-border-color-lighter);
  display: flex;
  justify-content: center;
}

.snapshot-detail-body {
  flex: 1;
  overflow-y: auto;
  padding: 16px;
}

.snapshot-detail-content {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.uri-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.uri-item {
  padding: 2px 6px;
  background: var(--el-fill-color-light);
  border-radius: 3px;
}

.json-block {
  margin: 0;
  padding: 8px;
  background: var(--el-fill-color-darker);
  border-radius: 4px;
  font-family: 'Consolas', 'Monaco', monospace;
  font-size: 12px;
  overflow-x: auto;
  max-height: 240px;
  overflow-y: auto;
}

.json-block--large {
  max-height: 480px;
}

.config-section__title {
  font-weight: 600;
  margin-bottom: 8px;
  font-size: 14px;
}
</style>
