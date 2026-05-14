<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

type TagType = 'success' | 'primary' | 'info' | 'warning' | 'danger'

const route = useRoute()
const branchId = route.params.id as string
const branch = ref<any>(null)
const evolutionHistory = ref<any[]>([])
const abExperiments = ref<any[]>([])
const metrics = ref<any>(null)
const loading = ref(false)
const activeTab = ref('info')

const API_BASE = import.meta.env.VITE_API_BASE || '/api/v1'

async function fetchBranch() {
  loading.value = true
  try {
    const res = await fetch(`${API_BASE}/templates/branches/${branchId}`)
    const data = await res.json()
    if (data.code === 'SUCCESS') branch.value = data.data
  } catch { /* empty */ } finally {
    loading.value = false
  }
}

async function fetchEvolutionHistory() {
  try {
    const res = await fetch(`${API_BASE}/templates/evolution/history?branch_id=${branchId}`)
    const data = await res.json()
    if (data.code === 'SUCCESS') evolutionHistory.value = data.data
  } catch { /* empty */ }
}

async function fetchABExperiments() {
  try {
    const res = await fetch(`${API_BASE}/templates/ab_tests`)
    const data = await res.json()
    if (data.code === 'SUCCESS') {
      abExperiments.value = (data.data || []).filter(
        (e: any) => e.control_branch === branchId || e.candidate_branch === branchId
      )
    }
  } catch { /* empty */ }
}

async function fetchMetrics() {
  try {
    const res = await fetch(`${API_BASE}/template_market/templates/${branchId}/metrics`)
    const data = await res.json()
    if (data.code === 'SUCCESS') metrics.value = data.data
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
  }
  return colors[type] || 'info'
}

onMounted(() => {
  fetchBranch()
  fetchEvolutionHistory()
  fetchABExperiments()
  fetchMetrics()
})
</script>

<template>
  <div class="template-detail-page">
    <el-page-header @back="$router.back()" :title="'返回'" class="page-header" />

    <el-card v-if="branch" class="info-card">
      <template #header>
        <div class="branch-header">
          <h2>{{ branch.name }}</h2>
          <el-tag :type="getBranchTypeColor(branch.metadata?.type)">
            {{ branch.metadata?.type || 'unknown' }}
          </el-tag>
        </div>
      </template>

      <el-descriptions :column="2" border>
        <el-descriptions-item label="分支ID">{{ branch.branch_id }}</el-descriptions-item>
        <el-descriptions-item label="基础分支">{{ branch.base_branch || '无' }}</el-descriptions-item>
        <el-descriptions-item label="创建时间">{{ formatDate(branch.created_at) }}</el-descriptions-item>
        <el-descriptions-item label="更新时间">{{ formatDate(branch.updated_at) }}</el-descriptions-item>
        <el-descriptions-item label="提交记录">{{ branch.commit_log?.length || 0 }} 条</el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-tabs v-model="activeTab" class="detail-tabs">
      <el-tab-pane label="模板数据" name="info">
        <el-card v-if="branch">
          <pre class="template-data">{{ JSON.stringify(branch.template_data, null, 2) }}</pre>
        </el-card>
      </el-tab-pane>

      <el-tab-pane label="进化历史" name="evolution">
        <el-timeline v-if="evolutionHistory.length > 0">
          <el-timeline-item v-for="entry in evolutionHistory" :key="entry.id" :timestamp="formatDate(entry.created_at)">
            <el-tag :type="entry.action === 'applied' ? 'success' : 'info'" size="small">
              {{ entry.action }}
            </el-tag>
            <div class="evolution-detail">
              建议ID: {{ entry.suggestion_id }}
              <pre v-if="entry.details">{{ JSON.stringify(entry.details, null, 2) }}</pre>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty v-else description="暂无进化记录" />
      </el-tab-pane>

      <el-tab-pane label="A/B测试" name="ab">
        <el-table :data="abExperiments" stripe>
          <el-table-column prop="name" label="实验名称" />
          <el-table-column label="控制组" width="120">
            <template #default="{ row }">
              <el-tag>{{ row.control_branch === branchId ? '本分支' : row.control_branch }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column label="候选组" width="120">
            <template #default="{ row }">
              <el-tag :type="row.candidate_branch === branchId ? 'primary' : 'info'">
                {{ row.candidate_branch === branchId ? '本分支' : row.candidate_branch }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column prop="status" label="状态" width="100" />
          <el-table-column prop="result" label="结果" width="120" />
        </el-table>
        <el-empty v-if="abExperiments.length === 0" description="暂无A/B测试" />
      </el-tab-pane>

      <el-tab-pane label="效果指标" name="metrics">
        <el-descriptions v-if="metrics" :column="2" border>
          <el-descriptions-item label="成功率">{{ (metrics.success_rate * 100).toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="实验次数">{{ metrics.total_experiments }}</el-descriptions-item>
          <el-descriptions-item label="采用次数">{{ metrics.adoption_count }}</el-descriptions-item>
          <el-descriptions-item label="最后更新">{{ formatDate(metrics.last_updated) }}</el-descriptions-item>
        </el-descriptions>
        <el-empty v-else description="暂无效果数据" />
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<style scoped>
.template-detail-page { padding: 20px; }
.page-header { margin-bottom: 16px; }
.branch-header { display: flex; align-items: center; gap: 12px; }
.branch-header h2 { margin: 0; }
.detail-tabs { margin-top: 16px; }
.template-data { max-height: 400px; overflow: auto; font-family: monospace; font-size: 13px; background: #f5f7fa; padding: 12px; border-radius: 4px; }
.evolution-detail { margin-top: 4px; font-size: 13px; }
.evolution-detail pre { max-height: 200px; overflow: auto; background: #f5f7fa; padding: 8px; border-radius: 4px; margin-top: 4px; }
.info-card { margin-bottom: 16px; }
</style>
