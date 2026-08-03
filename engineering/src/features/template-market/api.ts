/** Template Market — API service layer */
import http from '@/utils/http'
import { API_CONFIG } from '@/config/api'

export interface Template { id: string; name: string; version: string; category: string }
export interface TemplateDetail { id: string; name: string; content: unknown }

export async function fetchTemplates(params?: Record<string, unknown>): Promise<Template[]> {
  const res = await http.get(API_CONFIG.TEMPLATES, { params })
  return res.data.data
}
export async function fetchTemplate(id: string): Promise<TemplateDetail> {
  const res = await http.get(`${API_CONFIG.TEMPLATES}/${id}`)
  return res.data.data
}
export async function installTemplate(id: string): Promise<void> {
  await http.post(`${API_CONFIG.TEMPLATES}/${id}/install`)
}
export async function previewTemplate(id: string): Promise<TemplateDetail> {
  const res = await http.get(`${API_CONFIG.TEMPLATES}/${id}/preview`)
  return res.data.data
}
