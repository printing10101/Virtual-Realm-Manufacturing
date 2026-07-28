<template>
  <div class="flywheel-dashboard-page">
    <!-- ===== Page Header ===== -->
    <div class="page-header">
      <div class="page-header__title">
        <h1>{{ t('flywheel.pageTitle') }}</h1>
        <span class="page-header__subtitle">
          {{ t('flywheel.pageSubtitle') }}
        </span>
      </div>
      <div class="page-header__actions">
        <el-tag
          v-if="store.status"
          :type="store.healthTagType"
          size="default"
        >
          {{ t('flywheel.healthLabel') }}: {{ store.healthStatusLabel }}
        </el-tag>
        <el-button
          size="small"
          :icon="Refresh"
          :loading="store.anyLoading"
          @click="handleRefreshAll"
        >
          {{ t('flywheel.btnRefresh') }}
        </el-button>
      </div>
    </div>

    <!-- ===== Error Banner ===== -->
    <el-alert
      v-if="store.error"
      :title="store.error"
      type="error"
      show-icon
      :closable="true"
      class="error-banner"
      @close="store.error = null"
    />

    <!-- ===== Tabs ===== -->
    <el-tabs
      v-model="activeTab"
      type="card"
      class="flywheel-tabs"
    >
      <!-- ====== Tab 1: 概览 ====== -->
      <el-tab-pane
        :label="t('flywheel.tabOverview')"
        name="overview"
      >
        <div
          v-loading="store.loading"
          class="tab-content"
        >
          <el-empty
            v-if="!store.status && !store.loading"
            :description="t('flywheel.emptyNoStatus')"
            :image-size="80"
          />
          <template v-else-if="store.status">
            <!-- ===== 健康分数卡片 ===== -->
            <el-row :gutter="16" class="metric-cards">
              <el-col :span="6">
                <div class="metric-card metric-card--health">
                  <div class="metric-card__label">{{ t('flywheel.metricHealthScore') }}</div>
                  <div class="metric-card__value">
                    {{ store.formatNumber(store.status.health_score) }}
                  </div>
                  <div class="metric-card__unit">/ 100</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricDataVolume') }}</div>
                  <div class="metric-card__value">
                    {{ store.formatNumber(store.status.data_volume) }}
                  </div>
                  <div class="metric-card__unit">{{ t('flywheel.unitRecords') }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricModelQuality') }}</div>
                  <div class="metric-card__value">
                    {{ store.formatPercent(store.status.model_quality) }}
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricAdoptionRate') }}</div>
                  <div class="metric-card__value">
                    {{ store.formatPercent(store.status.adoption_rate) }}
                  </div>
                </div>
              </el-col>
            </el-row>

            <el-row :gutter="16" class="metric-cards">
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricUncertainty') }}</div>
                  <div class="metric-card__value">
                    {{ (store.status.uncertainty_mean ?? 0).toFixed(3) }}
                  </div>
                  <div class="metric-card__unit">/ 1</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricFeedbackDelay') }}</div>
                  <div class="metric-card__value">
                    {{ store.formatNumber(store.status.feedback_delay) }}
                  </div>
                  <div class="metric-card__unit">{{ t('flywheel.unitMinutes') }}</div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricStatus') }}</div>
                  <div class="metric-card__value">
                    <el-tag :type="store.healthTagType">{{ store.healthStatusLabel }}</el-tag>
                  </div>
                </div>
              </el-col>
              <el-col :span="6">
                <div class="metric-card">
                  <div class="metric-card__label">{{ t('flywheel.metricTimestamp') }}</div>
                  <div class="metric-card__value metric-card__value--small">
                    {{ store.formatTime(store.status.timestamp) }}
                  </div>
                </div>
              </el-col>
            </el-row>

            <!-- ===== 周报摘要 ===== -->
            <el-card class="section-card" shadow="never">
              <template #header>
                <span class="section-title">{{ t('flywheel.weeklyReportTitle') }}</span>
                <el-button
                  size="small"
                  link
                  :loading="store.reportLoading"
                  @click="handleFetchWeeklyReport"
                >
                  {{ t('flywheel.btnRegenerate') }}
                </el-button>
              </template>
              <el-empty
                v-if="!store.weeklyReport && !store.reportLoading"
                :description="t('flywheel.emptyNoReport')"
                :image-size="60"
              />
              <div v-else-if="store.weeklyReport" class="report-body">
                <el-descriptions :column="2" border>
                  <el-descriptions-item :label="t('flywheel.reportGeneratedAt')">
                    {{ store.formatTime(store.weeklyReport.generated_at) }}
                  </el-descriptions-item>
                  <el-descriptions-item :label="t('flywheel.reportType')">
                    {{ store.weeklyReport.report_type }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="store.weeklyReport.period"
                    :label="t('flywheel.reportPeriod')"
                  >
                    {{ store.weeklyReport.period.start }} ~ {{ store.weeklyReport.period.end }}
                  </el-descriptions-item>
                  <el-descriptions-item
                    v-if="store.weeklyReport.summary"
                    :label="t('flywheel.reportSummary')"
                  >
                    <pre class="report-summary">{{ JSON.stringify(store.weeklyReport.summary, null, 2) }}</pre>
                  </el-descriptions-item>
                </el-descriptions>
              </div>
            </el-card>
          </template>
        </div>
      </el-tab-pane>

      <!-- ====== Tab 2: 反馈 ====== -->
      <el-tab-pane
        :label="t('flywheel.tabFeedback')"
        name="feedback"
      >
        <div class="tab-content">
          <el-row :gutter="16" class="metric-cards">
            <el-col :span="6">
              <div class="metric-card">
                <div class="metric-card__label">{{ t('flywheel.feedbackDataVolume') }}</div>
                <div class="metric-card__value">
                  {{ store.formatNumber(store.feedbackStats.dataVolume) }}
                </div>
                <div class="metric-card__unit">{{ t('flywheel.unitRecords') }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="metric-card">
                <div class="metric-card__label">{{ t('flywheel.feedbackAdoptionRate') }}</div>
                <div class="metric-card__value">
                  {{ store.formatPercent(store.feedbackStats.adoptionRate) }}
                </div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="metric-card">
                <div class="metric-card__label">{{ t('flywheel.feedbackDelay') }}</div>
                <div class="metric-card__value">
                  {{ store.formatNumber(store.feedbackStats.feedbackDelay) }}
                </div>
                <div class="metric-card__unit">{{ t('flywheel.unitMinutes') }}</div>
              </div>
            </el-col>
            <el-col :span="6">
              <div class="metric-card">
                <div class="metric-card__label">{{ t('flywheel.feedbackHealthScore') }}</div>
                <div class="metric-card__value">
                  {{ store.formatNumber(store.feedbackStats.healthScore) }}
                </div>
                <div class="metric-card__unit">/ 100</div>
              </div>
            </el-col>
          </el-row>

          <el-alert
            :title="t('flywheel.feedbackAdoptionHint')"
            type="info"
            show-icon
            :closable="false"
            class="info-banner"
          />

          <el-card class="section-card" shadow="never">
            <template #header>
              <span class="section-title">{{ t('flywheel.metricDefinitionsTitle') }}</span>
              <el-button
                size="small"
                link
                :loading="store.definitionsLoading"
                @click="store.fetchDefinitions()"
              >
                {{ t('flywheel.btnReload') }}
              </el-button>
            </template>
            <el-table
              :data="store.metricDefinitions"
              size="small"
              stripe
              :empty-text="t('flywheel.emptyNoDefinitions')"
            >
              <el-table-column
                prop="name"
                :label="t('flywheel.colMetricName')"
                width="180"
              />
              <el-table-column
                prop="description"
                :label="t('flywheel.colMetricDescription')"
              />
              <el-table-column
                prop="unit"
                :label="t('flywheel.colMetricUnit')"
                width="100"
              />
              <el-table-column
                prop="range"
                :label="t('flywheel.colMetricRange')"
                width="120"
              />
              <el-table-column
                prop="calculation"
                :label="t('flywheel.colMetricCalculation')"
                show-overflow-tooltip
              />
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ====== Tab 3: 模型热更新 ====== -->
      <el-tab-pane
        :label="t('flywheel.tabModels')"
        name="models"
      >
        <div
          v-loading="store.deploymentsLoading"
          class="tab-content"
        >
          <div class="filter-bar">
            <el-input
              v-model="filterModelName"
              size="small"
              :placeholder="t('flywheel.filterModelName')"
              clearable
              style="width: 240px"
              @change="handleFilterDeployments"
            />
            <el-select
              v-model="filterStatus"
              size="small"
              :placeholder="t('flywheel.filterStatus')"
              clearable
              style="width: 160px"
              @change="handleFilterDeployments"
            >
              <el-option value="deploying" :label="t('flywheel.statusDeploying')" />
              <el-option value="observing" :label="t('flywheel.statusObserving')" />
              <el-option value="promoted" :label="t('flywheel.statusPromoted')" />
              <el-option value="rolled_back" :label="t('flywheel.statusRolledBack')" />
              <el-option value="failed" :label="t('flywheel.statusFailed')" />
            </el-select>
            <el-button
              size="small"
              type="primary"
              @click="handleFilterDeployments"
            >
              {{ t('flywheel.btnSearch') }}
            </el-button>
            <el-button
              size="small"
              @click="handleResetDeploymentFilters"
            >
              {{ t('flywheel.btnReset') }}
            </el-button>
          </div>

          <!-- ===== 活跃部署 ===== -->
          <el-card class="section-card" shadow="never">
            <template #header>
              <span class="section-title">
                {{ t('flywheel.activeDeploymentsTitle') }}
                <el-tag type="warning" size="small" class="count-tag">
                  {{ store.activeDeployments.length }}
                </el-tag>
              </span>
            </template>
            <el-empty
              v-if="store.activeDeployments.length === 0"
              :description="t('flywheel.emptyNoActiveDeployments')"
              :image-size="60"
            />
            <el-table
              v-else
              :data="store.activeDeployments"
              size="small"
              stripe
            >
              <el-table-column
                prop="deployment_id"
                :label="t('flywheel.colDeploymentId')"
                width="180"
              />
              <el-table-column
                prop="model_name"
                :label="t('flywheel.colModelName')"
                width="160"
              />
              <el-table-column
                prop="new_model_uri"
                :label="t('flywheel.colNewModelUri')"
                show-overflow-tooltip
              />
              <el-table-column
                prop="status"
                :label="t('flywheel.colStatus')"
                width="120"
              >
                <template #default="{ row }">
                  <el-tag :type="deploymentStatusTagType(row.status)">
                    {{ deploymentStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="canary_ratio"
                :label="t('flywheel.colCanaryRatio')"
                width="110"
              >
                <template #default="{ row }">
                  {{ store.formatPercent((row.canary_ratio ?? 0) * 100, 0) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="created_at"
                :label="t('flywheel.colCreatedAt')"
                width="180"
              >
                <template #default="{ row }">
                  {{ store.formatTime(row.created_at) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>

          <!-- ===== 历史部署 ===== -->
          <el-card class="section-card" shadow="never">
            <template #header>
              <span class="section-title">
                {{ t('flywheel.allDeploymentsTitle') }}
                <el-tag size="small" class="count-tag">
                  {{ store.deployments.length }}
                </el-tag>
              </span>
            </template>
            <el-empty
              v-if="store.deployments.length === 0"
              :description="t('flywheel.emptyNoDeployments')"
              :image-size="60"
            />
            <el-table
              v-else
              :data="store.deployments"
              size="small"
              stripe
            >
              <el-table-column
                prop="deployment_id"
                :label="t('flywheel.colDeploymentId')"
                width="180"
              />
              <el-table-column
                prop="model_name"
                :label="t('flywheel.colModelName')"
                width="160"
              />
              <el-table-column
                prop="new_model_uri"
                :label="t('flywheel.colNewModelUri')"
                show-overflow-tooltip
              />
              <el-table-column
                prop="status"
                :label="t('flywheel.colStatus')"
                width="120"
              >
                <template #default="{ row }">
                  <el-tag :type="deploymentStatusTagType(row.status)">
                    {{ deploymentStatusLabel(row.status) }}
                  </el-tag>
                </template>
              </el-table-column>
              <el-table-column
                prop="decision"
                :label="t('flywheel.colDecision')"
                width="120"
              >
                <template #default="{ row }">
                  {{ row.decision || '-' }}
                </template>
              </el-table-column>
              <el-table-column
                prop="created_at"
                :label="t('flywheel.colCreatedAt')"
                width="180"
              >
                <template #default="{ row }">
                  {{ store.formatTime(row.created_at) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="updated_at"
                :label="t('flywheel.colUpdatedAt')"
                width="180"
              >
                <template #default="{ row }">
                  {{ store.formatTime(row.updated_at) }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>

      <!-- ====== Tab 4: 指标历史 ====== -->
      <el-tab-pane
        :label="t('flywheel.tabMetrics')"
        name="metrics"
      >
        <div
          v-loading="store.metricsLoading"
          class="tab-content"
        >
          <div class="filter-bar">
            <span class="filter-label">{{ t('flywheel.daysRangeLabel') }}</span>
            <el-select
              v-model="metricsDays"
              size="small"
              style="width: 120px"
              @change="handleMetricsDaysChange"
            >
              <el-option :value="1" label="1 天" />
              <el-option :value="7" label="7 天" />
              <el-option :value="14" label="14 天" />
              <el-option :value="30" label="30 天" />
              <el-option :value="90" label="90 天" />
            </el-select>
            <el-button
              size="small"
              type="primary"
              @click="handleRefreshMetrics"
            >
              {{ t('flywheel.btnRefresh') }}
            </el-button>
          </div>

          <!-- ===== 当前指标 ===== -->
          <el-card class="section-card" shadow="never">
            <template #header>
              <span class="section-title">{{ t('flywheel.currentMetricsTitle') }}</span>
            </template>
            <el-empty
              v-if="!store.currentMetrics && !store.metricsLoading"
              :description="t('flywheel.emptyNoCurrentMetrics')"
              :image-size="60"
            />
            <el-descriptions
              v-else-if="store.currentMetrics"
              :column="3"
              border
            >
              <el-descriptions-item :label="t('flywheel.metricDataVolume')">
                {{ store.formatNumber(store.currentMetrics.data_volume) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('flywheel.metricModelQuality')">
                {{ store.formatPercent(store.currentMetrics.model_quality) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('flywheel.metricAdoptionRate')">
                {{ store.formatPercent(store.currentMetrics.adoption_rate) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('flywheel.metricUncertainty')">
                {{ (store.currentMetrics.uncertainty_mean ?? 0).toFixed(3) }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('flywheel.metricFeedbackDelay')">
                {{ store.formatNumber(store.currentMetrics.feedback_delay) }}
                {{ t('flywheel.unitMinutes') }}
              </el-descriptions-item>
              <el-descriptions-item :label="t('flywheel.metricTimestamp')">
                {{ store.formatTime(store.currentMetrics.timestamp) }}
              </el-descriptions-item>
            </el-descriptions>
          </el-card>

          <!-- ===== 历史指标表格 ===== -->
          <el-card class="section-card" shadow="never">
            <template #header>
              <span class="section-title">
                {{ t('flywheel.historicalMetricsTitle') }}
                <span class="period-hint">
                  ({{ t('flywheel.periodDaysLabel', { days: store.metricsPeriodDays }) }})
                </span>
              </span>
            </template>
            <el-empty
              v-if="store.historicalMetrics.length === 0"
              :description="t('flywheel.emptyNoHistoricalMetrics')"
              :image-size="60"
            />
            <el-table
              v-else
              :data="store.historicalMetrics"
              size="small"
              stripe
              max-height="480"
            >
              <el-table-column
                prop="timestamp"
                :label="t('flywheel.colTimestamp')"
                width="200"
              >
                <template #default="{ row }">
                  {{ store.formatTime(row.timestamp) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="data_volume"
                :label="t('flywheel.metricDataVolume')"
                width="140"
              >
                <template #default="{ row }">
                  {{ store.formatNumber(row.data_volume) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="model_quality"
                :label="t('flywheel.metricModelQuality')"
                width="140"
              >
                <template #default="{ row }">
                  {{ store.formatPercent(row.model_quality) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="adoption_rate"
                :label="t('flywheel.metricAdoptionRate')"
                width="140"
              >
                <template #default="{ row }">
                  {{ store.formatPercent(row.adoption_rate) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="uncertainty_mean"
                :label="t('flywheel.metricUncertainty')"
                width="140"
              >
                <template #default="{ row }">
                  {{ (row.uncertainty_mean ?? 0).toFixed(3) }}
                </template>
              </el-table-column>
              <el-table-column
                prop="feedback_delay"
                :label="t('flywheel.metricFeedbackDelay')"
              >
                <template #default="{ row }">
                  {{ store.formatNumber(row.feedback_delay) }}
                  {{ t('flywheel.unitMinutes') }}
                </template>
              </el-table-column>
            </el-table>
          </el-card>
        </div>
      </el-tab-pane>
    </el-tabs>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
import { useFlywheelStore } from '@/stores/flywheel'
import type { DeploymentStatus } from '@/stores/flywheel'

const { t } = useI18n()
const store = useFlywheelStore()

// ---------------------------------------------------------------------------
// 本地状态
// ---------------------------------------------------------------------------
const activeTab = ref<'overview' | 'feedback' | 'models' | 'metrics'>('overview')
const filterModelName = ref<string>('')
const filterStatus = ref<DeploymentStatus | ''>('')
const metricsDays = ref<number>(7)

// ---------------------------------------------------------------------------
// 状态映射（部署）
// ---------------------------------------------------------------------------
function deploymentStatusTagType(
  status: DeploymentStatus,
): 'success' | 'warning' | 'danger' | 'info' {
  const map: Record<DeploymentStatus, 'success' | 'warning' | 'danger' | 'info'> = {
    deploying: 'info',
    observing: 'warning',
    promoted: 'success',
    rolled_back: 'danger',
    failed: 'danger',
  }
  return map[status] ?? 'info'
}

function deploymentStatusLabel(status: DeploymentStatus): string {
  const map: Record<DeploymentStatus, string> = {
    deploying: t('flywheel.statusDeploying'),
    observing: t('flywheel.statusObserving'),
    promoted: t('flywheel.statusPromoted'),
    rolled_back: t('flywheel.statusRolledBack'),
    failed: t('flywheel.statusFailed'),
  }
  return map[status] ?? status
}

// ---------------------------------------------------------------------------
// 事件处理
// ---------------------------------------------------------------------------
async function handleRefreshAll(): Promise<void> {
  await store.refreshAll(metricsDays.value)
}

async function handleFetchWeeklyReport(): Promise<void> {
  await store.fetchWeeklyReport(false)
}

async function handleRefreshMetrics(): Promise<void> {
  await store.fetchMetrics(metricsDays.value)
}

async function handleMetricsDaysChange(): Promise<void> {
  await store.fetchMetrics(metricsDays.value)
}

async function handleFilterDeployments(): Promise<void> {
  await store.fetchDeployments(
    filterModelName.value || undefined,
    filterStatus.value || undefined,
  )
}

async function handleResetDeploymentFilters(): Promise<void> {
  filterModelName.value = ''
  filterStatus.value = ''
  await store.fetchDeployments()
}

// ---------------------------------------------------------------------------
// 生命周期
// ---------------------------------------------------------------------------
onMounted(() => {
  void store.refreshAll(metricsDays.value)
})
</script>

<style scoped>
.flywheel-dashboard-page {
  padding: 16px 24px;
  height: 100%;
  overflow-y: auto;
}

.page-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 16px;
}

.page-header__title h1 {
  margin: 0 0 4px 0;
  font-size: 20px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.page-header__subtitle {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.page-header__actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.error-banner {
  margin-bottom: 16px;
}

.info-banner {
  margin-bottom: 16px;
}

.flywheel-tabs {
  margin-top: 8px;
}

.tab-content {
  padding: 8px 4px;
}

.metric-cards {
  margin-bottom: 16px;
}

.metric-card {
  padding: 16px;
  border: 1px solid var(--el-border-color-light);
  border-radius: var(--radius-sm);
  background: var(--el-bg-color);
  transition: border-color 0.2s, box-shadow 0.2s;
}

.metric-card:hover {
  border-color: var(--brand-300);
  box-shadow: var(--shadow-sm);
}

.metric-card--health {
  background: linear-gradient(135deg, var(--accent-light), var(--el-bg-color));
  border-color: var(--brand-200);
}

.metric-card__label {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-bottom: 8px;
}

.metric-card__value {
  font-size: 22px;
  font-weight: 600;
  color: var(--el-text-color-primary);
  line-height: 1.4;
}

.metric-card__value--small {
  font-size: 13px;
  font-weight: 500;
}

.metric-card__unit {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  margin-top: 4px;
}

.section-card {
  margin-bottom: 16px;
}

.section-card :deep(.el-card__header) {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 16px;
}

.section-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--el-text-color-primary);
}

.count-tag {
  margin-left: 8px;
}

.period-hint {
  font-size: 12px;
  color: var(--el-text-color-secondary);
  font-weight: normal;
  margin-left: 4px;
}

.filter-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.filter-label {
  font-size: 13px;
  color: var(--el-text-color-secondary);
}

.report-body {
  padding: 4px 0;
}

.report-summary {
  margin: 0;
  font-family: var(--font-mono);
  font-size: 12px;
  white-space: pre-wrap;
  word-break: break-all;
  max-height: 240px;
  overflow-y: auto;
}
</style>
