/** Quality Inspection — API 服务层 */
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

export interface QualityStats { total: number; passed: number; failed: number; [key: string]: unknown }
export interface Inspection { id: string; status: string; result: string; created_at: string; [key: string]: unknown }

export async function fetchQualityStats(): Promise<QualityStats> {
  const res = await http.get(API_CONFIG.QUALITY + '/stats/')
  return res.data.data
}
export async function fetchInspections(params?: Record<string, unknown>): Promise<Inspection[]> {
  const res = await http.get(API_CONFIG.QUALITY + '/inspections', { params })
  return res.data.data
}
