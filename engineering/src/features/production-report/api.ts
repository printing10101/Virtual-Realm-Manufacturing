/** Production Report — API 服务层 */
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

export interface ProductionDashboard { [key: string]: unknown }
export interface ProductionStats { [key: string]: unknown }
export interface ProductionRecord { id: string; created_at: string; [key: string]: unknown }

export async function fetchDashboard(signal?: AbortSignal): Promise<ProductionDashboard> {
  const res = await http.get(API_CONFIG.PRODUCTION + '/dashboard', { signal })
  return res.data.data
}
export async function fetchStats(days: number, signal?: AbortSignal): Promise<ProductionStats> {
  const res = await http.get(API_CONFIG.PRODUCTION + '/stats', { params: { days }, signal })
  return res.data.data
}
export async function fetchRecords(limit = 20, signal?: AbortSignal): Promise<ProductionRecord[]> {
  const res = await http.get(API_CONFIG.PRODUCTION + '/records', { params: { limit }, signal })
  return res.data.data
}
