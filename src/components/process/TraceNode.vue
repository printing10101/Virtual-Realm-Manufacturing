<template>
  <div class="trace-node">
    <div 
      class="node-item" 
      :class="[
        'node-status-' + getNodeStatus(node),
        { 'node-selected': node.node_id === selectedId }
      ]"
      @click="$emit('select', node.node_id)"
    >
      <svg viewBox="0 0 1024 1024" width="14" height="14" class="node-icon">
        <path d="M512 64C264.6 64 64 264.6 64 512s200.6 448 448 448 448-200.6 448-448S759.4 64 512 64zm0 820c-205.4 0-372-166.6-372-372s166.6-372 372-372 372 166.6 372 372-166.6 372-372 372z" fill="currentColor"/>
      </svg>
      <span class="node-label">{{ getShortId(node.node_id) }}</span>
      <span class="node-hypothesis">{{ truncate(node.hypothesis, 30) }}</span>
      <span v-if="node.is_sota" class="sota-tag">SOTA</span>
    </div>

    <div class="node-children" v-if="children.length > 0">
      <TraceNode
        v-for="child in children"
        :key="child.node_id"
        :node="child"
        :nodes="nodes"
        :children-map="childrenMap"
        :selected-id="selectedId"
        @select="$emit('select', $event)"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

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
  node: TraceNode
  nodes: TraceNode[]
  childrenMap: Record<string, string[]>
  selectedId: string | null
}>()

const emit = defineEmits<{
  select: [nodeId: string]
}>()

const children = computed(() => {
  const childIds = props.childrenMap[props.node.node_id] || []
  return props.nodes.filter(n => childIds.includes(n.node_id))
})

function getNodeStatus(node: TraceNode): string {
  if (node.is_sota) return 'sota'
  if (node.validation_result?.passed) return 'passed'
  if (node.validation_result && !node.validation_result.passed) return 'failed'
  return 'pending'
}

function getShortId(id: string): string {
  return id.slice(0, 8)
}

function truncate(text: string, len: number): string {
  if (!text) return '无假设'
  return text.length > len ? text.slice(0, len) + '...' : text
}
</script>

<style scoped>
.trace-node {
  margin-left: 20px;
}

.node-item {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 8px;
  border-radius: 4px;
  cursor: pointer;
  margin: 4px 0;
  border: 1px solid transparent;
  transition: all 0.2s;
}

.node-item:hover {
  background: #f5f5f5;
}

.node-selected {
  background: #e6f7ff;
  border-color: #91d5ff;
}

.node-icon {
  color: #999;
}

.node-status-sota .node-icon {
  color: #1890ff;
}

.node-status-passed .node-icon {
  color: #52c41a;
}

.node-status-failed .node-icon {
  color: #ff4d4f;
}

.node-status-pending .node-icon {
  color: #d9d9d9;
}

.node-label {
  font-size: 11px;
  color: #999;
  font-family: monospace;
}

.node-hypothesis {
  font-size: 12px;
  color: #333;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.sota-tag {
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
  padding: 1px 6px;
  border-radius: 8px;
  font-size: 10px;
  font-weight: 600;
}

.node-children {
  position: relative;
}

.node-children::before {
  content: '';
  position: absolute;
  left: -10px;
  top: 0;
  bottom: 0;
  width: 1px;
  background: #e8e8e8;
}
</style>
