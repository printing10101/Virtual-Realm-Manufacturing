import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import http from '@/utils/http'
import { extractErrorMessage } from '@/utils/errorUtils'

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
  metrics: Record<string, unknown>
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
    goal_chain: unknown[]
    current_stage: string
    conversation_history: unknown[]
    injected_skills: string[]
    active_context_keys: string[]
    custom_context: Record<string, unknown>
  }
  checkpoint: CheckpointInfo | null
  checkpoints_history: CheckpointInfo[]
  memory: MemoryEntryInfo[]
  state_version: {
    state_version: number
    schema_version: string
    migration_history: unknown[]
  }
  metadata: Record<string, unknown>
}

const API_BASE = API_CONFIG.AGENTS

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

  /**
   * 获取 Agent 列表
   * @returns void
   */
  async function fetchAgents(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const params: Record<string, string> = {}
      if (statusFilter.value) params.status = statusFilter.value
      const response = await http.get(API_BASE + '/', { params })
      agents.value = response.data.data || []
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '获取Agent列表失败')
    } finally {
      loading.value = false
    }
  }

  /**
   * 获取 Agent 详情
   * @param agentId - Agent ID
   * @returns Agent详情或null
   */
  async function fetchAgentDetail(agentId: string): Promise<AgentDetail | null> {
    detailLoading.value = true
    error.value = null
    try {
      const response = await http.get(`${API_BASE}/${agentId}`)
      currentAgent.value = response.data.data
      return response.data.data as AgentDetail
    } catch (e: unknown) {
      error.value = extractErrorMessage(e, '获取Agent详情失败')
      return null
    } finally {
      detailLoading.value = false
    }
  }

  /**
   * 保存 Agent 检查点
   * @param agentId - Agent ID
   * @param data - 检查点数据
   * @returns 检查点数据
   */
  async function saveCheckpoint(agentId: string, data: Record<string, unknown>): Promise<unknown> {
    const response = await http.post(`${API_BASE}/${agentId}/checkpoints/save`, data)
    return response.data.data
  }

  /**
   * 回滚到指定检查点
   * @param agentId - Agent ID
   * @param checkpointId - 检查点ID
   * @returns 回滚结果
   */
  async function rollbackCheckpoint(agentId: string, checkpointId: string): Promise<unknown> {
    const response = await http.post(`${API_BASE}/${agentId}/checkpoints/rollback`, {
      checkpoint_id: checkpointId,
    })
    return response.data.data
  }

  /**
   * 克隆 Agent
   * @param sourceId - 源Agent ID
   * @param targetId - 目标Agent ID
   * @returns 克隆结果
   */
  async function cloneAgent(sourceId: string, targetId: string): Promise<unknown> {
    const response = await http.post(`${API_BASE}/${sourceId}/clone`, {
      target_agent_id: targetId,
    })
    return response.data.data
  }

  /**
   * 恢复 Agent
   * @param agentId - Agent ID
   * @returns 恢复结果
   */
  async function resumeAgent(agentId: string): Promise<unknown> {
    const response = await http.post(`${API_BASE}/${agentId}/resume`)
    return response.data.data
  }

  /**
   * 保存 Agent 状态
   * @param agentId - Agent ID
   * @param payload - 状态数据
   * @returns 保存结果
   */
  async function saveAgentState(agentId: string, payload: Record<string, unknown>): Promise<unknown> {
    const response = await http.post(`${API_BASE}/${agentId}/save`, payload)
    return response.data.data
  }

  /**
   * 开始 Agent 心跳
   * @param agentId - Agent ID
   */
  async function startHeartbeat(agentId: string): Promise<void> {
    await http.post(`${API_BASE}/${agentId}/heartbeat/start`)
  }

  /**
   * 停止 Agent 心跳
   * @param agentId - Agent ID
   */
  async function stopHeartbeat(agentId: string): Promise<void> {
    await http.post(`${API_BASE}/${agentId}/heartbeat/stop`)
  }

  /**
   * 删除 Agent
   * @param agentId - Agent ID
   */
  async function deleteAgent(agentId: string): Promise<void> {
    await http.delete(`${API_BASE}/${agentId}`)
    agents.value = agents.value.filter((a) => a.agent_id !== agentId)
  }

  /**
   * 更新 Agent 上下文
   * @param agentId - Agent ID
   * @param updates - 更新数据
   * @returns 更新结果
   */
  async function updateContext(agentId: string, updates: Record<string, unknown>): Promise<unknown> {
    const response = await http.post(`${API_BASE}/${agentId}/context/update`, { updates })
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
