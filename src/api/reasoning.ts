/**
 * 推理过程可视化 API
 * 负责获取推理轨迹数据、支持实时流式和歷史查询
 */

import http from '@/utils/http'

/** 推理步骤类型 */
export type StepType = 'task_routing' | 'physical_validation' | 'active_learning' | 'recommendation'

/** 步骤状态 */
export type StepStatus = 'pending' | 'running' | 'completed' | 'failed' | 'skipped'

/** 路由规则匹配 */
export interface RoutingRule {
  rule: string
  matched: boolean
  description?: string
}

/** 相似案例 */
export interface SimilarCase {
  taskId: string
  similarity: number
  result: string
  timestamp?: number
}

/** 物理校验参数 */
export interface ValidationParam {
  name: string
  value: number
  threshold: number
  unit?: string
  passed: boolean
}

/** 学习曲线数据点 */
export interface LearningCurvePoint {
  epoch: number
  loss: number
  accuracy?: number
}

/** 样本对比 */
export interface SampleComparison {
  source: string
  features: number[]
  label?: string
}

/** 依据数据（按步骤类型差异化） */
export interface EvidenceData {
  summary: string
  // 任务路由专属
  routingRules?: RoutingRule[]
  similarCases?: SimilarCase[]
  // 物理校验专属
  validationParams?: ValidationParam[]
  physicsFormulas?: string[]
  // 主动学习专属
  learningCurve?: LearningCurvePoint[]
  sampleComparison?: SampleComparison[]
}

/** 单个推理步骤 */
export interface ReasoningStep {
  id: string
  type: StepType
  title: string
  status: StepStatus
  timestamp: number
  duration?: number
  confidence?: number
  evidence: EvidenceData
  branchPath?: string[]
}

/** 完整推理轨迹 */
export interface ReasoningTrace {
  traceId: string
  taskId: string
  steps: ReasoningStep[]
  startTime: number
  endTime?: number
  overallConfidence?: number
}

/** API 响应包装 */
interface ApiResponse<T> {
  data: T
  message?: string
  status?: number
}

/**
 * 获取推理轨迹详情
 * @param traceId 推理轨迹ID
 */
export async function getReasoningTrace(traceId: string): Promise<ReasoningTrace> {
  try {
    const response = await http.get<ApiResponse<ReasoningTrace>>(
      `/reasoning/trace/${traceId}`
    )
    return response.data.data
  } catch (error) {
    console.error('获取推理轨迹失败:', error)
    throw error
  }
}

/**
 * 获取任务的推理轨迹列表
 * @param taskId 任务ID
 */
export async function listReasoningTraces(taskId: string): Promise<ReasoningTrace[]> {
  try {
    const response = await http.get<ApiResponse<ReasoningTrace[]>>(
      `/reasoning/traces/${taskId}`
    )
    return response.data.data
  } catch (error) {
    console.error('获取推理轨迹列表失败:', error)
    throw error
  }
}

/**
 * 获取推理轨迹的 SSE 流地址
 * @param traceId 推理轨迹ID
 */
export function getReasoningStreamUrl(traceId: string): string {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  return `${baseUrl}/api/v1/reasoning/${traceId}/stream`
}
