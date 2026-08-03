/** Simulation View — API service layer */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface SimRequest { gcode_path: string; stock_path: string; tool: Record<string, unknown> }
export interface SimTask { task_id: string; status: string }

export async function submitSimulation(req: SimRequest): Promise<SimTask> {
  const res = await http.post(buildApiPath(API_CONFIG.SIMULATION, '/run/async'), req)
  return res.data.data
}
export async function getSimulationStatus(taskId: string): Promise<SimTask> {
  const res = await http.get(buildApiPath(API_CONFIG.SIMULATION, `/status/${taskId}`))
  return res.data.data
}
export async function getHistory(projectId?: string): Promise<SimTask[]> {
  const params = projectId ? { project_id: projectId } : {}
  const res = await http.get(buildApiPath(API_CONFIG.SIMULATION, '/history'), { params })
  return res.data.data
}
