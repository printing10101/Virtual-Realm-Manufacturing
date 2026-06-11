/**
 * 后端进程状态管理 Composable
 *
 * 通过 Tauri 提供的 IPC 与后端 Sidecar 管理器通信：
 * - get_backend_state: 获取当前快照
 * - start_backend / stop_backend / restart_backend: 主动控制
 * - ping_backend: 主动 HTTP 健康探测
 *
 * 同时订阅 'sidecar://state' 事件，接收后端状态变化推送。
 */

import { reactive, ref, onMounted, onBeforeUnmount } from 'vue'

export type BackendStatusKind =
  | 'idle'
  | 'starting'
  | 'running'
  | 'stopping'
  | 'crashed'
  | 'failed'
  | 'stopped'

export interface BackendState {
  status: BackendStatusKind
  pid: number | null
  progress: number
  message: string
  last_error: string | null
  started_at: string | null
  restart_count: number
  port: number
}

const DEFAULT_STATE: BackendState = {
  status: 'idle',
  pid: null,
  progress: 0,
  message: '等待启动后端服务',
  last_error: null,
  started_at: null,
  restart_count: 0,
  port: 8000,
}

/**
 * 检测当前是否运行在 Tauri 容器内
 */
export function isTauriEnv(): boolean {
  return typeof window !== 'undefined' && Boolean((window as any).__TAURI_INTERNALS__)
}

/**
 * 异步导入 @tauri-apps/api/core invoke，避免在非 Tauri 环境下导入失败
 */
async function tauriInvoke<T = any>(cmd: string, args?: Record<string, unknown>): Promise<T> {
  const mod = await import('@tauri-apps/api/core')
  return mod.invoke<T>(cmd, args)
}

async function tauriListen<T = any>(
  event: string,
  handler: (payload: T) => void,
): Promise<() => void> {
  const mod = await import('@tauri-apps/api/event')
  const un = await mod.listen<T>(event, (e) => handler(e.payload))
  return un
}

let _state: ReturnType<typeof reactive<BackendState>> | null = null
let _unlisten: Array<() => void> = []
let _initialized = false

export function useBackendStatus() {
  if (!_state) {
    _state = reactive<BackendState>({ ...DEFAULT_STATE })
  }

  const loading = ref(false)
  const tauriMode = ref(false)

  async function refresh() {
    if (!isTauriEnv()) {
      tauriMode.value = false
      return
    }
    tauriMode.value = true
    try {
      const next = await tauriInvoke<BackendState>('get_backend_state')
      Object.assign(_state!, next)
    } catch (e) {
      console.warn('[useBackendStatus] refresh failed', e)
    }
  }

  async function start() {
    if (!isTauriEnv()) return
    loading.value = true
    try {
      const next = await tauriInvoke<BackendState>('start_backend')
      Object.assign(_state!, next)
    } catch (e) {
      console.error('[useBackendStatus] start failed', e)
      if (_state) {
        _state.last_error = String(e)
        _state.status = 'failed'
      }
    } finally {
      loading.value = false
    }
  }

  async function stop() {
    if (!isTauriEnv()) return
    loading.value = true
    try {
      const next = await tauriInvoke<BackendState>('stop_backend')
      Object.assign(_state!, next)
    } catch (e) {
      console.error('[useBackendStatus] stop failed', e)
    } finally {
      loading.value = false
    }
  }

  async function restart() {
    if (!isTauriEnv()) return
    loading.value = true
    try {
      const next = await tauriInvoke<BackendState>('restart_backend')
      Object.assign(_state!, next)
    } catch (e) {
      console.error('[useBackendStatus] restart failed', e)
      if (_state) {
        _state.last_error = String(e)
        _state.status = 'failed'
      }
    } finally {
      loading.value = false
    }
  }

  async function ping(): Promise<boolean> {
    if (!isTauriEnv()) return true
    try {
      return await tauriInvoke<boolean>('ping_backend')
    } catch {
      return false
    }
  }

  if (!_initialized) {
    _initialized = true
    onMounted(async () => {
      await refresh()
      try {
        const offState = await tauriListen<BackendState>('sidecar://state', (payload) => {
          if (_state && payload) Object.assign(_state, payload)
        })
        const offTerm = await tauriListen<{ code: number | null; signal: number | null }>(
          'sidecar://terminated',
          (payload) => {
            if (!_state) return
            if (_state.status !== 'stopping' && _state.status !== 'stopped') {
              _state.status = 'crashed'
              _state.message = `后端进程异常退出 (code=${payload?.code ?? '?'})`
              _state.pid = null
            }
          },
        )
        const offError = await tauriListen<string>('sidecar://error', (msg) => {
          if (_state) _state.last_error = msg
        })
        _unlisten.push(offState, offTerm, offError)
      } catch (e) {
        console.warn('[useBackendStatus] listen failed', e)
      }
    })

    onBeforeUnmount(() => {
      // 全局单例：不卸载监听器，确保跨组件状态一致
    })
  }

  return {
    state: _state!,
    loading,
    tauriMode,
    refresh,
    start,
    stop,
    restart,
    ping,
  }
}
