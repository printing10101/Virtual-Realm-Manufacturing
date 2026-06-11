<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { useI18n } from 'vue-i18n'
import { formatSecondsTimestamp } from '@/utils/formatters'
import { getBranchTypeTagType } from '@/utils/statusHelpers'

const { t } = useI18n()
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

onMounted(() => {
  fetchBranch()
  fetchEvolutionHistory()
  fetchABExperiments()
  fetchMetrics()
})
</script>

<template>
  <div class="template-detail-page">
    <el-page-header
      :title="t('templateDetail.back')"
      class="page-header"
      @back="$router.back()"
    />

    <el-card
      v-if="branch"
      class="info-card"
    >
      <template #header>
        <div class="branch-header">
          <h2>{{ branch.name }}</h2>
          <el-tag :type="getBranchTypeTagType(branch.metadata?.type)">
            {{ branch.metadata?.type || 'unknown' }}
          </el-tag>
        </div>
      </template>

      <el-descriptions
        :column="2"
        border
      >
        <el-descriptions-item :label="t('templateDetail.branchId')">
          {{ branch.branch_id }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('templateDetail.baseBranch')">
          {{ branch.base_branch || t('templateDetail.none') }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('templateDetail.createdAt')">
          {{ formatSecondsTimestamp(branch.created_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('templateDetail.updatedAt')">
          {{ formatSecondsTimestamp(branch.updated_at) }}
        </el-descriptions-item>
        <el-descriptions-item :label="t('templateDetail.commits')">
          {{ t('templateDetail.commitCount', { count: branch.commit_log?.length || 0 }) }}
        </el-descriptions-item>
      </el-descriptions>
    </el-card>

    <el-tabs
      v-model="activeTab"
      class="detail-tabs"
    >
      <el-tab-pane
        :label="t('templateDetail.tabTemplate')"
        name="info"
      >
        <el-card v-if="branch">
          <pre class="template-data">{{ JSON.stringify(branch.template_data, null, 2) }}</pre>
        </el-card>
      </el-tab-pane>

      <el-tab-pane
        :label="t('templateDetail.tabEvolution')"
        name="evolution"
      >
        <el-timeline v-if="evolutionHistory.length > 0">
          <el-timeline-item
            v-for="entry in evolutionHistory"
            :key="entry.id"
            :timestamp="formatSecondsTimestamp(entry.created_at)"
          >
            <el-tag
              :type="entry.action === 'applied' ? 'success' : 'info'"
              size="small"
            >
              {{ entry.action }}
            </el-tag>
            <div class="evolution-detail">
              {{ t('templateDetail.suggestionId', { id: entry.suggestion_id }) }}
              <pre v-if="entry.details">{{ JSON.stringify(entry.details, null, 2) }}</pre>
            </div>
          </el-timeline-item>
        </el-timeline>
        <el-empty
          v-else
          :description="t('templateDetail.noEvolution')"
        />
      </el-tab-pane>

      <el-tab-pane
        :label="t('templateDetail.tabAb')"
        name="ab"
      >
        <el-table
          :data="abExperiments"
          stripe
        >
          <el-table-column
            prop="name"
            :label="t('templateDetail.experimentName')"
          />
          <el-table-column
            :label="t('templateDetail.controlGroup')"
            width="120"
          >
            <template #default="{ row }">
              <el-tag>{{ row.control_branch === branchId ? t('templateDetail.thisBranch') : row.control_branch }}</el-tag>
            </template>
          </el-table-column>
          <el-table-column
            :label="t('templateDetail.candidateGroup')"
            width="120"
          >
            <template #default="{ row }">
              <el-tag :type="row.candidate_branch === branchId ? 'primary' : 'info'">
                {{ row.candidate_branch === branchId ? t('templateDetail.thisBranch') : row.candidate_branch }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="status"
            :label="t('userManagement.colStatus')"
            width="100"
          />
          <el-table-column
            prop="result"
            :label="t('templateDetail.result')"
            width="120"
          />
        </el-table>
        <el-empty
          v-if="abExperiments.length === 0"
          :description="t('templateDetail.noAbTests')"
        />
      </el-tab-pane>

      <el-tab-pane
        :label="t('templateDetail.tabMetrics')"
        name="metrics"
      >
        <el-descriptions
          v-if="metrics"
          :column="2"
          border
        >
          <el-descriptions-item :label="t('templateDetail.successRate')">
            {{ (metrics.success_rate * 100).toFixed(1) }}%
          </el-descriptions-item>
          <el-descriptions-item :label="t('templateDetail.totalExperiments')">
            {{ metrics.total_experiments }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('templateDetail.adoptionCount')">
            {{ metrics.adoption_count }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('templateDetail.lastUpdated')">
            {{ formatSecondsTimestamp(metrics.last_updated) }}
          </el-descriptions-item>
        </el-descriptions>
        <el-empty
          v-else
          :description="t('templateDetail.noMetrics')"
        />
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
