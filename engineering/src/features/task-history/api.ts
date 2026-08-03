/** Task History — API service layer */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface JobRecord { id: string; type: string; status: string; created_at: string }

export async function fetchJobs(params?: Record<string, unknown>): Promise<JobRecord[]> {
  const res = await http.get(API_CONFIG.JOBS, { params })
  return res.data.data
}
export async function resubmitTraining(config: Record<string, unknown>): Promise<JobRecord> {
  const res = await http.post(buildApiPath(API_CONFIG.LNN, '/train'), config)
  return res.data.data
}
export async function resubmitInference(config: Record<string, unknown>): Promise<JobRecord> {
  const res = await http.post(buildApiPath(API_CONFIG.LNN, '/batch-inference'), config)
  return res.data.data
}
