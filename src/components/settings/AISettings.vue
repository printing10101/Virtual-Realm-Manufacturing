<template>
  <div class="ai-settings">
    <!-- AI 自主权 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">
          <el-icon style="margin-right: 6px;"><MagicStick /></el-icon>
          {{ $t('settings.aiSovereignty') }}
        </span>
        <el-tag
          type="success"
          size="small"
        >
          {{ $t('settings.sovereigntyMode') }}
        </el-tag>
      </div>
      <div class="content-card__body">
        <el-alert
          v-if="showSovereigntyIntro"
          :title="$t('settings.autonomyModeTitle')"
          type="info"
          :closable="true"
          show-icon
          style="margin-bottom: 20px;"
          @close="showSovereigntyIntro = false"
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

        <el-form
          :model="sovereigntySettings"
          label-width="160px"
          class="settings-form"
        >
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
                <span
                  v-for="(label, idx) in autonomyLabels"
                  :key="idx"
                  class="autonomy-label"
                >{{ label }}</span>
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

          <el-divider />

          <div class="switch-grid">
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
              <el-switch
                v-model="sovereigntySettings.require_confirmation_for_predict"
                :disabled="sovereigntySettings.ai_autonomy_level >= 3"
              />
            </el-form-item>
            <el-form-item :label="$t('settings.trainConfirm')">
              <el-switch
                v-model="sovereigntySettings.require_confirmation_for_train"
                :disabled="sovereigntySettings.ai_autonomy_level >= 4"
              />
            </el-form-item>
          </div>

          <div class="form-actions">
            <el-button
              type="primary"
              @click="saveSovereigntySettings"
            >
              <el-icon style="margin-right: 4px;">
                <Check />
              </el-icon>
              {{ $t('settings.saveSovereignty') }}
            </el-button>
            <el-button @click="resetSovereigntySettings">
              <el-icon style="margin-right: 4px;">
                <RefreshLeft />
              </el-icon>
              {{ $t('common.reset') }}
            </el-button>
          </div>
        </el-form>
      </div>
    </div>

    <!-- 系统健康监控 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">
          <el-icon style="margin-right: 6px;"><Odometer /></el-icon>
          {{ $t('settings.systemHealth') }}
        </span>
        <div style="display: flex; align-items: center; gap: 8px;">
          <el-tag
            :type="healthStatus.backendOnline ? 'success' : 'danger'"
            size="small"
          >
            {{ healthStatus.backendOnline ? $t('common.online') : $t('common.offline') }}
          </el-tag>
          <el-button
            size="small"
            :loading="healthLoading"
            circle
            @click="refreshHealth"
          >
            <el-icon><Refresh /></el-icon>
          </el-button>
        </div>
      </div>
      <div class="content-card__body">
        <!-- 关键指标 -->
        <div class="health-stats">
          <div class="health-stat">
            <div class="health-stat__icon health-stat__icon--blue">
              <el-icon :size="18">
                <Timer />
              </el-icon>
            </div>
            <div class="health-stat__content">
              <span class="health-stat__label">{{ $t('settings.uptime') }}</span>
              <span class="health-stat__value">{{ healthStatus.uptimeStr }}</span>
            </div>
          </div>
          <div class="health-stat">
            <div class="health-stat__icon health-stat__icon--green">
              <el-icon :size="18">
                <DataLine />
              </el-icon>
            </div>
            <div class="health-stat__content">
              <span class="health-stat__label">{{ $t('settings.totalRequests') }}</span>
              <span class="health-stat__value">{{ healthStatus.totalRequests.toLocaleString() }}</span>
            </div>
          </div>
          <div class="health-stat">
            <div class="health-stat__icon health-stat__icon--orange">
              <el-icon :size="18">
                <Lightning />
              </el-icon>
            </div>
            <div class="health-stat__content">
              <span class="health-stat__label">{{ $t('settings.avgResponse') }}</span>
              <span class="health-stat__value">{{ healthStatus.avgResponseMs }}ms</span>
            </div>
          </div>
          <div class="health-stat">
            <div class="health-stat__icon health-stat__icon--purple">
              <el-icon :size="18">
                <Box />
              </el-icon>
            </div>
            <div class="health-stat__content">
              <span class="health-stat__label">{{ $t('settings.activeModels') }}</span>
              <span class="health-stat__value">{{ healthStatus.activeModels }}</span>
            </div>
          </div>
        </div>

        <!-- 资源使用 -->
        <div class="resource-section">
          <div class="resource-bar">
            <div class="resource-bar__header">
              <span class="resource-bar__label">{{ $t('settings.memoryUsage') }}</span>
              <span class="resource-bar__value">{{ healthStatus.memoryUsedMb }} / {{ healthStatus.memoryTotalMb }} MB</span>
            </div>
            <el-progress
              :percentage="healthStatus.memoryPercent"
              :status="healthStatus.memoryPercent > 80 ? 'exception' : healthStatus.memoryPercent > 60 ? 'warning' : ''"
              :stroke-width="8"
              :show-text="true"
            />
          </div>
          <div class="resource-bar">
            <div class="resource-bar__header">
              <span class="resource-bar__label">{{ $t('settings.cpuUsage') }}</span>
              <span class="resource-bar__value">{{ healthStatus.cpuPercent }}%</span>
            </div>
            <el-progress
              :percentage="healthStatus.cpuPercent"
              :status="healthStatus.cpuPercent > 80 ? 'exception' : healthStatus.cpuPercent > 60 ? 'warning' : ''"
              :stroke-width="8"
              :show-text="true"
            />
          </div>
          <div class="resource-bar">
            <div class="resource-bar__header">
              <span class="resource-bar__label">{{ $t('settings.trainingTasks') }}</span>
              <el-tag
                :type="healthStatus.activeTrainingTasks > 0 ? 'warning' : 'info'"
                size="small"
              >
                {{ healthStatus.activeTrainingTasks }} {{ $t('settings.activeSuffix') }}
              </el-tag>
            </div>
          </div>
        </div>

        <!-- 推理趋势 -->
        <div class="trend-section">
          <div class="trend-section__header">
            <span class="trend-section__title">{{ $t('settings.lnnTrend') }}</span>
            <span class="trend-section__stats">P50: {{ healthStatus.p50Ms }}ms | P95: {{ healthStatus.p95Ms }}ms | Max: {{ healthStatus.maxRecentDuration }}ms</span>
          </div>
          <div class="trend-chart">
            <div
              v-for="(item, idx) in healthStatus.recentInferences"
              :key="idx"
              class="trend-bar-wrapper"
            >
              <div
                class="trend-bar"
                :style="{
                  height: Math.max(4, (item.duration_ms / Math.max(healthStatus.maxRecentDuration, 1)) * 48) + 'px',
                  backgroundColor: item.duration_ms > 500 ? 'var(--el-color-error)' : item.duration_ms > 200 ? 'var(--el-color-warning)' : 'var(--el-color-success)'
                }"
                :title="`${item.model}: ${item.duration_ms}ms`"
              />
              <span class="trend-bar-label">{{ item.model ? item.model.substring(0, 6) : '-' }}</span>
            </div>
          </div>
        </div>

        <!-- 服务状态 -->
        <div class="services-bar">
          <span class="services-bar__label">{{ $t('settings.serviceStatus') }}</span>
          <div class="services-bar__tags">
            <el-tag
              :type="healthStatus.dbHealthy ? 'success' : 'danger'"
              size="small"
              effect="plain"
            >
              DB
            </el-tag>
            <el-tag
              :type="healthStatus.redisHealthy ? 'success' : 'danger'"
              size="small"
              effect="plain"
            >
              Redis
            </el-tag>
            <el-tag
              :type="healthStatus.prometheusHealthy ? 'success' : 'danger'"
              size="small"
              effect="plain"
            >
              Prometheus
            </el-tag>
          </div>
          <span class="services-bar__interval">{{ $t('settings.autoRefresh') }}: {{ healthStatus.pollInterval }}s</span>
        </div>
      </div>
    </div>

    <!-- 系统健康检查 -->
    <div class="content-card">
      <div class="content-card__header">
        <span class="content-card__title">
          <el-icon style="margin-right: 6px;"><CircleCheck /></el-icon>
          {{ $t('settings.systemHealthCheck') }}
        </span>
        <span style="font-size: 12px; color: var(--text-tertiary);">{{ $t('settings.healthCheckDesc') }}</span>
      </div>
      <div class="content-card__body">
        <HealthCheck ref="healthCheckRef" />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import {
  Refresh, MagicStick, Odometer, Timer, DataLine, Lightning, Box,
  Check, RefreshLeft, CircleCheck
} from '@element-plus/icons-vue'
import { useSovereigntySettings } from '@/composables/useSovereigntySettings'
import { useHealthMonitor } from '@/composables/useHealthMonitor'
import HealthCheck from '@/components/HealthCheck.vue'

const { t } = useI18n()
const healthCheckRef = ref<InstanceType<typeof HealthCheck> | null>(null)

const {
  sovereigntySettings,
  autonomyMarks,
  formatAutonomyLevel,
  currentAutonomyDescription,
  getAutonomyAlertType,
  handleAutonomyChange,
  saveSovereigntySettings,
  resetSovereigntySettings,
} = useSovereigntySettings()

const {
  healthStatus,
  healthLoading,
  refreshHealth,
} = useHealthMonitor()

const showSovereigntyIntro = ref(true)

let healthCheckTimeoutId: number | null = null

const autonomyLabels = computed(() => [
  t('settings.fullyManual'),
  t('settings.confirmRequired'),
  t('settings.recommended'),
  t('settings.semiAuto'),
  t('settings.fullyAuto'),
])

onMounted(() => {
  healthCheckTimeoutId = window.setTimeout(() => {
    healthCheckRef.value?.runAllChecks()
  }, 300)
})

onBeforeUnmount(() => {
  if (healthCheckTimeoutId !== null) {
    clearTimeout(healthCheckTimeoutId)
    healthCheckTimeoutId = null
  }
})
</script>

<style scoped>
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
  color: var(--text-secondary);
  text-align: center;
  flex: 1;
}

.switch-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 32px;
}

.form-actions {
  display: flex;
  gap: 8px;
  padding-top: 16px;
  margin-top: 8px;
  border-top: 1px solid var(--bg-100);
}

.settings-form :deep(.el-form-item) {
  margin-bottom: 18px;
}

.settings-form :deep(.el-divider) {
  border-color: var(--bg-100);
  margin: 4px 0;
}

/* 健康监控指标网格 */
.health-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 24px;
}

.health-stat {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 14px;
  background: var(--bg-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-100);
}

.health-stat__icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--radius-md);
  flex-shrink: 0;
}

.health-stat__icon--blue { background: rgba(59, 130, 246, 0.1); color: #3b82f6; }
.health-stat__icon--green { background: rgba(34, 197, 94, 0.1); color: #22c55e; }
.health-stat__icon--orange { background: rgba(249, 115, 22, 0.1); color: #f97316; }
.health-stat__icon--purple { background: rgba(139, 92, 246, 0.1); color: #8b5cf6; }

.health-stat__content {
  display: flex;
  flex-direction: column;
  gap: 2px;
  min-width: 0;
}

.health-stat__label {
  font-size: 12px;
  color: var(--text-tertiary);
}

.health-stat__value {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-primary);
}

/* 资源使用进度条 */
.resource-section {
  display: flex;
  flex-direction: column;
  gap: 16px;
  margin-bottom: 24px;
  padding: 16px;
  background: var(--bg-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-100);
}

.resource-bar__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 6px;
}

.resource-bar__label {
  font-size: 13px;
  color: var(--text-secondary);
}

.resource-bar__value {
  font-size: 13px;
  color: var(--text-tertiary);
  font-family: monospace;
}

/* 推理趋势 */
.trend-section {
  padding: 16px;
  background: var(--bg-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-100);
  margin-bottom: 16px;
}

.trend-section__header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.trend-section__title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
}

.trend-section__stats {
  font-size: 11px;
  color: var(--text-tertiary);
  font-family: monospace;
}

.trend-chart {
  display: flex;
  align-items: flex-end;
  gap: 4px;
  height: 56px;
  padding: 4px 0;
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
  max-width: 28px;
  border-radius: 3px 3px 0 0;
  min-height: 4px;
  transition: height 0.3s ease;
}

.trend-bar-label {
  font-size: 9px;
  color: var(--text-tertiary);
  margin-top: 3px;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

/* 服务状态栏 */
.services-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 16px;
  background: var(--bg-50);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-100);
}

.services-bar__label {
  font-size: 13px;
  color: var(--text-secondary);
  font-weight: 500;
}

.services-bar__tags {
  display: flex;
  gap: 6px;
}

.services-bar__interval {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-tertiary);
}
</style>
