/** Approval Dashboard — API 服务层 */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface ApprovalDashboard { pending: number; reviewed: number; [key: string]: unknown }
export interface ApprovalRequest { request_id: string; type: string; status: string; created_at: string; [key: string]: unknown }

export async function fetchDashboard(): Promise<ApprovalDashboard> {
  const res = await http.get(buildApiPath(API_CONFIG.GOVERNANCE, '/approval-dashboard'))
  return res.data.data
}
export async function fetchRequests(params?: Record<string, unknown>): Promise<ApprovalRequest[]> {
  const res = await http.get(buildApiPath(API_CONFIG.GOVERNANCE, '/approval-requests'), { params })
  return res.data.data
}
export async function decideRequest(requestId: string, decision: string, reason?: string): Promise<void> {
  await http.post(buildApiPath(API_CONFIG.GOVERNANCE, `/approval-requests/${requestId}/decide`), {
    decision, reason
  })
}
