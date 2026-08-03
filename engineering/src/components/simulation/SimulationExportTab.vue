<template>
    <div
      v-show="activeTab === 'export'"
      class="tab-panel"
    >
      <div class="export-section">
        <div class="export-grid">
          <div class="export-card">
            <h4 class="export-card-title">
              {{ t('simulationPage.exportGifTitle') }}
            </h4>
            <p class="export-card-desc">
              {{ t('simulationPage.exportGifDesc') }}
            </p>
            <el-form
              label-position="top"
              class="export-form"
            >
              <el-form-item :label="t('simulationPage.exportResolution')">
                <el-select
                  v-model="gifExport.resolution"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    label="640 x 360"
                    value="640x360"
                  />
                  <el-option
                    label="1280 x 720"
                    value="1280x720"
                  />
                  <el-option
                    label="1920 x 1080"
                    value="1920x1080"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('simulationPage.exportFramerate')">
                <el-select
                  v-model="gifExport.framerate"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    label="10 fps"
                    :value="10"
                  />
                  <el-option
                    label="15 fps"
                    :value="15"
                  />
                  <el-option
                    label="24 fps"
                    :value="24"
                  />
                  <el-option
                    label="30 fps"
                    :value="30"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('simulationPage.exportQuality')">
                <el-select
                  v-model="gifExport.quality"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    :label="t('simulationPage.qualityLow')"
                    value="low"
                  />
                  <el-option
                    :label="t('simulationPage.qualityMedium')"
                    value="medium"
                  />
                  <el-option
                    :label="t('simulationPage.qualityHigh')"
                    value="high"
                  />
                </el-select>
              </el-form-item>
            </el-form>
            <el-button
              type="primary"
              size="small"
              class="btn-export"
              @click="handleExportGif"
            >
              {{ t('simulationPage.exportGifBtn') }}
            </el-button>
          </div>
          <div class="export-card">
            <h4 class="export-card-title">
              {{ t('simulationPage.exportMp4Title') }}
            </h4>
            <p class="export-card-desc">
              {{ t('simulationPage.exportMp4Desc') }}
            </p>
            <el-form
              label-position="top"
              class="export-form"
            >
              <el-form-item :label="t('simulationPage.exportResolution')">
                <el-select
                  v-model="mp4Export.resolution"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    label="1280 x 720"
                    value="1280x720"
                  />
                  <el-option
                    label="1920 x 1080"
                    value="1920x1080"
                  />
                  <el-option
                    label="2560 x 1440"
                    value="2560x1440"
                  />
                  <el-option
                    label="3840 x 2160"
                    value="3840x2160"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('simulationPage.exportFramerate')">
                <el-select
                  v-model="mp4Export.framerate"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    label="24 fps"
                    :value="24"
                  />
                  <el-option
                    label="30 fps"
                    :value="30"
                  />
                  <el-option
                    label="60 fps"
                    :value="60"
                  />
                </el-select>
              </el-form-item>
              <div class="export-form-row">
                <el-form-item
                  :label="t('simulationPage.exportCodec')"
                  class="form-item-half"
                >
                  <el-select
                    v-model="mp4Export.codec"
                    size="small"
                    style="width: 100%"
                  >
                    <el-option
                      label="H.264"
                      value="h264"
                    />
                    <el-option
                      label="H.265"
                      value="h265"
                    />
                    <el-option
                      label="AV1"
                      value="av1"
                    />
                  </el-select>
                </el-form-item>
                <el-form-item
                  :label="t('simulationPage.exportBitrate')"
                  class="form-item-half"
                >
                  <el-select
                    v-model="mp4Export.bitrate"
                    size="small"
                    style="width: 100%"
                  >
                    <el-option
                      label="2 Mbps"
                      value="2"
                    />
                    <el-option
                      label="5 Mbps"
                      value="5"
                    />
                    <el-option
                      label="10 Mbps"
                      value="10"
                    />
                    <el-option
                      label="20 Mbps"
                      value="20"
                    />
                  </el-select>
                </el-form-item>
              </div>
            </el-form>
            <el-button
              type="primary"
              size="small"
              class="btn-export"
              @click="handleExportMp4"
            >
              {{ t('simulationPage.exportMp4Btn') }}
            </el-button>
          </div>
        </div>
        <div class="content-card">
          <div class="content-card__header">
            <span class="content-card__title">{{ t('simulationPage.exportHistoryTitle') }}</span>
          </div>
          <div class="content-card__body">
            <el-empty
              :description="t('simulationPage.noExportHistory')"
              :image-size="60"
            />
          </div>
        </div>
      </div>
    </div>

    <!-- Collision Detail Modal -->
    <CollisionAlertModal
      v-model:visible="showCollisionDetail"
      :collisions="collisionList"
      @locate="handleLocateCollision"
      @dismiss="handleDismissCollision"
      @dismiss-all="handleDismissAllCollisions"
    />

</template>

<script setup lang="ts">
import { useI18n } from 'vue-i18n'
const { t } = useI18n()
// State managed by parent Simulation.vue - received via props
defineProps<Record<string, any>>()
defineEmits<Record<string, never>>()
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
