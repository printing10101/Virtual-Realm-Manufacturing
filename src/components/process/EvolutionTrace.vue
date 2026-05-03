<template>
  <div class="evolution-trace">
    <div class="trace-header">
      <h3 class="trace-title">
        <svg viewBox="0 0 1024 1024" width="20" height="20" class="title-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#409EFF"/>
          <path d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256zm0 472c-119.3 0-216-96.7-216-216s96.7-216 216-216 216 96.7 216 216-96.7 216-216 216z" fill="#409EFF"/>
        </svg>
        工艺演化路径
      </h3>
      <div class="header-actions">
        <button class="action-btn" @click="fetchTraceData" :disabled="loading">
          <svg viewBox="0 0 1024 1024" width="16" height="16">
            <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="currentColor"/>
            <path d="M512 720c-114.9 0-208-93.1-208-208s93.1-208 208-208 208 93.1 208 208-93.1 208-208 208z" fill="currentColor"/>
          </svg>
          刷新
        </button>
        <button class="action-btn" @click="toggleView">
          {{ showMermaid ? '切换节点视图' : '切换DAG视图' }}
        </button>
      </div>
    </div>

    <div class="trace-body">
      <div class="trace-filters" v-if="traces.length > 0">
        <select v-model="selectedNodeFilter" class="filter-select">
          <option value="">全部节点</option>
          <option value="sota">仅最优解</option>
          <option value="passed">验证通过</option>
          <option value="failed">验证失败</option>
        </select>
        <span class="node-count">{{ filteredTraces.length }} / {{ traces.length }} 节点</span>
      </div>

      <div v-if="loading" class="loading">
        <svg viewBox="0 0 1024 1024" width="48" height="48" class="loading-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#d9d9d9"/>
          <path d="M512 256c-141.4 0-256 114.6-256 256s114.6 256 256 256 256-114.6 256-256-114.6-256-256-256z" fill="#409EFF"/>
        </svg>
        <p>加载演化历史中...</p>
      </div>

      <div v-else-if="traces.length === 0" class="empty-traces">
        <svg viewBox="0 0 1024 1024" width="48" height="48" class="empty-icon">
          <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="#d9d9d9"/>
          <path d="M464 336c0-26.5 21.5-48 48-48s48 21.5 48 48v240c0 26.5-21.5 48-48 48s-48-21.5-48-48V336z" fill="#d9d9d9"/>
        </svg>
        <p>暂无演化记录</p>
      </div>

      <div v-else-if="showMermaid" class="mermaid-viewer">
        <div class="mermaid-container" ref="mermaidContainer" v-html="mermaidSvg"></div>
      </div>

      <div v-else class="node-view">
        <div class="node-tree">
          <TraceNode
            v-for="node in rootNodes"
            :key="node.node_id"
            :node="node"
            :nodes="traces"
            :children-map="childrenMap"
            :selected-id="selectedNodeId"
            @select="selectNode"
          />
        </div>
      </div>
    </div>

    <div class="trace-detail" v-if="selectedNode">
      <div class="detail-header">
        <h4 class="detail-title">节点详情</h4>
        <button class="close-detail-btn" @click="selectedNodeId = null">
          <svg viewBox="0 0 1024 1024" width="16" height="16">
            <path d="M563.8 512l262.5-312.9c4.4-5.2.7-13.1-6.1-13.1h-77.3c-4.2 0-8.1 1.8-10.7 5L512 432.4 291.8 191c-2.6-3.2-6.5-5-10.7-5H203.8c-6.8 0-10.5 7.9-6.1 13.1L460.2 512 197.7 824.9A7.95 7.95 0 0 0 203.8 838h77.3c4.2 0 8.1-1.8 10.7-5L512 591.6l220.2 241.4c2.6 3.2 6.5 5 10.7 5h77.3c6.8 0 10.5-7.9 6.1-13.1L563.8 512z" fill="#999"/>
          </svg>
        </button>
      </div>
      <div class="detail-body">
        <div class="detail-section">
          <h5 class="section-title">假设</h5>
          <p class="section-content">{{ selectedNode.hypothesis || '无' }}</p>
        </div>
        <div class="detail-section">
          <h5 class="section-title">理由</h5>
          <p class="section-content">{{ selectedNode.reason || '无' }}</p>
        </div>
        <div class="detail-section">
          <h5 class="section-title">求解结果</h5>
          <pre class="section-content result-json">{{ formatResult(selectedNode.result) }}</pre>
        </div>
        <div class="detail-section">
          <h5 class="section-title">验证指标</h5>
          <pre class="section-content result-json">{{ formatValidation(selectedNode.validation_result) }}</pre>
        </div>
        <div class="detail-section" v-if="selectedNode.feedback">
          <h5 class="section-title">反馈</h5>
          <p class="section-content feedback">{{ selectedNode.feedback }}</p>
        </div>
        <div class="detail-section" v-if="selectedNode.metrics">
          <h5 class="section-title">关键指标</h5>
          <div class="metrics-grid">
            <div class="metric-item" v-for="(value, key) in selectedNode.metrics" :key="key">
              <span class="metric-label">{{ key }}</span>
              <span class="metric-value">{{ typeof value === 'number' ? value.toFixed(4) : value }}</span>
            </div>
          </div>
        </div>
        <div class="detail-section">
          <h5 class="section-title">状态</h5>
          <span class="status-badge" :class="getNodeStatusClass(selectedNode)">
            {{ getNodeStatusLabel(selectedNode) }}
          </span>
          <span class="sota-badge" v-if="selectedNode.is_sota">SOTA</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, nextTick } from 'vue'
import axios from 'axios'

interface TraceNode {
  node_id: string
  task_id: string
  parent_ids: string[]
  hypothesis: string
  reason: string
  result: Record<string, any>
  validation_result: Record<string, any>
  feedback: string
  metrics: Record<string, number>
  is_sota: boolean
  created_at: string
}

const props = defineProps<{
  taskId: string
}>()

const traces = ref<TraceNode[]>([])
const loading = ref(false)
const selectedNodeId = ref<string | null>(null)
const showMermaid = ref(true)
const selectedNodeFilter = ref('')
const mermaidSvg = ref('')
const mermaidContainer = ref<HTMLElement | null>(null)

const childrenMap = computed(() => {
  const map: Record<string, string[]> = {}
  traces.value.forEach(node => {
    if (!map[node.node_id]) map[node.node_id] = []
    node.parent_ids.forEach(pid => {
      if (!map[pid]) map[pid] = []
      map[pid].push(node.node_id)
    })
  })
  return map
})

const rootNodes = computed(() => {
  return traces.value.filter(n => n.parent_ids.length === 0)
})

const filteredTraces = computed(() => {
  if (!selectedNodeFilter.value) return traces.value
  
  return traces.value.filter(node => {
    if (selectedNodeFilter.value === 'sota') return node.is_sota
    if (selectedNodeFilter.value === 'passed') return node.validation_result?.passed
    if (selectedNodeFilter.value === 'failed') return !node.validation_result?.passed
    return true
  })
})

const selectedNode = computed(() => {
  return traces.value.find(n => n.node_id === selectedNodeId.value) || null
})

watch(selectedNodeId, async () => {
  if (selectedNodeId.value && showMermaid.value) {
    await nextTick()
  }
})

watch(showMermaid, async (val) => {
  if (val) {
    await nextTick()
    fetchMermaidDiagram()
  }
})

async function fetchTraceData() {
  if (!props.taskId) return
  
  loading.value = true
  try {
    const response = await axios.get(`/api/v1/traces/${props.taskId}`)
    if (response.data.code === 200) {
      traces.value = response.data.data.traces || []
      if (traces.value.length > 0 && !selectedNodeId.value) {
        const sota = traces.value.find(n => n.is_sota)
        selectedNodeId.value = sota?.node_id || traces.value[0].node_id
      }
    }
  } catch (e) {
    console.error('获取演化历史失败:', e)
  } finally {
    loading.value = false
  }
}

async function fetchMermaidDiagram() {
  if (!props.taskId) return
  
  try {
    const response = await axios.get(`/api/v1/traces/${props.taskId}/mermaid`)
    if (response.data.code === 200) {
      mermaidSvg.value = response.data.data.mermaid || ''
    }
  } catch (e) {
    console.error('获取DAG图失败:', e)
  }
}

function toggleView() {
  showMermaid.value = !showMermaid.value
}

function selectNode(nodeId: string) {
  selectedNodeId.value = nodeId
}

function formatResult(result: Record<string, any>): string {
  if (!result || Object.keys(result).length === 0) return '无'
  try {
    return JSON.stringify(result, null, 2)
  } catch {
    return String(result)
  }
}

function formatValidation(validation: Record<string, any>): string {
  if (!validation || Object.keys(validation).length === 0) return '无'
  try {
    return JSON.stringify(validation, null, 2)
  } catch {
    return String(validation)
  }
}

function getNodeStatusClass(node: TraceNode): string {
  if (node.is_sota) return 'status-sota'
  if (node.validation_result?.passed) return 'status-passed'
  if (node.validation_result && !node.validation_result.passed) return 'status-failed'
  return 'status-pending'
}

function getNodeStatusLabel(node: TraceNode): string {
  if (node.is_sota) return '当前最优'
  if (node.validation_result?.passed) return '验证通过'
  if (node.validation_result && !node.validation_result.passed) return '验证失败'
  return '待验证'
}

onMounted(() => {
  fetchTraceData()
})
</script>

<script lang="ts">
export default {
  name: 'EvolutionTrace'
}
</script>

<style scoped>
.evolution-trace {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: #fff;
}

.trace-header {
  padding: 12px 16px;
  background: #fafafa;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.trace-title {
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
  display: flex;
  align-items: center;
  gap: 4px;
  color: #666;
}

.action-btn:hover:not(:disabled) {
  border-color: #409EFF;
  color: #409EFF;
}

.action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.trace-body {
  flex: 1;
  overflow: auto;
  padding: 12px;
}

.trace-filters {
  padding: 8px 0;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
}

.filter-select {
  padding: 6px 8px;
  border: 1px solid #d9d9d9;
  border-radius: 4px;
  font-size: 12px;
  background: #fff;
}

.node-count {
  font-size: 12px;
  color: #999;
}

.loading, .empty-traces {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 0;
  color: #999;
}

.loading-icon, .empty-icon {
  margin-bottom: 12px;
}

.loading-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.mermaid-viewer {
  width: 100%;
  overflow: auto;
  padding: 16px;
  background: #fafafa;
  border-radius: 4px;
  min-height: 400px;
}

.mermaid-container {
  width: 100%;
  text-align: center;
}

.node-view {
  width: 100%;
}

.node-tree {
  padding: 8px;
}

.trace-detail {
  border-top: 1px solid #e8e8e8;
  background: #fafafa;
  max-height: 40%;
  overflow: auto;
}

.detail-header {
  padding: 8px 12px;
  background: #fff;
  border-bottom: 1px solid #e8e8e8;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.detail-title {
  margin: 0;
  font-size: 13px;
  font-weight: 600;
  color: #333;
}

.close-detail-btn {
  background: none;
  border: none;
  cursor: pointer;
  padding: 4px;
  color: #999;
}

.close-detail-btn:hover {
  color: #333;
}

.detail-body {
  padding: 12px;
}

.detail-section {
  margin-bottom: 12px;
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
}

.result-json {
  background: #fff;
  border: 1px solid #e8e8e8;
  border-radius: 4px;
  padding: 8px;
  font-size: 11px;
  overflow: auto;
  max-height: 150px;
}

.feedback {
  color: #ff4d4f;
}

.metrics-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(120px, 1fr));
  gap: 8px;
}

.metric-item {
  background: #fff;
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

.status-badge {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 11px;
  font-weight: 500;
}

.status-sota {
  background: #e6f7ff;
  color: #1890ff;
  border: 1px solid #91d5ff;
}

.status-passed {
  background: #f6ffed;
  color: #52c41a;
  border: 1px solid #b7eb8f;
}

.status-failed {
  background: #fff2f0;
  color: #ff4d4f;
  border: 1px solid #ffccc7;
}

.status-pending {
  background: #fafafa;
  color: #999;
  border: 1px solid #d9d9d9;
}

.sota-badge {
  display: inline-block;
  margin-left: 8px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  padding: 2px 8px;
  border-radius: 10px;
  font-size: 10px;
  font-weight: 600;
}
</style>
