<template>
  <div>
    <el-card class="log-manage-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.logManagement') }}</span>
          <div class="header-actions">
            <el-button
              size="small"
              type="primary"
              :loading="exportingLogs"
              :disabled="exportingLogs"
              @click="exportSystemLogs(store.settings.logSettings.exportDays)"
            >
              <el-icon v-if="!exportingLogs">
                <Download />
              </el-icon>
              {{ exportingLogs ? `${$t('settings.exporting')} ${exportProgress}%` : $t('settings.exportLogs') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-form
        :model="store.settings.logSettings"
        label-width="160px"
      >
        <el-form-item :label="$t('settings.logLevel')">
          <el-select
            v-model="store.settings.logSettings.logLevel"
            style="width: 160px;"
          >
            <el-option
              label="DEBUG"
              value="DEBUG"
            />
            <el-option
              label="INFO"
              value="INFO"
            />
            <el-option
              label="WARN"
              value="WARN"
            />
            <el-option
              label="ERROR"
              value="ERROR"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.logMaxFileSize')">
          <el-input-number
            v-model="store.settings.logSettings.maxFileSizeMB"
            :min="10"
            :max="500"
            :step="10"
            style="width: 160px;"
          />
          <span style="margin-left: 8px; color: var(--info); font-size: 12px;">MB</span>
        </el-form-item>
        <el-form-item :label="$t('settings.logRetentionDays')">
          <el-input-number
            v-model="store.settings.logSettings.retentionDays"
            :min="1"
            :max="365"
            :step="1"
            style="width: 160px;"
          />
          <span style="margin-left: 8px; color: var(--info); font-size: 12px;">{{ $t('settings.days') }}</span>
        </el-form-item>
        <el-form-item :label="$t('settings.logExportDays')">
          <el-input-number
            v-model="store.settings.logSettings.exportDays"
            :min="1"
            :max="90"
            :step="1"
            style="width: 160px;"
          />
          <span style="margin-left: 8px; color: var(--info); font-size: 12px;">{{ $t('settings.days') }}</span>
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            @click="store.saveSettings()"
          >
            {{ $t('settings.saveSettings') }}
          </el-button>
        </el-form-item>
      </el-form>

      <el-alert
        v-if="exportResult"
        :title="exportResult.success ? $t('settings.exportSuccess') : $t('settings.exportFailed')"
        :type="exportResult.success ? 'success' : 'error'"
        :closable="true"
        show-icon
        style="margin-top: 12px;"
        @close="exportResult = null"
      >
        <div>
          <p>{{ exportResult.message }}</p>
          <p
            v-if="exportResult.outputPath"
            style="font-size: 12px; color: var(--info); word-break: break-all;"
          >
            {{ $t('settings.exportSavePath') }}: {{ exportResult.outputPath }}
          </p>
        </div>
      </el-alert>
    </el-card>

    <el-card class="audit-log-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.auditLog') }}</span>
          <div class="header-actions">
            <el-button
              size="small"
              :loading="exporting"
              @click="exportLogs"
            >
              {{ $t('settings.exportLogs') }}
            </el-button>
            <el-button
              size="small"
              type="danger"
              :loading="clearing"
              @click="clearLogs"
            >
              {{ $t('settings.clearLogs') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-form
        :inline="true"
        class="log-filters"
      >
        <el-form-item :label="$t('settings.aiModule')">
          <el-select
            v-model="logFilters.ai_module"
            :placeholder="$t('settings.allModules')"
            clearable
            @change="loadAuditLogs"
          >
            <el-option
              :label="$t('settings.lnnPredict')"
              value="lnn_predict"
            />
            <el-option
              :label="$t('settings.lnnTrain')"
              value="lnn_train"
            />
            <el-option
              :label="$t('settings.processOptimize')"
              value="process_optimize"
            />
            <el-option
              :label="$t('settings.toolWearAnalyze')"
              value="tool_wear_analyze"
            />
            <el-option
              :label="$t('settings.cadGenerate')"
              value="cad_generate"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.userDecision')">
          <el-select
            v-model="logFilters.user_decision"
            :placeholder="$t('settings.allModules')"
            clearable
            @change="loadAuditLogs"
          >
            <el-option
              :label="$t('settings.accept')"
              value="accept"
            />
            <el-option
              :label="$t('settings.modify')"
              value="modify"
            />
            <el-option
              :label="$t('settings.reject')"
              value="reject"
            />
            <el-option
              :label="$t('settings.autoExecuted')"
              value="auto_executed"
            />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.timeRange')">
          <el-date-picker
            v-model="logFilters.dateRange"
            type="daterange"
            :range-separator="$t('settings.to')"
            :start-placeholder="$t('settings.startDate')"
            :end-placeholder="$t('settings.endDate')"
            @change="loadAuditLogs"
          />
        </el-form-item>
        <el-form-item :label="$t('common.search')">
          <el-input
            v-model="logSearchKeyword"
            :placeholder="$t('settings.keyword')"
            clearable
            @keyup.enter="searchLogs"
          />
          <el-button
            type="primary"
            @click="searchLogs"
          >
            {{ $t('common.search') }}
          </el-button>
        </el-form-item>
      </el-form>

      <div
        v-if="auditLogStatistics"
        class="log-statistics"
      >
        <el-descriptions
          :column="3"
          border
          size="small"
        >
          <el-descriptions-item :label="$t('settings.totalEntries')">
            {{ auditLogStatistics.total_entries }}
          </el-descriptions-item>
          <el-descriptions-item :label="$t('settings.avgConfidence')">
            {{ ((auditLogStatistics.avg_confidence ?? 0) * 100).toFixed(1) }}%
          </el-descriptions-item>
          <el-descriptions-item :label="$t('settings.recent24h')">
            {{ auditLogStatistics.recent_24h }} 条
          </el-descriptions-item>
        </el-descriptions>
      </div>

      <el-table
        v-loading="loadingLogs"
        :data="auditLogs"
        style="width: 100%; margin-top: 16px;"
      >
        <el-table-column
          prop="timestamp_ms"
          :label="$t('common.time')"
          width="180"
        >
          <template #default="{ row }">
            {{ formatTimestamp(row.timestamp_ms) }}
          </template>
        </el-table-column>
        <el-table-column
          prop="ai_module"
          :label="$t('settings.aiModuleCol')"
          width="140"
        >
          <template #default="{ row }">
            <el-tag size="small">
              {{ getModuleName(row.ai_module) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="user_decision"
          :label="$t('settings.userDecisionCol')"
          width="100"
        >
          <template #default="{ row }">
            <el-tag
              :type="getDecisionType(row.user_decision as string)"
              size="small"
            >
              {{ getDecisionName(row.user_decision) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="operation_status"
          :label="$t('settings.opStatus')"
          width="100"
        >
          <template #default="{ row }">
            <el-tag
              :type="getStatusType(row.operation_status as string)"
              size="small"
            >
              {{ getStatusName(row.operation_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column
          prop="confidence"
          :label="$t('settings.confidence')"
          width="100"
        >
          <template #default="{ row }">
            <span v-if="row.confidence !== null">{{ (row.confidence * 100).toFixed(0) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column
          prop="reasoning"
          :label="$t('settings.reasoningDesc')"
          min-width="200"
        >
          <template #default="{ row }">
            <el-tooltip
              :content="row.reasoning"
              placement="top"
            >
              <span class="reasoning-text">{{ row.reasoning }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column
          :label="$t('common.operation')"
          width="80"
        >
          <template #default="{ row }">
            <el-button
              type="primary"
              link
              size="small"
              @click="viewLogDetail(row)"
            >
              {{ $t('common.detail') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-model:current-page="logPagination.page"
        v-model:page-size="logPagination.pageSize"
        :total="logPagination.total"
        :page-sizes="[10, 20, 50, 100]"
        layout="total, sizes, prev, pager, next"
        style="margin-top: 16px; justify-content: flex-end;"
        @size-change="loadAuditLogs"
        @current-change="loadAuditLogs"
      />
    </el-card>

    <el-dialog
      v-model="logDetailVisible"
      :title="$t('settings.logDetail')"
      width="60%"
    >
      <el-descriptions
        v-if="selectedLog"
        :column="1"
        border
      >
        <el-descriptions-item :label="$t('settings.timestamp')">
          {{ formatTimestamp(selectedLog.timestamp_ms as number) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.aiModuleCol')">
          {{ getModuleName(selectedLog.ai_module as string) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.userDecisionCol')">
          {{ getDecisionName(selectedLog.user_decision as string) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.opStatus')">
          {{ getStatusName(selectedLog.operation_status as string) }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.confidence')">
          {{ (selectedLog.confidence as number) !== null ? `${((selectedLog.confidence as number) * 100).toFixed(2)}%` : 'N/A' }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.aiRecommend')">
          <pre>{{ JSON.stringify(selectedLog.ai_recommendation, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.finalExecution')">
          <pre>{{ JSON.stringify(selectedLog.final_execution, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item
          v-if="selectedLog.user_modifications"
          :label="$t('settings.userModifications')"
        >
          <pre>{{ JSON.stringify(selectedLog.user_modifications, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.reasoningDesc')">
          {{ selectedLog.reasoning }}
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { Download } from '@element-plus/icons-vue'
import { useSettingsStore } from '@/stores/settings'
import { useAuditLog } from '@/composables/useAuditLog'
import { useSettings } from '@/composables/useSettings'

const store = useSettingsStore()

const {
  auditLogs,
  auditLogStatistics,
  loadingLogs,
  exporting,
  clearing,
  logSearchKeyword,
  logDetailVisible,
  selectedLog,
  logFilters,
  logPagination,
  loadAuditLogs,
  searchLogs,
  exportLogs,
  clearLogs,
  viewLogDetail,
  getModuleName,
  getDecisionName,
  getDecisionType,
  getStatusName,
  getStatusType,
} = useAuditLog()

const {
  exportingLogs,
  exportProgress,
  exportResult,
  exportSystemLogs,
  formatTimestamp,
} = useSettings()
</script>

<style scoped>
.log-manage-card {
  margin-bottom: 24px;
}

.audit-log-card {
  margin-bottom: 24px;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.header-actions {
  display: flex;
  gap: 8px;
}

.log-filters {
  margin-bottom: 16px;
}

.log-statistics {
  margin-bottom: 16px;
}

.reasoning-text {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 300px;
  display: inline-block;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}
</style>
