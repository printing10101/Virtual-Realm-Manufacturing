<template>
  <div class="report-view">
    <div class="report-header">
      <div class="report-meta">
        <h2>ReACT 工艺分析报告</h2>
        <div class="meta-info">
          <span class="meta-item">
            <el-icon><Clock /></el-icon>
            生成时间：{{ generatedAt }}
          </span>
          <span class="meta-item">
            <el-icon><Cpu /></el-icon>
            模型：{{ model || '未指定' }}
          </span>
          <span class="meta-item">
            <el-icon><Timer /></el-icon>
            耗时：{{ formatDuration(totalDuration) }}
          </span>
          <span class="meta-item">
            <el-icon><ChatDotSquare /></el-icon>
            Tokens：{{ totalTokens }}
          </span>
        </div>
      </div>
      <div class="report-actions">
        <el-button type="primary" @click="generateNewReport">
          <el-icon><RefreshRight /></el-icon>
          生成新报告
        </el-button>
        <el-button @click="exportPDF">
          <el-icon><Download /></el-icon>
          导出 PDF
        </el-button>
      </div>
    </div>

    <div class="report-content">
      <div class="report-reasoning">
        <h3 class="section-title">
          <el-icon><List /></el-icon>
          ReACT 推理过程
          <span class="step-count">({{ reasoningSteps.length }} 步)</span>
        </h3>
        <div class="reasoning-timeline">
          <div
            v-for="step in reasoningSteps"
            :key="step.step_number"
            class="timeline-item"
            :class="`step-${step.step_type}`"
          >
            <div class="timeline-dot"></div>
            <div class="timeline-content">
              <div class="step-header" @click="toggleStep(step.step_number)">
                <span class="step-badge">
                  {{ step.step_type === 'thought' ? '思考' : step.step_type === 'action' ? '行动' : step.step_type === 'observation' ? '观察' : '结论' }}
                </span>
                <span class="step-title-text">{{ step.content.substring(0, 60) }}{{ step.content.length > 60 ? '...' : '' }}</span>
                <el-icon v-if="step.tool_name" class="tool-icon"><Tools /></el-icon>
                <span class="tool-name" v-if="step.tool_name">{{ step.tool_name }}</span>
                <span class="step-duration" v-if="step.duration_ms">{{ (step.duration_ms / 1000).toFixed(2) }}s</span>
              </div>
              <div class="step-detail" v-show="expandedSteps.includes(step.step_number)">
                <pre class="step-content" v-if="step.content.length > 60">{{ step.content }}</pre>
                <div class="step-io" v-if="step.tool_input || step.tool_output">
                  <div class="io-section" v-if="step.tool_input">
                    <h4>输入：</h4>
                    <pre>{{ JSON.stringify(step.tool_input, null, 2) }}</pre>
                  </div>
                  <div class="io-section" v-if="step.tool_output">
                    <h4>输出：</h4>
                    <pre>{{ JSON.stringify(step.tool_output, null, 2) }}</pre>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="report-main" ref="reportContentRef">
        <h3 class="section-title">
          <el-icon><Document /></el-icon>
          分析报告
        </h3>
        <div class="report-body" v-if="reportContent">
          <div class="markdown-content" v-html="renderedMarkdown"></div>
        </div>
        <div class="report-empty" v-else>
          <el-empty description="尚未生成报告" />
          <el-button type="primary" @click="generateNewReport">开始生成</el-button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { Clock, Cpu, Timer, ChatDotSquare, RefreshRight, Download, List, Document, Tools } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { reportService, type ReACTStep } from '@/services/reportService'
import MarkdownIt from 'markdown-it'

const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true,
  breaks: true
})

const generatedAt = ref('')
const model = ref('')
const totalDuration = ref(0)
const totalTokens = ref(0)
const reasoningSteps = ref<ReACTStep[]>([])
const reportContent = ref('')
const expandedSteps = ref<number[]>([])
const reportContentRef = ref<HTMLElement | null>(null)

const renderedMarkdown = computed(() => {
  return reportContent.value ? md.render(reportContent.value) : ''
})

function toggleStep(stepNumber: number) {
  const index = expandedSteps.value.indexOf(stepNumber)
  if (index === -1) {
    expandedSteps.value.push(stepNumber)
  } else {
    expandedSteps.value.splice(index, 1)
  }
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`
  const seconds = ms / 1000
  if (seconds < 60) return `${seconds.toFixed(2)}s`
  const minutes = Math.floor(seconds / 60)
  const remainingSeconds = seconds % 60
  return `${minutes}分${remainingSeconds.toFixed(0)}秒`
}

async function generateNewReport() {
  try {
    ElMessage.info('开始生成 ReACT 报告...')
    const result = await reportService.generateReport()
    ElMessage.success(`报告生成任务已创建，Task ID: ${result.task_id}`)

    await pollForCompletion(result.task_id)
  } catch (e) {
    ElMessage.error('报告生成失败')
  }
}

async function pollForCompletion(taskId: string) {
  const maxAttempts = 60
  let attempts = 0

  while (attempts < maxAttempts) {
    await new Promise(resolve => setTimeout(resolve, 2000))

    try {
      const report = await reportService.getReport(taskId)
      if (report) {
        reportContent.value = report.report
        reasoningSteps.value = report.reasoning_steps
        generatedAt.value = new Date().toLocaleString('zh-CN')

        ElMessage.success('报告生成完成')
        return
      }
    } catch (e) {
      attempts++
    }
  }

  ElMessage.warning('报告生成超时，请稍后重试')
}

function exportPDF() {
  if (!reportContentRef.value) return

  const printWindow = window.open('', '_blank')
  if (!printWindow) return

  printWindow.document.write(`
    <!DOCTYPE html>
    <html>
    <head>
      <meta charset="utf-8">
      <title>工艺分析报告</title>
      <style>
        body { font-family: 'Segoe UI', sans-serif; padding: 40px; line-height: 1.6; color: #333; }
        h1, h2, h3 { color: #1a1a1a; margin-top: 24px; }
        table { border-collapse: collapse; width: 100%; margin: 16px 0; }
        th, td { border: 1px solid #ddd; padding: 8px 12px; text-align: left; }
        th { background: #f5f5f5; font-weight: 600; }
        pre { background: #f5f5f5; padding: 12px; border-radius: 4px; overflow-x: auto; }
        code { background: #f5f5f5; padding: 2px 4px; border-radius: 3px; font-size: 0.9em; }
        @media print { body { padding: 20px; } }
      </style>
    </head>
    <body>
      ${reportContentRef.value.innerHTML}
    </body>
    </html>
  `)
  printWindow.document.close()
  printWindow.focus()
  setTimeout(() => {
    printWindow.print()
    printWindow.close()
  }, 250)
}

onMounted(() => {
})
</script>

<style scoped>
.report-view {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #f5f7fa;
}

.report-header {
  padding: 16px 24px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.report-meta h2 {
  margin: 0 0 8px 0;
  font-size: 20px;
  color: #1a1a1a;
}

.meta-info {
  display: flex;
  gap: 16px;
}

.meta-item {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  color: #666;
}

.report-actions {
  display: flex;
  gap: 8px;
}

.report-content {
  flex: 1;
  display: flex;
  overflow: hidden;
}

.report-reasoning {
  width: 360px;
  background: #fff;
  border-right: 1px solid #e8e8e8;
  padding: 16px;
  overflow-y: auto;
}

.report-main {
  flex: 1;
  padding: 16px 24px;
  overflow-y: auto;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 8px;
  margin: 0 0 16px 0;
  font-size: 16px;
  color: #1a1a1a;
}

.step-count {
  font-size: 12px;
  color: #999;
  font-weight: normal;
}

.reasoning-timeline {
  position: relative;
  padding-left: 20px;
}

.reasoning-timeline::before {
  content: '';
  position: absolute;
  left: 6px;
  top: 0;
  bottom: 0;
  width: 2px;
  background: #e8e8e8;
}

.timeline-item {
  position: relative;
  margin-bottom: 16px;
}

.timeline-dot {
  position: absolute;
  left: -17px;
  top: 8px;
  width: 10px;
  height: 10px;
  border-radius: 50%;
  border: 2px solid #409EFF;
  background: #fff;
}

.step-thought .timeline-dot {
  border-color: #E6A23C;
  background: #fdf6ec;
}

.step-action .timeline-dot {
  border-color: #409EFF;
  background: #ecf5ff;
}

.step-observation .timeline-dot {
  border-color: #67C23A;
  background: #f0f9eb;
}

.step-final_answer .timeline-dot {
  border-color: #F56C6C;
  background: #fef0f0;
}

.timeline-content {
  padding-left: 8px;
}

.step-header {
  display: flex;
  align-items: center;
  gap: 6px;
  cursor: pointer;
  padding: 8px;
  background: #f9f9f9;
  border-radius: 6px;
  transition: background 0.2s;
}

.step-header:hover {
  background: #f0f0f0;
}

.step-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 10px;
  font-weight: 500;
  white-space: nowrap;
}

.step-thought .step-badge {
  background: #fdf6ec;
  color: #E6A23C;
}

.step-action .step-badge {
  background: #ecf5ff;
  color: #409EFF;
}

.step-observation .step-badge {
  background: #f0f9eb;
  color: #67C23A;
}

.step-final_answer .step-badge {
  background: #fef0f0;
  color: #F56C6C;
}

.step-title-text {
  flex: 1;
  font-size: 12px;
  color: #333;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.tool-icon {
  font-size: 12px;
  color: #666;
}

.tool-name {
  font-size: 11px;
  color: #999;
  font-family: monospace;
}

.step-duration {
  font-size: 10px;
  color: #bbb;
  margin-left: auto;
}

.step-detail {
  margin-top: 8px;
  padding: 12px;
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 6px;
}

.step-content {
  font-size: 12px;
  line-height: 1.6;
  color: #333;
  margin: 0 0 12px 0;
  white-space: pre-wrap;
  word-break: break-word;
}

.step-io {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.io-section h4 {
  margin: 0 0 4px 0;
  font-size: 11px;
  color: #666;
}

.io-section pre {
  margin: 0;
  padding: 8px;
  background: #f5f5f5;
  border-radius: 4px;
  font-size: 11px;
  overflow-x: auto;
}

.report-body {
  background: #fff;
  padding: 24px;
  border-radius: 8px;
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
}

.markdown-content {
  line-height: 1.8;
  color: #333;
}

.markdown-content :deep(h1),
.markdown-content :deep(h2),
.markdown-content :deep(h3) {
  color: #1a1a1a;
  margin-top: 24px;
  margin-bottom: 12px;
}

.markdown-content :deep(table) {
  border-collapse: collapse;
  width: 100%;
  margin: 16px 0;
}

.markdown-content :deep(th),
.markdown-content :deep(td) {
  border: 1px solid #ddd;
  padding: 8px 12px;
  text-align: left;
}

.markdown-content :deep(th) {
  background: #f5f5f5;
  font-weight: 600;
}

.markdown-content :deep(pre) {
  background: #f5f5f5;
  padding: 12px;
  border-radius: 4px;
  overflow-x: auto;
}

.markdown-content :deep(code) {
  background: #f5f5f5;
  padding: 2px 4px;
  border-radius: 3px;
  font-size: 0.9em;
}

.report-empty {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  height: 100%;
}
</style>
