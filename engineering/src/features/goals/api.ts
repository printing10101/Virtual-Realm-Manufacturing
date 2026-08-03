/** Goals — API service layer */
import http from '@/utils/http'
import { API_CONFIG, buildApiPath } from '@/config/api'

export interface Goal { id: string; title: string; status: string; [key: string]: unknown }

export async function fetchGoals(): Promise<Goal[]> {
  const res = await http.get(buildApiPath(API_CONFIG.GOALS, '/list'))
  return res.data.data
}
export async function createGoal(data: Record<string, unknown>): Promise<Goal> {
  const res = await http.post(buildApiPath(API_CONFIG.GOALS, '/create'), data)
  return res.data.data
}
export async function updateGoalProgress(id: string, progress: number): Promise<void> {
  await http.put(buildApiPath(API_CONFIG.GOALS, `/${id}/progress`), { progress })
}
export async function deleteGoal(id: string): Promise<void> {
  await http.delete(buildApiPath(API_CONFIG.GOALS, `/${id}`))
}
