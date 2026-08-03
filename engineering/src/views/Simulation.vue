<template>
  <div class="simulation-page">
    <!-- 页面头部 -->
    <div class="page-header">
      <div class="page-header__title">
        <h1 class="page-title">
          {{ t('simulationPage.pageTitle') }}
        </h1>
        <p class="page-subtitle">
          {{ t('simulationPage.pageSubtitle') }}
        </p>
      </div>
      <div class="page-header__actions">
        <el-button
          size="small"
          :icon="Refresh"
          :loading="historyLoading"
          @click="fetchHistory"
        >
          {{ t('simulationPage.refreshHistory') }}
        </el-button>
        <el-button
          type="primary"
          size="small"
          :icon="Plus"
          @click="handleNewSimulation"
        >
          {{ t('simulationPage.newSimulation') }}
        </el-button>
      </div>
    </div>

    <!-- 统计概览 -->
    <div class="stats-row">
      <div
        class="stat-card"
        :class="'stat-card--info'"
      >
        <div class="stat-card__icon">
          <el-icon :size="24">
            <Monitor />
          </el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__value">{{ historyItems.length }}</span>
          <span class="stat-card__label">{{ t('simulationPage.statTotalSim') }}</span>
        </div>
      </div>
      <div
        class="stat-card"
        :class="'stat-card--success'"
      >
        <div class="stat-card__icon">
          <el-icon :size="24">
            <CircleCheck />
          </el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__value">{{ passCount }}</span>
          <span class="stat-card__label">{{ t('simulationPage.statPassCount') }}</span>
        </div>
      </div>
      <div
        class="stat-card"
        :class="'stat-card--danger'"
      >
        <div class="stat-card__icon">
          <el-icon :size="24">
            <Warning />
          </el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__value">{{ failCount }}</span>
          <span class="stat-card__label">{{ t('simulationPage.statCollisionCount') }}</span>
        </div>
      </div>
      <div
        class="stat-card"
        :class="'stat-card--accent'"
      >
        <div class="stat-card__icon">
          <el-icon :size="24">
            <Timer />
          </el-icon>
        </div>
        <div class="stat-card__content">
          <span class="stat-card__value">{{ avgDuration }}</span>
          <span class="stat-card__label">{{ t('simulationPage.statAvgDuration') }}</span>
        </div>
      </div>
    </div>

    <!-- Tab 切换 -->
    <div
      class="content-card"
      style="margin-bottom: 16px"
    >
      <div
        class="content-card__body"
        style="padding: 4px"
      >
        <div class="sim-tabs">
          <div
            v-for="tab in tabs"
            :key="tab.key"
            :class="['sim-tab-item', { active: activeTab === tab.key }]"
            @click="activeTab = tab.key"
          >
            <el-icon
              :size="16"
              style="margin-right: 6px"
            >
              <component :is="tab.icon" />
            </el-icon>
            {{ tab.label }}
          </div>
        </div>
      </div>
    </div>

    <!-- Tab 1: NC Code Simulation -->
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

    <!-- Tab 2: FEM Analysis -->
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
          <div class="result-viewport" v-loading="femSolving">
            <template v-if="femResult">
              <div class="fem-result-summary">
                <div class="fem-result-row">
                  <span class="fem-result-label">{{ t('simulationPage.femResultMaxStress') }}</span>
                  <span class="fem-result-value">{{ femResult.max_stress }} MPa</span>
                </div>
                <div class="fem-result-row">
                  <span class="fem-result-label">{{ t('simulationPage.femResultDeflection') }}</span>
                  <span class="fem-result-value">{{ femResult.max_deflection }} mm</span>
                </div>
                <div class="fem-result-row">
                  <span class="fem-result-label">{{ t('simulationPage.femResultSafety') }}</span>
                  <el-tag
                    :type="femResult.safety_factor >= 1.5 ? 'success' : femResult.safety_factor >= 1 ? 'warning' : 'danger'"
                    size="small"
                    effect="light"
                  >
                    {{ femResult.safety_factor }}
                  </el-tag>
                </div>
                <div class="fem-result-row">
                  <span class="fem-result-label">{{ t('simulationPage.femResultNodes') }}</span>
                  <span class="fem-result-value">{{ femResult.nodes }}</span>
                </div>
                <p v-if="femResult.warning" class="fem-result-warning">
                  {{ femResult.warning }}
                </p>
              </div>
            </template>
            <div v-else class="result-placeholder">
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

    <!-- Tab 3: Export Management -->
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
              :loading="exportLoading === 'gif'"
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
              :loading="exportLoading === 'mp4'"
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
  </div>
</template>

<script setup lang="ts">
// TODO(P1-3): 巨型组件拆分 — 本文件 1884+ 行，应拆分为子组件/composable：
//   - 仿真控制面板 → SimulationControls.vue
//   - 3D 视口 → SimulationViewport.vue
//   - 碰撞检测逻辑 → useCollisionDetection.ts
//   - 播放/时间轴控制 → useSimulationPlayback.ts
// 拆分时注意保持 props/emits 接口不变，逐模块迁移并验证。
import { ref, computed, onMounted, onUnmounted } from 'vue'
import {
  VideoPlay, Plus, Upload, Delete, Download,
  WarningFilled, Loading, Refresh, Monitor, CircleCheck, Warning, Timer,
} from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import type { UploadFile } from 'element-plus'
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'
import { useProjectStore } from '@/stores/project'
import SimulationViewer from '@/components/simulation/SimulationViewer.vue'
import CollisionAlertModal from '@/components/simulation/CollisionAlertModal.vue'
import { useI18n } from 'vue-i18n'

const projectStore = useProjectStore()
const { t } = useI18n()

// ─── Types ──────────────────────────────────────────────

interface CollisionInfo {
  position: [number, number, number]
  severity: 'warning' | 'critical'
  toolSegment: number
  description: string
}

interface SimResultData {
  task_id: string
  collision_detected: boolean
  collision_details: {
    timestamp: string
    positions: number[][]
    segment_indices: number[]
    severity: string
    count: number
  } | null
  duration_seconds: number
  voxel_count: number
  removed_voxel_count: number
  voxel_size: number
  toolpath_segment_count: number
  simulation_result: {
    workpiece_stl_path: string
    voxel_count: number
    removed_voxel_count: number
    voxel_size: number
    original_bbox: Record<string, number> | null
  } | null
}

interface HistoryItem {
  task_id: string
  project_id: string
  duration_seconds: number
  collision_collided: boolean
  voxel_size: number
  segment_count: number
}

// ─── Tabs ──────────────────────────────────────────────

interface Tab {
  key: string
  label: string
  icon: ReturnType<typeof Object>
}
const tabs: Tab[] = [
  { key: 'simulation', label: t('simulationPage.tabSimulation'), icon: VideoPlay },
  { key: 'fem', label: t('simulationPage.tabFem'), icon: Monitor },
  { key: 'export', label: t('simulationPage.tabExport'), icon: Download },
]
const activeTab = ref<string>('simulation')

// ─── Stats from History ──────────────────────────────────

const passCount = computed(() => historyItems.value.filter((h) => !h.collision_collided).length)
const failCount = computed(() => historyItems.value.filter((h) => h.collision_collided).length)
const avgDuration = computed(() => {
  const items = historyItems.value
  if (items.length === 0) return '--'
  const total = items.reduce((sum, h) => sum + (h.duration_seconds ?? 0), 0)
  return (total / items.length).toFixed(1) + 's'
})

// ─── NC Code ────────────────────────────────────────────

const gcode = ref('')
const viewerRef = ref<InstanceType<typeof SimulationViewer> | null>(null)

const gcodeStats = computed(() => {
  const text = gcode.value
  const lines = text ? text.split('\n').filter((l) => l.trim() && !l.trim().startsWith('(') && !l.trim().startsWith('//')).length : 0
  const gCommands = (text.match(/[Gg]\d+/g) || []).length
  const mCommands = (text.match(/[Mm]\d+/g) || []).length
  return { lines, gCommands, mCommands }
})

function handleFileUpload(file: UploadFile) {
  const reader = new FileReader()
  reader.onload = (e) => {
    const content = e.target?.result as string
    if (content) {
      gcode.value = content
      ElMessage.success(t('simulationPage.msgFileLoaded', { name: file.name, lines: gcodeStats.value.lines }))
    }
  }
  reader.onerror = () => {
    ElMessage.error(t('simulationPage.msgFileReadFailed'))
  }
  if (file.raw) {
    reader.readAsText(file.raw)
  }
}

function handleNewSimulation() {
  gcode.value = ''
  simResult.value = null
  simState.value = 'idle'
  currentTaskId.value = ''
  showCollisionDetail.value = false
  activeTab.value = 'simulation'
}

// ─── Simulation Parameters ──────────────────────────────

const simParams = ref({
  voxelSize: 1.0,
  toolType: 'flat',
  toolDiameter: 10.0,
  toolLength: 50.0,
  toolCornerRadius: 0.0,
  safeZ: 30.0,
  stockStlPath: '',
})

// ─── Simulation State ────────────────────────────────────

type SimState = 'idle' | 'running' | 'completed' | 'failed'
const simState = ref<SimState>('idle')
const currentTaskId = ref('')
const simResult = ref<SimResultData | null>(null)
const showCollisionDetail = ref(false)

const runButtonText = computed(() => {
  switch (simState.value) {
    case 'running': return t('simulationPage.simRunning')
    case 'completed': return t('simulationPage.rerunSim')
    default: return t('simulationPage.runSim')
  }
})

// 已忽略（dismiss）的碰撞索引集合
const dismissedCollisions = ref<Set<number>>(new Set())

const collisionList = computed<CollisionInfo[]>(() => {
  if (!simResult.value?.collision_detected || !simResult.value.collision_details) return []
  const details = simResult.value.collision_details
  return details.positions
    .map((pos, idx) => ({
      position: pos as [number, number, number],
      severity: (details.severity === 'critical' ? 'critical' : 'warning') as CollisionInfo['severity'],
      toolSegment: details.segment_indices[idx] ?? idx,
      description: t('simulationPage.msgCollisionDesc', { idx: idx + 1, severity: details.severity }),
    }))
    .filter((_, idx) => !dismissedCollisions.value.has(idx))
})

let pollTimer: ReturnType<typeof setInterval> | null = null

function onViewerReady() {
  // Viewer is initialized
}

async function handleRunSimulation() {
  if (!gcode.value.trim()) {
    ElMessage.warning(t('simulationPage.msgNoGcode'))
    return
  }

  simState.value = 'running'
  simResult.value = null
  showCollisionDetail.value = false

  try {
    // Submit async simulation
    const res = await http.post(buildApiPath(API_CONFIG.SIMULATION, '/run/async'), {
      project_id: projectStore.projectId || 'default',
      voxel_size: simParams.value.voxelSize,
      tool_diameter: simParams.value.toolDiameter,
      tool_length: simParams.value.toolLength,
      tool_type: simParams.value.toolType,
      tool_corner_radius: simParams.value.toolCornerRadius,
      gcode: gcode.value,
      safe_z_height: simParams.value.safeZ,
      stock_stl_path: simParams.value.stockStlPath || undefined,
    })

    const responseData = res.data?.data ?? res.data
    const taskId = responseData?.task_id
    if (!taskId) {
      throw new Error(t('simulationPage.msgNoTaskId'))
    }

    currentTaskId.value = taskId
    ElMessage.info(t('simulationPage.msgTaskSubmitted', { taskId }))

    // Start polling
    startPolling(taskId)
  } catch (err: unknown) {
    simState.value = 'failed'
    const msg = err instanceof Error ? err.message : t('simulationPage.msgSubmitFailed')
    ElMessage.error(msg)
  }
}

function startPolling(taskId: string) {
  stopPolling()
  pollTimer = setInterval(async () => {
    try {
      const res = await http.get(buildApiPath(API_CONFIG.SIMULATION, `/status/${taskId}`))
      const responseData = res.data?.data ?? res.data
      const status = responseData?.status

      if (status === 'completed') {
        stopPolling()
        simState.value = 'completed'
        simResult.value = responseData?.result ?? null

        if (simResult.value?.collision_detected) {
          ElMessage.warning(t('simulationPage.msgCollisionDetected'))
        } else {
          ElMessage.success(t('simulationPage.msgSimPassed'))
        }

        // Try to load STL into the 3D viewer
        if (simResult.value?.simulation_result?.workpiece_stl_path && viewerRef.value) {
          viewerRef.value.loadVoxelData(simResult.value.simulation_result)
        }

        // Refresh history
        fetchHistory()
      } else if (status === 'not_found') {
        stopPolling()
        simState.value = 'failed'
        ElMessage.error(t('simulationPage.msgTaskNotFound'))
      }
      // status === 'running' or 'pending' → continue polling
    } catch {
      // Network error, continue polling
    }
  }, 2000)
}

function stopPolling() {
  if (pollTimer) {
    clearInterval(pollTimer)
    pollTimer = null
  }
}

// ─── Collision Actions ──────────────────────────────────

function handleLocateCollision(index: number) {
  const collision = collisionList.value[index]
  if (collision && viewerRef.value) {
    // Future: highlight collision point in 3D viewer
    ElMessage.info(t('simulationPage.msgLocateCollision', { index: index + 1, pos: collision.position.map((v) => v.toFixed(2)).join(', ') }))
  }
}

function handleDismissCollision(index?: number) {
  // 从碰撞列表中移除指定索引（真实状态变更）
  if (index === undefined) return
  dismissedCollisions.value = new Set(dismissedCollisions.value).add(index)
  if (collisionList.value.length === 0) {
    ElMessage.success(t('simulationPage.msgAllCollisionsDismissed'))
  }
}

function handleDismissAllCollisions() {
  // 忽略全部碰撞
  const details = simResult.value?.collision_details
  if (details) {
    details.positions.forEach((_, idx) => {
      dismissedCollisions.value = new Set(dismissedCollisions.value).add(idx)
    })
  }
  ElMessage.success(t('simulationPage.msgAllCollisionsDismissed'))
}

// ─── Download STL ─────────────────────────────────────

function handleDownloadStl() {
  const stlPath = simResult.value?.simulation_result?.workpiece_stl_path
  if (!stlPath) {
    ElMessage.warning(t('simulationPage.msgNoStl'))
    return
  }
  // Extract filename from path
  const filename = stlPath.split('/').pop() || stlPath.split('\\').pop() || 'result.stl'
  const url = `/simulation/output/${filename}`
  // Create download link
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
}

// ─── History ────────────────────────────────────────────

const historyItems = ref<HistoryItem[]>([])
const historyLoading = ref(false)

async function fetchHistory() {
  historyLoading.value = true
  try {
    const res = await http.get(buildApiPath(API_CONFIG.SIMULATION, '/history'), {
      params: { limit: 20 },
    })
    const data = res.data?.data ?? res.data
    historyItems.value = data?.items ?? []
  } catch {
    historyItems.value = []
  } finally {
    historyLoading.value = false
  }
}

// ─── Tab 2: FEM ─────────────────────────────────────────

const femParams = ref({
  material: 'steel45',
  elasticModulus: 210.0,
  poissonRatio: 0.300,
  density: 7850.0,
  yieldStrength: 355.0,
  thermalConductivity: 50.0,
  meshType: 'tetrahedral',
  elementSize: 2.0,
  adaptiveRefinement: true,
})

const estimatedMeshCount = computed(() => {
  const base = 50000
  const factor = (10 - femParams.value.elementSize) ** 2
  return t('simulationPage.meshCountUnit', { count: Math.round(base * factor * 0.8).toLocaleString() })
})

function resetFemParams() {
  femParams.value = {
    material: 'steel45',
    elasticModulus: 210.0,
    poissonRatio: 0.300,
    density: 7850.0,
    yieldStrength: 355.0,
    thermalConductivity: 50.0,
    meshType: 'tetrahedral',
    elementSize: 2.0,
    adaptiveRefinement: true,
  }
}

// FEM 求解结果（真实接口返回）
interface FEMResult {
  material: string
  max_stress: number
  max_deflection: number
  yield_strength: number
  safety_factor: number
  nodes: number
  status: string
  warning?: string
  stress_distribution?: Array<{ x: number; stress: number }>
}

const femResult = ref<FEMResult | null>(null)
const femSolving = ref(false)

async function handleStartSolve() {
  femSolving.value = true
  femResult.value = null
  try {
    const res = await http.post(buildApiPath(API_CONFIG.SIMULATION, '/fem/solve'), {
      material: femParams.value.material,
      elastic_modulus: femParams.value.elasticModulus,
      poisson_ratio: femParams.value.poissonRatio,
      density: femParams.value.density,
      yield_strength: femParams.value.yieldStrength,
      mesh_type: femParams.value.meshType,
      element_size: femParams.value.elementSize,
      adaptive_refinement: femParams.value.adaptiveRefinement,
      beam_length: 100.0,
      beam_width: 20.0,
      beam_height: 20.0,
      load_force: 5000.0,
    })
    if (res.data.code === 0 && res.data.data) {
      femResult.value = res.data.data
      ElMessage.success(t('simulationPage.msgFemDone'))
    } else {
      ElMessage.error(res.data.message || t('simulationPage.msgFemFailed'))
    }
  } catch (e: unknown) {
    console.warn('[Simulation] FEM solve failed:', e)
    ElMessage.error(t('simulationPage.msgFemFailed'))
  } finally {
    femSolving.value = false
  }
}

// ─── Tab 3: Export ──────────────────────────────────────

const gifExport = ref({
  resolution: '1280x720',
  framerate: 15,
  quality: 'medium',
})

const mp4Export = ref({
  resolution: '1920x1080',
  framerate: 30,
  codec: 'h264',
  bitrate: '10',
})

const exportLoading = ref<'gif' | 'mp4' | null>(null)

/** 导出仿真动画（真实调用 POST /api/simulation/export-animation，blob 下载）。 */
async function exportAnimation(format: 'gif' | 'mp4') {
  if (!gcode.value.trim()) {
    ElMessage.warning(t('simulationPage.msgNoGcode'))
    return
  }
  exportLoading.value = format
  try {
    const res = await http.post(
      buildApiPath(API_CONFIG.SIMULATION, '/export-animation'),
      {
        nc_code: gcode.value,
        format,
        voxel_size: simParams.value.voxelSize,
        tool_diameter: simParams.value.toolDiameter,
        tool_length: simParams.value.toolLength,
        tool_type: simParams.value.toolType,
      },
      { responseType: 'blob' },
    )
    // 后端返回文件流，触发浏览器下载
    const blob = res.data as Blob
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    const ts = new Date().toISOString().replace(/[:.]/g, '-')
    a.href = url
    a.download = `simulation_${format}_${ts}.${format}`
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
    ElMessage.success(t('simulationPage.msgExportSuccess', { format: format.toUpperCase() }))
  } catch (e: unknown) {
    console.warn('[Simulation] export animation failed:', e)
    ElMessage.error(t('simulationPage.msgExportFailed'))
  } finally {
    exportLoading.value = null
  }
}

function handleExportGif() {
  void exportAnimation('gif')
}

function handleExportMp4() {
  void exportAnimation('mp4')
}

// ─── Utilities ──────────────────────────────────────────

function formatNumber(n: number): string {
  if (n >= 1000000) return (n / 1000000).toFixed(1) + 'M'
  if (n >= 1000) return (n / 1000).toFixed(1) + 'K'
  return String(n)
}

// ─── Lifecycle ──────────────────────────────────────────

onMounted(() => {
  fetchHistory()
})

// Stop polling when component is destroyed
onUnmounted(() => {
  stopPolling()
})
</script>

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
.fem-result-summary {
  width: 100%;
  padding: 20px;
  text-align: left;
}

.fem-result-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-bottom: 1px solid var(--border-color, rgba(0, 0, 0, 0.06));
}

.fem-result-label {
  color: var(--text-secondary);
  font-size: 13px;
}

.fem-result-value {
  font-weight: 600;
  font-size: 14px;
}

.fem-result-warning {
  margin-top: 12px;
  font-size: 12px;
  color: var(--warning);
  line-height: 1.5;
}
</style>
