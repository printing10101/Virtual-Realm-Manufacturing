//! 灵境制造 V4 - Tauri 桌面应用入口
//!
//! 该 crate 负责：
//! 1. 启动 Tauri 运行时与窗口
//! 2. 启动由 PyInstaller 打包的 Python 后端 Sidecar 进程
//! 3. 暴露 IPC 命令供前端调用
//! 4. 监听应用退出事件，优雅终止后端

mod commands;
mod sidecar;

use std::sync::Arc;

use tauri::{Manager, RunEvent, WindowEvent};

use crate::commands::{
    get_app_version, get_backend_port, get_backend_state, ping_backend, restart_backend,
    start_backend, stop_backend, AppState,
};
use crate::sidecar::SidecarManager;

/// 默认后端端口（与 `python/app/main.py` 中 uvicorn 启动端口保持一致）
pub const DEFAULT_BACKEND_PORT: u16 = 8000;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let _ = env_logger::try_init();

    let manager = Arc::new(SidecarManager::new(DEFAULT_BACKEND_PORT));
    let app_state = AppState {
        sidecar: manager.clone(),
    };

    let manager_for_setup = manager.clone();

    let app = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .plugin(tauri_plugin_dialog::init())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            get_backend_state,
            start_backend,
            stop_backend,
            restart_backend,
            ping_backend,
            get_app_version,
            get_backend_port,
        ])
        .setup(move |app| {
            let app_handle = app.handle().clone();

            // 启动 Sidecar（仅在 desktop 平台执行；移动端暂不打包后端）
            #[cfg(desktop)]
            {
                let manager_for_start = manager_for_setup.clone();
                let app_for_start = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    // 应用启动后稍等片刻，让 UI 有时间显示"启动中"状态
                    tokio::time::sleep(std::time::Duration::from_millis(300)).await;
                    if let Err(e) = manager_for_start.start(&app_for_start).await {
                        log::error!("Sidecar 启动失败: {e}");
                    }
                });
            }

            // 为主窗口注册关闭事件：主窗口关闭 -> 优雅停止后端
            if let Some(main_window) = app.get_webview_window("main") {
                let manager_for_close = manager_for_setup.clone();
                let app_for_close = app_handle.clone();
                main_window.on_window_event(move |event| {
                    if let WindowEvent::CloseRequested { .. } = event {
                        let mgr = manager_for_close.clone();
                        let app_h = app_for_close.clone();
                        tauri::async_runtime::block_on(async move {
                            if let Err(e) = mgr.stop(&app_h).await {
                                log::warn!("停止 sidecar 时出现错误: {e}");
                            }
                        });
                    }
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("启动 Tauri 应用失败");

    let manager_for_run = manager.clone();
    app.run(move |_app_handle, event| match event {
        RunEvent::ExitRequested { .. } => {
            log::info!("收到 ExitRequested，进程即将退出");
        }
        RunEvent::Exit => {
            log::info!("Tauri RunEvent::Exit 已触发");
            // 兜底清理：阻止 Rust 端提前释放 SidecarManager
            let _ = manager_for_run;
        }
        _ => {}
    });
}
