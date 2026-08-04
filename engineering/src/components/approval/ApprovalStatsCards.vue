<template>
  <el-row :gutter="16" class="stats-row">
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card stat-pending">
        <div class="stat-value">{{ counts.pending }}</div>
        <div class="stat-label">{{ t('approvalDashboard.statPending') }}</div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card stat-review">
        <div class="stat-value">{{ counts.under_review }}</div>
        <div class="stat-label">{{ t('approvalDashboard.statUnderReview') }}</div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card stat-approved">
        <div class="stat-value">{{ counts.approved }}</div>
        <div class="stat-label">{{ t('approvalDashboard.statApproved') }}</div>
      </el-card>
    </el-col>
    <el-col :span="6">
      <el-card shadow="hover" class="stat-card stat-rejected">
        <div class="stat-value">{{ counts.rejected }}</div>
        <div class="stat-label">{{ t('approvalDashboard.statRejected') }}</div>
      </el-card>
    </el-col>
  </el-row>
</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'

const { t } = useI18n()

interface ApprovalCounts {
  pending: number
  under_review: number
  approved: number
  rejected: number
}

defineProps<{
  counts: ApprovalCounts
}>()
</script>

<style scoped>
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

@media (max-width: 768px) {
  .stats-row .el-col {
    margin-bottom: 12px;
  }
}
</style>