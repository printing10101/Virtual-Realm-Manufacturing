// 切削体验（数据飞轮）API 客户端（P2-3 前端侧）
//
// 对应后端路由：/api/v1/experience
// - POST /capture      单条采集（手工录入）
// - POST /batch        批量采集（MTConnect 管道）
// - GET  /             分页查询
// - GET  /stats        聚合统计
// - GET  /{id}         详情
// - DELETE /{id}       删除

import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

const BASE = `${API_CONFIG.V1}/experience`

// 类型定义（与后端 app/contracts/cutting_experience.py 对齐）

export type MachiningType =
  | 'milling'
  | 'turning'
  | 'drilling'
  | 'tapping'
  | 'boring'
  | 'grooving'
  | 'threading'

export type MachiningResult = 'ok' | 'rework' | 'scrap'

export type CoolantMode = 'off' | 'flood' | 'mist' | 'through_tool'

export interface CuttingParameters {
  depth_of_cut_mm: number
  feed_mm_per_rev: number
  spindle_rpm: number
  cutting_speed_m_min?: number | null
  stepover_mm?: number | null
  coolant?: CoolantMode
}

export interface CuttingResults {
  cycle_time_s: number
  surface_roughness_ra?: number | null
  tool_wear_percent?: number | null
  dimensional_error_mm?: number | null
  result: MachiningResult
}

export interface MachiningAnomaly {
  anomaly_type: string
  severity: number
  message?: string
  measured_value?: number | null
  threshold_value?: number | null
}

export interface CuttingExperiencePayload {
  job_id?: string | null
  machine_id: string
  program_number?: string
  tool_id: string
  material?: string
  machining_type?: MachiningType
  parameters: CuttingParameters
  results: CuttingResults
  anomalies?: MachiningAnomaly[]
  tags?: Record<string, unknown>
  operator?: string | null
  source?: 'manual' | 'mtconnect' | 'api'
}

export interface CuttingExperienceRecord extends CuttingExperiencePayload {
  id: string
  created_at: string
  updated_at: string
}

export interface ExperienceListResult {
  records: CuttingExperienceRecord[]
  total: number
  limit: number
  offset: number
}

export interface ExperienceStats {
  total_records: number
  avg_cycle_time_s?: number | null
  avg_surface_roughness_ra?: number | null
  avg_tool_wear_percent?: number | null
  ok_rate?: number | null
  anomaly_rate?: number | null
}

export interface ExperienceQueryParams {
  machine_id?: string
  tool_id?: string
  material?: string
  machining_type?: MachiningType
  result?: MachiningResult
  has_anomaly?: boolean
  start_time?: string
  end_time?: string
  limit?: number
  offset?: number
}

// API 函数

/** 单条采集（手工录入 / 现场实测） */
export async function captureExperience(
  payload: CuttingExperiencePayload,
): Promise<CuttingExperienceRecord> {
  const resp = await http.post(`${BASE}/capture`, payload)
  return resp.data?.data ?? resp.data
}

/** 批量采集（MTConnect 管道 / CSV 导入） */
export async function batchCaptureExperiences(
  payloads: CuttingExperiencePayload[],
): Promise<{ inserted: number; requested: number }> {
  const resp = await http.post(`${BASE}/batch`, payloads)
  return resp.data?.data ?? resp.data
}

/** 分页查询 */
export async function queryExperiences(
  params: ExperienceQueryParams,
): Promise<ExperienceListResult> {
  const resp = await http.get(BASE, { params })
  return resp.data?.data ?? resp.data
}

/** 聚合统计（仪表盘） */
export async function getExperienceStats(params: {
  machine_id?: string
  tool_id?: string
}): Promise<ExperienceStats> {
  const resp = await http.get(`${BASE}/stats`, { params })
  return resp.data?.data ?? resp.data
}

/** 单条详情 */
export async function getExperienceDetail(
  recordId: string,
): Promise<CuttingExperienceRecord> {
  const resp = await http.get(`${BASE}/${encodeURIComponent(recordId)}`)
  return resp.data?.data ?? resp.data
}

/** 删除（管理用途） */
export async function deleteExperience(
  recordId: string,
): Promise<{ deleted: boolean; id: string }> {
  const resp = await http.delete(`${BASE}/${encodeURIComponent(recordId)}`)
  return resp.data?.data ?? resp.data
}
