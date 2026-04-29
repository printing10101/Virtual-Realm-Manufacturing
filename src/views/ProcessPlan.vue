<template>
  <div class="process-plan-view">
    <el-card class="view-card">
      <template #header>
        <div class="card-header">
          <h2>{{ t('processPlan.title') }}</h2>
          <el-button @click="resetForm" size="small">
            <el-icon><RefreshLeft /></el-icon>
            {{ t('processPlan.reset') }}
          </el-button>
        </div>
      </template>

      <el-form :model="form" label-width="120px">
        <el-form-item :label="t('processPlan.inputLabel')">
          <el-input
            v-model="form.userInput"
            type="textarea"
            :rows="4"
            :placeholder="t('processPlan.inputPlaceholder')"
          />
        </el-form-item>

        <el-form-item>
          <el-button
            type="primary"
            @click="handleGenerate"
            :loading="isGenerating"
            :disabled="!form.userInput || isGenerating"
          >
            {{ isGenerating ? t('processPlan.generating') : t('processPlan.generateBtn') }}
          </el-button>
        </el-form-item>
      </el-form>

      <div v-if="isGenerating || workflowResult" class="workflow-progress">
        <h3>{{ t('processPlan.workflowProgress') }}</h3>
        <el-steps :active="currentStep" finish-status="success" simple>
          <el-step :title="t('processPlan.step1')" />
          <el-step :title="t('processPlan.step2')" />
          <el-step :title="t('processPlan.step3')" />
          <el-step :title="t('processPlan.step4')" />
          <el-step :title="t('processPlan.step5')" />
          <el-step :title="t('processPlan.step6')" />
        </el-steps>
        <el-progress
          :percentage="progressPercent"
          :status="progressStatus"
          :stroke-width="20"
        />
      </div>

      <div v-if="workflowResult" class="result-area">
        <el-tabs type="border-card">
          <el-tab-pane :label="t('processPlan.tab1')">
            <el-descriptions :column="2" border>
              <el-descriptions-item :label="t('processPlan.labelMaterial')">{{ workflowResult.extracted_params.material || '-' }}</el-descriptions-item>
              <el-descriptions-item :label="t('processPlan.labelPartType')">{{ workflowResult.extracted_params.part_type || '-' }}</el-descriptions-item>
              <el-descriptions-item :label="t('processPlan.labelTolerance')">{{ workflowResult.extracted_params.tolerance || '-' }}</el-descriptions-item>
              <el-descriptions-item :label="t('processPlan.labelSurfaceRoughness')">{{ workflowResult.extracted_params.surface_roughness || '-' }}</el-descriptions-item>
            </el-descriptions>
          </el-tab-pane>

          <el-tab-pane :label="t('processPlan.tab2')">
            <el-table :data="workflowResult.process_route" stripe>
              <el-table-column prop="step" :label="t('processPlan.colStep')" width="80" />
              <el-table-column prop="operation" :label="t('processPlan.colOperation')" width="120" />
              <el-table-column prop="machine" :label="t('processPlan.colMachine')" width="100" />
              <el-table-column prop="description" :label="t('processPlan.colDescription')" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane :label="t('processPlan.tab3')">
            <el-table :data="workflowResult.cutting_parameters.parameters || []" stripe>
              <el-table-column prop="step" :label="t('processPlan.colStep')" width="80" />
              <el-table-column prop="operation" :label="t('processPlan.colOperation')" width="100" />
              <el-table-column prop="v" :label="t('processPlan.colSpeed')" />
              <el-table-column prop="f" :label="t('processPlan.colFeed')" />
              <el-table-column prop="ap" :label="t('processPlan.colDepth')" />
              <el-table-column prop="n" :label="t('processPlan.colSpindleSpeed')" />
            </el-table>
          </el-tab-pane>

          <el-tab-pane :label="t('processPlan.tab4')">
            <pre class="code-block">{{ workflowResult.nc_code }}</pre>
          </el-tab-pane>

          <el-tab-pane :label="t('processPlan.tab5')">
            <el-alert
              :title="workflowResult.verification_result.summary || t('processPlan.verificationComplete')"
              :type="workflowResult.verification_result.is_valid ? 'success' : 'warning'"
              :closable="false"
              show-icon
            />
            <el-table v-if="workflowResult.verification_result.issues?.length" :data="workflowResult.verification_result.issues" stripe style="margin-top: 16px">
              <el-table-column prop="type" :label="t('processPlan.colType')" width="100" />
              <el-table-column prop="description" :label="t('processPlan.colIssue')" />
              <el-table-column prop="severity" :label="t('processPlan.colSeverity')" width="100">
                <template #default="scope">
                  <el-tag :type="scope.row.severity === 'high' ? 'danger' : scope.row.severity === 'medium' ? 'warning' : 'info'">
                    {{ scope.row.severity }}
                  </el-tag>
                </template>
              </el-table-column>
            </el-table>
          </el-tab-pane>

          <el-tab-pane :label="t('processPlan.tab6')">
            <div v-if="workflowResult.repair_suggestions && workflowResult.repair_suggestions.length">
              <div class="suggestion-content">{{ workflowResult.repair_suggestions }}</div>
            </div>
            <el-empty v-else :description="t('processPlan.noRepairSuggestions')" />
          </el-tab-pane>
        </el-tabs>
      </div>

      <div v-if="!workflowResult && !isGenerating" class="empty-result">
        <el-empty :description="t('processPlan.emptyResult')" />
      </div>
    </el-card>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed } from 'vue'
import { ElMessage } from 'element-plus'
import { RefreshLeft } from '@element-plus/icons-vue'
import { useI18n } from 'vue-i18n'
import axios from 'axios'

const { t } = useI18n()

const form = reactive({
  userInput: ''
})

const isGenerating = ref(false)
const currentStep = ref(0)
const progressPercent = ref(0)
const workflowResult = ref<any>(null)

const progressStatus = computed(() => {
  if (progressPercent.value >= 100) return 'success'
  if (progressPercent.value < 0) return 'exception'
  return ''
})

const handleGenerate = async () => {
  if (!form.userInput.trim()) {
    ElMessage.warning(t('processPlan.inputRequired'))
    return
  }

  isGenerating.value = true
  currentStep.value = 0
  progressPercent.value = 0
  workflowResult.value = null

  try {
    const response = await axios.post('http://127.0.0.1:8765/api/workflow/process-plan', {
      user_input: form.userInput
    })

    if (response.data.code === 0) {
      workflowResult.value = response.data.data
      progressPercent.value = 100
      currentStep.value = 6
      ElMessage.success(t('processPlan.generateSuccess'))
    } else {
      ElMessage.error(response.data.message || t('processPlan.generateFailed'))
    }
  } catch (error: any) {
    ElMessage.error(`${t('processPlan.generateFailed')}: ${error.message}`)
  } finally {
    isGenerating.value = false
  }
}

const resetForm = () => {
  form.userInput = ''
  workflowResult.value = null
  currentStep.value = 0
  progressPercent.value = 0
  isGenerating.value = false
}
</script>

<style scoped lang="scss">
.process-plan-view {
  .view-card {
    .card-header {
      display: flex;
      justify-content: space-between;
      align-items: center;

      h2 {
        margin: 0;
        font-size: 20px;
        color: #303133;
      }
    }

    .workflow-progress {
      margin-top: 30px;
      padding: 20px;
      background-color: #f5f7fa;
      border-radius: 8px;

      h3 {
        margin-bottom: 16px;
        font-size: 16px;
        color: #303133;
      }

      .el-steps {
        margin-bottom: 20px;
      }
    }

    .result-area {
      margin-top: 30px;
    }

    .empty-result {
      margin-top: 30px;
      min-height: 300px;
    }

    .code-block {
      background-color: #1e1e1e;
      color: #d4d4d4;
      padding: 16px;
      border-radius: 8px;
      font-family: 'Consolas', 'Courier New', monospace;
      font-size: 13px;
      line-height: 1.5;
      overflow-x: auto;
      white-space: pre-wrap;
      word-wrap: break-word;
    }

    .suggestion-content {
      padding: 16px;
      line-height: 1.8;
      font-size: 14px;
      color: #303133;
    }
  }
}

@media (max-width: 768px) {
  .process-plan-view {
    .view-card {
      .card-header {
        flex-direction: column;
        align-items: flex-start;
        gap: 12px;
      }
      
      .workflow-progress {
        .el-steps {
          :deep(.el-step__title) {
            font-size: 12px;
          }
        }
      }
    }
  }
}
</style>
