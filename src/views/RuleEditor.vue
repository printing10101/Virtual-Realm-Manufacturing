<template>
  <div class="rule-editor">
    <div class="page-header">
      <h2>{{ $t('ruleEditor.pageTitle') }}</h2>
      <p class="subtitle">{{ $t('ruleEditor.subtitle') }}</p>
    </div>

    <el-row
      :gutter="16"
      class="stats-cards"
    >
      <el-col
        :xs="12"
        :sm="8"
        :md="4"
      >
        <el-card
          shadow="hover"
          class="stat-card"
        >
          <div class="stat-value">
            {{ ruleStore.stats?.total_rules || 0 }}
          </div>
          <div class="stat-label">
            {{ $t('ruleEditor.totalRules') }}
          </div>
        </el-card>
      </el-col>
      <el-col
        :xs="12"
        :sm="8"
        :md="4"
      >
        <el-card
          shadow="hover"
          class="stat-card active"
        >
          <div class="stat-value">
            {{ ruleStore.stats?.active_rules || 0 }}
          </div>
          <div class="stat-label">
            {{ $t('ruleEditor.activeRules') }}
          </div>
        </el-card>
      </el-col>
      <el-col
        :xs="12"
        :sm="8"
        :md="4"
      >
        <el-card
          shadow="hover"
          class="stat-card draft"
        >
          <div class="stat-value">
            {{ ruleStore.stats?.draft_rules || 0 }}
          </div>
          <div class="stat-label">
            {{ $t('ruleEditor.draftRules') }}
          </div>
        </el-card>
      </el-col>
      <el-col
        :xs="12"
        :sm="8"
        :md="4"
      >
        <el-card
          shadow="hover"
          class="stat-card groups"
        >
          <div class="stat-value">
            {{ ruleStore.stats?.total_groups || 0 }}
          </div>
          <div class="stat-label">
            {{ $t('ruleEditor.ruleGroups') }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchKeyword"
            :placeholder="$t('ruleEditor.searchPlaceholder')"
            prefix-icon="Search"
            clearable
            style="width: 280px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-select
            v-model="filterGroup"
            :placeholder="$t('ruleEditor.filterByGroup')"
            clearable
            style="width: 180px; margin-left: 12px"
            @change="handleSearch"
          >
            <el-option
              v-for="g in ruleStore.groups"
              :key="g.id"
              :label="g.name"
              :value="g.id"
            />
          </el-select>
          <el-select
            v-model="filterStatus"
            :placeholder="$t('ruleEditor.filterByStatus')"
            clearable
            style="width: 140px; margin-left: 12px"
            @change="handleSearch"
          >
            <el-option
              :label="$t('ruleEditor.statusActive')"
              value="active"
            />
            <el-option
              :label="$t('ruleEditor.statusInactive')"
              value="inactive"
            />
            <el-option
              :label="$t('ruleEditor.statusDraft')"
              value="draft"
            />
          </el-select>
        </div>
        <div class="toolbar-right">
          <el-button
            type="primary"
            @click="ruleStore.openCreateDialog()"
          >
            <el-icon><Plus /></el-icon>
            {{ $t('ruleEditor.newRule') }}
          </el-button>
          <el-button @click="ruleStore.openCreateGroupDialog()">
            <el-icon><FolderAdd /></el-icon>
            {{ $t('ruleEditor.newGroup') }}
          </el-button>
          <el-button @click="handleExport">
            <el-icon><Download /></el-icon>
            {{ $t('common.export') }}
          </el-button>
          <el-upload
            :show-file-list="false"
            :before-upload="handleImport"
            accept=".json"
          >
            <el-button>
              <el-icon><Upload /></el-icon>
              {{ $t('common.import') }}
            </el-button>
          </el-upload>
          <el-button @click="handleBackup">
            <el-icon><CopyDocument /></el-icon>
            {{ $t('common.backup') }}
          </el-button>
        </div>
      </div>
    </el-card>

    <el-card class="table-card">
      <el-table
        v-loading="ruleStore.loading"
        :data="ruleStore.rules"
        stripe
        border
        style="width: 100%"
        @sort-change="handleSortChange"
      >
        <el-table-column
          prop="id"
          :label="$t('ruleEditor.tableId')"
          width="70"
          sortable="custom"
        />
        <el-table-column
          prop="name"
          :label="$t('ruleEditor.tableName')"
          min-width="180"
          sortable="custom"
        >
          <template #default="{ row }">
            <el-link
              type="primary"
              @click="handleViewDetail(row as ProcessRule)"
            >
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column
          prop="preview_text"
          :label="$t('ruleEditor.tablePreview')"
          min-width="300"
        >
          <template #default="{ row }">
            <span class="preview-text">{{ row.preview_text }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="status"
          :label="$t('ruleEditor.tableStatus')"
          width="100"
          sortable="custom"
        >
          <template #default="{ row }">
            <el-tag
              :type="getRuleStatusTagType(row.status)"
              size="small"
            >
              {{ getRuleStatusLabel(row.status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="priority"
          :label="$t('ruleEditor.tablePriority')"
          width="90"
          sortable="custom"
        />
        <el-table-column
          prop="group_id"
          :label="$t('ruleEditor.tableGroup')"
          width="120"
        >
          <template #default="{ row }">
            {{ getGroupName(row.group_id) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="updated_at"
          :label="$t('ruleEditor.tableUpdated')"
          width="170"
          sortable="custom"
        />
        <el-table-column
          :label="$t('ruleEditor.tableActions')"
          width="200"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              link
              @click="ruleStore.openEditDialog(row as ProcessRule)"
            >
              {{ $t('ruleEditor.edit') }}
            </el-button>
            <el-button
              size="small"
              type="success"
              link
              @click="handleToggleStatus(row as ProcessRule)"
            >
              {{ row.status === 'active' ? $t('ruleEditor.disable') : $t('ruleEditor.enable') }}
            </el-button>
            <el-popconfirm
              :title="$t('ruleEditor.deleteConfirm')"
              :confirm-button-text="$t('common.delete')"
              :cancel-button-text="$t('common.cancel')"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button
                  size="small"
                  type="danger"
                  link
                >
                  {{ $t('common.delete') }}
                </el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>

      <div class="pagination">
        <el-pagination
          v-model:current-page="ruleStore.currentPage"
          v-model:page-size="ruleStore.pageSize"
          :total="ruleStore.totalRules"
          :page-sizes="[10, 20, 50, 100]"
          layout="total, sizes, prev, pager, next, jumper"
          @size-change="handleSearch"
          @current-change="handlePageChange"
        />
      </div>
    </el-card>

    <RuleEditDialog
      v-model:visible="ruleStore.showDialog"
      :rule="ruleStore.editingRule"
      @saved="ruleStore.refreshAll()"
    />

    <GroupManagerDialog
      v-model:visible="ruleStore.showGroupDialog"
      :group="ruleStore.editingGroup"
      @saved="ruleStore.refreshAll()"
    />

    <el-dialog
      v-model="detailDialogVisible"
      :title="$t('ruleEditor.detailTitle')"
      width="700px"
    >
      <div
        v-if="currentDetailRule"
        class="rule-detail"
      >
        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item :label="$t('ruleEditor.ruleId')">
            {{ currentDetailRule.id }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.ruleName')">
            {{ currentDetailRule.name }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.status')">
            <el-tag :type="getRuleStatusTagType(currentDetailRule.status)">
              {{ getRuleStatusLabel(currentDetailRule.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.priority')">
            {{ currentDetailRule.priority }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.group')">
            {{ getGroupName(currentDetailRule.group_id) }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.logicOperator')">
            {{ currentDetailRule.logic_operator }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">
          {{ $t('ruleEditor.conditions') }}
        </h4>
        <el-table
          :data="currentDetailRule.conditions"
          border
          size="small"
        >
          <el-table-column
            prop="parameter"
            :label="$t('ruleEditor.parameter')"
          />
          <el-table-column
            prop="operator"
            :label="$t('ruleEditor.operator')"
            width="100"
          />
          <el-table-column
            prop="value"
            :label="$t('ruleEditor.value')"
          />
          <el-table-column
            prop="unit"
            :label="$t('ruleEditor.unit')"
            width="80"
          />
        </el-table>

        <h4 class="section-title">
          {{ $t('ruleEditor.result') }}
        </h4>
        <el-descriptions
          :column="4"
          border
          size="small"
        >
          <el-descriptions-item :label="$t('ruleEditor.parameter')">
            {{ currentDetailRule.result?.parameter }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.operator')">
            {{ currentDetailRule.result?.operator }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.value')">
            {{ currentDetailRule.result?.value }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('ruleEditor.unit')">
            {{ currentDetailRule.result?.unit || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">
          {{ $t('ruleEditor.rulePreview') }}
        </h4>
        <el-alert
          :title="currentDetailRule.preview_text"
          type="info"
          :closable="false"
        />

        <p
          v-if="currentDetailRule.description"
          class="description"
        >
          <strong>{{ $t('ruleEditor.description') }}：</strong>{{ currentDetailRule.description }}
        </p>
        <p class="time-info">
          {{ $t('ruleEditor.timeInfo', { created: currentDetailRule.created_at, updated: currentDetailRule.updated_at }) }}
        </p>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, FolderAdd, Download, Upload, CopyDocument } from '@element-plus/icons-vue'
import { useRuleStore } from '@/stores/rules'
import type { ProcessRule } from '@/types'
import RuleEditDialog from '@/components/rule_editor/RuleEditDialog.vue'
import GroupManagerDialog from '@/components/rule_editor/GroupManagerDialog.vue'
import { getRuleStatusTagType, getRuleStatusLabel } from '@/utils/statusHelpers'

const ruleStore = useRuleStore()

const searchKeyword = ref('')
const filterGroup = ref<number | undefined>(undefined)
const filterStatus = ref<string | undefined>(undefined)
const detailDialogVisible = ref(false)
const currentDetailRule = ref<ProcessRule | null>(null)

onMounted(() => {
  ruleStore.refreshAll()
})

function handleSearch() {
  ruleStore.fetchRules({
    keyword: searchKeyword.value || undefined,
    group_id: filterGroup.value,
    status: filterStatus.value,
    page: ruleStore.currentPage,
    page_size: ruleStore.pageSize,
  })
}

function handlePageChange(page: number) {
  ruleStore.fetchRules({
    keyword: searchKeyword.value || undefined,
    group_id: filterGroup.value,
    status: filterStatus.value,
    page,
    page_size: ruleStore.pageSize,
  })
}

function handleSortChange({ prop, order }: { prop: string | null; order: string | null }) {
  ruleStore.fetchRules({
    keyword: searchKeyword.value || undefined,
    group_id: filterGroup.value,
    status: filterStatus.value,
    sort_by: prop || undefined,
    sort_order: order === 'ascending' ? 'ASC' : 'DESC',
    page: ruleStore.currentPage,
    page_size: ruleStore.pageSize,
  })
}

async function handleExport() {
  await ruleStore.exportRules()
}

async function handleImport(file: File) {
  await ruleStore.importRules(file)
  return false
}

async function handleBackup() {
  await ruleStore.backupDatabase()
}

function handleViewDetail(rule: ProcessRule) {
  currentDetailRule.value = rule
  detailDialogVisible.value = true
}

async function handleToggleStatus(rule: ProcessRule) {
  const newStatus = rule.status === 'active' ? 'inactive' : 'active'
  await ruleStore.updateRule(rule.id!, { status: newStatus })
}

async function handleDelete(ruleId?: number) {
  if (!ruleId) return
  await ruleStore.deleteRule(ruleId)
}

function getGroupName(groupId?: number): string {
  if (!groupId) return '-'
  const group = ruleStore.groups.find((g) => g.id === groupId)
  return group?.name || '-'
}

</script>

<style scoped>
.rule-editor {
  padding: 20px;
  max-width: 1400px;
  margin: 0 auto;
}

.page-header {
  margin-bottom: 20px;
}

.page-header h2 {
  margin: 0 0 4px 0;
  font-size: 24px;
  color: var(--text-primary);
  font-weight: 600;
}

.subtitle {
  margin: 0;
  color: var(--text-tertiary);
  font-size: 14px;
}

.stats-cards {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 8px 0;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  transition: all var(--transition-fast);
}

.stat-card:hover {
  box-shadow: var(--shadow-md);
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: var(--accent-primary);
}

.stat-card.active .stat-value {
  color: var(--success);
}

.stat-card.draft .stat-value {
  color: var(--warning);
}

.stat-card.groups .stat-value {
  color: var(--text-tertiary);
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary);
  margin-top: 4px;
}

.toolbar-card {
  margin-bottom: 16px;
  background: var(--bg-card);
  border: 1px solid var(--border-light);
}

.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 12px;
}

.toolbar-left {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 8px;
}

.preview-text {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  display: block;
  max-width: 300px;
}

.pagination {
  margin-top: 16px;
  display: flex;
  justify-content: flex-end;
}

.rule-detail {
  padding: 12px 0;
}

.section-title {
  margin: 20px 0 12px 0;
  font-size: 16px;
  color: var(--text-primary);
  border-left: 3px solid var(--accent-primary);
  padding-left: 8px;
  font-weight: 600;
}

.description {
  margin-top: 16px;
  color: var(--text-secondary);
  font-size: 14px;
  line-height: 1.6;
}

.time-info {
  margin-top: 16px;
  color: var(--text-tertiary);
  font-size: 12px;
  text-align: right;
}
</style>
