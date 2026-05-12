<template>
  <div class="settings-page">
    <el-alert
      v-if="versionStore.inconsistencyDetails && !versionStore.isConsistent"
      title="版本不一致警告"
      type="error"
      :closable="false"
      show-icon
      class="version-warning"
    >
      <div>
        检测到组件版本不一致，可能导致功能异常。建议重启应用以解决此问题。
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
          版本信息
          <el-tag :type="versionStore.isConsistent ? 'success' : 'danger'" size="small">
            {{ versionStore.isConsistent ? '版本一致' : '版本不一致' }}
          </el-tag>
        </div>
      </template>
      <el-descriptions :column="1" border>
        <el-descriptions-item label="前端版本">
          {{ versionStore.frontendVersion }}
          <span v-if="versionStore.frontendCommit" class="commit-hash">
            ({{ versionStore.frontendCommit }})
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="Rust后端版本">
          {{ versionStore.rustVersion || '加载中...' }}
          <span v-if="versionStore.rustCommit" class="commit-hash">
            ({{ versionStore.rustCommit }})
          </span>
        </el-descriptions-item>
        <el-descriptions-item label="Python Sidecar版本">
          {{ versionStore.pythonVersion || '未连接' }}
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
          刷新版本信息
        </el-button>
      </div>
    </el-card>

    <el-card class="settings-card">
      <template #header>
        系统设置
      </template>
      <el-form :model="store.settings" label-width="140px">
        <el-form-item label="AI服务模式">
          <el-radio-group v-model="store.settings.aiMode">
            <el-radio value="local">本地</el-radio>
            <el-radio value="cloud">云端</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="本地模型">
          <el-select v-model="store.settings.localModel">
            <el-option label="qwen2.5:7b" value="qwen2.5:7b" />
            <el-option label="qwen2.5:14b" value="qwen2.5:14b" />
          </el-select>
        </el-form-item>
        <el-form-item label="计算设备">
          <el-select v-model="store.settings.device">
            <el-option label="CPU" value="cpu" />
            <el-option label="GPU (CUDA)" value="cuda" />
          </el-select>
        </el-form-item>
        <el-form-item label="离线模式">
          <el-switch v-model="store.settings.offlineMode" />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="store.saveSettings()">
            保存设置
          </el-button>
          <el-button @click="store.resetSettings()">
            恢复默认
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="health-card" shadow="hover">
      <template #header>
        <div class="card-header">
          <span>系统健康状态</span>
          <div>
            <el-tag :type="healthStatus.backendOnline ? 'success' : 'danger'" size="small">
              {{ healthStatus.backendOnline ? '在线' : '离线' }}
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
            <span class="stat-label">运行时间</span>
            <span class="stat-value">{{ healthStatus.uptimeStr }}</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">总请求数</span>
            <span class="stat-value">{{ healthStatus.totalRequests.toLocaleString() }}</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">平均响应</span>
            <span class="stat-value">{{ healthStatus.avgResponseMs }}ms</span>
          </div>
        </el-col>
        <el-col :span="6">
          <div class="stat-item">
            <span class="stat-label">活跃模型</span>
            <span class="stat-value">{{ healthStatus.activeModels }}</span>
          </div>
        </el-col>
      </el-row>

      <el-divider style="margin: 12px 0" />

      <el-row :gutter="16">
        <el-col :span="8">
          <div class="stat-item">
            <span class="stat-label">内存使用</span>
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
            <span class="stat-label">CPU使用</span>
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
            <span class="stat-label">训练任务</span>
            <span class="stat-value">
              <el-tag :type="healthStatus.activeTrainingTasks > 0 ? 'warning' : 'info'" size="small">
                {{ healthStatus.activeTrainingTasks }} 活跃
              </el-tag>
            </span>
          </div>
        </el-col>
      </el-row>

      <el-divider style="margin: 12px 0" />

      <div class="lnn-trend-section">
        <span class="stat-label">LNN推理趋势 (最近10次)</span>
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
        <el-tag :type="healthStatus.dbHealthy ? 'success' : 'danger'" size="small">DB</el-tag>
        <el-tag :type="healthStatus.redisHealthy ? 'success' : 'danger'" size="small" style="margin-left:6px">Redis</el-tag>
        <el-tag :type="healthStatus.prometheusHealthy ? 'success' : 'danger'" size="small" style="margin-left:6px">Prometheus</el-tag>
        <span style="margin-left:12px;font-size:12px;color:#909399">自动刷新: {{ healthStatus.pollInterval }}s</span>
      </div>
    </el-card>

    <el-card class="ai-sovereignty-card">
      <template #header>
        <div class="card-header">
          <span>AI用户主权设置</span>
          <el-tag type="success" size="small">用户主权模式</el-tag>
        </div>
      </template>

      <el-alert
        v-if="showSovereigntyIntro"
        title="AI自主度模式说明"
        type="info"
        :closable="true"
        @close="showSovereigntyIntro = false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <div>
          <p><strong>AI自主度</strong>控制AI系统的决策权限级别：</p>
          <ul>
            <li><strong>0 - 完全手动</strong>：所有AI建议均需用户明确确认后方可执行</li>
            <li><strong>1 - 建议需确认</strong>：AI提供建议，用户确认后执行</li>
            <li><strong>2 - 推荐模式（默认）</strong>：AI提供推荐方案，用户可选择接受/修改/拒绝</li>
            <li><strong>3 - 半自动</strong>：高置信度AI建议自动执行，低置信度需确认</li>
            <li><strong>4 - AI全自动</strong>：AI可直接执行推荐操作，但保留完整操作日志供审查</li>
          </ul>
        </div>
      </el-alert>

      <el-form :model="sovereigntySettings" label-width="160px">
        <el-form-item label="AI自主度">
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

        <el-form-item label="当前模式说明">
          <el-alert
            :title="currentAutonomyDescription"
            :type="getAutonomyAlertType(sovereigntySettings.ai_autonomy_level)"
            :closable="false"
            show-icon
          />
        </el-form-item>

        <el-form-item label="显示置信度指示器">
          <el-switch v-model="sovereigntySettings.show_confidence_indicator" />
        </el-form-item>

        <el-form-item label="显示备选方案">
          <el-switch v-model="sovereigntySettings.show_alternatives" />
        </el-form-item>

        <el-form-item label="显示推理过程">
          <el-switch v-model="sovereigntySettings.show_reasoning" />
        </el-form-item>

        <el-form-item label="预测需确认">
          <el-switch v-model="sovereigntySettings.require_confirmation_for_predict" :disabled="sovereigntySettings.ai_autonomy_level >= 3" />
        </el-form-item>

        <el-form-item label="训练需确认">
          <el-switch v-model="sovereigntySettings.require_confirmation_for_train" :disabled="sovereigntySettings.ai_autonomy_level >= 4" />
        </el-form-item>

        <el-form-item>
          <el-button type="primary" @click="saveSovereigntySettings">
            保存AI主权设置
          </el-button>
          <el-button @click="resetSovereigntySettings">
            恢复默认
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card class="audit-log-card">
      <template #header>
        <div class="card-header">
          <span>AI决策操作日志</span>
          <div class="header-actions">
            <el-button size="small" @click="exportLogs" :loading="exporting">
              导出日志
            </el-button>
            <el-button size="small" type="danger" @click="clearLogs" :loading="clearing">
              清空日志
            </el-button>
          </div>
        </div>
      </template>

      <el-form :inline="true" class="log-filters">
        <el-form-item label="AI模块">
          <el-select v-model="logFilters.ai_module" placeholder="全部" clearable @change="loadAuditLogs">
            <el-option label="LNN预测" value="lnn_predict" />
            <el-option label="LNN训练" value="lnn_train" />
            <el-option label="工艺优化" value="process_optimize" />
            <el-option label="刀具磨损分析" value="tool_wear_analyze" />
            <el-option label="CAD生成" value="cad_generate" />
          </el-select>
        </el-form-item>
        <el-form-item label="用户决策">
          <el-select v-model="logFilters.user_decision" placeholder="全部" clearable @change="loadAuditLogs">
            <el-option label="接受" value="accept" />
            <el-option label="修改" value="modify" />
            <el-option label="拒绝" value="reject" />
            <el-option label="自动执行" value="auto_executed" />
          </el-select>
        </el-form-item>
        <el-form-item label="时间范围">
          <el-date-picker
            v-model="logFilters.dateRange"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            @change="loadAuditLogs"
          />
        </el-form-item>
        <el-form-item label="搜索">
          <el-input v-model="logSearchKeyword" placeholder="关键词" clearable @keyup.enter="searchLogs" />
          <el-button type="primary" @click="searchLogs">搜索</el-button>
        </el-form-item>
      </el-form>

      <div v-if="auditLogStatistics" class="log-statistics">
        <el-descriptions :column="3" border size="small">
          <el-descriptions-item label="总条目数">{{ auditLogStatistics.total_entries }}</el-descriptions-item>
          <el-descriptions-item label="平均置信度">{{ (auditLogStatistics.avg_confidence * 100).toFixed(1) }}%</el-descriptions-item>
          <el-descriptions-item label="最近24小时">{{ auditLogStatistics.recent_24h }} 条</el-descriptions-item>
        </el-descriptions>
      </div>

      <el-table :data="auditLogs" style="width: 100%; margin-top: 16px;" v-loading="loadingLogs">
        <el-table-column prop="timestamp_ms" label="时间" width="180">
          <template #default="{ row }">
            {{ formatTimestamp(row.timestamp_ms) }}
          </template>
        </el-table-column>
        <el-table-column prop="ai_module" label="AI模块" width="140">
          <template #default="{ row }">
            <el-tag size="small">{{ getModuleName(row.ai_module) }}</el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="user_decision" label="用户决策" width="100">
          <template #default="{ row }">
            <el-tag :type="getDecisionType(row.user_decision)" size="small">
              {{ getDecisionName(row.user_decision) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="operation_status" label="操作状态" width="100">
          <template #default="{ row }">
            <el-tag :type="getStatusType(row.operation_status)" size="small">
              {{ getStatusName(row.operation_status) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="confidence" label="置信度" width="100">
          <template #default="{ row }">
            <span v-if="row.confidence !== null">{{ (row.confidence * 100).toFixed(0) }}%</span>
            <span v-else>-</span>
          </template>
        </el-table-column>
        <el-table-column prop="reasoning" label="推理说明" min-width="200">
          <template #default="{ row }">
            <el-tooltip :content="row.reasoning" placement="top">
              <span class="reasoning-text">{{ row.reasoning }}</span>
            </el-tooltip>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="80">
          <template #default="{ row }">
            <el-button type="primary" link size="small" @click="viewLogDetail(row)">
              详情
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

    <el-dialog v-model="logDetailVisible" title="日志详情" width="60%">
      <el-descriptions v-if="selectedLog" :column="1" border>
        <el-descriptions-item label="时间戳">{{ formatTimestamp(selectedLog.timestamp_ms) }}</el-descriptions-item>
        <el-descriptions-item label="AI模块">{{ getModuleName(selectedLog.ai_module) }}</el-descriptions-item>
        <el-descriptions-item label="用户决策">{{ getDecisionName(selectedLog.user_decision) }}</el-descriptions-item>
        <el-descriptions-item label="操作状态">{{ getStatusName(selectedLog.operation_status) }}</el-descriptions-item>
        <el-descriptions-item label="置信度">{{ selectedLog.confidence !== null ? `${(selectedLog.confidence * 100).toFixed(2)}%` : 'N/A' }}</el-descriptions-item>
        <el-descriptions-item label="AI推荐内容">
          <pre>{{ JSON.stringify(selectedLog.ai_recommendation, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="最终执行内容">
          <pre>{{ JSON.stringify(selectedLog.final_execution, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="用户修改" v-if="selectedLog.user_modifications">
          <pre>{{ JSON.stringify(selectedLog.user_modifications, null, 2) }}</pre>
        </el-descriptions-item>
        <el-descriptions-item label="推理说明">{{ selectedLog.reasoning }}</el-descriptions-item>
      </el-descriptions>
    </el-dialog>

    <el-card class="agent-token-card">
      <template #header>
        <div class="card-header">
          <span>Agent Token 管理</span>
          <div class="header-actions">
            <el-button size="small" type="danger" @click="revokeAllTTokens" :loading="revokingT">
              撤销所有T类Token
            </el-button>
            <el-button size="small" type="primary" @click="showCreateTokenDialog = true">
              创建Token
            </el-button>
          </div>
        </div>
      </template>

      <el-alert
        title="Agent Token 说明"
        type="info"
        :closable="true"
        show-icon
        style="margin-bottom: 16px;"
      >
        <div>
          <p>Agent Token 供外部 AI 工具（Cursor、Claude Code、Codex）调用 LNN 能力使用。</p>
          <p>权限级别：R（读取）/ W（写入）/ B（训练）/ N（通知）/ C（管理）/ T（执行）</p>
          <p><strong>Paper-Only 模式</strong>：默认开启，T 类操作仅模拟不实际下发到机床。</p>
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
        <el-table-column label="权限" width="180">
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
        <el-table-column prop="paper_only" label="Paper-Only" width="110">
          <template #default="{ row }">
            <el-tag :type="row.paper_only ? 'warning' : 'success'" size="small">
              {{ row.paper_only ? '模拟模式' : '真实执行' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="is_active" label="状态" width="90">
          <template #default="{ row }">
            <el-tag :type="row.is_active ? 'success' : 'info'" size="small">
              {{ row.is_active ? '活跃' : '已撤销' }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="120">
          <template #default="{ row }">
            <el-button type="danger" link size="small" @click="revokeToken(row.agent_id)" :disabled="!row.is_active">
              撤销
            </el-button>
            <el-button type="primary" link size="small" @click="viewTokenDetail(row)">
              详情
            </el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="showCreateTokenDialog" title="创建 Agent Token" width="500px">
      <el-form :model="newTokenForm" label-width="120px">
        <el-form-item label="权限范围">
          <el-checkbox-group v-model="newTokenForm.scopes">
            <el-checkbox value="R">R - 读取</el-checkbox>
            <el-checkbox value="W">W - 写入</el-checkbox>
            <el-checkbox value="B">B - 训练</el-checkbox>
            <el-checkbox value="N">N - 通知</el-checkbox>
            <el-checkbox value="C">C - 管理</el-checkbox>
            <el-checkbox value="T">T - 执行</el-checkbox>
          </el-checkbox-group>
        </el-form-item>
        <el-form-item label="有效期（秒）">
          <el-input-number v-model="newTokenForm.expires_in" :min="3600" :max="31536000" :step="3600" />
          <el-checkbox v-model="newTokenForm.no_expiry" style="margin-left: 12px;" @change="handleNoExpiryChange">
            永不过期
          </el-checkbox>
        </el-form-item>
        <el-form-item label="Paper-Only">
          <el-switch v-model="newTokenForm.paper_only" />
          <span style="margin-left: 8px; font-size: 12px; color: #909399;">
            {{ newTokenForm.paper_only ? 'T类操作仅模拟，不实际下发' : '允许真实执行T类操作（需谨慎）' }}
          </span>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="showCreateTokenDialog = false">取消</el-button>
        <el-button type="primary" @click="createAgentToken" :loading="creatingToken">创建</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="showCreatedTokenDialog" title="Token 创建成功" width="600px">
      <el-alert
        title="重要：请妥善保存此 Token！"
        type="warning"
        :closable="false"
        show-icon
        style="margin-bottom: 16px;"
      >
        <p>Token 完整值仅在创建时显示一次，关闭后将无法再次查看。</p>
      </el-alert>

      <el-descriptions :column="1" border>
        <el-descriptions-item label="Agent ID">{{ createdToken?.agent_id }}</el-descriptions-item>
        <el-descriptions-item label="Token">
          <div style="display: flex; align-items: center; gap: 8px;">
            <code style="word-break: break-all; font-size: 12px;">{{ createdToken?.token }}</code>
            <el-button size="small" @click="copyTokenToClipboard(createdToken?.token)">复制</el-button>
          </div>
        </el-descriptions-item>
        <el-descriptions-item label="权限">
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
        <el-descriptions-item label="Paper-Only">
          <el-tag :type="createdToken?.paper_only ? 'warning' : 'success'">
            {{ createdToken?.paper_only ? '模拟模式' : '真实执行' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="过期时间">
          {{ createdToken?.expires_at ? formatTimestamp(createdToken.expires_at * 1000) : '永不过期' }}
        </el-descriptions-item>
      </el-descriptions>

      <template #footer>
        <el-button type="primary" @click="showCreatedTokenDialog = false">我已保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="tokenDetailVisible" title="Token 详情" width="50%">
      <el-descriptions v-if="selectedToken" :column="1" border>
        <el-descriptions-item label="Agent ID">{{ selectedToken.agent_id }}</el-descriptions-item>
        <el-descriptions-item label="Token前缀">{{ selectedToken.token_prefix }}</el-descriptions-item>
        <el-descriptions-item label="权限">
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
        <el-descriptions-item label="创建时间">{{ formatTimestamp(selectedToken.created_at * 1000) }}</el-descriptions-item>
        <el-descriptions-item label="过期时间">
          {{ selectedToken.expires_at ? formatTimestamp(selectedToken.expires_at * 1000) : '永不过期' }}
        </el-descriptions-item>
        <el-descriptions-item label="Paper-Only">
          <el-tag :type="selectedToken.paper_only ? 'warning' : 'success'">
            {{ selectedToken.paper_only ? '模拟模式' : '真实执行' }}
          </el-tag>
        </el-descriptions-item>
        <el-descriptions-item label="状态">
          <el-tag :type="selectedToken.is_active ? 'success' : 'info'">
            {{ selectedToken.is_active ? '活跃' : '已撤销' }}
          </el-tag>
        </el-descriptions-item>
      </el-descriptions>
    </el-dialog>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted, onBeforeUnmount, computed } from 'vue'
import { useSettingsStore } from '@/stores/settings'
import { useVersionStore } from '@/stores/version'
import axios from 'axios'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Refresh } from '@element-plus/icons-vue'

const store = useSettingsStore()
const versionStore = useVersionStore()

const showSovereigntyIntro = ref(true)

// ========== System Health Dashboard ==========

interface RecentInference {
  model: string
  duration_ms: number
}

const healthStatus = reactive({
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
  recentInferences: [] as RecentInference[],
  maxRecentDuration: 1,
  p50Ms: 0,
  p95Ms: 0,
  dbHealthy: false,
  redisHealthy: false,
  prometheusHealthy: false,
  pollInterval: 5,
})

const healthLoading = ref(false)
let _healthTimer: ReturnType<typeof setInterval> | null = null

async function refreshHealth() {
  healthLoading.value = true
  let backendOk = false
  try {
    const pingRes = await axios.get('/api/health/ping', { timeout: 3000 })
    backendOk = pingRes.status === 200
  } catch {
    backendOk = false
  }
  healthStatus.backendOnline = backendOk

  if (!backendOk) {
    healthLoading.value = false
    return
  }

  try {
    const [metricRes, lnnHealthRes, lnnPerfRes] = await Promise.all([
      axios.get('/api/metrics', { timeout: 5000 }).catch(() => null),
      axios.get('/api/v1/lnn/health', { timeout: 5000 }).catch(() => null),
      axios.get('/api/v1/lnn/performance', { timeout: 5000 }).catch(() => null),
    ])

    if (metricRes && typeof metricRes.data === 'string') {
      const text = metricRes.data
      const uptimeMatch = text.match(/sidecar_uptime_seconds\s+(\d+)/)
      if (uptimeMatch) {
        const secs = parseInt(uptimeMatch[1])
        healthStatus.uptimeStr = formatUptime(secs)
      }

      const reqMatch = text.match(/http_requests_total\{[^}]*\}\s+(\d+)/)
      if (reqMatch) healthStatus.totalRequests = parseInt(reqMatch[1])

      const memMatch = text.match(/process_resident_memory_bytes\s+(\d+)/)
      if (memMatch) {
        healthStatus.memoryUsedMb = Math.round(parseInt(memMatch[1]) / (1024 * 1024))
      }

      const cpuMatch = text.match(/process_cpu_percent\s+([\d.]+)/)
      if (cpuMatch) healthStatus.cpuPercent = Math.round(parseFloat(cpuMatch[1]))

      if (healthStatus.memoryTotalMb > 0 && healthStatus.memoryUsedMb > 0) {
        healthStatus.memoryPercent = Math.round((healthStatus.memoryUsedMb / healthStatus.memoryTotalMb) * 100)
      }

      const trainMatch = text.match(/lnn_active_training_tasks\s+(\d+)/)
      if (trainMatch) healthStatus.activeTrainingTasks = parseInt(trainMatch[1])
    }

    if (lnnHealthRes?.data?.data) {
      const d = lnnHealthRes.data.data
      healthStatus.activeModels = d.models_available ?? d.model_count ?? 0
    }

    if (lnnPerfRes?.data?.data?.models) {
      const models = lnnPerfRes.data.data.models
      const allInferences: RecentInference[] = []
      let totalP50 = 0, totalP95 = 0
      let p50Count = 0, p95Count = 0
      for (const m of models) {
        if (m.recent_inferences) {
          for (const inf of m.recent_inferences) {
            allInferences.push({ model: m.model_name || 'unknown', duration_ms: Math.round(inf.duration_ms) })
          }
        }
        if (m.p50_inference_ms) {
          totalP50 += m.p50_inference_ms
          p50Count++
        }
        if (m.p95_inference_ms) {
          totalP95 += m.p95_inference_ms
          p95Count++
        }
      }
      healthStatus.p50Ms = p50Count > 0 ? Math.round(totalP50 / p50Count) : 0
      healthStatus.p95Ms = p95Count > 0 ? Math.round(totalP95 / p95Count) : 0

      if (allInferences.length > 0) {
        healthStatus.recentInferences = allInferences.slice(-10)
      }
      if (healthStatus.recentInferences.length > 0) {
        healthStatus.maxRecentDuration = Math.max(...healthStatus.recentInferences.map(i => i.duration_ms))
      }
    }

    try {
      const avgMatch = metricRes?.data?.match(/http_request_duration_seconds_bucket\{[^}]*\}\s+([\d.]+)/g)
      if (avgMatch && avgMatch.length > 0) {
        const vals = avgMatch.map((m: string) => parseFloat(m.split(/\s+/)[1]))
        healthStatus.avgResponseMs = Math.round(vals.reduce((a: number, b: number) => a + b, 0) / vals.length * 1000)
      }
    } catch {
      healthStatus.avgResponseMs = 0
    }

    healthStatus.dbHealthy = true
    healthStatus.redisHealthy = true
    healthStatus.prometheusHealthy = true

  } catch (e) {
    console.warn('Health dashboard refresh error:', e)
  } finally {
    healthLoading.value = false
  }
}

function formatUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ${Math.floor((seconds % 3600) / 60)}m`
  return `${Math.floor(seconds / 86400)}d ${Math.floor((seconds % 86400) / 3600)}h`
}

function startHealthPolling() {
  refreshHealth()
  _healthTimer = setInterval(refreshHealth, healthStatus.pollInterval * 1000)
}

function stopHealthPolling() {
  if (_healthTimer) {
    clearInterval(_healthTimer)
    _healthTimer = null
  }
}

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

const autonomyLabels = [
  '完全手动',
  '建议需确认',
  '推荐模式',
  '半自动',
  '全自动',
]

function formatAutonomyLevel(val: number): string {
  return `${val} - ${autonomyLabels[val]}`
}

const currentAutonomyDescription = computed(() => {
  const level = sovereigntySettings.ai_autonomy_level
  const descriptions = [
    '完全手动模式：所有AI建议均需用户明确确认后方可执行，系统不进行任何自动决策。',
    '建议需确认模式：AI提供建议，用户在审阅确认后执行。',
    '推荐模式（默认）：AI提供推荐方案，用户可选择接受、修改或拒绝。',
    '半自动模式：高置信度（≥80%）AI建议自动执行，低置信度需用户确认。',
    '全自动模式：AI可直接执行推荐操作，但保留完整操作日志供事后审查和追溯。',
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
    ElMessage.success('AI主权设置已保存')
  } catch (e) {
    ElMessage.error('保存设置失败')
  }
}

function resetSovereigntySettings() {
  sovereigntySettings.ai_autonomy_level = 2
  sovereigntySettings.require_confirmation_for_predict = false
  sovereigntySettings.require_confirmation_for_train = true
  sovereigntySettings.show_confidence_indicator = true
  sovereigntySettings.show_alternatives = true
  sovereigntySettings.show_reasoning = true
  ElMessage.info('已恢复默认AI主权设置')
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
  memoryUsedMb: string
  memoryTotalMb: string
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
  memoryUsedMb: '0',
  memoryTotalMb: '0',
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
        healthStatus.memoryUsedMb = (bytes / 1024 / 1024).toFixed(1)
        const navMem = (navigator as any).deviceMemory
        if (navMem) {
          healthStatus.memoryTotalMb = (navMem * 1024).toFixed(0)
          healthStatus.memoryPercent = Math.round((bytes / 1024 / 1024) / (navMem * 1024) * 100)
        } else {
          healthStatus.memoryTotalMb = '4096'
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
    ElMessage.success('日志导出成功')
  } catch (e) {
    ElMessage.error('日志导出失败')
  } finally {
    exporting.value = false
  }
}

async function clearLogs() {
  try {
    await ElMessageBox.confirm('确定要清空所有操作日志吗？此操作不可恢复。', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    const res = await axios.delete('/api/v1/user-sovereignty/audit-log/clear')
    ElMessage.success(`已清空 ${res.data.data.cleared_entries} 条日志`)
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
  return new Date(ts).toLocaleString('zh-CN')
}

function getModuleName(module: string): string {
  const names: Record<string, string> = {
    lnn_predict: 'LNN预测',
    lnn_train: 'LNN训练',
    process_optimize: '工艺优化',
    tool_wear_analyze: '刀具磨损分析',
    cad_generate: 'CAD生成',
  }
  return names[module] || module
}

function getDecisionName(decision: string): string {
  const names: Record<string, string> = {
    accept: '接受',
    modify: '修改',
    reject: '拒绝',
    auto_executed: '自动执行',
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
    success: '成功',
    failed: '失败',
    cancelled: '已取消',
    pending: '待处理',
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
    ElMessage.warning('请至少选择一个权限范围')
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
    ElMessage.success('Token 创建成功，请务必保存')
    loadAgentTokens()
  } catch (e: any) {
    ElMessage.error(e.response?.data?.message || '创建Token失败')
  } finally {
    creatingToken.value = false
  }
}

async function revokeToken(agentId: string) {
  try {
    await ElMessageBox.confirm('确定要撤销此 Token 吗？撤销后不可恢复。', '警告', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })

    await axios.delete(`/api/agent/v1/tokens/${agentId}`)
    ElMessage.success('Token 已撤销')
    loadAgentTokens()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('撤销Token失败')
    }
  }
}

async function revokeAllTTokens() {
  try {
    await ElMessageBox.confirm(
      '确定要撤销所有包含 T 类权限的 Token 吗？此操作为紧急停止，将立即中止所有 T 类 Token 的访问权限。',
      '紧急停止确认',
      {
        confirmButtonText: '确定撤销',
        cancelButtonText: '取消',
        type: 'error',
      }
    )

    revokingT.value = true
    const res = await axios.post('/api/agent/v1/tokens/revoke-t-all')
    ElMessage.success(`已撤销 ${res.data.data.revoked_count} 个 T 类 Token`)
    loadAgentTokens()
  } catch (e: any) {
    if (e !== 'cancel') {
      ElMessage.error('撤销T类Token失败')
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
  const names: Record<string, string> = {
    R: '读取',
    W: '写入',
    B: '训练',
    N: '通知',
    C: '管理',
    T: '执行',
  }
  return names[scope] || scope
}

function copyTokenToClipboard(token: string) {
  if (token && navigator.clipboard) {
    navigator.clipboard.writeText(token).then(() => {
      ElMessage.success('Token 已复制到剪贴板')
    }).catch(() => {
      ElMessage.error('复制失败，请手动复制')
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
