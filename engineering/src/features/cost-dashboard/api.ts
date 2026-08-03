/** Cost Dashboard — API service layer */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface CostPolicy { id: string; name: string; limit: number; current: number }
export interface CostSummary { total: number; by_category: Record<string, number> }

export async function fetchPolicies(): Promise<CostPolicy[]> {
  const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/policies'))
  return res.data.data
}
export async function fetchSummary(params?: Record<string, unknown>): Promise<CostSummary> {
  const res = await http.get(buildApiPath(API_CONFIG.COST_BUDGET, '/summary'), { params })
  return res.data.data
}
