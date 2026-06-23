<template>
  <div>
    <el-card class="ai-sovereignty-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.aiSovereignty') }}</span>
          <el-tag
            type="success"
            size="small"
          >
            {{ $t('settings.sovereigntyMode') }}
          </el-tag>
        </div>
      </template>

      <el-alert
        v-if="showSovereigntyIntro"
        :title="$t('settings.autonomyModeTitle')"
        type="info"
        :closable="true"
        show-icon
        style="margin-bottom: 16px;"
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
              >
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

        <el-form-item>
          <el-button
            type="primary"
            @click="saveSovereigntySettings"
          >
            {{ $t('settings.saveSovereignty') }}
          </el-button>
          <el-button @click="resetSovereigntySettings">
            {{ $t('common.reset') }}
          </el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card
      class="health-card"
      shadow="hover"
    >
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.systemHealth') }}</span>
          <div>
            <el-tag
              :type="healthStatus.backendOnline ? 'success' : 'danger'"
              size="small"
            >
              {{ healthStatus.backendOnline ? $t('common.online') : $t('common.offline') }}
            </el-tag>
            <el-button
              size="small"
              :loading="healthLoading"
              style="margin-left:8px"
              circle
              @click="refreshHealth"
            >
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
              <el-tag
                :type="healthStatus.activeTrainingTasks > 0 ? 'warning' : 'info'"
                size="small"
              >
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
                backgroundColor: item.duration_ms > 500 ? 'var(--error)' : item.duration_ms > 200 ? 'var(--warning)' : 'var(--success)'
              }"
              :title="`${item.model}: ${item.duration_ms}ms`"
            />
            <span class="trend-bar-label">{{ item.model ? item.model.substring(0, 6) : '-' }}</span>
          </div>
        </div>
        <div class="stat-sub">
          P50: {{ healthStatus.p50Ms }}ms | P95: {{ healthStatus.p95Ms }}ms | 最大: {{ healthStatus.maxRecentDuration }}ms
        </div>
      </div>

      <el-divider style="margin: 12px 0" />

      <div class="services-row">
        <el-tag
          :type="healthStatus.dbHealthy ? 'success' : 'danger'"
          size="small"
        >
          {{ $t('settings.db') }}
        </el-tag>
        <el-tag
          :type="healthStatus.redisHealthy ? 'success' : 'danger'"
          size="small"
          style="margin-left:6px"
        >
          Redis
        </el-tag>
        <el-tag
          :type="healthStatus.prometheusHealthy ? 'success' : 'danger'"
          size="small"
          style="margin-left:6px"
        >
          Prometheus
        </el-tag>
        <span style="margin-left:12px;font-size:12px;color:var(--text-secondary)">{{ $t('settings.autoRefresh') }}: {{ healthStatus.pollInterval }}s</span>
      </div>
    </el-card>

    <el-card class="health-check-card">
      <template #header>
        <div class="card-header">
          <span>{{ $t('settings.systemHealthCheck') }}</span>
          <span style="font-size:12px;color:var(--text-secondary)">{{ $t('settings.healthCheckDesc') }}</span>
        </div>
      </template>
      <HealthCheck ref="healthCheckRef" />
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted, onBeforeUnmount, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { Refresh } from '@element-plus/icons-vue'
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
.health-card {
  margin-bottom: 16px;
}

.health-check-card {
  margin-bottom: 24px;
}

.health-card .card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  width: 100%;
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
  color: var(--text-secondary);
  text-align: center;
  flex: 1;
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.stat-item {
  text-align: center;
  padding: 8px 0;
}

.stat-label {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-bottom: 4px;
}

.stat-value {
  display: block;
  font-size: 20px;
  font-weight: 600;
  color: var(--text-primary);
}

.stat-sub {
  display: block;
  font-size: 11px;
  color: var(--text-tertiary);
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
  color: var(--text-tertiary);
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
</style>
