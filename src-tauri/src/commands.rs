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

/// 关闭 splashscreen 窗口并显示主窗口
///
/// 前端在 Vue 应用挂载完成、首屏渲染就绪后调用此命令，
/// 实现"启动动画 → 主应用"的平滑切换，避免出现白屏过渡。
#[tauri::command]
pub fn close_splashscreen<R: Runtime>(app: AppHandle<R>) -> Result<(), String> {
    // 先显示主窗口（避免先关 splash 再显主窗口造成的视觉空档）
    if let Some(main_window) = app.get_webview_window("main") {
        main_window
            .show()
            .map_err(|e| format!("显示主窗口失败: {e}"))?;
        // 把焦点切到主窗口
        let _ = main_window.set_focus();
    } else {
        log::warn!("未找到 main 窗口，无法切换");
    }

    // 关闭 splashscreen 窗口
    if let Some(splash_window) = app.get_webview_window("splashscreen") {
        splash_window
            .close()
            .map_err(|e| format!("关闭 splashscreen 窗口失败: {e}"))?;
    } else {
        log::warn!("未找到 splashscreen 窗口，可能已被关闭");
    }

    Ok(())
}
