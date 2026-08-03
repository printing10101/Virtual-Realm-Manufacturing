/** Home — API service layer */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface SystemStatus { version: string; uptime: number }
export interface ActivityBrief { alerts: unknown[]; recent: unknown[] }

export async function fetchSystemStatus(): Promise<SystemStatus> {
  const res = await http.get(buildApiPath(API_CONFIG.V1, '/system/status'))
  return res.data.data
}
export async function fetchActivityBrief(): Promise<ActivityBrief> {
  const res = await http.get(buildApiPath(API_CONFIG.V1, '/activity/brief'))
  return res.data.data
}
