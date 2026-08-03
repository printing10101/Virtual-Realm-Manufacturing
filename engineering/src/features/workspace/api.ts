/** Workspace 功能模块 — API 服务层。

V3.0 Feature-Sliced Design: 将 views/Workspace.vue 中直接的 http 调用
封装到本模块，视图组件通过 import 使用，而非直接依赖 http 客户端。

模式：
  views/Workspace.vue → features/workspace/api.ts → shared/api/http.ts
*/

import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

// =============================================================================
// 类型定义
// =============================================================================

export interface LNNPredictRequest {
  model_name: string
  features: number[]
  [key: string]: unknown
}

export interface LNNPredictResponse {
  prediction: number[]
  confidence?: number
  inference_time_ms?: number
}

export interface LNNTrainingConfig {
  model_name: string
  dataset_path: string
  epochs?: number
  learning_rate?: number
  [key: string]: unknown
}

export interface DryRunResponse {
  estimated_epochs: number
  estimated_time_seconds: number
  dataset_size: number
  warnings?: string[]
}

export interface TrainingJob {
  job_id: string
  status: string
  [key: string]: unknown
}

export interface LNNModel {
  name: string
  version: string
  created_at: string
  [key: string]: unknown
}

// =============================================================================
// API 函数
// =============================================================================

/** LNN 推理预测 */
export async function predictLNN(req: LNNPredictRequest): Promise<LNNPredictResponse> {
  const res = await http.post(buildApiPath(API_CONFIG.LNN, '/predict'), req)
  return res.data.data
}

/** 训练 Dry Run（预估资源消耗） */
export async function trainDryRun(req: LNNTrainingConfig): Promise<DryRunResponse> {
  const res = await http.post(buildApiPath(API_CONFIG.LNN, '/train/dry_run'), req)
  return res.data.data
}

/** 启动 LNN 训练任务 */
export async function startTraining(req: LNNTrainingConfig): Promise<TrainingJob> {
  const res = await http.post(buildApiPath(API_CONFIG.LNN, '/train'), req)
  return res.data.data
}

/** 取消运行中的训练任务 */
export async function cancelJob(jobId: string): Promise<void> {
  await http.post(buildApiPath(API_CONFIG.JOBS, `/${jobId}/cancel`))
}

/** 记录审计日志 */
export async function recordAuditLog(entry: Record<string, unknown>): Promise<void> {
  await http.post(buildApiPath(API_CONFIG.USER_SOVEREIGNTY, '/audit-log/record'), null, {
    params: entry,
  })
}

/** 获取可用 LNN 模型列表 */
export async function listModels(): Promise<LNNModel[]> {
  const res = await http.get(buildApiPath(API_CONFIG.LNN, '/models'))
  return res.data.data
}
