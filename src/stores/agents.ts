import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import axios from 'axios'

export interface AgentSummary {
  agent_id: string
  status: string
  current_task_id: string | null
  last_heartbeat: string | number
  updated_at: string | number
}

export interface CheckpointInfo {
  checkpoint_id: string
  epoch: number
  step: number
  best_metric: number | null
  best_metric_name: string
  checkpoint_type: string
  created_at: number
  metrics: Record<string, any>
  file_size_bytes: number
}

export interface MemoryEntryInfo {
  memory_id: string
  content: string
  memory_type: string
  importance: number
  created_at: number
  last_accessed: number
  access_count: number
  tags: string[]
}

export interface AgentDetail {
  agent_id: string
  current_task_id: string | null
  status: string
  last_heartbeat: number
  created_at: number
  updated_at: number
  session_context: {
    task_id: string | null
    task_type: string | null
    task_description: string
    goal_chain: any[]
    current_stage: string
    conversation_history: any[]
    injected_skills: string[]
    active_context_keys: string[]
    custom_context: Record<string, any>
  }
  checkpoint: CheckpointInfo | null
  checkpoints_history: CheckpointInfo[]
  memory: MemoryEntryInfo[]
  state_version: {
    state_version: number
    schema_version: string
    migration_history: any[]
  }
  metadata: Record<string, any>
}

const API_BASE = '/api/v1/agents'

export const useAgentStore = defineStore('agents', () => {
  const agents = ref<AgentSummary[]>([])
  const currentAgent = ref<AgentDetail | null>(null)
  const loading = ref(false)
  const detailLoading = ref(false)
  const error = ref<string | null>(null)
  const statusFilter = ref<string | null>(null)

  const activeAgents = computed(() =>
    agents.value.filter((a) => a.status === 'busy' || a.status === 'recovering')
  )
  const idleAgents = computed(() => agents.value.filter((a) => a.status === 'idle'))
  const errorAgents = computed(() =>
    agents.value.filter((a) => a.status === 'error' || a.status === 'stopped')
  )

  const statusStats = computed(() => ({
    total: agents.value.length,
    active: activeAgents.value.length,
    idle: idleAgents.value.length,
    error: errorAgents.value.length,
  }))

  function formatTime(ts: string | number): string {
    if (!ts) return '-'
    const d = new Date(typeof ts === 'string' ? ts : ts * 1000)
    return d.toLocaleString('zh-CN')
  }

  function statusTagType(status: string): 'success' | 'warning' | 'danger' | 'info' {
    const map: Record<string, 'success' | 'warning' | 'danger' | 'info'> = {
      idle: 'info',
      busy: 'success',
      paused: 'warning',
      error: 'danger',
      stopped: 'info',
      recovering: 'warning',
    }
    return map[status] || 'info'
  }

  function statusLabel(status: string): string {
    const map: Record<string, string> = {
      idle: '空闲',
      busy: '忙碌',
      paused: '暂停',
      error: '错误',
      stopped: '已停止',
      recovering: '恢复中',
    }
    return map[status] || status
  }

  async function fetchAgents() {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = {}
      if (statusFilter.value) params.status = statusFilter.value
      const response = await axios.get(API_BASE + '/', { params })
      agents.value = response.data.data || []
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message
    } finally {
      loading.value = false
    }
  }

  async function fetchAgentDetail(agentId: string) {
    detailLoading.value = true
    error.value = null
    try {
      const response = await axios.get(`${API_BASE}/${agentId}`)
      currentAgent.value = response.data.data
      return response.data.data as AgentDetail
    } catch (e: any) {
      error.value = e.response?.data?.detail || e.message
      return null
    } finally {
      detailLoading.value = false
    }
  }

  async function saveCheckpoint(agentId: string, data: Record<string, any>) {
    const response = await axios.post(`${API_BASE}/${agentId}/checkpoints/save`, data)
    return response.data.data
  }

  async function rollbackCheckpoint(agentId: string, checkpointId: string) {
    const response = await axios.post(`${API_BASE}/${agentId}/checkpoints/rollback`, {
      checkpoint_id: checkpointId,
    })
    return response.data.data
  }

  async function cloneAgent(sourceId: string, targetId: string) {
    const response = await axios.post(`${API_BASE}/${sourceId}/clone`, {
      target_agent_id: targetId,
    })
    return response.data.data
  }

  async function resumeAgent(agentId: string) {
    const response = await axios.post(`${API_BASE}/${agentId}/resume`)
    return response.data.data
  }

  async function saveAgentState(agentId: string, payload: Record<string, any>) {
    const response = await axios.post(`${API_BASE}/${agentId}/save`, payload)
    return response.data.data
  }

  async function startHeartbeat(agentId: string) {
    await axios.post(`${API_BASE}/${agentId}/heartbeat/start`)
  }

  async function stopHeartbeat(agentId: string) {
    await axios.post(`${API_BASE}/${agentId}/heartbeat/stop`)
  }

  async function deleteAgent(agentId: string) {
    await axios.delete(`${API_BASE}/${agentId}`)
    agents.value = agents.value.filter((a) => a.agent_id !== agentId)
  }

  async function updateContext(agentId: string, updates: Record<string, any>) {
    const response = await axios.post(`${API_BASE}/${agentId}/context/update`, { updates })
    return response.data.data
  }

  return {
    agents,
    currentAgent,
    loading,
    detailLoading,
    error,
    statusFilter,
    activeAgents,
    idleAgents,
    errorAgents,
    statusStats,
    formatTime,
    statusTagType,
    statusLabel,
    fetchAgents,
    fetchAgentDetail,
    saveCheckpoint,
    rollbackCheckpoint,
    cloneAgent,
    resumeAgent,
    saveAgentState,
    startHeartbeat,
    stopHeartbeat,
    deleteAgent,
    updateContext,
  }
})
