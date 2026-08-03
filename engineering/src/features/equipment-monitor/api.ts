/** Equipment Monitor — API 服务层 */
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

export interface Equipment {
  id: string; name: string; status: string; [key: string]: unknown
}
export interface EquipmentStats {
  total: number; online: number; offline: number; [key: string]: unknown
}
export interface EquipmentAlarm {
  id: string; equipment_id: string; message: string; severity: string; timestamp: string
}

export async function fetchEquipment(): Promise<Equipment[]> {
  const res = await http.get(API_CONFIG.EQUIPMENT)
  return res.data.data
}
export async function fetchStats(): Promise<EquipmentStats> {
  const res = await http.get(API_CONFIG.EQUIPMENT + '/stats/')
  return res.data.data
}
export async function fetchAlarms(): Promise<EquipmentAlarm[]> {
  const res = await http.get(API_CONFIG.EQUIPMENT + '/alarms/')
  return res.data.data
}
