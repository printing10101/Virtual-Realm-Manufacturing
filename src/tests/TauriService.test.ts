import { describe, it, expect } from 'vitest'
import { TauriService } from '@/services/tauri'
import type { FileInfo, SidecarStatusResponse, AppInfo } from '@/types/tauri'

describe('TauriService', () => {
  const service = new TauriService()

  it('should be defined', () => {
    expect(service).toBeDefined()
  })

  it('should have all required methods', () => {
    expect(typeof service.getAppDataDir).toBe('function')
    expect(typeof service.saveFile).toBe('function')
    expect(typeof service.readFile).toBe('function')
    expect(typeof service.listFiles).toBe('function')
    expect(typeof service.deleteFile).toBe('function')
    expect(typeof service.createDirectory).toBe('function')
    expect(typeof service.startSidecar).toBe('function')
    expect(typeof service.stopSidecar).toBe('function')
    expect(typeof service.checkSidecarStatus).toBe('function')
    expect(typeof service.getAppInfo).toBe('function')
    expect(typeof service.openExternalUrl).toBe('function')
  })
})

describe('TypeScript Types', () => {
  it('FileInfo type should have correct shape', () => {
    const fileInfo: FileInfo = {
      name: 'test.txt',
      path: '/path/to/test.txt',
      is_dir: false,
      size: 1024,
      modified_at: '2024-01-01T00:00:00Z',
      extension: 'txt'
    }
    expect(fileInfo.name).toBe('test.txt')
    expect(fileInfo.is_dir).toBe(false)
  })

  it('SidecarStatusResponse type should have correct shape', () => {
    const status: SidecarStatusResponse = {
      is_running: true,
      status: 'running',
      pid: 12345,
      port: 8080,
      started_at: '2024-01-01T00:00:00Z'
    }
    expect(status.is_running).toBe(true)
    expect(status.pid).toBe(12345)
  })

  it('AppInfo type should have correct shape', () => {
    const appInfo: AppInfo = {
      app_name: 'lingjing-v4',
      version: '0.1.0',
      tauri_version: '2.0.0',
      os: 'windows',
      os_version: '10',
      arch: 'x86_64',
      hostname: 'localhost'
    }
    expect(appInfo.app_name).toBe('lingjing-v4')
    expect(appInfo.version).toBe('0.1.0')
  })
})
