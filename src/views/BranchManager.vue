<script setup lang="ts">
import { ref, onMounted } from 'vue'

type TagType = 'success' | 'primary' | 'info' | 'warning' | 'danger'

const branches = ref<any[]>([])
const loading = ref(false)
const createDialog = ref(false)
const mergeDialog = ref(false)
const mergeForm = ref({ source_id: '', target_id: '', strategy: 'overwrite' })
const createForm = ref({ name: '', base_branch: '', type: 'main', data: {} })
const typeFilter = ref('')
const branchDataInput = ref('{}')

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

async function fetchBranches() {
  loading.value = true
  try {
    const url = typeFilter.value
      ? `${API_BASE}/templates/branches?type=${typeFilter.value}`
      : `${API_BASE}/templates/branches`
    const res = await fetch(url)
    const data = await res.json()
    if (data.code === 'SUCCESS') branches.value = data.data
  } catch { /* empty */ } finally {
    loading.value = false
  }
}

async function createBranch() {
  let data = {}
  try {
    data = JSON.parse(branchDataInput.value || '{}')
  } catch {
    data = {}
  }
  try {
    await fetch(`${API_BASE}/templates/branches`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        name: createForm.value.name,
        base_branch: createForm.value.base_branch || null,
        data,
        metadata: { type: createForm.value.type }
      })
    })
    createDialog.value = false
    createForm.value = { name: '', base_branch: '', type: 'main', data: {} }
    branchDataInput.value = '{}'
    fetchBranches()
  } catch { /* empty */ }
}

async function mergeBranch() {
  try {
    await fetch(`${API_BASE}/templates/branches/${mergeForm.value.source_id}/merge`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        target_id: mergeForm.value.target_id,
        strategy: mergeForm.value.strategy
      })
    })
    mergeDialog.value = false
    fetchBranches()
  } catch { /* empty */ }
}

async function deleteBranch(branchId: string, type: string) {
  if (type === 'main') {
    alert('不能删除主线分支')
    return
  }
  if (!confirm('确定删除此分支？')) return
  try {
    await fetch(`${API_BASE}/templates/branches/${branchId}`, { method: 'DELETE' })
    fetchBranches()
  } catch { /* empty */ }
}

function formatDate(ts: number): string {
  if (!ts) return '-'
  return new Date(ts * 1000).toLocaleString()
}

function getBranchTypeColor(type: string): TagType {
  const colors: Record<string, TagType> = {
    main: 'success',
    industry: 'warning',
    material: 'primary',
    project: 'info',
    experiment: 'danger',
    imported: 'info',
  }
  return colors[type] || 'info'
}

onMounted(fetchBranches)
</script>

<template>
  <div class="branch-manager-page">
    <el-card class="header-card">
      <div class="page-header">
        <h2>分支管理</h2>
        <div class="header-actions">
          <el-select v-model="typeFilter" placeholder="全部类型" clearable @change="fetchBranches" style="width: 150px; margin-right: 12px;">
            <el-option label="全部" value="" />
            <el-option label="主线" value="main" />
            <el-option label="行业" value="industry" />
            <el-option label="材料" value="material" />
            <el-option label="项目" value="project" />
            <el-option label="实验" value="experiment" />
          </el-select>
          <el-button type="primary" @click="createDialog = true">创建分支</el-button>
          <el-button @click="mergeDialog = true">合并分支</el-button>
        </div>
      </div>
    </el-card>

    <div v-if="loading" class="loading">加载中...</div>

    <el-table v-else :data="branches" stripe>
      <el-table-column prop="name" label="分支名称" min-width="150" />
      <el-table-column label="类型" width="120">
        <template #default="{ row }">
          <el-tag :type="getBranchTypeColor(row.metadata?.type)" size="small">
            {{ row.metadata?.type || 'unknown' }}
          </el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="base_branch" label="基础分支" width="120">
        <template #default="{ row }">{{ row.base_branch || '-' }}</template>
      </el-table-column>
      <el-table-column label="提交记录" width="100">
        <template #default="{ row }">{{ row.commit_log?.length || 0 }}</template>
      </el-table-column>
      <el-table-column label="更新时间" width="180">
        <template #default="{ row }">{{ formatDate(row.updated_at) }}</template>
      </el-table-column>
      <el-table-column label="操作" width="180" fixed="right">
        <template #default="{ row }">
          <el-button size="small" @click="$router.push(`/templates/${row.branch_id}`)">详情</el-button>
          <el-button v-if="row.metadata?.type !== 'main'" size="small" type="danger" @click="deleteBranch(row.branch_id, row.metadata?.type)">删除</el-button>
        </template>
      </el-table-column>
    </el-table>

    <el-empty v-if="!loading && branches.length === 0" description="暂无分支" />

    <!-- Create Dialog -->
    <el-dialog v-model="createDialog" title="创建分支" width="500px">
      <el-form :model="createForm" label-width="80px">
        <el-form-item label="名称">
          <el-input v-model="createForm.name" placeholder="分支名称" />
        </el-form-item>
        <el-form-item label="基础分支">
          <el-select v-model="createForm.base_branch" clearable placeholder="无（主线）">
            <el-option v-for="b in branches" :key="b.branch_id" :label="b.name" :value="b.branch_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="类型">
          <el-select v-model="createForm.type">
            <el-option label="主线" value="main" />
            <el-option label="行业" value="industry" />
            <el-option label="材料" value="material" />
            <el-option label="项目" value="project" />
            <el-option label="实验" value="experiment" />
          </el-select>
        </el-form-item>
        <el-form-item label="初始数据">
          <el-input v-model="branchDataInput" type="textarea" :rows="6" placeholder="JSON 格式的模板数据" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="createDialog = false">取消</el-button>
        <el-button type="primary" @click="createBranch">创建</el-button>
      </template>
    </el-dialog>

    <!-- Merge Dialog -->
    <el-dialog v-model="mergeDialog" title="合并分支" width="500px">
      <el-form :model="mergeForm" label-width="80px">
        <el-form-item label="源分支">
          <el-select v-model="mergeForm.source_id">
            <el-option v-for="b in branches.filter(x => x.metadata?.type !== 'main')" :key="b.branch_id" :label="b.name" :value="b.branch_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="目标分支">
          <el-select v-model="mergeForm.target_id">
            <el-option v-for="b in branches" :key="b.branch_id" :label="b.name" :value="b.branch_id" />
          </el-select>
        </el-form-item>
        <el-form-item label="策略">
          <el-select v-model="mergeForm.strategy">
            <el-option label="覆盖" value="overwrite" />
            <el-option label="深度合并" value="deep_merge" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="mergeDialog = false">取消</el-button>
        <el-button type="primary" @click="mergeBranch">合并</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.branch-manager-page { padding: 20px; }
.page-header { display: flex; justify-content: space-between; align-items: center; }
.page-header h2 { margin: 0; }
.header-actions { display: flex; align-items: center; }
.loading { text-align: center; padding: 40px; color: #999; }
.header-card { margin-bottom: 16px; }
</style>
