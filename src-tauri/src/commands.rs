//! Tauri 命令模块：暴露给前端调用的 IPC 接口

use crate::sidecar::{BackendState, SidecarManager};
use std::sync::Arc;
use tauri::{AppHandle, Manager, Runtime, State};

/// 全局状态包装
pub struct AppState {
    pub sidecar: Arc<SidecarManager>,
}

/// 获取后端当前运行状态
#[tauri::command]
pub fn get_backend_state(state: State<'_, AppState>) -> BackendState {
    state.sidecar.state()
}

/// 主动启动后端
#[tauri::command]
pub async fn start_backend<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, AppState>,
) -> Result<BackendState, String> {
    state.sidecar.start(&app).await?;
    Ok(state.sidecar.state())
}

/// 主动停止后端
#[tauri::command]
pub async fn stop_backend<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, AppState>,
) -> Result<BackendState, String> {
    state.sidecar.stop(&app).await?;
    Ok(state.sidecar.state())
}

/// 重启后端
#[tauri::command]
pub async fn restart_backend<R: Runtime>(
    app: AppHandle<R>,
    state: State<'_, AppState>,
) -> Result<BackendState, String> {
    state.sidecar.restart(&app).await?;
    Ok(state.sidecar.state())
}

/// 健康检查：探测后端 HTTP 端点
#[tauri::command]
pub async fn ping_backend(state: State<'_, AppState>) -> Result<bool, String> {
    let port = state.sidecar.state().port;
    let url = format!("http://127.0.0.1:{port}/api/health/ping");
    let client = reqwest::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .map_err(|e| e.to_string())?;
    match client.get(&url).send().await {
        Ok(resp) if resp.status().is_success() => Ok(true),
        Ok(_) => Ok(false),
        Err(_) => Ok(false),
    }
}

/// 获取 Tauri 应用的版本号
#[tauri::command]
pub fn get_app_version<R: Runtime>(app: AppHandle<R>) -> String {
    app.package_info().version.to_string()
}

/// 获取后端服务监听端口
#[tauri::command]
pub fn get_backend_port(state: State<'_, AppState>) -> u16 {
    state.sidecar.state().port
}
