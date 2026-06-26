<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { formatSecondsTimestamp } from '@/utils/formatters'
import { getBranchTypeTagType } from '@/utils/statusHelpers'
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

// 类型定义
interface Branch {
  id: string
  name: string
  type: string
  base_branch: string | null
  data: Record<string, unknown>
  metadata: Record<string, unknown>
  created_at: number
  updated_at: number
}

interface MergeForm {
  source_id: string
  target_id: string
  strategy: 'overwrite' | 'merge' | 'rebase'
}

interface CreateForm {
  name: string
  base_branch: string
  type: 'main' | 'feature' | 'hotfix'
  data: Record<string, unknown>
}

const branches = ref<Branch[]>([])
const loading = ref(false)
const createDialog = ref(false)
const mergeDialog = ref(false)
const mergeForm = ref<MergeForm>({ source_id: '', target_id: '', strategy: 'overwrite' })
const createForm = ref<CreateForm>({ name: '', base_branch: '', type: 'main', data: {} })
const typeFilter = ref('')
const branchDataInput = ref('{}')

const API_BASE = API_CONFIG.V1

async function fetchBranches() {
  loading.value = true
  try {
    const url = typeFilter.value
      ? `${API_BASE}/templates/branches?type=${typeFilter.value}`
      : `${API_BASE}/templates/branches`
    const res = await http.get(url)
    if (res.data.code === 'SUCCESS') branches.value = res.data.data
  } catch {
    // 静默处理
  } finally {
    loading.value = false
  }
}

async function createBranch() {
  let data: Record<string, unknown> = {}
  try {
    data = JSON.parse(branchDataInput.value || '{}')
  } catch {
    // JSON 解析失败，使用空对象
    data = {}
  }
  try {
    await http.post(`${API_BASE}/templates/branches`, {
      name: createForm.value.name,
      base_branch: createForm.value.base_branch || null,
      data,
      metadata: { type: createForm.value.type }
    })
    createDialog.value = false
    createForm.value = { name: '', base_branch: '', type: 'main', data: {} }
    branchDataInput.value = '{}'
    fetchBranches()
  } catch {
    // 静默处理
  }
}

async function mergeBranch() {
  try {
    await http.post(`${API_BASE}/templates/branches/${mergeForm.value.source_id}/merge`, {
      target_id: mergeForm.value.target_id,
      strategy: mergeForm.value.strategy
    })
    mergeDialog.value = false
    fetchBranches()
  } catch {
    // 静默处理
  }
}

async function deleteBranch(branchId: string, type: string) {
  if (type === 'main') {
    ElMessage.warning('不能删除主线分支')
    return
  }
  try {
    await ElMessageBox.confirm('确定删除此分支？', '确认删除', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await http.delete(`${API_BASE}/templates/branches/${branchId}`)
    fetchBranches()
  } catch (e: unknown) {
    // 用户取消对话框时不处理
    if (e !== 'cancel') {
      // 静默处理
    }
  }
}

onMounted(fetchBranches)
</script>

<template>
  <div class="branch-manager-page">
    <el-card class="header-card">
      <div class="page-header">
        <h2>分支管理</h2>
        <div class="header-actions">
          <el-select
            v-model="typeFilter"
            placeholder="全部类型"
            clearable
            style="width: 150px; margin-right: 12px;"
            @change="fetchBranches"
          >
            <el-option
              label="全部"
              value=""
            />
            <el-option
              label="主线"
              value="main"
            />
            <el-option
              label="行业"
              value="industry"
            />
            <el-option
              label="材料"
              value="material"
            />
            <el-option
              label="项目"
              value="project"
            />
            <el-option
              label="实验"
              value="experiment"
            />
          </el-select>
          <el-button
            type="primary"
            @click="createDialog = true"
          >
            创建分支
          </el-button>
          <el-button @click="mergeDialog = true">
            合并分支
          </el-button>
        </div>
      </div>
    </el-card>

    <div
      v-if="loading"
      class="loading"
    >
      加载中...
    </div>

    <el-table
      v-else
      :data="branches"
      stripe
    >
      <el-table-column
        prop="name"
        label="分支名称"
        min-width="150"
      />
      <el-table-column
        label="类型"
        width="120"
      >
        <template #default="{ row }">
          <el-tag
            :type="getBranchTypeTagType(row.metadata?.type)"
            size="small"
          >
            {{ row.metadata?.type || 'unknown' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column
        prop="base_branch"
        label="基础分支"
        width="120"
      >
        <template #default="{ row }">
          {{ row.base_branch || '-' }}
        </template>
      </el-table-column>
      <el-table-column
        label="提交记录"
        width="100"
      >
        <template #default="{ row }">
          {{ row.commit_log?.length || 0 }}
        </template>
      </el-table-column>
      <el-table-column
        label="更新时间"
        width="180"
      >
        <template #default="{ row }">
          {{ formatSecondsTimestamp(row.updated_at) }}
        </template>
      </el-table-column>
      <el-table-column
        label="操作"
        width="180"
        fixed="right"
      >
        <template #default="{ row }">
          <el-button
            size="small"
            @click="$router.push(`/templates/${row.branch_id}`)"
          >
            详情
          </el-button>
          <el-button
            v-if="row.metadata?.type !== 'main'"
            size="small"
            type="danger"
            @click="deleteBranch(row.branch_id, row.metadata?.type)"
          >
            删除
          </el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty
      v-if="!loading && branches.length === 0"
      description="暂无分支"
    />

    <!-- Create Dialog -->
    <el-dialog
      v-model="createDialog"
      title="创建分支"
      width="500px"
    >
      <el-form
        :model="createForm"
        label-width="80px"
      >
        <el-form-item label="名称">
          <el-input
            v-model="createForm.name"
            placeholder="分支名称"
          />
        </el-form-item>
        <el-form-item label="基础分支">
          <el-select
            v-model="createForm.base_branch"
            clearable
            placeholder="无（主线）"
          >
            <el-option
              v-for="b in branches"
              :key="b.branch_id"
              :label="b.name"
              :value="b.branch_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="createForm.type">
            <el-option
              label="主线"
              value="main"
            />
            <el-option
              label="行业"
              value="industry"
            />
            <el-option
              label="材料"
              value="material"
            />
            <el-option
              label="项目"
              value="project"
            />
            <el-option
              label="实验"
              value="experiment"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="初始数据">
          <el-input
            v-model="branchDataInput"
            type="textarea"
            :rows="6"
            placeholder="JSON 格式的模板数据"
          />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="createBranch"
        >
          创建
        </el-button>
      </template>
    </el-dialog>

    <!-- Merge Dialog -->
    <el-dialog
      v-model="mergeDialog"
      title="合并分支"
      width="500px"
    >
      <el-form
        :model="mergeForm"
        label-width="80px"
      >
        <el-form-item label="源分支">
          <el-select v-model="mergeForm.source_id">
            <el-option
              v-for="b in branches.filter(x => x.metadata?.type !== 'main')"
              :key="b.branch_id"
              :label="b.name"
              :value="b.branch_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="目标分支">
          <el-select v-model="mergeForm.target_id">
            <el-option
              v-for="b in branches"
              :key="b.branch_id"
              :label="b.name"
              :value="b.branch_id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="策略">
          <el-select v-model="mergeForm.strategy">
            <el-option
              label="覆盖"
              value="overwrite"
            />
            <el-option
              label="深度合并"
              value="deep_merge"
            />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeDialog = false">
          取消
        </el-button>
        <el-button
          type="primary"
          @click="mergeBranch"
        >
          合并
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.branch-manager-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { margin: 0; }
.header-actions { display: flex; align-items: center; }
.loading { text-align: center; padding: 40px; color: var(--text-tertiary); }
.header-card { margin-bottom: 16px; }
</style>
