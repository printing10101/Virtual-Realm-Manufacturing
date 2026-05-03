<template>
  <div class="hypothesis-timeline">
    <div class="timeline-header">
      <h3 class="timeline-title">
        <svg viewBox="0 0 1024 1024" width="20" height="20" class="title-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#409EFF"/>
          <path d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256z" fill="#409EFF"/>
        </svg>
        假设演化时间线
      </h3>
      <div class="header-actions">
        <button class="action-btn" @click="toggleAllExpanded">
          {{ allExpanded ? '全部折叠' : '全部展开' }}
        </button>
      </div>
    </div>

    <div class="timeline-body">
      <div v-if="!iterations || iterations.length === 0" class="empty-timeline">
        <svg viewBox="0 0 1024 1024" width="48" height="48" class="empty-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#d9d9d9"/>
          <path d="M464 336c0-26.5 21.5-48 48-48s48 21.5 48 48v240c0 26.5-21.5 48-48 48s-48-21.5-48-48V336z" fill="#d9d9d9"/>
        </svg>
        <p>暂无假设演化记录</p>
      </div>

      <div v-else class="timeline-list">
        <div 
          v-for="(iteration, index) in iterations" 
          :key="iteration.hypothesis?.hypothesis_id || index"
          class="timeline-item"
          :class="{
            'timeline-item-passed': iteration.is_passed,
            'timeline-item-failed': !iteration.is_passed,
            'timeline-item-final': iteration.is_passed && isFinalIteration(index)
          }"
        >
          <div class="timeline-node">
            <div class="timeline-dot" :class="getDotClass(iteration)">
              <span class="iteration-number">{{ iteration.iteration }}</span>
            </div>
            <div class="timeline-line" v-if="!isLastIteration(index)"></div>
          </div>

          <div class="timeline-content">
            <div class="timeline-header" @click="toggleExpand(index)">
              <div class="timeline-main-info">
                <div class="timeline-status-badge" :class="getStatusClass(iteration)">
                  {{ getStatusLabel(iteration) }}
                </div>
                <div class="timeline-confidence">
                  置信度: {{ (iteration.hypothesis?.confidence || 0).toFixed(2) }}
                </div>
                <div class="timeline-duration">
                  耗时: {{ formatDuration(iteration.duration_ms) }}
                </div>
              </div>
              <svg 
                class="expand-icon" 
                :class="{ 'expand-icon-expanded': expandedItems[index] }"
                viewBox="0 0 1024 1024" 
                width="16" 
                height="16"
              >
                <path d="M512 714.7a14.8 14.8 0 0 1-10.2-4.1L200.1 409.3a14.3 14.3 0 0 1 0-20.7 15.4 15.4 0 0 1 21.3 0L512 673.4l290.6-284.7a15.4 15.4 0 0 1 21.3 0 14.3 14.3 0 0 1 0 20.7L522.2 710.6a14.8 14.8 0 0 1-10.2 4.1z" fill="#999"/>
              </svg>
            </div>

            <div v-if="expandedItems[index]" class="timeline-detail">
              <div class="detail-section">
                <h5 class="section-title">假设内容</h5>
                <p class="section-content">{{ iteration.hypothesis?.content || '无' }}</p>
              </div>

              <div class="detail-section">
                <h5 class="section-title">理由</h5>
                <p class="section-content">{{ iteration.hypothesis?.reason || '无' }}</p>
              </div>

              <div class="detail-section" v-if="iteration.hypothesis?.expected_outcomes">
                <h5 class="section-title">预期效果</h5>
                <div class="outcomes-grid">
                  <div 
                    v-for="(value, key) in iteration.hypothesis.expected_outcomes" 
                    :key="key"
                    class="outcome-item"
                  >
                    <span class="outcome-label">{{ formatOutcomeKey(key) }}</span>
                    <span class="outcome-value">{{ value }}</span>
                  </div>
                </div>
              </div>

              <div class="detail-section" v-if="!iteration.is_passed">
                <h5 class="section-title">失败原因</h5>
                <p class="section-content failure-reason">
                  {{ iteration.validation_result?.failure_reason || '未知原因' }}
                </p>
              </div>

              <div class="detail-section" v-if="!iteration.is_passed">
                <h5 class="section-title">未满足约束</h5>
                <ul class="unmet-constraints">
                  <li 
                    v-for="(constraint, idx) in (iteration.validation_result?.unmet_constraints || [])" 
                    :key="idx"
                    class="constraint-item"
                  >
                    {{ constraint }}
                  </li>
                </ul>
              </div>

              <div class="detail-section" v-if="!iteration.is_passed">
                <h5 class="section-title">修正方向</h5>
                <p class="section-content correction-direction">
                  {{ iteration.correction_direction || '无' }}
                </p>
              </div>

              <div class="detail-section" v-if="iteration.validation_result?.metrics">
                <h5 class="section-title">验证指标</h5>
                <div class="metrics-grid">
                  <div 
                    v-for="(value, key) in iteration.validation_result.metrics" 
                    :key="key"
                    class="metric-item"
                  >
                    <span class="metric-label">{{ formatMetricKey(key) }}</span>
                    <span class="metric-value">{{ formatMetricValue(key, value) }}</span>
                  </div>
                </div>
              </div>

              <div class="detail-section" v-if="iteration.hypothesis?.source">
                <h5 class="section-title">假设来源</h5>
                <span class="source-badge" :class="getSourceClass(iteration.hypothesis.source)">
                  {{ getSourceLabel(iteration.hypothesis.source) }}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="warningMessage" class="warning-message">
        <svg viewBox="0 0 1024 1024" width="16" height="16" class="warning-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#faad14"/>
          <path d="M464 336c0-26.5 21.5-48 48-48s48 21.5 48 48v192c0 26.5-21.5 48-48 48s-48-21.5-48-48V336z" fill="#fff"/>
        </svg>
        <span>{{ warningMessage }}</span>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

interface Hypothesis {
  hypothesis_id: string
  content: string
  reason: string
  expected_outcomes: Record<string, string>
  confidence: number
  source: string
  based_on_hypothesis_id?: string
  created_at: string
}

interface ValidationFeedback {
  passed: boolean
  failure_reason?: string
  unmet_constraints?: string[]
  metrics?: Record<string, number>
}

interface Iteration {
  iteration: number
  hypothesis: Hypothesis
  validation_result: ValidationFeedback
  is_passed: boolean
  correction_direction: string
  duration_ms: number
  created_at: string
}

interface HypothesisLoopResult {
  success: boolean
  final_hypothesis: Hypothesis | null
  iterations: Iteration[]
  best_feasible_solution: Record<string, any> | null
  warning_message?: string
  total_duration_ms: number
}

const props = defineProps<{
  loopResult?: HypothesisLoopResult | null
}>()

const iterations = computed(() => props.loopResult?.iterations || [])
const warningMessage = computed(() => props.loopResult?.warning_message || '')

const expandedItems = ref<Record<number, boolean>>({})
const allExpanded = ref(false)

function toggleExpand(index: number) {
  expandedItems.value[index] = !expandedItems.value[index]
}

function toggleAllExpanded() {
  allExpanded.value = !allExpanded.value
  const newState = allExpanded.value
  expandedItems.value = {}
  iterations.value.forEach((_, index) => {
    expandedItems.value[index] = newState
  })
}

function getDotClass(iteration: Iteration): string {
  if (iteration.is_passed) return 'dot-passed'
  return 'dot-failed'
}

function getStatusClass(iteration: Iteration): string {
  if (iteration.is_passed) return 'status-passed'
  return 'status-failed'
}

function getStatusLabel(iteration: Iteration): string {
  if (iteration.is_passed) return '验证通过'
  return '验证失败'
}

function isFinalIteration(index: number): boolean {
  return index === iterations.value.length - 1 && iterations.value[index].is_passed
}

function isLastIteration(index: number): boolean {
  return index === iterations.value.length - 1
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms.toFixed(0)}ms`
  return `${(ms / 1000).toFixed(1)}s`
}

function formatOutcomeKey(key: string): string {
  const labels: Record<string, string> = {
    cutting_force: '切削力',
    surface_roughness: '表面粗糙度',
    tool_life: '刀具寿命',
    material_removal_rate: '材料去除率'
  }
  return labels[key] || key
}

function formatMetricKey(key: string): string {
  const labels: Record<string, string> = {
    cutting_force: '切削力',
    surface_roughness: '表面粗糙度',
    tool_life: '刀具寿命',
    cutting_speed: '切削速度',
    feed_rate: '进给量',
    depth_of_cut: '背吃刀量'
  }
  return labels[key] || key
}

function formatMetricValue(key: string, value: number): string {
  if (key === 'cutting_force') return `${value.toFixed(1)}N`
  if (key === 'surface_roughness') return `${value.toFixed(2)}μm`
  if (key === 'tool_life') return `${value.toFixed(1)}min`
  if (key === 'cutting_speed') return `${value.toFixed(1)}m/min`
  if (key === 'feed_rate') return `${value.toFixed(3)}mm/rev`
  if (key === 'depth_of_cut') return `${value.toFixed(2)}mm`
  return value.toFixed(2)
}

function getSourceClass(source: string): string {
  const classes: Record<string, string> = {
    llm_generated: 'source-llm',
    user_feedback: 'source-feedback',
    knowledge_base: 'source-knowledge'
  }
  return classes[source] || 'source-llm'
}

function getSourceLabel(source: string): string {
  const labels: Record<string, string> = {
    llm_generated: 'LLM生成',
    user_feedback: '用户反馈',
    knowledge_base: '知识库'
  }
  return labels[source] || '未知'
}
</script>

<style scoped>
.hypothesis-timeline {
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
  gap: 8px;
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

.timeline-body {
  flex: 1;
  overflow: auto;
  padding: 16px;
}

.empty-timeline {
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

.timeline-list {
  position: relative;
}

.timeline-item {
  display: flex;
  margin-bottom: 0;
  position: relative;
}

.timeline-item:last-child {
  margin-bottom: 0;
}

.timeline-node {
  display: flex;
  flex-direction: column;
  align-items: center;
  width: 40px;
  flex-shrink: 0;
}

.timeline-dot {
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
}

.dot-passed {
  background: #52c41a;
}

.dot-failed {
  background: #ff4d4f;
}

.iteration-number {
  line-height: 1;
}

.timeline-line {
  width: 2px;
  flex: 1;
  background: #e8e8e8;
  min-height: 40px;
}

.timeline-content {
  flex: 1;
  padding: 8px 0 24px 12px;
  background: #fff;
  border-radius: 8px;
  transition: all 0.2s;
}

.timeline-item-passed .timeline-content {
  background: #f6ffed;
}

.timeline-item-failed .timeline-content {
  background: #fff2f0;
}

.timeline-item-final {
  margin-bottom: 0;
}

.timeline-item-final .timeline-content {
  background: linear-gradient(135deg, #f6ffed 0%, #e6f7ff 100%);
  border: 1px solid #b7eb8f;
}

.timeline-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 4px;
  background: rgba(255, 255, 255, 0.8);
}

.timeline-header:hover {
  background: rgba(255, 255, 255, 0.95);
}

.timeline-main-info {
  display: flex;
  align-items: center;
  gap: 12px;
}

.timeline-status-badge {
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.status-passed {
  background: #52c41a;
  color: #fff;
}

.status-failed {
  background: #ff4d4f;
  color: #fff;
}

.timeline-confidence,
.timeline-duration {
  font-size: 12px;
  color: #666;
}

.expand-icon {
  transition: transform 0.2s;
}

.expand-icon-expanded {
  transform: rotate(180deg);
}

.timeline-detail {
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

.section-content {
  margin: 0;
  font-size: 12px;
  color: #333;
  line-height: 1.5;
}

.failure-reason {
  color: #ff4d4f;
}

.correction-direction {
  color: #1890ff;
}

.outcomes-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 8px;
}

.outcome-item {
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
}

.outcome-label {
  font-size: 11px;
  color: #999;
  margin-bottom: 2px;
}

.outcome-value {
  font-size: 12px;
  font-weight: 500;
  color: #333;
}

.unmet-constraints {
  list-style: none;
  padding: 0;
  margin: 0;
}

.constraint-item {
  padding: 4px 8px;
  background: #fff2f0;
  border-left: 2px solid #ff4d4f;
  margin-bottom: 4px;
  font-size: 12px;
  color: #ff4d4f;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}

.metric-item {
  background: #fafafa;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 6px 8px;
  display: flex;
  flex-direction: column;
}

.metric-label {
  font-size: 11px;
  color: #999;
  margin-bottom: 2px;
}

.metric-value {
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.source-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.source-llm {
  background: #e6f7ff;
  color: #1890ff;
  border: 1px solid #91d5ff;
}

.source-feedback {
  background: #fff7e6;
  color: #fa8c16;
  border: 1px solid #ffd591;
}

.source-knowledge {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.warning-message {
  margin-top: 16px;
  padding: 8px 12px;
  background: #fffbe6;
  border: 1px solid #ffe58f;
  border-radius: 4px;
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 12px;
  color: #d46b08;
}

.warning-icon {
  flex-shrink: 0;
}
</style>
