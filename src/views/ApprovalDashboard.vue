<template>
  <div class="approval-dashboard-page">
    <div class="dashboard-header">
      <h2>{{ t('approvalDashboard.pageTitle') }}</h2>
      <div class="header-actions">
        <el-button
          :loading="loading"
          :icon="Refresh"
          @click="loadDashboard"
        >
          {{ t('approvalDashboard.btnRefresh') }}
        </el-button>
        <el-button
          type="primary"
          :icon="Document"
          @click="showReport = true"
        >
          {{ t('approvalDashboard.btnGovernanceReport') }}
        </el-button>
      </div>
    </div>

    <el-row
      :gutter="16"
      class="stats-row"
    >
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-pending"
        >
          <div class="stat-value">
            {{ counts.pending }}
          </div>
          <div class="stat-label">
            {{ t('approvalDashboard.statPending') }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-review"
        >
          <div class="stat-value">
            {{ counts.under_review }}
          </div>
          <div class="stat-label">
            {{ t('approvalDashboard.statUnderReview') }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-approved"
        >
          <div class="stat-value">
            {{ counts.approved }}
          </div>
          <div class="stat-label">
            {{ t('approvalDashboard.statApproved') }}
          </div>
        </el-card>
      </el-col>
      <el-col :span="6">
        <el-card
          shadow="hover"
          class="stat-card stat-rejected"
        >
          <div class="stat-value">
            {{ counts.rejected }}
          </div>
          <div class="stat-label">
            {{ t('approvalDashboard.statRejected') }}
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-tabs
      v-model="activeTab"
      class="approval-tabs"
    >
      <el-tab-pane
        :label="t('approvalDashboard.tabPending')"
        name="pending"
      >
        <div
          v-loading="loading"
          class="tab-content"
        >
          <el-empty
            v-if="!pending.length"
            :description="t('approvalDashboard.emptyPending')"
          />
          <el-card
            v-for="req in pending"
            :key="req.request_id"
            class="request-card"
            shadow="hover"
          >
            <div class="request-header">
              <div class="request-id">
                {{ req.request_id }}
              </div>
              <div class="request-meta">
                <el-tag
                  :type="getPriorityTagType(req.priority)"
                  size="small"
                >
                  {{ getPriorityLabel(req.priority) }}
                </el-tag>
                <el-tag
                  :type="getRiskTagType(req.risk_score)"
                  size="small"
                >
                  {{ t('approvalDashboard.riskLabel', { score: req.risk_score.toFixed(2) }) }}
                </el-tag>
              </div>
            </div>
            <div class="request-body">
              <p><strong>{{ t('approvalDashboard.fieldTaskId') }}</strong> {{ req.task_id }}</p>
              <p><strong>{{ t('approvalDashboard.fieldRequester') }}</strong> {{ req.requester }}</p>
              <p><strong>{{ t('approvalDashboard.fieldRequestedAt') }}</strong> {{ formatSecondsTimestamp(req.requested_at) }}</p>
              <p v-if="req.suggested_decision">
                <strong>{{ t('approvalDashboard.fieldSuggestedDecision') }}</strong> {{ req.suggested_decision }}
              </p>
              <el-tag
                v-if="req.emergency_override"
                type="danger"
                size="small"
              >
                {{ t('approvalDashboard.tagEmergencyOverride') }}
              </el-tag>
            </div>
            <div class="request-actions">
              <el-button
                size="small"
                @click="viewDetail(req)"
              >
                {{ t('approvalDashboard.btnDetail') }}
              </el-button>
              <el-button
                size="small"
                type="success"
                @click="quickApprove(req, 'approved')"
              >
                {{ t('approvalDashboard.btnApprove') }}
              </el-button>
              <el-button
                size="small"
                type="danger"
                @click="quickApprove(req, 'rejected')"
              >
                {{ t('approvalDashboard.btnReject') }}
              </el-button>
              <el-button
                size="small"
                type="warning"
                @click="quickApprove(req, 'escalated')"
              >
                {{ t('approvalDashboard.btnEscalate') }}
              </el-button>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane
        :label="t('approvalDashboard.tabApproved')"
        name="approved"
      >
        <div
          v-loading="loading"
          class="tab-content"
        >
          <el-empty
            v-if="!approved.length"
            :description="t('approvalDashboard.emptyApproved')"
          />
          <el-card
            v-for="req in approved"
            :key="req.request_id"
            class="request-card"
            shadow="hover"
          >
            <div class="request-header">
              <div class="request-id">
                {{ req.request_id }}
              </div>
              <el-tag
                type="success"
                size="small"
              >
                {{ t('approvalDashboard.statApproved') }}
              </el-tag>
            </div>
            <div class="request-body">
              <p><strong>{{ t('approvalDashboard.fieldTaskId') }}</strong> {{ req.task_id }}</p>
              <p><strong>{{ t('approvalDashboard.fieldRequester') }}</strong> {{ req.requester }}</p>
              <p><strong>{{ t('approvalDashboard.fieldCompletedAt') }}</strong> {{ formatSecondsTimestamp(req.completed_at) }}</p>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane
        :label="t('approvalDashboard.tabRejected')"
        name="rejected"
      >
        <div
          v-loading="loading"
          class="tab-content"
        >
          <el-empty
            v-if="!rejected.length"
            :description="t('approvalDashboard.emptyRejected')"
          />
          <el-card
            v-for="req in rejected"
            :key="req.request_id"
            class="request-card"
            shadow="hover"
          >
            <div class="request-header">
              <div class="request-id">
                {{ req.request_id }}
              </div>
              <el-tag
                type="danger"
                size="small"
              >
                {{ t('approvalDashboard.statRejected') }}
              </el-tag>
            </div>
            <div class="request-body">
              <p><strong>{{ t('approvalDashboard.fieldTaskId') }}</strong> {{ req.task_id }}</p>
              <p><strong>{{ t('approvalDashboard.fieldRequester') }}</strong> {{ req.requester }}</p>
              <p><strong>{{ t('approvalDashboard.fieldCompletedAt') }}</strong> {{ formatSecondsTimestamp(req.completed_at) }}</p>
            </div>
          </el-card>
        </div>
      </el-tab-pane>

      <el-tab-pane
        :label="t('approvalDashboard.tabHistory')"
        name="history"
      >
        <div
          v-loading="historyLoading"
          class="tab-content"
        >
          <el-table
            :data="history"
            stripe
          >
            <el-table-column
              prop="request_id"
              :label="t('approvalDashboard.colRequestId')"
              width="150"
            />
            <el-table-column
              prop="task_id"
              :label="t('approvalDashboard.colTaskId')"
              width="120"
            />
            <el-table-column
              prop="requester"
              :label="t('approvalDashboard.colRequester')"
              width="100"
            />
            <el-table-column
              prop="status"
              :label="t('approvalDashboard.colStatus')"
              width="100"
            >
              <template #default="{ row }">
                <el-tag
                  :type="getApprovalStatusTagType(row.status)"
                  size="small"
                >
                  {{ getApprovalStatusLabel(row.status) }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column
              prop="risk_score"
              :label="t('approvalDashboard.colRiskScore')"
              width="100"
            >
              <template #default="{ row }">
                {{ row.risk_score.toFixed(2) }}
              </template>
            </el-table-column>
            <el-table-column
              prop="requested_at"
              :label="t('approvalDashboard.colRequestedAt')"
              width="160"
            >
              <template #default="{ row }">
                {{ formatSecondsTimestamp(row.requested_at) }}
              </template>
            </el-table-column>
            <el-table-column
              :label="t('approvalDashboard.colActions')"
              fixed="right"
            >
              <template #default="{ row }">
                <el-button
                  size="small"
                  @click="viewDetail(row as ApprovalRequest)"
                >
                  {{ t('approvalDashboard.btnView') }}
                </el-button>
              </template>
            </el-table-column>
          </el-table>
        </div>
      </el-tab-pane>
    </el-tabs>

    <el-dialog
      v-model="detailDialogVisible"
      :title="t('approvalDashboard.detailDialogTitle')"
      width="800px"
      destroy-on-close
    >
      <div
        v-if="selectedRequest"
        class="detail-content"
      >
        <el-descriptions
          :column="2"
          border
        >
          <el-descriptions-item
            :label="t('approvalDashboard.detailRequestId')"
            :span="2"
          >
            {{ selectedRequest.request_id }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailTaskId')">
            {{ selectedRequest.task_id }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailStatus')">
            <el-tag :type="getApprovalStatusTagType(selectedRequest.status)">
              {{ getApprovalStatusLabel(selectedRequest.status) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailRequester')">
            {{ selectedRequest.requester }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailPriority')">
            <el-tag :type="getPriorityTagType(selectedRequest.priority)">
              {{ getPriorityLabel(selectedRequest.priority) }}
            </el-tag>
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailRiskScore')">
            {{ selectedRequest.risk_score.toFixed(2) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailSuggestedDecision')">
            {{ selectedRequest.suggested_decision }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailRequestedAt')">
            {{ formatSecondsTimestamp(selectedRequest.requested_at) }}
          </el-descriptions-item>
          <el-descriptions-item :label="t('approvalDashboard.detailExpiresAt')">
            {{ formatSecondsTimestamp(selectedRequest.expires_at) }}
          </el-descriptions-item>
        </el-descriptions>

        <el-divider content-position="left">
          {{ t('approvalDashboard.detailOperationContext') }}
        </el-divider>
        <pre class="context-json">{{ formatContext(selectedRequest.context) }}</pre>

        <el-divider
          v-if="selectedRequest.decisions.length"
          content-position="left"
        >
          {{ t('approvalDashboard.detailDecisionHistory') }}
        </el-divider>
        <el-table
          v-if="selectedRequest.decisions.length"
          :data="selectedRequest.decisions"
          size="small"
        >
          <el-table-column
            prop="approver_id"
            :label="t('approvalDashboard.colApprover')"
            width="150"
          />
          <el-table-column
            prop="decision"
            :label="t('approvalDashboard.colDecision')"
            width="100"
          >
            <template #default="{ row }">
              <el-tag
                :type="row.decision === 'approved' ? 'success' : row.decision === 'rejected' ? 'danger' : 'warning'"
                size="small"
              >
                {{ row.decision }}
              </el-tag>
            </template>
          </el-table-column>
          <el-table-column
            prop="comment"
            :label="t('approvalDashboard.colComment')"
            min-width="200"
          />
          <el-table-column
            prop="decided_at"
            :label="t('approvalDashboard.colDecidedAt')"
            width="160"
          >
            <template #default="{ row }">
              {{ formatSecondsTimestamp(row.decided_at) }}
            </template>
          </el-table-column>
        </el-table>

        <el-divider content-position="left">
          {{ t('approvalDashboard.detailDecisionActions') }}
        </el-divider>
        <div class="decision-actions">
          <el-input
            v-model="decisionComment"
            type="textarea"
            :rows="3"
            :placeholder="t('approvalDashboard.decisionCommentPlaceholder')"
            style="margin-bottom: 12px;"
          />
          <el-button
            type="success"
            @click="submitDecision('approved')"
          >
            {{ t('approvalDashboard.btnApprove') }}
          </el-button>
          <el-button
            type="danger"
            @click="submitDecision('rejected')"
          >
            {{ t('approvalDashboard.btnReject') }}
          </el-button>
          <el-button
            type="warning"
            @click="submitDecision('request_info')"
          >
            {{ t('approvalDashboard.btnRequestInfo') }}
          </el-button>
          <el-button
            type="info"
            @click="submitDecision('escalated')"
          >
            {{ t('approvalDashboard.btnEscalate') }}
          </el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="showReport"
      :title="t('approvalDashboard.reportDialogTitle')"
      width="900px"
      destroy-on-close
    >
      <div
        v-loading="reportLoading"
        class="report-content"
      >
        <template v-if="report">
          <el-descriptions
            :column="3"
            border
          >
            <el-descriptions-item :label="t('approvalDashboard.reportTotalRequests')">
              {{ report.total_requests }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportApprovedCount')">
              {{ report.approved_count }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportRejectedCount')">
              {{ report.rejected_count }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportEscalatedCount')">
              {{ report.escalated_count }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportEmergencyCount')">
              {{ report.emergency_count }}
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportAvgApprovalTime')">
              {{ report.avg_approval_time_hours.toFixed(2) }}h
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportRejectionRate')">
              {{ (report.rejection_rate * 100).toFixed(2) }}%
            </el-descriptions-item>
            <el-descriptions-item :label="t('approvalDashboard.reportEscalationRate')">
              {{ (report.escalation_rate * 100).toFixed(2) }}%
            </el-descriptions-item>
          </el-descriptions>
          <el-button
            type="primary"
            style="margin-top: 16px;"
            @click="exportAuditLog"
          >
            {{ t('approvalDashboard.btnExportAuditLog') }}
          </el-button>
        </template>
      </div>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { Refresh, Document } from '@element-plus/icons-vue'
import http from '@/utils/http'
import { triggerFileDownload } from '@/utils/download'
import { formatSecondsTimestamp } from '@/utils/formatters'
import { getPriorityTagType, getPriorityLabel, getApprovalStatusTagType, getApprovalStatusLabel } from '@/utils/statusHelpers'
import { API_CONFIG, buildApiPath } from '@/config/api'
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface ApprovalRequest {
  request_id: string
  task_id: string
  requester: string
  requested_at: number
  priority: string
  context: Record<string, unknown>
  status: string
  assigned_approver: string | null
  approvers: string[]
  decisions: Array<Record<string, unknown>>
  required_approvals: number
  risk_score: number
  risk_factors: string[]
  suggested_decision: string
  emergency_override: boolean
  emergency_reason: string
  expires_at: number | null
  completed_at: number | null
}

interface DashboardData {
  pending: ApprovalRequest[]
  under_review: ApprovalRequest[]
  approved: ApprovalRequest[]
  rejected: ApprovalRequest[]
  counts: {
    pending: number
    under_review: number
    approved: number
    rejected: number
  }
}

interface GovernanceReport {
  total_requests: number
  approved_count: number
  rejected_count: number
  escalated_count: number
  emergency_count: number
  avg_approval_time_hours: number
  rejection_rate: number
  escalation_rate: number
}

const loading = ref(false)
const historyLoading = ref(false)
const activeTab = ref('pending')
const dashboard = ref<DashboardData>({
  pending: [],
  under_review: [],
  approved: [],
  rejected: [],
  counts: { pending: 0, under_review: 0, approved: 0, rejected: 0 },
})
const history = ref<ApprovalRequest[]>([])
const selectedRequest = ref<ApprovalRequest | null>(null)
const detailDialogVisible = ref(false)
const decisionComment = ref('')
const showReport = ref(false)
const reportLoading = ref(false)
const report = ref<GovernanceReport | null>(null)

const pending = computed(() => dashboard.value.pending)
const approved = computed(() => dashboard.value.approved)
const rejected = computed(() => dashboard.value.rejected)
const counts = computed(() => dashboard.value.counts)

async function loadDashboard() {
  loading.value = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.GOVERNANCE, '/approval-dashboard'))
    dashboard.value = res.data?.data || dashboard.value
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('approvalDashboard.msgLoadDashboardFailed', { error: errorMsg }))
  } finally {
    loading.value = false
  }
}

async function loadHistory() {
  historyLoading.value = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.GOVERNANCE, '/approval-requests'), {
      params: { limit: 100 },
    })
    history.value = res.data?.data || []
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('approvalDashboard.msgLoadHistoryFailed', { error: errorMsg }))
  } finally {
    historyLoading.value = false
  }
}

function viewDetail(request: ApprovalRequest) {
  selectedRequest.value = request
  decisionComment.value = ''
  detailDialogVisible.value = true
}

async function quickApprove(request: ApprovalRequest, decision: string) {
  try {
    const comment = decision === 'approved' ? t('approvalDashboard.msgQuickApprove') : decision === 'rejected' ? t('approvalDashboard.msgQuickReject') : t('approvalDashboard.msgQuickEscalate')
    await http.post(buildApiPath(API_CONFIG.GOVERNANCE, `/approval-requests/${request.request_id}/decide`), {
      approver_id: 'current_user',
      decision,
      comment,
    })
    ElMessage.success(t('approvalDashboard.msgApproveSuccess', { decision }))
    await loadDashboard()
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('approvalDashboard.msgApproveFailed', { error: errorMsg }))
  }
}

async function submitDecision(decision: string) {
  if (!selectedRequest.value) return
  try {
    await http.post(buildApiPath(API_CONFIG.GOVERNANCE, `/approval-requests/${selectedRequest.value.request_id}/decide`), {
      approver_id: 'current_user',
      decision,
      comment: decisionComment.value,
    })
    ElMessage.success(t('approvalDashboard.msgSubmitDecisionSuccess', { decision }))
    detailDialogVisible.value = false
    await loadDashboard()
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('approvalDashboard.msgSubmitDecisionFailed', { error: errorMsg }))
  }
}

async function loadReport() {
  reportLoading.value = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.GOVERNANCE, '/reports/governance'), {
      params: { days: 30 },
    })
    report.value = res.data?.data || null
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('approvalDashboard.msgLoadReportFailed', { error: errorMsg }))
  } finally {
    reportLoading.value = false
  }
}

async function exportAuditLog() {
  try {
    const res = await http.get(buildApiPath(API_CONFIG.GOVERNANCE, '/audit-log/export'), {
      params: { format: 'csv' },
    })
    const blob = new Blob([res.data.data], { type: 'text/csv' })
    triggerFileDownload(blob, `audit_log_${Date.now()}.csv`)
    ElMessage.success(t('approvalDashboard.msgExportAuditLogSuccess'))
  } catch (e: unknown) {
    const errorMsg = e instanceof Error ? e.message : String(e)
    ElMessage.error(t('approvalDashboard.msgExportFailed', { error: errorMsg }))
  }
}

function getRiskTagType(score: number): 'primary' | 'success' | 'warning' | 'info' | 'danger' {
  if (score >= 0.8) return 'danger'
  if (score >= 0.6) return 'warning'
  if (score >= 0.4) return 'info'
  return 'success'
}

function formatContext(context: Record<string, any>): string {
  try {
    return JSON.stringify(context, null, 2)
  } catch {
    return String(context)
  }
}

onMounted(() => {
  loadDashboard()
  loadHistory()
  loadReport()
})
</script>

<style scoped>
.approval-dashboard-page {
  padding: 16px;
  max-width: 1600px;
  margin: 0 auto;
}

.dashboard-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.dashboard-header h2 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.stats-row {
  margin-bottom: 16px;
}

.stat-card {
  text-align: center;
  padding: 16px 0;
}

.stat-value {
  font-size: 32px;
  font-weight: 700;
  margin-bottom: 8px;
}

.stat-label {
  font-size: 14px;
  color: var(--text-tertiary);
}

.stat-pending .stat-value { color: var(--warning); }
.stat-review .stat-value { color: var(--info); }
.stat-approved .stat-value { color: var(--success); }
.stat-rejected .stat-value { color: var(--error); }

.approval-tabs {
  margin-top: 16px;
}

.tab-content {
  min-height: 200px;
  padding: 8px;
}

.request-card {
  margin-bottom: 12px;
  border-left: 4px solid var(--accent-primary);
}

.request-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.request-id {
  font-family: monospace;
  font-size: 14px;
  font-weight: 600;
}

.request-meta {
  display: flex;
  gap: 8px;
}

.request-body {
  margin-bottom: 12px;
}

.request-body p {
  margin: 4px 0;
  font-size: 13px;
}

.request-actions {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
  border-top: 1px solid var(--border-light);
  padding-top: 12px;
}

.detail-content {
  max-height: 70vh;
  overflow-y: auto;
}

.context-json {
  background: var(--bg-secondary);
  padding: 12px;
  border-radius: var(--radius-sm);
  font-size: 12px;
  max-height: 200px;
  overflow: auto;
  margin: 0;
}

.decision-actions {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.decision-actions .el-button {
  align-self: flex-start;
}

.report-content {
  min-height: 200px;
}

@media (max-width: 768px) {
  .stats-row .el-col {
    margin-bottom: 12px;
  }
  .request-card {
    margin-bottom: 8px;
  }
}
</style>
