<template>
  <div class="accept-modify-reject">
    <div class="decision-header">
      <span class="title">AI建议操作</span>
      <span v-if="showTimestamp" class="timestamp">{{ formatTimestamp(timestamp) }}</span>
    </div>

    <div v-if="aiRecommendation" class="recommendation-card">
      <div class="card-header">
        <el-icon><Promotion /></el-icon>
        <span class="card-title">AI推荐</span>
        <el-tag v-if="confidence !== null" :type="getConfidenceType(confidence)" size="small">
          置信度: {{ (confidence * 100).toFixed(0) }}%
        </el-tag>
      </div>
      <div class="card-content">
        <slot name="recommendation">
          <pre>{{ formatRecommendation(aiRecommendation) }}</pre>
        </slot>
      </div>
    </div>

    <div v-if="reasoning" class="reasoning-card">
      <div class="card-header">
        <el-icon><ChatDotRound /></el-icon>
        <span class="card-title">推理过程</span>
      </div>
      <div class="card-content">
        <p>{{ reasoning }}</p>
      </div>
    </div>

    <div v-if="showAlternatives && alternatives && alternatives.length > 0" class="alternatives-section">
      <div class="section-header">
        <el-icon><Grid /></el-icon>
        <span class="section-title">备选方案</span>
      </div>
      <el-radio-group v-model="selectedAlternative" class="alternatives-list">
        <el-card
          v-for="alt in alternatives"
          :key="alt.plan_id"
          class="alternative-card"
          :class="{ 'is-selected': selectedAlternative === alt.plan_id }"
          @click="selectedAlternative = alt.plan_id"
        >
          <div class="alternative-header">
            <el-tag :type="getConfidenceType(alt.confidence)" size="small">
              {{ (alt.confidence * 100).toFixed(0) }}%
            </el-tag>
            <span class="alternative-title">{{ alt.expected_outcome }}</span>
          </div>
          <div class="alternative-reasoning" v-if="showReasoning">
            {{ alt.reasoning }}
          </div>
        </el-card>
      </el-radio-group>
    </div>

    <div class="action-buttons">
      <el-button
        type="success"
        size="large"
        @click="handleAccept"
        :icon="Check"
      >
        接受
      </el-button>
      <el-button
        v-if="allowModify"
        type="warning"
        size="large"
        @click="handleModify"
        :icon="Edit"
      >
        修改
      </el-button>
      <el-button
        type="danger"
        size="large"
        @click="handleReject"
        :icon="Close"
      >
        拒绝
      </el-button>
    </div>

    <el-drawer
      v-model="modifyDrawerVisible"
      title="修改AI推荐"
      size="50%"
    >
      <div class="modify-content">
        <slot name="modify-form" :recommendation="aiRecommendation">
          <el-alert
            title="您可以在此修改AI推荐的参数"
            type="info"
            :closable="false"
            show-icon
          />
          <el-form :model="modifiedParams" label-width="120px" style="margin-top: 16px;">
            <el-form-item
              v-for="(value, key) in aiRecommendation"
              :key="key"
              :label="key"
            >
              <el-input
                v-if="typeof value === 'string'"
                v-model="modifiedParams[key]"
              />
              <el-input-number
                v-else-if="typeof value === 'number'"
                v-model="modifiedParams[key]"
                :step="0.01"
              />
              <el-switch
                v-else-if="typeof value === 'boolean'"
                v-model="modifiedParams[key]"
              />
              <pre v-else>{{ JSON.stringify(value, null, 2) }}</pre>
            </el-form-item>
          </el-form>
        </slot>
      </div>
      <template #footer>
        <div class="drawer-footer">
          <el-button @click="modifyDrawerVisible = false">取消</el-button>
          <el-button type="primary" @click="confirmModify">确认修改</el-button>
        </div>
      </template>
    </el-drawer>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Promotion, ChatDotRound, Grid, Check, Edit, Close } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

interface AlternativePlan {
  plan_id: string
  parameters: Record<string, any>
  expected_outcome: string
  confidence: number
  reasoning: string
}

interface Props {
  aiRecommendation?: Record<string, any>
  confidence?: number | null
  reasoning?: string
  alternatives?: AlternativePlan[]
  timestamp?: number
  allowModify?: boolean
  showAlternatives?: boolean
  showReasoning?: boolean
  showTimestamp?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  confidence: null,
  reasoning: '',
  alternatives: () => [],
  timestamp: () => Date.now(),
  allowModify: true,
  showAlternatives: true,
  showReasoning: true,
  showTimestamp: true,
})

const emit = defineEmits<{
  accept: [recommendation: Record<string, any>]
  modify: [modifiedParams: Record<string, any>]
  reject: [recommendation: Record<string, any>]
}>()

const selectedAlternative = ref<string | null>(null)
const modifyDrawerVisible = ref(false)
const modifiedParams = ref<Record<string, any>>({})

function formatTimestamp(ts: number): string {
  return new Date(ts).toLocaleString('zh-CN')
}

function formatRecommendation(rec: Record<string, any>): string {
  return JSON.stringify(rec, null, 2)
}

function getConfidenceType(conf: number): 'success' | 'warning' | 'danger' {
  if (conf >= 0.8) return 'success'
  if (conf >= 0.5) return 'warning'
  return 'danger'
}

function handleAccept() {
  const selected = selectedAlternative.value
    ? props.alternatives?.find(a => a.plan_id === selectedAlternative.value)
    : null

  const recommendation = selected
    ? { ...selected.parameters, plan_id: selected.plan_id }
    : { ...props.aiRecommendation }

  emit('accept', recommendation)
  ElMessage.success('已接受AI推荐')
}

function handleModify() {
  modifiedParams.value = { ...props.aiRecommendation }
  modifyDrawerVisible.value = true
}

function confirmModify() {
  emit('modify', modifiedParams.value)
  modifyDrawerVisible.value = false
  ElMessage.info('已应用您的修改')
}

function handleReject() {
  emit('reject', { ...props.aiRecommendation })
  ElMessage.warning('已拒绝AI推荐')
}
</script>

<style scoped>
.accept-modify-reject {
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  padding: 16px;
  background: #fafafa;
}

.decision-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 16px;
}

.decision-header .title {
  font-size: 16px;
  font-weight: 600;
  color: #303133;
}

.decision-header .timestamp {
  font-size: 12px;
  color: #909399;
}

.recommendation-card,
.reasoning-card {
  background: #fff;
  border-radius: 6px;
  padding: 12px;
  margin-bottom: 12px;
  border: 1px solid #ebeef5;
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 8px;
  font-weight: 500;
  color: #409eff;
}

.card-content {
  color: #606266;
  font-size: 14px;
  line-height: 1.6;
}

.card-content pre {
  margin: 0;
  white-space: pre-wrap;
  word-break: break-all;
  background: #f5f7fa;
  padding: 8px;
  border-radius: 4px;
  font-size: 12px;
}

.alternatives-section {
  margin: 16px 0;
}

.section-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  font-weight: 500;
  color: #67c23a;
}

.alternatives-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.alternative-card {
  cursor: pointer;
  transition: all 0.3s;
  border: 2px solid transparent;
}

.alternative-card:hover {
  border-color: #409eff;
}

.alternative-card.is-selected {
  border-color: #409eff;
  background: #ecf5ff;
}

.alternative-header {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.alternative-title {
  font-size: 14px;
  color: #303133;
  line-height: 1.5;
}

.alternative-reasoning {
  margin-top: 8px;
  font-size: 12px;
  color: #909399;
  line-height: 1.5;
}

.action-buttons {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-top: 20px;
  padding-top: 16px;
  border-top: 1px solid #ebeef5;
}

.modify-content {
  padding: 16px;
}

.drawer-footer {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
}
</style>
