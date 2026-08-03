<template>
    <div
      v-show="activeTab === 'simulation'"
      class="tab-panel"
    >
      <div class="sim-layout">
        <!-- Left Column: Input & Controls -->
        <div class="sim-left">
          <!-- NC Code Input Section -->
          <div class="content-card">
            <div class="content-card__header">
              <span class="content-card__title">{{ t('simulationPage.ncCodeTitle') }}</span>
              <div class="header-actions">
                <el-upload
                  ref="uploadRef"
                  :auto-upload="false"
                  :show-file-list="false"
                  accept=".nc,.NC,.gcode,.gc,.tap,.txt,.CNC,.cnc"
                  :on-change="handleFileUpload"
                >
                  <el-button
                    size="small"
                    :icon="Upload"
                  >
                    {{ t('simulationPage.uploadFile') }}
                  </el-button>
                </el-upload>
                <el-button
                  v-if="gcode"
                  size="small"
                  :icon="Delete"
                  @click="gcode = ''"
                >
                  {{ t('simulationPage.clear') }}
                </el-button>
              </div>
            </div>
            <div class="content-card__body">
              <el-input
                v-model="gcode"
                type="textarea"
                :placeholder="t('simulationPage.gcodePlaceholder')"
                :autosize="{ minRows: 6, maxRows: 14 }"
                resize="vertical"
                class="gcode-textarea"
              />
              <div
                v-if="gcodeStats.lines > 0"
                class="gcode-stats"
              >
                <span>{{ t('simulationPage.gcodeLines', { count: gcodeStats.lines }) }}</span>
                <span>{{ t('simulationPage.gcodeGCommands', { count: gcodeStats.gCommands }) }}</span>
                <span>{{ t('simulationPage.gcodeMCommands', { count: gcodeStats.mCommands }) }}</span>
              </div>
            </div>
          </div>

          <!-- Simulation Parameters -->
          <div class="content-card">
            <div class="content-card__header">
              <span class="content-card__title">{{ t('simulationPage.paramsTitle') }}</span>
            </div>
            <div class="content-card__body">
              <el-form
                label-position="left"
                label-width="80px"
                size="small"
              >
                <div class="params-grid">
                  <el-form-item :label="t('simulationPage.paramVoxelSize')">
                    <el-input-number
                      v-model="simParams.voxelSize"
                      :min="0.1"
                      :max="10"
                      :step="0.1"
                      :controls="false"
                      style="width: 100%"
                    />
                  </el-form-item>
                  <el-form-item :label="t('simulationPage.paramToolType')">
                    <el-select
                      v-model="simParams.toolType"
                      style="width: 100%"
                    >
                      <el-option
                        :label="t('simulationPage.toolFlat')"
                        value="flat"
                      />
                      <el-option
                        :label="t('simulationPage.toolBall')"
                        value="ball"
                      />
                      <el-option
                        :label="t('simulationPage.toolDrill')"
                        value="drill"
                      />
                    </el-select>
                  </el-form-item>
                  <el-form-item :label="t('simulationPage.paramToolDiameter')">
                    <el-input-number
                      v-model="simParams.toolDiameter"
                      :min="0.5"
                      :max="300"
                      :step="0.5"
                      :controls="false"
                      style="width: 100%"
                    />
                  </el-form-item>
                  <el-form-item :label="t('simulationPage.paramToolLength')">
                    <el-input-number
                      v-model="simParams.toolLength"
                      :min="1"
                      :max="500"
                      :step="1"
                      :controls="false"
                      style="width: 100%"
                    />
                  </el-form-item>
                  <el-form-item :label="t('simulationPage.paramSafeZ')">
                    <el-input-number
                      v-model="simParams.safeZ"
                      :min="0"
                      :max="200"
                      :step="1"
                      :controls="false"
                      style="width: 100%"
                    />
                  </el-form-item>
                  <el-form-item :label="t('simulationPage.paramCornerRadius')">
                    <el-input-number
                      v-model="simParams.toolCornerRadius"
                      :min="0"
                      :max="150"
                      :step="0.5"
                      :controls="false"
                      style="width: 100%"
                    />
                  </el-form-item>
                </div>
                <el-form-item :label="t('simulationPage.paramStockStl')">
                  <el-input
                    v-model="simParams.stockStlPath"
                    :placeholder="t('simulationPage.stockStlPlaceholder')"
                    clearable
                  />
                </el-form-item>
              </el-form>
            </div>
          </div>

          <!-- Run Button -->
          <div class="run-section">
            <el-button
              type="primary"
              size="large"
              class="btn-run"
              :loading="simState === 'running'"
              :disabled="!gcode.trim()"
              @click="handleRunSimulation"
            >
              <el-icon
                v-if="simState !== 'running'"
                class="btn-icon"
              >
                <VideoPlay />
              </el-icon>
              <span>{{ runButtonText }}</span>
            </el-button>
            <el-button
              v-if="simState === 'completed'"
              size="large"
              class="btn-rerun"
              @click="handleRunSimulation"
            >
              {{ t('simulationPage.rerunSim') }}
            </el-button>
          </div>

          <!-- Simulation Result -->
          <div
            v-if="simState === 'completed' && simResult"
            class="content-card result-card"
          >
            <div class="content-card__header">
              <span class="content-card__title">{{ t('simulationPage.resultTitle') }}</span>
              <el-tag
                :type="simResult.collision_detected ? 'danger' : 'success'"
                effect="dark"
                size="small"
              >
                {{ simResult.collision_detected ? t('simulationPage.collisionDetected') : t('simulationPage.simPassed') }}
              </el-tag>
            </div>
            <div class="content-card__body">
              <div class="result-stats">
                <div class="result-stat">
                  <span class="stat-label">{{ t('simulationPage.statDuration') }}</span>
                  <span class="stat-value">{{ (simResult.duration_seconds ?? 0).toFixed(2) }}s</span>
                </div>
                <div class="result-stat">
                  <span class="stat-label">{{ t('simulationPage.statVoxelCount') }}</span>
                  <span class="stat-value">{{ formatNumber(simResult.voxel_count ?? 0) }}</span>
                </div>
                <div class="result-stat">
                  <span class="stat-label">{{ t('simulationPage.statRemovedVoxel') }}</span>
                  <span class="stat-value">{{ formatNumber(simResult.removed_voxel_count ?? 0) }}</span>
                </div>
                <div class="result-stat">
                  <span class="stat-label">{{ t('simulationPage.statToolpathSegments') }}</span>
                  <span class="stat-value">{{ simResult.toolpath_segment_count ?? 0 }}</span>
                </div>
              </div>

              <!-- Collision Alert -->
              <div
                v-if="simResult.collision_detected"
                class="collision-warning"
              >
                <el-icon
                  :size="20"
                  color="var(--state-error)"
                >
                  <WarningFilled />
                </el-icon>
                <div class="collision-warning__content">
                  <span class="collision-warning__title">
                    {{ t('simulationPage.collisionCount', { count: simResult.collision_details?.count ?? 0 }) }}
                  </span>
                  <span class="collision-warning__desc">
                    {{ t('simulationPage.collisionSeverity', { severity: simResult.collision_details?.severity ?? '-' }) }}
                  </span>
                </div>
                <el-button
                  size="small"
                  type="danger"
                  plain
                  @click="showCollisionDetail = true"
                >
                  {{ t('simulationPage.viewDetail') }}
                </el-button>
              </div>

              <!-- Pass/Fail Action -->
              <div
                v-if="simResult.collision_detected"
                class="fail-actions"
              >
                <el-alert
                  type="error"
                  :closable="false"
                  show-icon
                >
                  <template #title>
                    <span>{{ t('simulationPage.failAlertTitle') }}</span>
                  </template>
                  <template #default>
                    <div class="fail-suggestions">
                      <p>{{ t('simulationPage.suggestTitle') }}</p>
                      <ul>
                        <li>{{ t('simulationPage.suggest1') }}</li>
                        <li>{{ t('simulationPage.suggest2') }}</li>
                        <li>{{ t('simulationPage.suggest3') }}</li>
                        <li>{{ t('simulationPage.suggest4') }}</li>
                      </ul>
                    </div>
                  </template>
                </el-alert>
              </div>
              <div
                v-else
                class="pass-info"
              >
                <el-alert
                  type="success"
                  :closable="false"
                  show-icon
                >
                  <template #title>
                    <span>{{ t('simulationPage.passAlertTitle') }}</span>
                  </template>
                  <template #default>
                    <span>{{ t('simulationPage.passAlertDesc') }}</span>
                  </template>
                </el-alert>
              </div>

              <!-- Action buttons for completed simulation -->
              <div class="result-actions">
                <el-button
                  size="small"
                  :icon="Download"
                  :disabled="!simResult?.simulation_result?.workpiece_stl_path"
                  @click="handleDownloadStl"
                >
                  {{ t('simulationPage.downloadStl') }}
                </el-button>
                <el-button
                  size="small"
                  @click="showCollisionDetail = true"
                >
                  {{ simResult.collision_detected ? t('simulationPage.collisionDetail') : t('simulationPage.viewReport') }}
                </el-button>
              </div>
            </div>
          </div>

          <!-- Simulation History -->
          <div class="content-card">
            <div class="content-card__header">
              <span class="content-card__title">{{ t('simulationPage.historyTitle') }}</span>
            </div>
            <div class="content-card__body">
              <div
                v-if="historyLoading"
                class="loading-wrap"
              >
                <el-skeleton
                  :rows="3"
                  animated
                />
              </div>
              <el-empty
                v-else-if="historyItems.length === 0"
                :description="t('simulationPage.noHistory')"
                :image-size="60"
              />
              <div
                v-else
                class="history-list"
              >
                <div
                  v-for="item in historyItems"
                  :key="item.task_id"
                  class="history-item"
                >
                  <div class="history-item__main">
                    <el-tag
                      :type="item.collision_collided ? 'danger' : 'success'"
                      size="small"
                      effect="plain"
                      class="history-status"
                    >
                      {{ item.collision_collided ? t('simulationPage.historyCollision') : t('simulationPage.historyPass') }}
                    </el-tag>
                    <span class="history-id">{{ item.task_id }}</span>
                  </div>
                  <div class="history-item__meta">
                    <span>{{ item.duration_seconds?.toFixed(2) ?? '-' }}s</span>
                    <span>{{ t('simulationPage.historyVoxel', { size: item.voxel_size ?? '-' }) }}</span>
                    <span>{{ t('simulationPage.historySegments', { count: item.segment_count ?? 0 }) }}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right Column: 3D Viewport -->
        <div class="sim-right">
          <SimulationViewer
            ref="viewerRef"
            width="100%"
            height="100%"
            :show-grid="true"
            :show-axes="true"
            @ready="onViewerReady"
          />

          <!-- Status overlay -->
          <div
            v-if="simState === 'running'"
            class="viewport-overlay running-overlay"
          >
            <div class="overlay-spinner">
              <el-icon
                :size="32"
                class="is-loading"
              >
                <Loading />
              </el-icon>
            </div>
            <span class="overlay-text">{{ t('simulationPage.overlayRunning') }}</span>
            <span class="overlay-sub">{{ t('simulationPage.overlayTaskId', { taskId: currentTaskId }) }}</span>
          </div>
          <div
            v-else-if="simState === 'idle' && !gcode"
            class="viewport-overlay idle-overlay"
          >
            <div class="idle-content">
              <svg
                width="64"
                height="64"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                stroke-width="1.2"
                class="idle-icon"
              >
                <path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" />
              </svg>
              <span class="idle-title">{{ t('simulationPage.idleTitle') }}</span>
              <span class="idle-desc">{{ t('simulationPage.idleDesc') }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

</template>

<script setup lang="ts">
import { ref } from 'vue'
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
// 本组件为预留的独立页签组件，模板中可写状态在此本地声明，
// 其余只读状态通过 props 由父组件传入
defineProps<Record<string, any>>()
defineEmits<Record<string, never>>()
const gcode = ref('')
const showCollisionDetail = ref(false)
const simParams = ref({
  voxelSize: 1.0,
  toolType: 'flat',
  toolDiameter: 10.0,
  toolLength: 50.0,
  toolCornerRadius: 0.0,
  safeZ: 30.0,
  stockStlPath: '',
})
</script>


<style scoped>
<style scoped>
.simulation-page {
  padding: var(--page-padding);
  max-width: var(--content-max-width);
  margin: 0 auto;
}

/* ─── Sim Tabs (inside content-card wrapper) ─────────── */
.sim-tabs {
  display: flex;
  gap: 4px;
}

.sim-tab-item {
  display: flex;
  align-items: center;
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 14px;
  color: var(--text-secondary);
  transition: all 0.2s ease;
  user-select: none;
}

.sim-tab-item:hover {
  color: var(--text-primary);
  background: var(--bg-200);
}

.sim-tab-item.active {
  background: var(--accent-primary);
  color: var(--text-white);
  font-weight: 500;
}

/* ─── Tab Panel ────────────────────────────────────────── */
.tab-panel {
  animation: fadeIn 0.25s ease;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: translateY(0); }
}

/* ─── Simulation Layout ──────────────────────────────── */
.sim-layout {
  display: grid;
  grid-template-columns: 420px 1fr;
  gap: 20px;
  min-height: 600px;
}

@media (max-width: 1200px) {
  .sim-layout {
    grid-template-columns: 1fr;
  }
  .sim-right {
    min-height: 400px;
  }
}

.sim-left {
  display: flex;
  flex-direction: column;
  gap: 16px;
  max-height: calc(100vh - 180px);
  overflow-y: auto;
  padding-right: 4px;
}

.sim-right {
  position: relative;
  min-height: 500px;
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--bg-200);
  background: var(--bg-100);
}

/* ─── Content Card overrides (minimal) ─────────────────── */
.content-card__header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 20px;
  border-bottom: 1px solid var(--bg-200);
}

.content-card__title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
}

.content-card__body {
  padding: 16px 20px;
}

.header-actions {
  display: flex;
  gap: 8px;
}

/* ─── G-code Textarea ──────────────────────────────────── */
.gcode-textarea :deep(.el-textarea__inner) {
  font-family: var(--font-mono);
  font-size: 12.5px;
  line-height: 1.6;
  color: var(--text-primary);
}

.gcode-stats {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ─── Parameters Grid ─────────────────────────────────── */
.params-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

/* ─── Run Button ───────────────────────────────────────── */
.run-section {
  display: flex;
  gap: 12px;
  align-items: center;
}

.btn-run {
  flex: 1;
  font-weight: 500;
  height: 42px;
}

.btn-icon {
  margin-right: 4px;
}

.btn-rerun {
  height: 42px;
}

/* ─── Result Card ───────────────────────────────────────── */
  .result-card {
    border-left: 3px solid var(--state-success);
  }

  .result-card:has(.collision-warning) {
  border-left-color: var(--state-error);
}

.result-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.result-stat {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 10px 8px;
  background: var(--bg-200);
  border-radius: var(--radius-sm);
}

.stat-label {
  font-size: 11px;
  color: var(--text-tertiary);
}

.stat-value {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  font-variant-numeric: tabular-nums;
}

/* ─── Collision Warning ────────────────────────────────── */
.collision-warning {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 12px;
  margin: 12px 0;
  background: var(--state-error-bg);
  border: 1px solid var(--state-error-border);
  border-radius: var(--radius-sm);
}

.collision-warning__content {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.collision-warning__title {
  font-size: 14px;
  font-weight: 500;
  color: var(--state-error);
}

.collision-warning__desc {
  font-size: 12px;
  color: var(--text-secondary);
}

.fail-actions {
  margin-top: 12px;
}

.fail-suggestions {
  margin: 4px 0 0 0;
  padding-left: 0;
}

.fail-suggestions p {
  margin: 0 0 4px;
  font-size: 13px;
  color: var(--text-primary);
}

.fail-suggestions ul {
  margin: 0;
  padding-left: 18px;
}

.fail-suggestions li {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.8;
}

.pass-info {
  margin-top: 12px;
}

.result-actions {
  display: flex;
  gap: 8px;
  margin-top: 14px;
}

/* ─── Viewport Overlay ─────────────────────────────────── */
.viewport-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  z-index: 20;
  pointer-events: none;
}

.running-overlay {
  background: var(--bg-3d-overlay);
  backdrop-filter: blur(4px);
}

.overlay-spinner {
  color: var(--accent-primary);
}

.overlay-text {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-primary);
}

.overlay-sub {
  font-size: 12px;
  color: var(--text-tertiary);
  font-family: var(--font-mono);
}

.idle-overlay {
  background: transparent;
}

.idle-content {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 14px;
}

.idle-icon {
  color: var(--text-tertiary);
  opacity: 0.3;
}

.idle-title {
  font-size: 16px;
  font-weight: 500;
  color: var(--text-tertiary);
  opacity: 0.5;
}

.idle-desc {
  font-size: 13px;
  color: var(--text-tertiary);
  opacity: 0.4;
  text-align: center;
  max-width: 240px;
}

/* ─── History ─────────────────────────────────────────── */
.loading-wrap {
  padding: 8px 0;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px;
  background: var(--bg-200);
  border-radius: var(--radius-sm);
  transition: background 0.2s;
}

.history-item:hover {
  background: var(--bg-200);
}

.history-item__main {
  display: flex;
  align-items: center;
  gap: 10px;
}

.history-status {
  flex-shrink: 0;
}

.history-id {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
}

.history-item__meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
  color: var(--text-tertiary);
}

/* ─── Section Title ──────────────────────────────────── */
.section-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

/* ─── FEM Section ──────────────────────────────────────── */
.fem-section {
  margin-bottom: 32px;
}

.fem-params-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}

@media (max-width: 768px) {
  .fem-params-grid {
    grid-template-columns: 1fr;
  }
}

.param-card {
  background: var(--bg-100);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-200);
  padding: 20px 24px;
}

.param-card-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 16px;
}

.param-form :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-size: 13px;
}

.fem-actions {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

.slider-labels {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

/* Results Section */
.results-section {
  margin-top: 32px;
}

.result-viewport-wrap {
  position: relative;
}

.result-viewport {
  aspect-ratio: 16 / 9;
  min-height: 360px;
  background: var(--bg-100);
  border-radius: var(--radius-lg);
  border: 1px solid var(--bg-200);
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.result-placeholder {
  color: var(--text-tertiary);
  font-size: 15px;
}

.color-legend {
  position: absolute;
  right: 20px;
  top: 20px;
  bottom: 20px;
  width: 20px;
  display: flex;
  flex-direction: column;
  align-items: center;
}

.legend-bar {
  flex: 1;
  width: 14px;
  border-radius: var(--radius-md);
  background: var(--gradient-heatmap);
  border: 1px solid var(--bg-200);
}

.legend-labels {
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  font-size: 10px;
  color: var(--text-tertiary);
  margin-top: 4px;
  height: 100%;
  position: absolute;
  left: 24px;
  top: 0;
}

/* ─── Export Section ────────────────────────────────────── */
.export-section {
  /* no extra styles needed */
}

.export-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
  gap: 20px;
  margin-bottom: 32px;
}

.export-card {
  background: var(--bg-100);
  border-radius: var(--radius-md);
  border: 1px solid var(--bg-200);
  padding: 24px;
  transition: border-color 0.25s ease, box-shadow 0.25s ease;
}

.export-card:hover {
  border-color: var(--accent-primary);
  box-shadow: var(--shadow-sm);
}

.export-card-title {
  font-size: 16px;
  font-weight: 600;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.export-card-desc {
  font-size: 13px;
  color: var(--text-secondary);
  margin: 0 0 16px;
  line-height: 1.6;
}

.export-form {
  margin-bottom: 16px;
}

.export-form :deep(.el-form-item__label) {
  color: var(--text-secondary);
  font-size: 13px;
}

.export-form-row {
  display: flex;
  gap: 16px;
}

.form-item-half {
  flex: 1;
}

.btn-export {
  width: 100%;
  font-weight: 500;
}
</style>

</style>
