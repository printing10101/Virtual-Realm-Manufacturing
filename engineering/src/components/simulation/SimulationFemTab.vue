<template>
    <div
      v-show="activeTab === 'fem'"
      class="tab-panel"
    >
      <div class="fem-section">
        <h3 class="section-title">
          {{ t('simulationPage.femSectionTitle') }}
        </h3>
        <div class="fem-params-grid">
          <div class="param-card">
            <h4 class="param-card-title">
              {{ t('simulationPage.femMaterialTitle') }}
            </h4>
            <el-form
              label-position="top"
              class="param-form"
            >
              <el-form-item :label="t('simulationPage.femMaterialName')">
                <el-select
                  v-model="femParams.material"
                  :placeholder="t('simulationPage.femMaterialPlaceholder')"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    :label="t('simulationPage.femSteel45')"
                    value="steel45"
                  />
                  <el-option
                    :label="t('simulationPage.femAl6061')"
                    value="al6061"
                  />
                  <el-option
                    :label="t('simulationPage.femSs304')"
                    value="ss304"
                  />
                  <el-option
                    :label="t('simulationPage.femTi6Al4V')"
                    value="ti6al4v"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('simulationPage.femElasticModulus')">
                <el-input-number
                  v-model="femParams.elasticModulus"
                  :min="0.01"
                  :precision="1"
                  size="small"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item :label="t('simulationPage.femPoissonRatio')">
                <el-input-number
                  v-model="femParams.poissonRatio"
                  :min="0"
                  :max="0.5"
                  :step="0.01"
                  :precision="3"
                  size="small"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item :label="t('simulationPage.femDensity')">
                <el-input-number
                  v-model="femParams.density"
                  :min="0.01"
                  :step="10"
                  :precision="1"
                  size="small"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item :label="t('simulationPage.femYieldStrength')">
                <el-input-number
                  v-model="femParams.yieldStrength"
                  :min="0.01"
                  :precision="1"
                  size="small"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item :label="t('simulationPage.femThermalConductivity')">
                <el-input-number
                  v-model="femParams.thermalConductivity"
                  :min="0.01"
                  :precision="2"
                  size="small"
                  style="width: 100%"
                />
              </el-form-item>
            </el-form>
          </div>
          <div class="param-card">
            <h4 class="param-card-title">
              {{ t('simulationPage.femMeshTitle') }}
            </h4>
            <el-form
              label-position="top"
              class="param-form"
            >
              <el-form-item :label="t('simulationPage.femMeshType')">
                <el-select
                  v-model="femParams.meshType"
                  :placeholder="t('simulationPage.femMeshTypePlaceholder')"
                  size="small"
                  style="width: 100%"
                >
                  <el-option
                    :label="t('simulationPage.femMeshTetra')"
                    value="tetrahedral"
                  />
                  <el-option
                    :label="t('simulationPage.femMeshHex')"
                    value="hexahedral"
                  />
                  <el-option
                    :label="t('simulationPage.femMeshHybrid')"
                    value="hybrid"
                  />
                </el-select>
              </el-form-item>
              <el-form-item :label="t('simulationPage.femElementSize')">
                <el-slider
                  v-model="femParams.elementSize"
                  :min="0.1"
                  :max="10"
                  :step="0.1"
                  :show-tooltip="true"
                />
                <div class="slider-labels">
                  <span>0.1 mm</span>
                  <span>10 mm</span>
                </div>
              </el-form-item>
              <el-form-item :label="t('simulationPage.femMeshCount')">
                <el-input
                  v-model="estimatedMeshCount"
                  readonly
                  size="small"
                  style="width: 100%"
                />
              </el-form-item>
              <el-form-item :label="t('simulationPage.femAdaptive')">
                <el-switch v-model="femParams.adaptiveRefinement" />
              </el-form-item>
            </el-form>
          </div>
        </div>
        <div class="fem-actions">
          <el-button
            type="primary"
            size="small"
            @click="handleStartSolve"
          >
            {{ t('simulationPage.femStartSolve') }}
          </el-button>
          <el-button
            size="small"
            @click="resetFemParams"
          >
            {{ t('simulationPage.femResetParams') }}
          </el-button>
        </div>
      </div>
      <div class="results-section">
        <div class="result-viewport-wrap">
          <div class="result-viewport">
            <div class="result-placeholder">
              <span>{{ t('simulationPage.femResultPlaceholder') }}</span>
            </div>
            <div class="color-legend">
              <div class="legend-bar" />
              <div class="legend-labels">
                <span>Max</span>
                <span>Min</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

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
