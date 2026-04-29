import { invoke } from '@tauri-apps/api/core'
import type { FileInfo, SidecarStatusResponse, AppInfo } from '@/types/tauri'

export class TauriService {
  async getAppDataDir(): Promise<string> {
    return invoke<string>('get_app_data_dir')
  }

  async saveFile(filePath: string, content: string): Promise<void> {
    return invoke<void>('save_file', { filePath, content })
  }

  async readFile(filePath: string): Promise<string> {
    return invoke<string>('read_file', { filePath })
  }

  async listFiles(dirPath: string, extension?: string): Promise<FileInfo[]> {
    return invoke<FileInfo[]>('list_files', { dirPath, extension })
  }

  async deleteFile(filePath: string, recursive = false): Promise<void> {
    return invoke<void>('delete_file', { filePath, recursive })
  }

  async createDirectory(dirPath: string, recursive = false): Promise<void> {
    return invoke<void>('create_directory', { dirPath, recursive })
  }

  async startSidecar(port?: number): Promise<number> {
    return invoke<number>('start_sidecar', { port })
  }

  async stopSidecar(): Promise<void> {
    return invoke<void>('stop_sidecar')
  }

  async checkSidecarStatus(): Promise<SidecarStatusResponse> {
    return invoke<SidecarStatusResponse>('check_sidecar_status')
  }

  async getAppInfo(): Promise<AppInfo> {
    return invoke<AppInfo>('get_app_info')
  }

  async openExternalUrl(url: string): Promise<void> {
    return invoke<void>('open_external_url', { url })
  }
}

export const tauriService = new TauriService()
export default tauriService
