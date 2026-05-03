<template>
  <div class="solver-progress-timeline">
    <div class="timeline-header">
      <h3 class="timeline-title">
        <svg viewBox="0 0 1024 1024" width="20" height="20" class="title-icon">
          <path d="M896 192H128v64h768v-64zM832 320H192v64h640v-64zM768 448H256v64h512v-64zM704 576H320v64h384v-64zM640 704H384v64h256v-64z" fill="#52c41a"/>
          <path d="M896 128H128c-35.3 0-64 28.7-64 64v640c0 35.3 28.7 64 64 64h768c35.3 0 64-28.7 64-64V192c0-35.3-28.7-64-64-64zm0 704H128V192h768v640z" fill="#52c41a"/>
        </svg>
        分阶段求解进度
      </h3>
      <div class="header-actions">
        <span v-if="isActive" class="active-indicator">
          <span class="pulse-dot"></span>
          求解中...
        </span>
        <button v-if="canTerminate" class="action-btn terminate-btn" @click="handleTerminate">
          终止求解
        </button>
      </div>
    </div>

    <div class="timeline-body">
      <div v-if="!phaseStates || phaseStates.length === 0" class="empty-state">
        <svg viewBox="0 0 1024 1024" width="48" height="48" class="empty-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#d9d9d9"/>
        </svg>
        <p>暂无求解进度</p>
      </div>

      <div v-else class="phase-list">
        <div 
          v-for="(phase, index) in phaseStates" 
          :key="phase.phase"
          class="phase-item"
          :class="getPhaseItemClass(phase, index)"
        >
          <div class="phase-connector">
            <div class="phase-dot" :class="getPhaseDotClass(phase)">
              <svg v-if="phase.state === 'completed'" viewBox="0 0 1024 1024" width="16" height="16">
                <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm193.6 298.4L394.4 673.6c-12.5 12.5-32.8 12.5-45.3 0-12.5-12.5-12.5-32.8 0-45.3l285.7-285.7c12.5-12.5 32.8-12.5 45.3 0 12.6 12.5 12.6 32.8.1 45.3z" fill="#fff"/>
              </svg>
              <svg v-else-if="phase.state === 'failed'" viewBox="0 0 1024 1024" width="16" height="16">
                <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm234.7 630.7c12.5-12.5 12.5-32.8 0-45.3-12.5-12.5-32.8-12.5-45.3 0L512 467.3 322.6 277.3c-12.5-12.5-32.8-12.5-45.3 0-12.5 12.5-12.5 32.8 0 45.3L466.7 512 277.3 701.4c-12.5 12.5-12.5 32.8 0 45.3 12.5 12.5 32.8 12.5 45.3 0L512 556.7l189.4 189.4c12.5 12.5 32.8 12.5 45.3 0z" fill="#fff"/>
              </svg>
              <span v-else-if="phase.state === 'solving'" class="loading-spinner"></span>
            </div>
            <div class="phase-line" v-if="index < phaseStates.length - 1"></div>
          </div>

          <div class="phase-content">
            <div class="phase-header" @click="togglePhaseExpand(index)">
              <div class="phase-info">
                <span class="phase-name">{{ getPhaseLabel(phase.phase) }}</span>
                <span class="phase-status" :class="getPhaseStatusLabelClass(phase)">
                  {{ getPhaseStatusLabel(phase) }}
                </span>
              </div>
              <div class="phase-metrics">
                <span v-if="phase.metrics" class="metric-brief">
                  {{ formatPhaseMetrics(phase.metrics) }}
                </span>
                <span v-if="phase.duration_ms" class="phase-duration">
                  {{ formatDuration(phase.duration_ms) }}
                </span>
              </div>
              <svg 
                class="expand-icon" 
                :class="{ 'expand-icon-expanded': expandedPhases[index] }"
                viewBox="0 0 1024 1024" 
                width="16" 
                height="16"
              >
                <path d="M512 714.7a14.8 14.8 0 0 1-10.2-4.1L200.1 409.3a14.3 14.3 0 0 1 0-20.7 15.4 15.4 0 0 1 21.3 0L512 673.4l290.6-284.7a15.4 15.4 0 0 1 21.3 0 14.3 14.3 0 0 1 0 20.7L522.2 710.6a14.8 14.8 0 0 1-10.2 4.1z" fill="#999"/>
              </svg>
            </div>

            <div v-if="expandedPhases[index]" class="phase-detail">
              <div v-if="phase.parameters" class="detail-section">
                <h5 class="section-title">求解参数</h5>
                <div class="params-grid">
                  <div v-for="(value, key) in phase.parameters" :key="key" class="param-item">
                    <span class="param-label">{{ formatParamKey(key) }}</span>
                    <span class="param-value">{{ formatParamValue(key, value) }}</span>
                  </div>
                </div>
              </div>

              <div v-if="phase.metrics" class="detail-section">
                <h5 class="section-title">优化指标</h5>
                <div class="metrics-grid">
                  <div v-for="(value, key) in phase.metrics" :key="key" class="metric-item">
                    <span class="metric-label">{{ formatMetricKey(key) }}</span>
                    <span class="metric-value">{{ formatMetricValue(key, value) }}</span>
                  </div>
                </div>
              </div>

              <div v-if="phase.validation" class="detail-section">
                <h5 class="section-title">验证结果</h5>
                <div class="validation-result" :class="{ 'validation-passed': phase.validation.validation_passed, 'validation-failed': !phase.validation.validation_passed }">
                  <span class="validation-status">
                    {{ phase.validation.validation_passed ? '验证通过' : '验证失败' }}
                  </span>
                  <span v-if="phase.validation.error_rate > 0" class="error-rate">
                    误差率: {{ (phase.validation.error_rate * 100).toFixed(2) }}%
                  </span>
                </div>
                <div v-if="phase.validation.warnings && phase.validation.warnings.length > 0" class="warnings-list">
                  <div v-for="(warning, idx) in phase.validation.warnings" :key="idx" class="warning-item">
                    <svg viewBox="0 0 1024 1024" width="14" height="14" class="warning-icon">
                      <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#faad14"/>
                      <path d="M464 336c0-26.5 21.5-48 48-48s48 21.5 48 48v192c0 26.5-21.5 48-48 48s-48-21.5-48-48V336z" fill="#fff"/>
                    </svg>
                    <span>{{ warning }}</span>
                  </div>
                </div>
                <div v-if="phase.validation.violations && Object.keys(phase.validation.violations).length > 0" class="violations-list">
                  <div v-for="(violation, key) in phase.validation.violations" :key="key" class="violation-item">
                    <span class="violation-label">{{ formatViolationKey(key) }}</span>
                    <span v-if="violation.actual" class="violation-value">
                      实际值: {{ formatViolationValue(key, violation.actual) }}
                      (要求: {{ formatViolationValue(key, violation.required) }})
                    </span>
                  </div>
                </div>
              </div>

              <div v-if="phase.error_message" class="detail-section error-section">
                <h5 class="section-title">错误信息</h5>
                <p class="error-message">{{ phase.error_message }}</p>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="performanceReport" class="performance-report">
        <h4 class="report-title">性能报告</h4>
        <div class="report-grid">
          <div class="report-item">
            <span class="report-label">总耗时</span>
            <span class="report-value">{{ formatDuration(performanceReport.total_time_ms) }}</span>
          </div>
          <div class="report-item">
            <span class="report-label">求解耗时</span>
            <span class="report-value">{{ formatDuration(performanceReport.total_solver_time_ms) }}</span>
          </div>
          <div class="report-item">
            <span class="report-label">验证耗时</span>
            <span class="report-value">{{ formatDuration(performanceReport.total_validation_time_ms) }}</span>
          </div>
          <div class="report-item">
            <span class="report-label">成功率</span>
            <span class="report-value">{{ (performanceReport.success_rate * 100).toFixed(1) }}%</span>
          </div>
        </div>
      </div>

      <div v-if="terminationReason" class="termination-message">
        <svg viewBox="0 0 1024 1024" width="16" height="16" class="termination-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#ff4d4f"/>
          <path d="M464 336c0-26.5 21.5-48 48-48s48 21.5 48 48v192c0 26.5-21.5 48-48 48s-48-21.5-48-48V336z" fill="#fff"/>
        </svg>
        <span>{{ terminationReason }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface PhaseState {
  phase: string
  state: 'waiting' | 'solving' | 'completed' | 'failed' | 'rollback' | 'terminated'
  parameters?: Record<string, number>
  metrics?: Record<string, number>
  duration_ms?: number
  validation?: {
    validation_passed: boolean
    error_rate: number
    warnings?: string[]
    violations?: Record<string, any>
  }
  error_message?: string
}

interface PerformanceReport {
  total_phases: number
  passed_phases: number
  failed_phases: number
  success_rate: number
  total_solver_time_ms: number
  total_validation_time_ms: number
  total_time_ms: number
  average_phase_time_ms: number
  strategy: string
}

const props = defineProps<{
  phaseStates?: PhaseState[]
  performanceReport?: PerformanceReport | null
  terminationReason?: string
  isActive?: boolean
  canTerminate?: boolean
}>()

const emit = defineEmits<{
  terminate: []
}>()

const expandedPhases = ref<Record<number, boolean>>({})

function togglePhaseExpand(index: number) {
  expandedPhases.value[index] = !expandedPhases.value[index]
}

function getPhaseItemClass(phase: PhaseState, index: number): string {
  const classes: string[] = []
  if (phase.state === 'completed') classes.push('phase-completed')
  if (phase.state === 'failed') classes.push('phase-failed')
  if (phase.state === 'solving') classes.push('phase-solving')
  return classes.join(' ')
}

function getPhaseDotClass(phase: PhaseState): string {
  if (phase.state === 'completed') return 'dot-completed'
  if (phase.state === 'failed') return 'dot-failed'
  if (phase.state === 'solving') return 'dot-solving'
  return 'dot-waiting'
}

function getPhaseLabel(phase: string): string {
  const labels: Record<string, string> = {
    feasibility: '可行性求解',
    cutting_force: '切削力优化',
    surface_roughness: '表面粗糙度优化',
    tool_life: '刀具寿命优化'
  }
  return labels[phase] || phase
}

function getPhaseStatusLabel(phase: PhaseState): string {
  const labels: Record<string, string> = {
    waiting: '等待中',
    solving: '求解中',
    completed: '已完成',
    failed: '失败',
    rollback: '回退中',
    terminated: '已终止'
  }
  return labels[phase.state] || phase.state
}

function getPhaseStatusLabelClass(phase: PhaseState): string {
  if (phase.state === 'completed') return 'status-completed'
  if (phase.state === 'failed') return 'status-failed'
  if (phase.state === 'solving') return 'status-solving'
  return 'status-waiting'
}

function formatPhaseMetrics(metrics: Record<string, number>): string {
  const parts: string[] = []
  if (metrics.cutting_force) parts.push(`力: ${metrics.cutting_force.toFixed(0)}N`)
  if (metrics.surface_roughness) parts.push(`Ra: ${metrics.surface_roughness.toFixed(2)}μm`)
  if (metrics.tool_life) parts.push(`寿命: ${metrics.tool_life.toFixed(0)}min`)
  return parts.join(' | ')
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatParamKey(key: string): string {
  const labels: Record<string, string> = {
    cutting_speed: '切削速度',
    feed_rate: '进给量',
    depth_of_cut: '背吃刀量'
  }
  return labels[key] || key
}

function formatParamValue(key: string, value: number): string {
  if (key === 'cutting_speed') return `${value.toFixed(1)} m/min`
  if (key === 'feed_rate') return `${value.toFixed(3)} mm/rev`
  if (key === 'depth_of_cut') return `${value.toFixed(2)} mm`
  return value.toFixed(2)
}

function formatMetricKey(key: string): string {
  const labels: Record<string, string> = {
    cutting_force: '切削力',
    surface_roughness: '表面粗糙度',
    tool_life: '刀具寿命'
  }
  return labels[key] || key
}

function formatMetricValue(key: string, value: number): string {
  if (key === 'cutting_force') return `${value.toFixed(1)} N`
  if (key === 'surface_roughness') return `${value.toFixed(2)} μm`
  if (key === 'tool_life') return `${value.toFixed(1)} min`
  return value.toFixed(2)
}

function formatViolationKey(key: string): string {
  return key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())
}

function formatViolationValue(key: string, value: number): string {
  if (key.includes('cutting_force')) return `${value.toFixed(1)}N`
  if (key.includes('roughness')) return `${value.toFixed(2)}μm`
  if (key.includes('tool_life')) return `${value.toFixed(1)}min`
  return value.toFixed(2)
}

function handleTerminate() {
  emit('terminate')
}
</script>

<style scoped>
.solver-progress-timeline {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.timeline-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.timeline-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.title-icon {
  width: 20px;
  height: 20px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
}

.active-indicator {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #52c41a;
}

.pulse-dot {
  width: 8px;
  height: 8px;
  background: #52c41a;
  border-radius: 50%;
  animation: pulse 1.5s ease-in-out infinite;
}

@keyframes pulse {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: 0.5; transform: scale(1.2); }
}

.action-btn {
  background: #fff;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  padding: 4px 8px;
  font-size: 12px;
  cursor: pointer;
  color: #666;
}

.action-btn:hover {
  border-color: #409EFF;
  color: #409EFF;
}

.terminate-btn {
  border-color: #ff4d4f;
  color: #ff4d4f;
}

.terminate-btn:hover {
  background: #ff4d4f;
  color: #fff;
}

.timeline-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: #999;
}

.empty-icon {
  margin-bottom: 12px;
}

.phase-list {
  position: relative;
}

.phase-item {
  display: flex;
  margin-bottom: 0;
  position: relative;
  transition: all 0.2s;
}

.phase-item:last-child {
  margin-bottom: 0;
}

.phase-connector {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 40px;
  flex-shrink: 0;
}

.phase-dot {
  width: 32px;
  height: 32px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  color: #fff;
  position: relative;
  z-index: 1;
  border: 2px solid #e8e8e8;
  background: #f0f0f0;
}

.dot-completed {
  background: #52c41a;
  border-color: #52c41a;
}

.dot-failed {
  background: #ff4d4f;
  border-color: #ff4d4f;
}

.dot-solving {
  background: #409EFF;
  border-color: #409EFF;
  animation: pulse 1.5s ease-in-out infinite;
}

.dot-waiting {
  background: #e8e8e8;
  border-color: #d9d9d9;
}

.loading-spinner {
  width: 12px;
  height: 12px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.phase-line {
  width: 2px;
  flex: 1;
  background: #e8e8e8;
  min-height: 40px;
}

.phase-content {
  flex: 1;
  padding: 8px 0 24px 12px;
  background: #fff;
  border-radius: 8px;
  transition: all 0.2s;
}

.phase-completed .phase-content {
  background: #f6ffed;
}

.phase-failed .phase-content {
  background: #fff2f0;
}

.phase-solving .phase-content {
  background: #e6f7ff;
}

.phase-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.8);
}

.phase-header:hover {
  background: rgba(255, 255, 255, 0.95);
}

.phase-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.phase-name {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.phase-status {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.status-completed {
  background: #52c41a;
  color: #fff;
}

.status-failed {
  background: #ff4d4f;
  color: #fff;
}

.status-solving {
  background: #409EFF;
  color: #fff;
}

.status-waiting {
  background: #e8e8e8;
  color: #999;
}

.phase-metrics {
  display: flex;
  align-items: center;
  gap: 12px;
}

.metric-brief {
  font-size: 12px;
  color: #666;
}

.phase-duration {
  font-size: 12px;
  color: #999;
}

.expand-icon {
  transition: transform 0.2s;
}

.expand-icon-expanded {
  transform: rotate(180deg);
}

.phase-detail {
  padding: 12px;
  background: #fff;
  border-radius: 4px;
  margin-top: 8px;
  border: 1px solid #e8e8e8;
}

.detail-section {
  margin-bottom: 12px;
}

.detail-section:last-child {
  margin-bottom: 0;
}

.section-title {
  margin: 0 0 4px 0;
  font-size: 12px;
  font-weight: 600;
  color: #666;
}

.params-grid, .metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}

.param-item, .metric-item {
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
}

.param-label, .metric-label {
  font-size: 11px;
  color: #999;
  margin-bottom: 2px;
}

.param-value, .metric-value {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.validation-result {
  padding: 8px 12px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.validation-passed {
  background: #f6ffed;
  border: 1px solid #b7eb8f;
}

.validation-failed {
  background: #fff2f0;
  border: 1px solid #ffccc7;
}

.validation-status {
  font-size: 12px;
  font-weight: 600;
}

.validation-passed .validation-status {
  color: #52c41a;
}

.validation-failed .validation-status {
  color: #ff4d4f;
}

.error-rate {
  font-size: 12px;
  color: #fa8c16;
}

.warnings-list {
  margin-top: 8px;
}

.warning-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 4px 8px;
  background: #fffbe6;
  border-left: 2px solid #faad14;
  margin-bottom: 4px;
  font-size: 12px;
  color: #d46b08;
}

.warning-icon {
  flex-shrink: 0;
}

.violations-list {
  margin-top: 8px;
}

.violation-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 4px 8px;
  background: #fff2f0;
  border-left: 2px solid #ff4d4f;
  margin-bottom: 4px;
  font-size: 12px;
}

.violation-label {
  font-weight: 600;
  color: #ff4d4f;
}

.violation-value {
  color: #ff4d4f;
}

.error-section {
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  padding: 8px 12px;
}

.error-message {
  margin: 0;
  font-size: 12px;
  color: #ff4d4f;
  line-height: 1.5;
}

.performance-report {
  margin-top: 16px;
  padding: 12px;
  background: #fafafa;
  border-radius: 8px;
  border: 1px solid #e8e8e8;
}

.report-title {
  margin: 0 0 8px 0;
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.report-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}

.report-item {
  display: flex;
  flex-direction: column;
  padding: 8px;
  background: #fff;
  border-radius: 4px;
  border: 1px solid #e8e8e8;
}

.report-label {
  font-size: 11px;
  color: #999;
  margin-bottom: 4px;
}

.report-value {
  font-size: 14px;
  font-weight: 600;
  color: #333;
}

.termination-message {
  margin-top: 16px;
  padding: 8px 12px;
  background: #fff2f0;
  border: 1px solid #ffccc7;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #ff4d4f;
}

.termination-icon {
  flex-shrink: 0;
}
</style>
