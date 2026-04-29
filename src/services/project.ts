import { invoke } from '@tauri-apps/api/core'
import type { ProjectMeta } from '@/types/persistence'

export async function getProjects(): Promise<ProjectMeta[]> {
  return invoke<ProjectMeta[]>('get_projects')
}

export async function createProject(name: string, description: string): Promise<ProjectMeta> {
  return invoke<ProjectMeta>('add_project_cmd', { name, description })
}

export async function deleteProject(projectId: string): Promise<void> {
  return invoke<void>('delete_project_cmd', { projectId })
}
