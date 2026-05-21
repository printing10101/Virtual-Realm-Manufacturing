<template>
  <div class="rule-editor">
    <div class="page-header">
      <h2>工艺规则编辑器</h2>
      <p class="subtitle">
        管理LNN切削参数推荐系统的工艺规则知识
      </p>
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
            总规则数
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
            启用规则
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
            草稿规则
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
            规则分组
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-card class="toolbar-card">
      <div class="toolbar">
        <div class="toolbar-left">
          <el-input
            v-model="searchKeyword"
            placeholder="搜索规则名称或描述..."
            prefix-icon="Search"
            clearable
            style="width: 280px"
            @keyup.enter="handleSearch"
            @clear="handleSearch"
          />
          <el-select
            v-model="filterGroup"
            placeholder="按分组筛选"
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
            placeholder="按状态筛选"
            clearable
            style="width: 140px; margin-left: 12px"
            @change="handleSearch"
          >
            <el-option
              label="启用"
              value="active"
            />
            <el-option
              label="停用"
              value="inactive"
            />
            <el-option
              label="草稿"
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
            新建规则
          </el-button>
          <el-button @click="ruleStore.openCreateGroupDialog()">
            <el-icon><FolderAdd /></el-icon>
            新建分组
          </el-button>
          <el-button @click="handleExport">
            <el-icon><Download /></el-icon>
            导出
          </el-button>
          <el-upload
            :show-file-list="false"
            :before-upload="handleImport"
            accept=".json"
          >
            <el-button>
              <el-icon><Upload /></el-icon>
              导入
            </el-button>
          </el-upload>
          <el-button @click="handleBackup">
            <el-icon><CopyDocument /></el-icon>
            备份
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
          label="ID"
          width="70"
          sortable="custom"
        />
        <el-table-column
          prop="name"
          label="规则名称"
          min-width="180"
          sortable="custom"
        >
          <template #default="{ row }">
            <el-link
              type="primary"
              @click="handleViewDetail(row)"
            >
              {{ row.name }}
            </el-link>
          </template>
        </el-table-column>
        <el-table-column
          prop="preview_text"
          label="规则预览"
          min-width="300"
        >
          <template #default="{ row }">
            <span class="preview-text">{{ row.preview_text }}</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="status"
          label="状态"
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
          label="优先级"
          width="90"
          sortable="custom"
        />
        <el-table-column
          prop="group_id"
          label="分组"
          width="120"
        >
          <template #default="{ row }">
            {{ getGroupName(row.group_id) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="updated_at"
          label="更新时间"
          width="170"
          sortable="custom"
        />
        <el-table-column
          label="操作"
          width="200"
          fixed="right"
        >
          <template #default="{ row }">
            <el-button
              size="small"
              type="primary"
              link
              @click="ruleStore.openEditDialog(row)"
            >
              编辑
            </el-button>
            <el-button
              size="small"
              type="success"
              link
              @click="handleToggleStatus(row)"
            >
              {{ row.status === 'active' ? '停用' : '启用' }}
            </el-button>
            <el-popconfirm
              title="确定删除此规则？"
              confirm-button-text="删除"
              cancel-button-text="取消"
              @confirm="handleDelete(row.id)"
            >
              <template #reference>
                <el-button
                  size="small"
                  type="danger"
                  link
                >
                  删除
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
      title="规则详情"
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
          <el-descriptions-item label="规则ID">
            {{ currentDetailRule.id }}
          </el-descriptions-item>
          <el-descriptions-item label="规则名称">
            {{ currentDetailRule.name }}
          </el-descriptions-item>
          <el-descriptions-item label="状态">
            <el-tag :type="getRuleStatusTagType(currentDetailRule.status)">
              {{ getRuleStatusLabel(currentDetailRule.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item label="优先级">
            {{ currentDetailRule.priority }}
          </el-descriptions-item>
          <el-descriptions-item label="分组">
            {{ getGroupName(currentDetailRule.group_id) }}
          </el-descriptions-item>
          <el-descriptions-item label="逻辑运算符">
            {{ currentDetailRule.logic_operator }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">
          条件项
        </h4>
        <el-table
          :data="currentDetailRule.conditions"
          border
          size="small"
        >
          <el-table-column
            prop="parameter"
            label="参数"
          />
          <el-table-column
            prop="operator"
            label="运算符"
            width="100"
          />
          <el-table-column
            prop="value"
            label="值"
          />
          <el-table-column
            prop="unit"
            label="单位"
            width="80"
          />
        </el-table>

        <h4 class="section-title">
          结果
        </h4>
        <el-descriptions
          :column="4"
          border
          size="small"
        >
          <el-descriptions-item label="参数">
            {{ currentDetailRule.result?.parameter }}
          </el-descriptions-item>
          <el-descriptions-item label="运算符">
            {{ currentDetailRule.result?.operator }}
          </el-descriptions-item>
          <el-descriptions-item label="值">
            {{ currentDetailRule.result?.value }}
          </el-descriptions-item>
          <el-descriptions-item label="单位">
            {{ currentDetailRule.result?.unit || '-' }}
          </el-descriptions-item>
        </el-descriptions>

        <h4 class="section-title">
          规则预览
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
          <strong>描述：</strong>{{ currentDetailRule.description }}
        </p>
        <p class="time-info">
          创建时间: {{ currentDetailRule.created_at }} | 更新时间: {{ currentDetailRule.updated_at }}
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

function handleSortChange({ prop, order }: { prop: string; order: string }) {
  ruleStore.fetchRules({
    keyword: searchKeyword.value || undefined,
    group_id: filterGroup.value,
    status: filterStatus.value,
    sort_by: prop,
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
  color: #303133;
}

.subtitle {
  margin: 0;
  color: #909399;
  font-size: 14px;
}

.stats-cards {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 8px 0;
}

.stat-value {
  font-size: 28px;
  font-weight: 600;
  color: #409eff;
}

.stat-card.active .stat-value {
  color: #67c23a;
}

.stat-card.draft .stat-value {
  color: #e6a23c;
}

.stat-card.groups .stat-value {
  color: #909399;
}

.stat-label {
  font-size: 13px;
  color: #909399;
  margin-top: 4px;
}

.toolbar-card {
  margin-bottom: 16px;
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
  color: #606266;
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
  color: #303133;
  border-left: 3px solid #409eff;
  padding-left: 8px;
}

.description {
  margin-top: 16px;
  color: #606266;
  font-size: 14px;
}

.time-info {
  margin-top: 16px;
  color: #909399;
  font-size: 12px;
  text-align: right;
}
</style>
