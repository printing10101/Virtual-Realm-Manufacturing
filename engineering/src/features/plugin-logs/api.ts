/** Plugin Logs — API service layer */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface PluginLog { id: string; level: string; message: string; timestamp: string }

export async function fetchPluginLogs(params?: Record<string, unknown>): Promise<PluginLog[]> {
  const res = await http.get(buildApiPath(API_CONFIG.PLUGINS, '/logs'), { params })
  return res.data.data
}
