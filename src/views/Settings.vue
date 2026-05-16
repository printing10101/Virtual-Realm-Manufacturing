<template>
  <div class="settings-page">
    <el-alert
      v-if="versionStore.inconsistencyDetails && !versionStore.isConsistent"
      :title="$t('settings.versionWarningTitle')"
      type="error"
      :closable="false"
      show-icon
      class="version-warning"
    >
      <div>
        {{ $t('settings.versionWarningMsg') }}
        <ul v-if="versionStore.inconsistencyDetails">
          <li v-for="(detail, idx) in versionStore.inconsistencyDetails" :key="idx">
            {{ detail }}
          </li>
        </ul>
      </div>
    </el-alert>

    <el-card class="version-card">
      <template #header>
        <div class="card-header">
          {{ $t('settings.versionInfo') }}
          <el-tag :type="versionStore.isConsistent ? 'success' : 'danger'" size="small">
            {{ versionStore.isConsistent ? $t('settings.versionConsistent') : $t('settings.versionInconsistent') }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item :label="$t('settings.frontendVersion')">
          {{ versionStore.frontendVersion }}
          <span v-if="versionStore.frontendCommit" class="commit-hash">
            ({{ versionStore.frontendCommit }})
          </span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.rustBackendVersion')">
          {{ versionStore.rustVersion || $t('settings.loading') }}
          <span v-if="versionStore.rustCommit" class="commit-hash">
            ({{ versionStore.rustCommit }})
          </span>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.pythonSidecarVersion')">
          {{ versionStore.pythonVersion || $t('settings.notConnected') }}
          <span v-if="versionStore.pythonCommit" class="commit-hash">
            ({{ versionStore.pythonCommit }})
          </span>
        </el-descriptions-item>
      </el-descriptions>
      <div class="refresh-btn">
        <el-button
          size="small"
          @click="refreshVersions"
          :loading="versionStore.isLoading"
        >
          {{ $t('settings.refreshVersion') }}
        </el-button>
      </div>
    </el-card>

    <el-card class="settings-card">
      <template #header>
        {{ $t('settings.systemSettings') }}
      </template>
      <el-form :model="store.settings" label-width="140px">
        <el-form-item :label="$t('settings.aiMode')">
          <el-radio-group v-model="store.settings.aiMode">
            <el-radio value="local">{{ $t('settings.localMode') }}</el-radio>
            <el-radio value="cloud">{{ $t('settings.cloudMode') }}</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item :label="$t('settings.localModel')">
          <el-select v-model="store.settings.localModel">
            <el-option label="qwen2.5:7b" value="qwen2.5:7b" />
            <el-option label="qwen2.5:14b" value="qwen2.5:14b" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.computeDevice')">
          <el-select v-model="store.settings.device">
            <el-option label="CPU" value="cpu" />
            <el-option :label="$t('settings.gpuCuda')" value="cuda" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.offlineMode')">
          <el-switch v-model="store.settings.offlineMode" />
        </el-form-item>
        <el-form-item :label="$t('settings.language')">
          <el-select v-model="currentLocale" @change="handleLocaleChange" style="width: 160px;">
            <el-option label="中文" value="zh-CN" />
            <el-option label="English" value="en" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="store.saveSettings()">
            {{ $t('settings.saveSettings') }}
          </el-button>
          <el-button @click="store.resetSettings()">
            {{ $t('common.reset') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="health-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.systemHealth') }}</span>
          <div>
            <el-tag :type="healthStatus.backendOnline ? 'success' : 'danger'" size="small">
              {{ healthStatus.backendOnline ? $t('common.online') : $t('common.offline') }}
            </el-tag>
            <el-button size="small" @click="refreshHealth" :loading="healthLoading" style="margin-left:8px" circle>
              <el-icon><Refresh /></el-icon>
            </el-button>
          </div>
        </div>
      </template>

      <el-row :gutter="16">
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.uptime') }}</span>
            <span class="stat-value">{{ healthStatus.uptimeStr }}</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.totalRequests') }}</span>
            <span class="stat-value">{{ healthStatus.totalRequests.toLocaleString() }}</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.avgResponse') }}</span>
            <span class="stat-value">{{ healthStatus.avgResponseMs }}ms</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.activeModels') }}</span>
            <span class="stat-value">{{ healthStatus.activeModels }}</span>
          </div>
        </el-col>
      </el-row>

      <el-divider style="margin: 12px 0" />

      <el-row :gutter="16">
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.memoryUsage') }}</span>
            <el-progress
              :percentage="healthStatus.memoryPercent"
              :status="healthStatus.memoryPercent > 80 ? 'exception' : healthStatus.memoryPercent > 60 ? 'warning' : ''"
              :stroke-width="6"
            />
            <span class="stat-sub">{{ healthStatus.memoryUsedMb }} / {{ healthStatus.memoryTotalMb }} MB</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.cpuUsage') }}</span>
            <el-progress
              :percentage="healthStatus.cpuPercent"
              :status="healthStatus.cpuPercent > 80 ? 'exception' : healthStatus.cpuPercent > 60 ? 'warning' : ''"
              :stroke-width="6"
            />
            <span class="stat-sub">{{ healthStatus.cpuPercent }}%</span>
          </div>
        </el-col>
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-label">{{ $t('settings.trainingTasks') }}</span>
            <span class="stat-value">
              <el-tag :type="healthStatus.activeTrainingTasks > 0 ? 'warning' : 'info'" size="small">
                {{ healthStatus.activeTrainingTasks }} {{ $t('settings.activeSuffix') }}
              </el-tag>
            </span>
          </div>
        </el-col>
      </el-row>

      <el-divider style="margin: 12px 0" />

      <div class="lnn-trend-section">
        <span class="stat-label">{{ $t('settings.lnnTrend') }}</span>
        <div class="trend-chart">
          <div
            v-for="(item, idx) in healthStatus.recentInferences"
            :key="idx"
            class="trend-bar-wrapper"
          >
            <div
              class="trend-bar"
              :style="{
                height: Math.max(4, (item.duration_ms / Math.max(healthStatus.maxRecentDuration, 1)) * 40) + 'px',
                backgroundColor: item.duration_ms > 500 ? '#f56c6c' : item.duration_ms > 200 ? '#e6a23c' : '#67c23a'
              }"
              :title="`${item.model}: ${item.duration_ms}ms`"
            ></div>
            <span class="trend-bar-label">{{ item.model ? item.model.substring(0, 6) : '-' }}</span>
          </div>
        </div>
        <div class="stat-sub">P50: {{ healthStatus.p50Ms }}ms | P95: {{ healthStatus.p95Ms }}ms | 最大: {{ healthStatus.maxRecentDuration }}ms</div>
      </div>

      <el-divider style="margin: 12px 0" />

      <div class="services-row">
        <el-tag :type="healthStatus.dbHealthy ? 'success' : 'danger'" size="small">{{ $t('settings.db') }}</el-tag>
        <el-tag :type="healthStatus.redisHealthy ? 'success' : 'danger'" size="small" style="margin-left:6px">Redis</el-tag>
        <el-tag :type="healthStatus.prometheusHealthy ? 'success' : 'danger'" size="small" style="margin-left:6px">Prometheus</el-tag>
        <span style="margin-left:12px;font-size:12px;color:#909399">{{ $t('settings.autoRefresh') }}: {{ healthStatus.pollInterval }}s</span>
      </div>
    </el-card>

    <el-card class="ai-sovereignty-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.aiSovereignty') }}</span>
          <el-tag type="success" size="small">{{ $t('settings.sovereigntyMode') }}</el-tag>
        </div>
      </template>

      <el-alert
        v-if="showSovereigntyIntro"
        :title="$t('settings.autonomyModeTitle')"
        type="info"
        :closable="true"
        @close="showSovereigntyIntro = false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <div>
          <p><strong>{{ $t('settings.aiAutonomyLevel') }}</strong>{{ $t('settings.autonomyModeDesc') }}</p>
          <ul>
            <li><strong>0 - {{ $t('settings.fullyManual') }}</strong>：{{ $t('settings.autonomyLevel0') }}</li>
            <li><strong>1 - {{ $t('settings.confirmRequired') }}</strong>：{{ $t('settings.autonomyLevel1') }}</li>
            <li><strong>2 - {{ $t('settings.recommended') }}</strong>：{{ $t('settings.autonomyLevel2') }}</li>
            <li><strong>3 - {{ $t('settings.semiAuto') }}</strong>：{{ $t('settings.autonomyLevel3') }}</li>
            <li><strong>4 - {{ $t('settings.fullyAuto') }}</strong>：{{ $t('settings.autonomyLevel4') }}</li>
          </ul>
        </div>
      </el-alert>

      <el-form :model="sovereigntySettings" label-width="160px">
        <el-form-item :label="$t('settings.aiAutonomyLevel')">
          <div class="autonomy-slider">
            <el-slider
              v-model="sovereigntySettings.ai_autonomy_level"
              :min="0"
              :max="4"
              :step="1"
              :marks="autonomyMarks"
              :format-tooltip="formatAutonomyLevel"
              @change="handleAutonomyChange"
            />
            <div class="autonomy-labels">
              <span v-for="(label, idx) in autonomyLabels" :key="idx" class="autonomy-label">
                {{ label }}
              </span>
            </div>
          </div>
        </el-form-item>

        <el-form-item :label="$t('settings.recommended')">
          <el-alert
            :title="currentAutonomyDescription"
            :type="getAutonomyAlertType(sovereigntySettings.ai_autonomy_level)"
            :closable="false"
            show-icon
          />
        </el-form-item>

        <el-form-item :label="$t('settings.showConfidence')">
          <el-switch v-model="sovereigntySettings.show_confidence_indicator" />
        </el-form-item>

        <el-form-item :label="$t('settings.showAlternatives')">
          <el-switch v-model="sovereigntySettings.show_alternatives" />
        </el-form-item>

        <el-form-item :label="$t('settings.showReasoning')">
          <el-switch v-model="sovereigntySettings.show_reasoning" />
        </el-form-item>

        <el-form-item :label="$t('settings.predictConfirm')">
          <el-switch v-model="sovereigntySettings.require_confirmation_for_predict" :disabled="sovereigntySettings.ai_autonomy_level >= 3" />
        </el-form-item>

        <el-form-item :label="$t('settings.trainConfirm')">
          <el-switch v-model="sovereigntySettings.require_confirmation_for_train" :disabled="sovereigntySettings.ai_autonomy_level >= 4" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveSovereigntySettings">
            {{ $t('settings.saveSovereignty') }}
          </el-button>
          <el-button @click="resetSovereigntySettings">
            {{ $t('common.reset') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="audit-log-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.auditLog') }}</span>
          <div class="header-actions">
            <el-button size="small" @click="exportLogs" :loading="exporting">
              {{ $t('settings.exportLogs') }}
            </el-button>
            <el-button size="small" type="danger" @click="clearLogs" :loading="clearing">
              {{ $t('settings.clearLogs') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" class="log-filters">
        <el-form-item :label="$t('settings.aiModule')">
          <el-select v-model="logFilters.ai_module" :placeholder="$t('settings.allModules')" clearable @change="loadAuditLogs">
            <el-option :label="$t('settings.lnnPredict')" value="lnn_predict" />
            <el-option :label="$t('settings.lnnTrain')" value="lnn_train" />
            <el-option :label="$t('settings.processOptimize')" value="process_optimize" />
            <el-option :label="$t('settings.toolWearAnalyze')" value="tool_wear_analyze" />
            <el-option :label="$t('settings.cadGenerate')" value="cad_generate" />
          </el-select>
        </el-form-item>
        <el-form-item :label="$t('settings.userDecision')">
          <el-select v-model="logFilters.user_decision" :placeholder="$t('settings.allModules')" clearable @change="loadAuditLogs">
            <el-option :label="$t('settings.accept')" value="accept" />
            <el-option :label="$t('settings.modify')" value="modify" />
            <el-option :label="$t('settings.reject')" value="reject" />
            <el-option :label="$t('settings.autoExecuted')" value="auto_executed" />
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
          <el-input v-model="logSearchKeyword" :placeholder="$t('settings.keyword')" clearable @keyup.enter="searchLogs" />
          <el-button type="primary" @click="searchLogs">{{ $t('common.search') }}</el-button>
        </el-form-item>
      </el-form>

      <div v-if="auditLogStatistics" class="log-statistics">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item :label="$t('settings.totalEntries')">{{ auditLogStatistics.total_entries }}</el-descriptions-item>
          <el-descriptions-item :label="$t('settings.avgConfidence')">{{ (auditLogStatistics.avg_confidence * 100).toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item :label="$t('settings.recent24h')">{{ auditLogStatistics.recent_24h }} 条</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-table :data="auditLogs" style="width: 100%; margin-top: 16px;" v-loading="loadingLogs">
        <el-table-column prop="timestamp_ms" :label="$t('common.time')" width="180">
          <template #default="{ row }">
            {{ formatTimestamp(row.timestamp_ms) }}
          </template>
        </el-table-column>
        <el-table-column prop="ai_module" :label="$t('settings.aiModuleCol')" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ getModuleName(row.ai_module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_decision" :label="$t('settings.userDecisionCol')" width="100">
          <template #default="{ row }">
            <el-tag :type="getDecisionType(row.user_decision)" size="small">
              {{ getDecisionName(row.user_decision) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operation_status" :label="$t('settings.opStatus')" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.operation_status)" size="small">
              {{ getStatusName(row.operation_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" :label="$t('settings.confidence')" width="100">
          <template #default="{ row }">
            <span v-if="row.confidence !== null">{{ (row.confidence * 100).toFixed(0) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reasoning" :label="$t('settings.reasoningDesc')" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.reasoning" placement="top">
              <span class="reasoning-text">{{ row.reasoning }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.operation')" width="80">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewLogDetail(row)">
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
        @size-change="loadAuditLogs"
        @current-change="loadAuditLogs"
        style="margin-top: 16px; justify-content: flex-end;"
      />
    </el-card>

    <el-dialog v-model="logDetailVisible" :title="$t('settings.logDetail')" width="60%">
      <el-descriptions v-if="selectedLog" :column="1" border>
        <el-descriptions-item :label="$t('settings.timestamp')">{{ formatTimestamp(selectedLog.timestamp_ms) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.aiModuleCol')">{{ getModuleName(selectedLog.ai_module) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.userDecisionCol')">{{ getDecisionName(selectedLog.user_decision) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.opStatus')">{{ getStatusName(selectedLog.operation_status) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.confidence')">{{ selectedLog.confidence !== null ? `${(selectedLog.confidence * 100).toFixed(2)}%` : 'N/A' }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.aiRecommend')">
          <pre>{{ JSON.stringify(selectedLog.ai_recommendation, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.finalExecution')">
          <pre>{{ JSON.stringify(selectedLog.final_execution, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.userModifications')" v-if="selectedLog.user_modifications">
          <pre>{{ JSON.stringify(selectedLog.user_modifications, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.reasoningDesc')">{{ selectedLog.reasoning }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-card class="agent-token-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.agentTokenManage') }}</span>
          <div class="header-actions">
            <el-button size="small" type="danger" @click="revokeAllTTokens" :loading="revokingT">
              {{ $t('settings.revokeAllT') }}
            </el-button>
            <el-button size="small" type="primary" @click="showCreateTokenDialog = true">
              {{ $t('settings.createToken') }}
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        :title="$t('settings.agentTokenInfo')"
        type="info"
        :closable="true"
        show-icon
        style="margin-bottom: 16px;"
      >
        <div>
          <p>{{ $t('settings.agentTokenDesc1') }}</p>
          <p>{{ $t('settings.agentTokenDesc2') }}</p>
          <p><strong>{{ $t('settings.db') }}</strong>{{ $t('settings.agentTokenDesc3') }}</p>
        </div>
      </el-alert>

      <el-table :data="agentTokens" style="width: 100%;" v-loading="loadingTokens">
        <el-table-column prop="agent_id" label="Agent ID" width="280">
          <template #default="{ row }">
            <span class="mono-text">{{ row.agent_id.slice(0, 8) }}...</span>
          </template>
        </el-table-column>
        <el-table-column prop="token_prefix" label="Token" width="160">
          <template #default="{ row }">
            <el-tag size="small" type="info">{{ row.token_prefix.slice(0, 16) }}...</el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('settings.scopePermission')" width="180">
          <template #default="{ row }">
            <el-tag
              v-for="scope in row.scopes"
              :key="scope"
              size="small"
              :type="getScopeType(scope)"
              style="margin-right: 4px;"
            >
              {{ getScopeName(scope) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="paper_only" :label="$t('settings.paperOnly')" width="110">
          <template #default="{ row }">
            <el-tag :type="row.paper_only ? 'warning' : 'success'" size="small">
              {{ row.paper_only ? $t('settings.simulateMode') : $t('settings.realExecute') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" :label="$t('common.status')" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? $t('common.active') : $t('common.revoked') }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column :label="$t('common.operation')" width="120">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="revokeToken(row.agent_id)" :disabled="!row.is_active">
              {{ $t('settings.revoke') }}
            </el-button>
            <el-button type="primary" link size="small" @click="viewTokenDetail(row)">
              {{ $t('common.detail') }}
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreateTokenDialog" :title="$t('settings.createTokenTitle')" width="500px">
      <el-form :model="newTokenForm" label-width="120px">
        <el-form-item :label="$t('settings.scopePermission')">
          <el-checkbox-group v-model="newTokenForm.scopes">
            <el-checkbox value="R">R - {{ $t('settings.getScopeName_R') }}</el-checkbox>
            <el-checkbox value="W">W - {{ $t('settings.getScopeName_W') }}</el-checkbox>
            <el-checkbox value="B">B - {{ $t('settings.getScopeName_B') }}</el-checkbox>
            <el-checkbox value="N">N - {{ $t('settings.getScopeName_N') }}</el-checkbox>
            <el-checkbox value="C">C - {{ $t('settings.getScopeName_C') }}</el-checkbox>
            <el-checkbox value="T">T - {{ $t('settings.getScopeName_T') }}</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item :label="$t('settings.validitySeconds')">
          <el-input-number v-model="newTokenForm.expires_in" :min="3600" :max="31536000" :step="3600" />
          <el-checkbox v-model="newTokenForm.no_expiry" style="margin-left: 12px;" @change="handleNoExpiryChange">
            {{ $t('settings.noExpiry') }}
          </el-checkbox>
        </el-form-item>
        <el-form-item label="Paper-Only">
          <el-switch v-model="newTokenForm.paper_only" />
          <span style="margin-left: 8px; font-size: 12px; color: #909399;">
            {{ newTokenForm.paper_only ? $t('settings.paperOnlyHint') : $t('settings.realExecuteHint') }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTokenDialog = false">{{ $t('common.cancel') }}</el-button>
        <el-button type="primary" @click="createAgentToken" :loading="creatingToken">{{ $t('settings.createToken') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCreatedTokenDialog" :title="$t('settings.importantNotice')" width="600px">
      <el-alert
        :title="$t('settings.importantNotice')"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <p>{{ $t('settings.importantNoticeMsg') }}</p>
      </el-alert>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="Agent ID">{{ createdToken?.agent_id }}</el-descriptions-item>
        <el-descriptions-item label="Token">
          <div style="display: flex; align-items: center; gap: 8px;">
            <code style="word-break: break-all; font-size: 12px;">{{ createdToken?.token }}</code>
            <el-button size="small" @click="copyTokenToClipboard(createdToken?.token)">{{ $t('common.export') }}</el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.scopePermission')">
          <el-tag
            v-for="scope in createdToken?.scopes"
            :key="scope"
            size="small"
            :type="getScopeType(scope)"
            style="margin-right: 4px;"
          >
            {{ getScopeName(scope) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.paperOnly')">
          <el-tag :type="createdToken?.paper_only ? 'warning' : 'success'">
            {{ createdToken?.paper_only ? $t('settings.simulateMode') : $t('settings.realExecute') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.expireTime')">
          {{ createdToken?.expires_at ? formatTimestamp(createdToken.expires_at * 1000) : $t('settings.noExpiry') }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button type="primary" @click="showCreatedTokenDialog = false">{{ $t('settings.iHaveSaved') }}</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tokenDetailVisible" :title="$t('settings.tokenDetail')" width="50%">
      <el-descriptions v-if="selectedToken" :column="1" border>
        <el-descriptions-item label="Agent ID">{{ selectedToken.agent_id }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.tokenPrefix')">{{ selectedToken.token_prefix }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.scopePermission')">
          <el-tag
            v-for="scope in selectedToken.scopes"
            :key="scope"
            size="small"
            :type="getScopeType(scope)"
            style="margin-right: 4px;"
          >
            {{ getScopeName(scope) }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.createTime')">{{ formatTimestamp(selectedToken.created_at * 1000) }}</el-descriptions-item>
        <el-descriptions-item :label="$t('settings.expireTime')">
          {{ selectedToken.expires_at ? formatTimestamp(selectedToken.expires_at * 1000) : $t('settings.noExpiry') }}
        </el-descriptions-item>
        <el-descriptions-item :label="$t('settings.paperOnly')">
          <el-tag :type="selectedToken.paper_only ? 'warning' : 'success'">
            {{ selectedToken.paper_only ? $t('settings.simulateMode') : $t('settings.realExecute') }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item :label="$t('common.status')">
          <el-tag :type="selectedToken.is_active ? 'success' : 'info'">
            {{ selectedToken.is_active ? $t('common.active') : $t('common.revoked') }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { useSettingsStore } from '@/stores/settings'
import { useVersionStore } from '@/stores/version'
import axios from 'axios'
import { Refresh } from '@element-plus/icons-vue'
import { setLocale, type SupportedLocale } from '@/i18n'

const { t } = useI18n()
const store = useSettingsStore()
const versionStore = useVersionStore()

const currentLocale = ref<SupportedLocale>((localStorage.getItem('app_locale') as SupportedLocale) || 'zh-CN')

function handleLocaleChange(locale: string) {
  const setter = (window as any).__setLocale
  if (setter) {
    setter(locale as SupportedLocale)
  } else {
    setLocale(locale as SupportedLocale)
  }
  currentLocale.value = locale as SupportedLocale
}

const showSovereigntyIntro = ref(true)

// ========== AI Sovereignty ==========

interface SovereigntySettings {
  ai_autonomy_level: number
  require_confirmation_for_predict: boolean
  require_confirmation_for_train: boolean
  show_confidence_indicator: boolean
  show_alternatives: boolean
  show_reasoning: boolean
}

const sovereigntySettings = reactive<SovereigntySettings>({
  ai_autonomy_level: 2,
  require_confirmation_for_predict: false,
  require_confirmation_for_train: true,
  show_confidence_indicator: true,
  show_alternatives: true,
  show_reasoning: true,
})

const autonomyMarks = {
  0: '0',
  1: '1',
  2: '2',
  3: '3',
  4: '4',
}

const autonomyLabels = computed(() => [
  t('settings.fullyManual'),
  t('settings.confirmRequired'),
  t('settings.recommended'),
  t('settings.semiAuto'),
  t('settings.fullyAuto'),
])

function formatAutonomyLevel(val: number): string {
  return `${val} - ${autonomyLabels.value[val]}`
}

const currentAutonomyDescription = computed(() => {
  const level = sovereigntySettings.ai_autonomy_level
  const descriptions = [
    t('settings.autonomyDesc0'),
    t('settings.autonomyDesc1'),
    t('settings.autonomyDesc2'),
    t('settings.autonomyDesc3'),
    t('settings.autonomyDesc4'),
  ]
  return descriptions[level]
})

function getAutonomyAlertType(level: number): 'success' | 'warning' | 'info' | 'error' {
  if (level <= 1) return 'info'
  if (level === 2) return 'success'
  if (level === 3) return 'warning'
  return 'error'
}

function handleAutonomyChange(val: number) {
  if (val >= 3) {
    sovereigntySettings.require_confirmation_for_predict = false
  }
  if (val >= 4) {
    sovereigntySettings.require_confirmation_for_train = false
  }
}

async function saveSovereigntySettings() {
  try {
    localStorage.setItem('ai_sovereignty_settings', JSON.stringify(sovereigntySettings))
    ElMessage.success(t('settings.sovereigntySaved'))
  } catch (e) {
    ElMessage.error(t('settings.saveFailed'))
  }
}

function resetSovereigntySettings() {
  sovereigntySettings.ai_autonomy_level = 2
  sovereigntySettings.require_confirmation_for_predict = false
  sovereigntySettings.require_confirmation_for_train = true
  sovereigntySettings.show_confidence_indicator = true
  sovereigntySettings.show_alternatives = true
  sovereigntySettings.show_reasoning = true
  ElMessage.info(t('settings.sovereigntyReset'))
}

const healthLoading = ref(false)
let healthTimer: ReturnType<typeof setInterval> | null = null

interface HealthStatus {
  backendOnline: boolean
  uptimeStr: string
  totalRequests: number
  avgResponseMs: number
  activeModels: number
  memoryPercent: number
  memoryUsedMb: number
  memoryTotalMb: number
  cpuPercent: number
  activeTrainingTasks: number
  recentInferences: Array<{ model: string; duration_ms: number }>
  maxRecentDuration: number
  p50Ms: number
  p95Ms: number
  dbHealthy: boolean
  redisHealthy: boolean
  prometheusHealthy: boolean
  pollInterval: number
}

const healthStatus = reactive<HealthStatus>({
  backendOnline: false,
  uptimeStr: '--',
  totalRequests: 0,
  avgResponseMs: 0,
  activeModels: 0,
  memoryPercent: 0,
  memoryUsedMb: 0,
  memoryTotalMb: 4096,
  cpuPercent: 0,
  activeTrainingTasks: 0,
  recentInferences: [],
  maxRecentDuration: 0,
  p50Ms: 0,
  p95Ms: 0,
  dbHealthy: false,
  redisHealthy: false,
  prometheusHealthy: false,
  pollInterval: 5,
})

function formatUptime(seconds: number): string {
  const d = Math.floor(seconds / 86400)
  const h = Math.floor((seconds % 86400) / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  const s = Math.floor(seconds % 60)
  if (d > 0) return `${d}d ${h}h ${m}m`
  if (h > 0) return `${h}h ${m}m ${s}s`
  return `${m}m ${s}s`
}

async function refreshHealth() {
  healthLoading.value = true
  try {
    const [pingRes, healthRes, metricsRes, lnnHealthRes, lnnPerfRes] = await Promise.allSettled([
      axios.get('/api/health/ping', { timeout: 3000 }),
      axios.get('/api/health', { timeout: 3000 }),
      axios.get('/api/metrics', { timeout: 3000 }),
      axios.get('/api/v1/lnn/health', { timeout: 3000 }),
      axios.get('/api/v1/lnn/performance', { timeout: 3000 }),
    ])

    healthStatus.backendOnline = pingRes.status === 'fulfilled' && pingRes.value.status === 200

    if (healthRes.status === 'fulfilled') {
      const hd = healthRes.value.data.data || healthRes.value.data || {}
      healthStatus.dbHealthy = hd.db_healthy ?? true
      healthStatus.redisHealthy = hd.redis_healthy ?? true
    }

    if (metricsRes.status === 'fulfilled') {
      const text = metricsRes.value.data
      const uptimeMatch = text.match(/sidecar_uptime_seconds\s+(\d+\.?\d*)/)
      if (uptimeMatch) {
        healthStatus.uptimeStr = formatUptime(parseFloat(uptimeMatch[1]))
      }
      const reqMatch = text.match(/http_requests_total\{[^}]*\}\s+(\d+)/)
      if (reqMatch) {
        healthStatus.totalRequests = parseInt(reqMatch[1], 10)
      }
      const memMatch = text.match(/process_resident_memory_bytes\s+(\d+)/)
      if (memMatch) {
        const bytes = parseInt(memMatch[1], 10)
        healthStatus.memoryUsedMb = Math.round(bytes / 1024 / 1024)
        const navMem = (navigator as any).deviceMemory
        if (navMem) {
          healthStatus.memoryTotalMb = Math.round(navMem * 1024)
          healthStatus.memoryPercent = Math.round((bytes / 1024 / 1024) / (navMem * 1024) * 100)
        } else {
          healthStatus.memoryTotalMb = 4096
          healthStatus.memoryPercent = Math.round((bytes / 1024 / 1024) / 4096 * 100)
        }
      }
      const cpuMatch = text.match(/process_cpu_percent\s+([\d.]+)/)
      if (cpuMatch) {
        healthStatus.cpuPercent = Math.round(parseFloat(cpuMatch[1]))
      }
      const ringMatch = text.match(/ring_buffer_appended_total\{type="request"\}\s+(\d+)/)
      if (ringMatch) {
        const total = parseInt(ringMatch[1], 10)
        const avgMatch = text.match(/http_request_duration_seconds_bucket\{[^}]*\}\s+([\d.]+)/)
        if (avgMatch && total > 0) {
          healthStatus.avgResponseMs = Math.round(parseFloat(avgMatch[1]) * 1000)
        }
      }
    }

    if (lnnHealthRes.status === 'fulfilled') {
      const lh = lnnHealthRes.value.data.data || lnnHealthRes.value.data || {}
      healthStatus.activeModels = lh.total_models ?? lh.models_count ?? 0
      healthStatus.activeTrainingTasks = lh.active_tasks ?? 0
    }

    if (lnnPerfRes.status === 'fulfilled') {
      const lp = lnnPerfRes.value.data.data || lnnPerfRes.value.data || {}
      const models = lp.models || []
      const inferences: Array<{ model: string; duration_ms: number }> = []
      let p50 = 0
      let p95 = 0
      for (const m of models) {
        if (m.avg_inference_ms) {
          inferences.push({ model: m.model_name, duration_ms: Math.round(m.avg_inference_ms) })
        }
        p50 = Math.max(p50, m.p50_inference_ms || 0)
        p95 = Math.max(p95, m.p95_inference_ms || 0)
      }
      healthStatus.recentInferences = inferences.slice(0, 10)
      healthStatus.maxRecentDuration = inferences.reduce((max, i) => Math.max(max, i.duration_ms), 1)
      healthStatus.p50Ms = Math.round(p50)
      healthStatus.p95Ms = Math.round(p95)
    }

    healthStatus.prometheusHealthy = true
  } catch {
    healthStatus.backendOnline = false
  } finally {
    healthLoading.value = false
  }
}

function startHealthPolling() {
  refreshHealth()
  healthTimer = setInterval(refreshHealth, healthStatus.pollInterval * 1000)
}

function stopHealthPolling() {
  if (healthTimer) {
    clearInterval(healthTimer)
    healthTimer = null
  }
}

const auditLogs = ref<any[]>([])
const auditLogStatistics = ref<any>(null)
const loadingLogs = ref(false)
const exporting = ref(false)
const clearing = ref(false)
const logSearchKeyword = ref('')
const logDetailVisible = ref(false)
const selectedLog = ref<any>(null)

const logFilters = reactive({
  ai_module: '',
  user_decision: '',
  dateRange: null as [Date, Date] | null,
})

const logPagination = reactive({
  page: 1,
  pageSize: 20,
  total: 0,
})

async function loadAuditLogs() {
  loadingLogs.value = true
  try {
    const params: any = {
      limit: logPagination.pageSize,
      offset: (logPagination.page - 1) * logPagination.pageSize,
    }

    if (logFilters.ai_module) params.ai_module = logFilters.ai_module
    if (logFilters.user_decision) params.user_decision = logFilters.user_decision
    if (logFilters.dateRange) {
      params.start_time = logFilters.dateRange[0].getTime()
      params.end_time = logFilters.dateRange[1].getTime()
    }

    const res = await axios.post('/api/v1/user-sovereignty/audit-log/query', params)
    auditLogs.value = res.data.data.logs
    logPagination.total = res.data.data.total
  } catch (e) {
    console.warn('Failed to load audit logs:', e)
  } finally {
    loadingLogs.value = false
  }
}

async function searchLogs() {
  if (!logSearchKeyword.value) {
    loadAuditLogs()
    return
  }

  loadingLogs.value = true
  try {
    const res = await axios.post('/api/v1/user-sovereignty/audit-log/search', {
      keyword: logSearchKeyword.value,
      limit: 50,
    })
    auditLogs.value = res.data.data.logs
    logPagination.total = res.data.data.total
  } catch (e) {
    console.warn('Failed to search audit logs:', e)
  } finally {
    loadingLogs.value = false
  }
}

async function loadStatistics() {
  try {
    const res = await axios.get('/api/v1/user-sovereignty/audit-log/statistics')
    auditLogStatistics.value = res.data.data
  } catch (e) {
    console.warn('Failed to load audit log statistics:', e)
  }
}

async function exportLogs() {
  exporting.value = true
  try {
    const params: any = { format: 'json' }
    if (logFilters.ai_module) params.ai_module = logFilters.ai_module
    if (logFilters.dateRange) {
      params.start_time = logFilters.dateRange[0].getTime()
      params.end_time = logFilters.dateRange[1].getTime()
    }

    const res = await axios.post('/api/v1/user-sovereignty/audit-log/export', params)
    const blob = new Blob([res.data.data.content], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `audit_log_${Date.now()}.json`
    a.click()
    URL.revokeObjectURL(url)
    ElMessage.success(t('settings.exportSuccess'))
  } catch (e) {
    ElMessage.error(t('settings.exportFailed'))
  } finally {
    exporting.value = false
  }
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm(t('settings.clearConfirmMsg'), t('settings.clearConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })

    const res = await axios.delete('/api/v1/user-sovereignty/audit-log/clear')
    ElMessage.success(t('settings.clearSuccess', { count: res.data.data.cleared_entries }))
    loadAuditLogs()
    loadStatistics()
  } catch (e) {
    // User cancelled or error
  }
}

function viewLogDetail(row: any) {
  selectedLog.value = row
  logDetailVisible.value = true
}

function formatTimestamp(ts: number): string {
  const locale = currentLocale.value === 'en' ? 'en-US' : 'zh-CN'
  return new Date(ts).toLocaleString(locale)
}

function getModuleName(module: string): string {
  const names: Record<string, string> = {
    lnn_predict: t('settings.lnnPredict'),
    lnn_train: t('settings.lnnTrain'),
    process_optimize: t('settings.processOptimize'),
    tool_wear_analyze: t('settings.toolWearAnalyze'),
    cad_generate: t('settings.cadGenerate'),
  }
  return names[module] || module
}

function getDecisionName(decision: string): string {
  const names: Record<string, string> = {
    accept: t('settings.accept'),
    modify: t('settings.modify'),
    reject: t('settings.reject'),
    auto_executed: t('settings.autoExecuted'),
  }
  return names[decision] || decision
}

function getDecisionType(decision: string): 'success' | 'warning' | 'danger' | 'info' {
  if (decision === 'accept') return 'success'
  if (decision === 'modify') return 'warning'
  if (decision === 'reject') return 'danger'
  return 'info'
}

function getStatusName(status: string): string {
  const names: Record<string, string> = {
    success: t('common.success'),
    failed: t('common.failed'),
    cancelled: t('common.cancelled'),
    pending: t('common.pending'),
  }
  return names[status] || status
}

function getStatusType(status: string): 'success' | 'danger' | 'info' | 'warning' {
  if (status === 'success') return 'success'
  if (status === 'failed') return 'danger'
  if (status === 'cancelled') return 'warning'
  return 'info'
}

async function refreshVersions() {
  await versionStore.fetchVersionInfo()
  versionStore.checkConsistency()
}

// Agent Token Management
const agentTokens = ref<any[]>([])
const loadingTokens = ref(false)
const creatingToken = ref(false)
const revokingT = ref(false)
const showCreateTokenDialog = ref(false)
const showCreatedTokenDialog = ref(false)
const createdToken = ref<any>(null)
const tokenDetailVisible = ref(false)
const selectedToken = ref<any>(null)

interface NewTokenForm {
  scopes: string[]
  expires_in: number | null
  no_expiry: boolean
  paper_only: boolean
}

const newTokenForm = reactive<NewTokenForm>({
  scopes: ['R'],
  expires_in: null,
  no_expiry: true,
  paper_only: true,
})

function handleNoExpiryChange(val: boolean) {
  if (val) {
    newTokenForm.expires_in = null
  } else {
    newTokenForm.expires_in = 86400 // 1 day default
  }
}

async function loadAgentTokens() {
  loadingTokens.value = true
  try {
    const res = await axios.get('/api/agent/v1/tokens')
    agentTokens.value = res.data.data.tokens
  } catch (e) {
    console.warn('Failed to load agent tokens:', e)
  } finally {
    loadingTokens.value = false
  }
}

async function createAgentToken() {
  if (newTokenForm.scopes.length === 0) {
    ElMessage.warning(t('settings.selectScopeHint'))
    return
  }

  creatingToken.value = true
  try {
    const payload: any = {
      scopes: newTokenForm.scopes,
      paper_only: newTokenForm.paper_only,
    }
    if (!newTokenForm.no_expiry && newTokenForm.expires_in) {
      payload.expires_in = newTokenForm.expires_in
    }

    const res = await axios.post('/api/agent/v1/tokens', payload)
    createdToken.value = res.data.data
    showCreatedTokenDialog.value = true
    showCreateTokenDialog.value = false
    ElMessage.success(t('settings.tokenCreatedSuccess'))
    loadAgentTokens()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || t('settings.saveFailed'))
  } finally {
    creatingToken.value = false
  }
}

async function revokeToken(agentId: string) {
  try {
    await ElMessageBox.confirm(t('settings.revokeConfirmMsg'), t('settings.revokeConfirmTitle'), {
      confirmButtonText: t('common.confirm'),
      cancelButtonText: t('common.cancel'),
      type: 'warning',
    })

    await axios.delete(`/api/agent/v1/tokens/${agentId}`)
    ElMessage.success(t('settings.revokeSuccess'))
    loadAgentTokens()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(t('settings.revokeFailed'))
    }
  }
}

async function revokeAllTTokens() {
  try {
    await ElMessageBox.confirm(
      t('settings.emergencyStopMsg'),
      t('settings.emergencyStopTitle'),
      {
        confirmButtonText: t('settings.emergencyStopConfirm'),
        cancelButtonText: t('common.cancel'),
        type: 'error',
      }
    )

    revokingT.value = true
    const res = await axios.post('/api/agent/v1/tokens/revoke-t-all')
    ElMessage.success(t('settings.revokeSuccessCount', { count: res.data.data.revoked_count }))
    loadAgentTokens()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error(t('settings.revokeTFailed'))
    }
  } finally {
    revokingT.value = false
  }
}

function viewTokenDetail(row: any) {
  selectedToken.value = row
  tokenDetailVisible.value = true
}

function getScopeType(scope: string): 'success' | 'warning' | 'danger' | 'info' | 'primary' {
  const types: Record<string, 'success' | 'warning' | 'danger' | 'info' | 'primary'> = {
    R: 'success',
    W: 'primary',
    B: 'warning',
    N: 'info',
    C: 'danger',
    T: 'danger',
  }
  return types[scope] || 'info'
}

function getScopeName(scope: string): string {
  const key = `settings.getScopeName_${scope}` as const
  return t(key as any) || scope
}

function copyTokenToClipboard(token: string) {
  if (token && navigator.clipboard) {
    navigator.clipboard.writeText(token).then(() => {
      ElMessage.success(t('settings.copySuccess'))
    }).catch(() => {
      ElMessage.error(t('settings.copyFailed'))
    })
  }
}

onMounted(() => {
  const saved = localStorage.getItem('ai_sovereignty_settings')
  if (saved) {
    try {
      const parsed = JSON.parse(saved)
      Object.assign(sovereigntySettings, parsed)
    } catch {
      // ignore parse errors
    }
  }

  loadAuditLogs()
  loadStatistics()
  loadAgentTokens()
  startHealthPolling()
})

onBeforeUnmount(() => {
  stopHealthPolling()
})
</script>

<style scoped>
.settings-page {
  max-width: 900px;
  margin: 0 auto;
}

.version-card {
  margin-bottom: 24px;
}

.version-warning {
  margin-bottom: 16px;
}

.health-card {
  margin-bottom: 16px;
}

.health-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
}

.stat-item {
  text-align: center;
  padding: 8px 0;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: #909399;
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: #303133;
}

.stat-sub {
  display: block;
  font-size: 11px;
  color: #c0c4cc;
  margin-top: 2px;
}

.lnn-trend-section {
  padding: 4px 0;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 48px;
  padding: 4px 0;
  margin: 8px 0;
}

.trend-bar-wrapper {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex: 1;
  min-width: 0;
}

.trend-bar {
  width: 100%;
  max-width: 24px;
  border-radius: 2px 2px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
}

.trend-bar-label {
  font-size: 9px;
  color: #c0c4cc;
  margin-top: 2px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.services-row {
  display: flex;
  align-items: center;
  padding: 4px 0;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.commit-hash {
  font-size: 0.75rem;
  color: #909399;
  margin-left: 8px;
  font-family: monospace;
}

.refresh-btn {
  margin-top: 16px;
  text-align: right;
}

.settings-card {
  margin-bottom: 24px;
}

.ai-sovereignty-card {
  margin-bottom: 24px;
}

.autonomy-slider {
  width: 100%;
}

.autonomy-labels {
  display: flex;
  justify-content: space-between;
  margin-top: 8px;
}

.autonomy-label {
  font-size: 12px;
  color: #909399;
  text-align: center;
  flex: 1;
}

.audit-log-card {
  margin-bottom: 24px;
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

.agent-token-card {
  margin-bottom: 24px;
}

.mono-text {
  font-family: monospace;
  font-size: 12px;
  color: #606266;
}

pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  font-size: 12px;
}

.header-actions {
  display: flex;
  gap: 8px;
}
</style>
