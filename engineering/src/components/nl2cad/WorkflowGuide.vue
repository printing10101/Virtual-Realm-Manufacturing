<template>
  <div class="workflow-guide">
    <WorkflowGuideStepsIndicator
      :steps="steps"
      :current-step="currentStep"
      @step-click="handleStepClick"
    />

    <!-- 步骤内容区域 -->
    <div class="step-content">
      <!-- 步骤1：自然语言描述 -->
      <div
        v-if="currentStep === 0"
        class="content-panel"
      >
        <div class="panel-header">
          <h3>{{ t('workflowGuide.step1Header') }}</h3>
          <p class="hint">
            {{ t('workflowGuide.step1Hint') }}
          </p>
        </div>
        <div class="panel-body">
          <div class="example-cards">
            <div
              v-for="example in examples"
              :key="example.text"
              class="example-card"
              @click="fillExample(example.text)"
            >
              <div class="example-icon">
                <el-icon><Document /></el-icon>
              </div>
              <div class="example-text">
                {{ example.text }}
              </div>
            </div>
          </div>
          <div class="input-section">
            <el-input
              v-model="nlDescription"
              type="textarea"
              :rows="4"
              :placeholder="t('workflowGuide.step1Placeholder')"
              class="nl-input"
            />
            <div class="input-actions">
              <el-button
                type="primary"
                :disabled="!nlDescription.trim()"
                @click="handleNextStep"
              >
                <el-icon><ArrowRight /></el-icon>
                {{ t('workflowGuide.btnNext') }}
              </el-button>
            </div>
          </div>
        </div>
      </div>

      <!-- 步骤2：参数确认 -->
      <div
        v-if="currentStep === 1"
        class="content-panel"
      >
        <div class="panel-header">
          <h3>{{ t('workflowGuide.step2Header') }}</h3>
          <p class="hint">
            {{ t('workflowGuide.step2Hint') }}
          </p>
        </div>
        <div class="panel-body">
          <div class="params-preview">
            <el-form
              :model="extractedParams"
              label-width="120px"
              class="params-form"
            >
              <el-form-item :label="t('workflowGuide.paramShapeType')">
                <el-select
                  v-model="extractedParams.shape_type"
                  :placeholder="t('workflowGuide.paramShapePlaceholder')"
                >
                  <el-option
                    :label="t('workflowGuide.shapeBox')"
                    value="box"
                  />
                  <el-option
                    :label="t('workflowGuide.shapeCylinder')"
                    value="cylinder"
                  />
                  <el-option
                    :label="t('workflowGuide.shapeSphere')"
                    value="sphere"
                  />
                  <el-option
                    :label="t('workflowGuide.shapeCone')"
                    value="cone"
                  />
                </el-select>
              </el-form-item>
              
              <template v-if="extractedParams.dimensions">
                <el-form-item
                  v-if="extractedParams.dimensions.length"
                  :label="t('workflowGuide.paramLength')"
                >
                  <el-input-number
                    v-model="extractedParams.dimensions.length"
                    :min="0.1"
                    :step="1"
                    controls-position="right"
                  />
                  <span class="unit">mm</span>
                </el-form-item>
                
                <el-form-item
                  v-if="extractedParams.dimensions.width"
                  :label="t('workflowGuide.paramWidth')"
                >
                  <el-input-number
                    v-model="extractedParams.dimensions.width"
                    :min="0.1"
                    :step="1"
                    controls-position="right"
                  />
                  <span class="unit">mm</span>
                </el-form-item>
                
                <el-form-item
                  v-if="extractedParams.dimensions.height"
                  :label="t('workflowGuide.paramHeight')"
                >
                  <el-input-number
                    v-model="extractedParams.dimensions.height"
                    :min="0.1"
                    :step="1"
                    controls-position="right"
                  />
                  <span class="unit">mm</span>
                </el-form-item>
                
                <el-form-item
                  v-if="extractedParams.dimensions.radius"
                  :label="t('workflowGuide.paramRadius')"
                >
                  <el-input-number
                    v-model="extractedParams.dimensions.radius"
                    :min="0.1"
                    :step="1"
                    controls-position="right"
                  />
                  <span class="unit">mm</span>
                </el-form-item>
              </template>

              <el-form-item
                v-if="extractedParams.material"
                :label="t('workflowGuide.paramMaterial')"
              >
                <el-input
                  v-model="extractedParams.material"
                  :placeholder="t('workflowGuide.paramMaterialInputPlaceholder')"
                />
              </el-form-item>

              <el-form-item :label="t('workflowGuide.paramConfidence')">
                <el-progress
                  :percentage="Math.round((extractedParams.confidence || 0.8) * 100)"
                  :color="getConfidenceColor(extractedParams.confidence)"
                />
              </el-form-item>
            </el-form>
          </div>
          <div class="panel-actions">
            <el-button @click="currentStep--">
              <el-icon><ArrowLeft /></el-icon>
              {{ t('workflowGuide.btnPrev') }}
            </el-button>
            <el-button
              type="primary"
              @click="handleGenerateModel"
            >
              <el-icon><Box /></el-icon>
              {{ t('workflowGuide.btnGenerateModel') }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤3：模型预览 -->
      <div
        v-if="currentStep === 2"
        class="content-panel"
      >
        <div class="panel-header">
          <h3>{{ t('workflowGuide.step3Header') }}</h3>
          <p class="hint">
            {{ t('workflowGuide.step3Hint') }}
          </p>
        </div>
        <div class="panel-body">
          <div class="model-preview">
            <div
              v-if="!modelGenerated"
              class="preview-placeholder"
            >
              <el-icon
                :size="64"
                class="loading-icon"
              >
                <Loading />
              </el-icon>
              <p>{{ t('workflowGuide.step3Loading') }}</p>
            </div>
            <div
              v-else
              class="preview-container"
            >
              <div class="preview-viewport">
                <slot name="3d-viewer" />
              </div>
              <div class="preview-info">
                <div class="info-item">
                  <span class="label">{{ t('workflowGuide.infoShape') }}</span>
                  <span class="value">{{ getShapeLabel(extractedParams.shape_type) }}</span>
                </div>
                <div class="info-item">
                  <span class="label">{{ t('workflowGuide.infoDimensions') }}</span>
                  <span class="value">{{ formatDimensions(extractedParams.dimensions) }}</span>
                </div>
                <div
                  v-if="extractedParams.material"
                  class="info-item"
                >
                  <span class="label">{{ t('workflowGuide.infoMaterial') }}</span>
                  <span class="value">{{ extractedParams.material }}</span>
                </div>
              </div>
            </div>
          </div>
          <div class="panel-actions">
            <el-button @click="currentStep--">
              <el-icon><ArrowLeft /></el-icon>
              {{ t('workflowGuide.btnModifyParams') }}
            </el-button>
            <el-button
              type="primary"
              :disabled="!modelGenerated"
              @click="handleNextStep"
            >
              <el-icon><ArrowRight /></el-icon>
              {{ t('workflowGuide.btnProcessPlanning') }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤4：工艺规划 -->
      <div
        v-if="currentStep === 3"
        class="content-panel"
      >
        <div class="panel-header">
          <h3>{{ t('workflowGuide.step4Header') }}</h3>
          <p class="hint">
            {{ t('workflowGuide.step4Hint') }}
          </p>
        </div>
        <div class="panel-body">
          <el-form
            :model="processConfig"
            label-width="120px"
            class="process-form"
          >
            <el-form-item :label="t('workflowGuide.paramMaterialType')">
              <el-select
                v-model="processConfig.material"
                :placeholder="t('workflowGuide.paramMaterialSelectPlaceholder')"
              >
                <el-option
                  :label="t('workflowGuide.materialAluminum6061')"
                  value="aluminum_6061"
                />
                <el-option
                  :label="t('workflowGuide.materialSteel45')"
                  value="steel_45"
                />
                <el-option
                  :label="t('workflowGuide.materialStainless304')"
                  value="stainless_304"
                />
                <el-option
                  :label="t('workflowGuide.materialCopper')"
                  value="copper"
                />
                <el-option
                  :label="t('workflowGuide.materialBrass')"
                  value="brass"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('workflowGuide.paramMachineType')">
              <el-select
                v-model="processConfig.machine_type"
                :placeholder="t('workflowGuide.paramMachineSelectPlaceholder')"
              >
                <el-option
                  :label="t('workflowGuide.machineCncMill')"
                  value="cnc_mill"
                />
                <el-option
                  :label="t('workflowGuide.machineCncLathe')"
                  value="cnc_lathe"
                />
                <el-option
                  :label="t('workflowGuide.machineMachiningCenter')"
                  value="machining_center"
                />
              </el-select>
            </el-form-item>
            <el-form-item :label="t('workflowGuide.paramPrecision')">
              <el-select
                v-model="processConfig.precision"
                :placeholder="t('workflowGuide.paramPrecisionSelectPlaceholder')"
              >
                <el-option
                  :label="t('workflowGuide.precisionRough')"
                  value="rough"
                />
                <el-option
                  :label="t('workflowGuide.precisionSemiFinish')"
                  value="semi-finish"
                />
                <el-option
                  :label="t('workflowGuide.precisionFinish')"
                  value="finish"
                />
                <el-option
                  :label="t('workflowGuide.precisionSuperFinish')"
                  value="super-finish"
                />
              </el-select>
            </el-form-item>
          </el-form>
          <div class="panel-actions">
            <el-button @click="currentStep--">
              <el-icon><ArrowLeft /></el-icon>
              {{ t('workflowGuide.btnPrev') }}
            </el-button>
            <el-button
              type="primary"
              @click="handleGenerateProcess"
            >
              <el-icon><SetUp /></el-icon>
              {{ t('workflowGuide.btnGenerateProcess') }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤5：NC代码 -->
      <div
        v-if="currentStep === 4"
        class="content-panel"
      >
        <div class="panel-header">
          <h3>{{ t('workflowGuide.step5Header') }}</h3>
          <p class="hint">
            {{ t('workflowGuide.step5Hint') }}
          </p>
        </div>
        <div class="panel-body">
          <div class="nc-code-container">
            <div
              v-if="!ncCodeGenerated"
              class="code-placeholder"
            >
              <el-icon
                :size="48"
                class="loading-icon"
              >
                <Loading />
              </el-icon>
              <p>{{ t('workflowGuide.step5Loading') }}</p>
            </div>
            <div
              v-else
              class="code-viewer"
            >
              <div class="code-header">
                <span class="code-title">{{ t('workflowGuide.codeTitle') }}</span>
                <div class="code-actions">
                  <el-button
                    size="small"
                    @click="handleCopyCode"
                  >
                    <el-icon><DocumentCopy /></el-icon>
                    {{ t('workflowGuide.btnCopy') }}
                  </el-button>
                  <el-button
                    size="small"
                    @click="handleDownloadCode"
                  >
                    <el-icon><Download /></el-icon>
                    {{ t('workflowGuide.btnDownload') }}
                  </el-button>
                </div>
              </div>
              <pre class="code-content"><code>{{ ncCode }}</code></pre>
            </div>
          </div>
          <div class="panel-actions">
            <el-button @click="currentStep--">
              <el-icon><ArrowLeft /></el-icon>
              {{ t('workflowGuide.btnModifyProcess') }}
            </el-button>
            <el-button
              type="primary"
              :disabled="!ncCodeGenerated"
              @click="handleNextStep"
            >
              <el-icon><VideoPlay /></el-icon>
              {{ t('workflowGuide.btnSimulate') }}
            </el-button>
          </div>
        </div>
      </div>

      <!-- 步骤6：仿真验证 -->
      <div
        v-if="currentStep === 5"
        class="content-panel"
      >
        <div class="panel-header">
          <h3>{{ t('workflowGuide.step6Header') }}</h3>
          <p class="hint">
            {{ t('workflowGuide.step6Hint') }}
          </p>
        </div>
        <div class="panel-body">
          <div class="simulation-container">
            <div class="simulation-viewport">
              <slot name="simulation-viewer" />
            </div>
            <div class="simulation-controls">
              <el-button-group>
                <el-button
                  type="primary"
                  @click="handleStartSimulation"
                >
                  <el-icon><VideoPlay /></el-icon>
                  {{ t('workflowGuide.btnStartSim') }}
                </el-button>
                <el-button @click="handlePauseSimulation">
                  <el-icon><VideoPause /></el-icon>
                  {{ t('workflowGuide.btnPause') }}
                </el-button>
                <el-button @click="handleResetSimulation">
                  <el-icon><RefreshRight /></el-icon>
                  {{ t('workflowGuide.btnReset') }}
                </el-button>
              </el-button-group>
              <el-button
                type="success"
                @click="handleDownloadAnimation"
              >
                <el-icon><Download /></el-icon>
                {{ t('workflowGuide.btnDownloadAnimation') }}
              </el-button>
            </div>
          </div>
          <div class="panel-actions">
            <el-button @click="currentStep--">
              <el-icon><ArrowLeft /></el-icon>
              {{ t('workflowGuide.btnModifyCode') }}
            </el-button>
            <el-button
              type="primary"
              @click="handleComplete"
            >
              <el-icon><CircleCheck /></el-icon>
              {{ t('workflowGuide.btnComplete') }}
            </el-button>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { useI18n } from 'vue-i18n'
import { ElMessage } from 'element-plus'
import {
  ArrowRight,
  ArrowLeft,
  Document,
  Box,
  Loading,
  SetUp,
  DocumentCopy,
  Download,
  VideoPlay,
  VideoPause,
  RefreshRight,
  CircleCheck,
} from '@element-plus/icons-vue'
import WorkflowGuideStepsIndicator from './WorkflowGuideStepsIndicator.vue'
import {
  extractParams as apiExtractParams,
  generateModel as apiGenerateModel,
  generateProcessPlanning as apiGenerateProcessPlanning,
  generateNC as apiGenerateNC,
  exportSimulationAnimation as apiExportAnimation,
} from '@/api/nl2cad'
import type {
  CADParams,
  ProcessConfig,
  ProcessPlan,
  CADDimensions,
} from '@/types/nl2cad'

// Props & Emits
const props = defineProps<{
  initialDescription?: string
}>()

const emit = defineEmits<{
  (e: 'step-change', step: number): void
  (e: 'params-extracted', params: CADParams): void
  (e: 'generate-model', params: CADParams): void
  (e: 'generate-process', payload: ProcessConfig & { process_plan?: ProcessPlan }): void
  (e: 'generate-nc', payload: { nc_code: string; process_plan?: ProcessPlan }): void
  (e: 'start-simulation'): void
  (e: 'complete'): void
}>()

const { t } = useI18n()

// Steps definition
const steps = computed(() => [
  { id: 'select-model', title: t('workflowGuide.step1Title'), description: t('workflowGuide.step1Desc'), clickable: true },
  { id: 'config-params', title: t('workflowGuide.step2Title'), description: t('workflowGuide.step2Desc'), clickable: true },
  { id: 'generate-cad', title: t('workflowGuide.step3Title'), description: t('workflowGuide.step3Desc'), clickable: false },
  { id: 'output-nc', title: t('workflowGuide.step4Title'), description: t('workflowGuide.step4Desc'), clickable: true },
  { id: 'validate', title: t('workflowGuide.step5Title'), description: t('workflowGuide.step5Desc'), clickable: false },
  { id: 'review', title: t('workflowGuide.step6Title'), description: t('workflowGuide.step6Desc'), clickable: false },
])

// Examples
const examples = computed(() => [
  { text: t('workflowGuide.example1') },
  { text: t('workflowGuide.example2') },
  { text: t('workflowGuide.example3') },
  { text: t('workflowGuide.example4') },
])

// Reactive state
const currentStep = ref(0)
const nlDescription = ref(props.initialDescription || '')
const extractedParams = reactive<CADParams>({
  shape_type: 'box',
  dimensions: { length: 50, width: 30, height: 20 },
  material: 'steel',
  confidence: 0.85,
})
const modelGenerated = ref(false)
const processConfig = reactive({
  material: 'aluminum_6061',
  machine_type: 'cnc_mill',
  precision: 'finish',
})
const ncCodeGenerated = ref(false)
const ncCode = ref('')

// Methods
function handleStepClick(index: number) {
  if (steps.value[index].clickable && index <= currentStep.value) {
    currentStep.value = index
    emit('step-change', index)
  }
}

function fillExample(text: string) {
  nlDescription.value = text
}

function handleNextStep() {
  if (currentStep.value === 0) {
    // 从NL描述提取参数
    extractParamsFromNL()
  } else if (currentStep.value === 2) {
    currentStep.value = 3
    emit('step-change', 3)
  } else if (currentStep.value === 4) {
    currentStep.value = 5
    emit('step-change', 5)
  } else {
    currentStep.value++
    emit('step-change', currentStep.value)
  }
}

async function extractParamsFromNL() {
  try {
    const data = await apiExtractParams({ description: nlDescription.value })
    Object.assign(extractedParams, data.params)

    currentStep.value = 1
    emit('step-change', 1)
    emit('params-extracted', extractedParams)
    ElMessage.success(t('workflowGuide.msgParamsExtracted'))
  } catch (error) {
    console.error('Extract params failed:', error)
    ElMessage.error(t('workflowGuide.msgParamsExtractFailed'))
  }
}

async function handleGenerateModel() {
  try {
    const data = await apiGenerateModel({
      description: nlDescription.value,
      output_format: 'stl',
    })
    emit('generate-model', { ...extractedParams, model_path: data.model_path })

    modelGenerated.value = true
    currentStep.value = 2
    emit('step-change', 2)
    ElMessage.success(t('workflowGuide.msgModelGenerated'))
  } catch (error) {
    console.error('Generate model failed:', error)
    ElMessage.error(t('workflowGuide.msgModelGenerateFailed'))
  }
}

async function handleGenerateProcess() {
  try {
    const data = await apiGenerateProcessPlanning({
      cad_params: extractedParams,
      material: processConfig.material,
      machine_type: processConfig.machine_type,
      precision: processConfig.precision,
    })
    emit('generate-process', { ...processConfig, process_plan: data.process_plan })

    currentStep.value = 4
    emit('step-change', 4)

    // 生成NC代码
    await generateNCCode(data.process_plan)
  } catch (error) {
    console.error('Generate process failed:', error)
    ElMessage.error(t('workflowGuide.msgProcessFailed'))
  }
}

async function generateNCCode(processPlan?: ProcessPlan) {
  try {
    const data = await apiGenerateNC({
      process_plan: processPlan || {},
      machine_type: processConfig.machine_type,
    })
    ncCode.value = data.nc_code
    ncCodeGenerated.value = true
    emit('generate-nc', { nc_code: data.nc_code, process_plan: processPlan })
    ElMessage.success(t('workflowGuide.msgNcGenerated'))
  } catch (error) {
    console.error('Generate NC code failed:', error)
    ElMessage.error(t('workflowGuide.msgNcGenerateFailed'))
  }
}

function handleCopyCode() {
  navigator.clipboard.writeText(ncCode.value)
  ElMessage.success(t('workflowGuide.msgCodeCopied'))
}

function handleDownloadCode() {
  const blob = new Blob([ncCode.value], { type: 'text/plain' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = 'part_program.gcode'
  a.click()
  URL.revokeObjectURL(url)
  ElMessage.success(t('workflowGuide.msgCodeDownloaded'))
}

function handleStartSimulation() {
  emit('start-simulation')
  ElMessage.info(t('workflowGuide.msgSimStarted'))
}

function handlePauseSimulation() {
  ElMessage.info(t('workflowGuide.msgSimPaused'))
}

function handleResetSimulation() {
  ElMessage.info(t('workflowGuide.msgSimReset'))
}

async function handleDownloadAnimation() {
  try {
    // 通过统一 http 客户端调用后端仿真动画导出接口（返回 Blob）
    const blob = await apiExportAnimation({
      nc_code: ncCode.value,
      format: 'gif',
    })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'simulation_animation.gif'
    a.click()
    URL.revokeObjectURL(url)

    ElMessage.success(t('workflowGuide.msgAnimationDownloaded'))
  } catch (error) {
    console.error('Download animation failed:', error)
    ElMessage.error(t('workflowGuide.msgAnimationDownloadFailed'))
  }
}

function handleComplete() {
  emit('complete')
  ElMessage.success(t('workflowGuide.msgWorkflowCompleted'))
}

// Helper functions
function getShapeLabel(shapeType: string): string {
  const labels: Record<string, string> = {
    box: t('workflowGuide.shapeBox'),
    cylinder: t('workflowGuide.shapeCylinder'),
    sphere: t('workflowGuide.shapeSphere'),
    cone: t('workflowGuide.shapeCone'),
  }
  return labels[shapeType] || shapeType
}

function formatDimensions(dimensions: CADDimensions | undefined): string {
  if (!dimensions) return '-'
  const parts = []
  if (dimensions.length) parts.push(`${t('workflowGuide.dimLength')}${dimensions.length}mm`)
  if (dimensions.width) parts.push(`${t('workflowGuide.dimWidth')}${dimensions.width}mm`)
  if (dimensions.height) parts.push(`${t('workflowGuide.dimHeight')}${dimensions.height}mm`)
  if (dimensions.radius) parts.push(`${t('workflowGuide.dimRadius')}${dimensions.radius}mm`)
  return parts.join(' × ') || '-'
}

function getConfidenceColor(confidence: number | undefined): string {
  const c = confidence ?? 0.8
  if (c >= 0.8) return 'var(--success)'
  if (c >= 0.6) return 'var(--warning)'
  return 'var(--error)'
}
</script>

<style scoped>
.workflow-guide {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--bg-primary);
}

/* Steps Indicator */
.steps-indicator {
  display: flex;
  align-items: center;
  padding: 24px 32px;
  background: var(--bg-card);
  border-bottom: 1px solid var(--border-light);
}

.step-item {
  display: flex;
  align-items: center;
  position: relative;
  flex: 1;
}

.step-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-tertiary);
  color: var(--text-secondary);
  font-weight: 600;
  font-size: 14px;
  transition: all var(--transition-normal);
  flex-shrink: 0;
}

.step-item.is-active .step-icon {
  background: var(--accent-primary);
  color: white;
  box-shadow: 0 4px 12px color-mix(in srgb, var(--brand-500) 30%, transparent);
}

.step-item.is-completed .step-icon {
  background: var(--success);
  color: white;
}

.step-item.is-clickable {
  cursor: pointer;
}

.step-item.is-clickable:hover .step-icon {
  transform: scale(1.05);
}

.step-info {
  margin-left: 12px;
  min-width: 0;
}

.step-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-primary);
  line-height: 1.4;
}

.step-desc {
  font-size: 12px;
  color: var(--text-tertiary);
  margin-top: 2px;
}

.step-connector {
  flex: 1;
  height: 2px;
  background: var(--border-light);
  margin: 0 16px;
  min-width: 40px;
}

.step-item.is-completed .step-connector {
  background: var(--success);
}

/* Step Content */
.step-content {
  flex: 1;
  overflow-y: auto;
  padding: 24px 32px;
}

.content-panel {
  max-width: 900px;
  margin: 0 auto;
}

.panel-header {
  margin-bottom: 24px;
}

.panel-header h3 {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-primary);
  margin: 0 0 8px;
}

.panel-header .hint {
  font-size: 14px;
  color: var(--text-tertiary);
  margin: 0;
}

.panel-body {
  background: var(--bg-card);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-lg);
  padding: 24px;
}

/* Example Cards */
.example-cards {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 12px;
  margin-bottom: 24px;
}

.example-card {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 16px;
  background: var(--bg-secondary);
  border: 1px solid var(--border-light);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: all var(--transition-normal);
}

.example-card:hover {
  background: var(--bg-tertiary);
  border-color: var(--accent-primary);
  transform: translateY(-2px);
}

.example-icon {
  width: 36px;
  height: 36px;
  border-radius: var(--radius-md);
  background: var(--accent-light);
  color: var(--accent-primary);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}

.example-text {
  font-size: 13px;
  color: var(--text-primary);
  line-height: 1.5;
}

/* Input Section */
.input-section {
  margin-top: 20px;
}

.nl-input :deep(.el-textarea__inner) {
  font-size: 14px;
  line-height: 1.6;
  resize: none;
}

.input-actions {
  display: flex;
  justify-content: flex-end;
  margin-top: 16px;
}

/* Params Form */
.params-form {
  max-width: 500px;
}

.params-form .el-form-item {
  margin-bottom: 20px;
}

.unit {
  margin-left: 8px;
  color: var(--text-tertiary);
  font-size: 13px;
}

.panel-actions {
  display: flex;
  justify-content: space-between;
  margin-top: 24px;
  padding-top: 20px;
  border-top: 1px solid var(--border-light);
}

/* Model Preview */
.model-preview {
  min-height: 400px;
}

.preview-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: var(--text-tertiary);
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.preview-viewport {
  height: 400px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.preview-info {
  display: flex;
  gap: 24px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}

.info-item {
  display: flex;
  gap: 8px;
  font-size: 13px;
}

.info-item .label {
  color: var(--text-tertiary);
}

.info-item .value {
  color: var(--text-primary);
  font-weight: 500;
}

/* Process Form */
.process-form {
  max-width: 500px;
}

/* NC Code */
.nc-code-container {
  min-height: 400px;
}

.code-placeholder {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 400px;
  color: var(--text-tertiary);
}

.code-viewer {
  background: var(--bg-code);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.code-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  background: var(--bg-code-header);
  border-bottom: 1px solid var(--bg-code-border);
}

.code-title {
  font-size: 13px;
  font-weight: 500;
  color: var(--text-code);
}

.code-actions {
  display: flex;
  gap: 8px;
}

.code-content {
  margin: 0;
  padding: 16px;
  max-height: 400px;
  overflow-y: auto;
  font-family: var(--font-mono);
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-code-content);
}

/* Simulation */
.simulation-container {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.simulation-viewport {
  height: 400px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
  overflow: hidden;
}

.simulation-controls {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 16px;
  padding: 16px;
  background: var(--bg-secondary);
  border-radius: var(--radius-md);
}
</style>
