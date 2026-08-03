/** Material Management — API 服务层 */
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

export interface Material { id: string; name: string; type: string; [key: string]: unknown }
export interface MaterialStats { total: number; by_type: Record<string, number> }

export async function fetchMaterials(params?: Record<string, unknown>): Promise<Material[]> {
  const res = await http.get(API_CONFIG.MATERIALS, { params })
  return res.data.data
}
export async function fetchMaterialStats(): Promise<MaterialStats> {
  const res = await http.get(API_CONFIG.MATERIALS + '/stats/summary')
  return res.data.data
}
