export interface FileInfo {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified_at: string
  extension: string | null
}

export interface SidecarStatusResponse {
  is_running: boolean
  status: string
  pid: number | null
  port: number
  started_at: string | null
}

export interface AppInfo {
  app_name: string
  version: string
  tauri_version: string
  os: string
  os_version: string
  arch: string
  hostname: string
}
