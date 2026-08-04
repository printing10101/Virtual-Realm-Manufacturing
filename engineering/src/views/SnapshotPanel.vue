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
          @click="createDialogVisible = true"
        >
          {{ t('snapshotPanel.btnCreate') }}
        </el-button>
      </div>
    </div>

    <!-- ===== Main Layout: List | Detail ===== -->
    <div class="snapshot-main">
      <!-- ===== Left: Snapshot List ===== -->
      <SnapshotListPanel
        :snapshots="snapshots"
        :loading="loading"
        :current-page="currentPage"
        :page-size="pageSize"
        :total-count="totalCount"
        :current-snapshot-id="currentSnapshot?.snapshot_id ?? null"
        :filter-created-by="filterCreatedBy"
        :filter-git-sha="filterGitSha"
        :filter-model-uri="filterModelUri"
        @update:filter-created-by="(val: string) => { filterCreatedBy = val }"
        @update:filter-git-sha="(val: string) => { filterGitSha = val }"
        @update:filter-model-uri="(val: string) => { filterModelUri = val }"
        @select="handleSelectSnapshot"
        @reset-filters="handleResetFilters"
        @page-change="handlePageChange"
        @filter-change="handleFilterChange"
      />

      <!-- ===== Right: Snapshot Detail ===== -->
      <SnapshotDetailPanel
        :current-snapshot="currentSnapshot"
        :current-loading="currentLoading"
        :reproducing="reproducing"
        @reproduce="handleReproduce"
        @close-detail="handleCloseDetail"
      />
    </div>

    <!-- ===== Create Snapshot Dialog ===== -->
    <SnapshotCreateDialog
      :visible="createDialogVisible"
      :creating="creating"
      @update:visible="(val: boolean) => createDialogVisible = val"
      @confirm="handleCreateConfirm"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  Refresh,
  Plus,
} from '@element-plus/icons-vue'
import { useSnapshots } from '@/composables/useSnapshots'
import type { CreateSnapshotRequest } from '@/composables/useSnapshots'
import SnapshotListPanel from '@/components/snapshot/SnapshotListPanel.vue'
import SnapshotDetailPanel from '@/components/snapshot/SnapshotDetailPanel.vue'
import SnapshotCreateDialog from '@/components/snapshot/SnapshotCreateDialog.vue'

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
// 创建快照
// ---------------------------------------------------------------------------

const createDialogVisible = ref(false)

async function handleCreateConfirm(body: CreateSnapshotRequest): Promise<void> {
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
</style>