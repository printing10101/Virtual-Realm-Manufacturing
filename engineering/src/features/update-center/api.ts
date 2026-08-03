/** Update Center — API 服务层 */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface TemplateUpdate { id: string; version: string; changes: string; [key: string]: unknown }

export async function fetchUpdates(projectId: string): Promise<TemplateUpdate[]> {
  const res = await http.get(buildApiPath(API_CONFIG.V1, `/templates/updates/${projectId}`))
  return res.data.data
}
export async function applyUpdate(id: string): Promise<void> {
  await http.post(buildApiPath(API_CONFIG.V1, `/templates/updates/apply/${id}`))
}
export async function dismissUpdate(id: string): Promise<void> {
  await http.post(buildApiPath(API_CONFIG.V1, `/templates/updates/dismiss/${id}`))
}
