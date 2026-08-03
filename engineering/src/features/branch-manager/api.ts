/** Branch Manager — API service layer */
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

export interface Branch { id: string; name: string; base_version: string }

export async function fetchBranches(url: string): Promise<Branch[]> {
  const res = await http.get(url)
  return res.data.data
}
export async function createBranch(data: Record<string, unknown>): Promise<Branch> {
  const res = await http.post(`${API_CONFIG.V1}/templates/branches`, data)
  return res.data.data
}
export async function mergeBranch(sourceId: string): Promise<void> {
  await http.post(`${API_CONFIG.V1}/templates/branches/${sourceId}/merge`)
}
