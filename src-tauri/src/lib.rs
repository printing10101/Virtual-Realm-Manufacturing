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

use tauri::{Manager, RunEvent, WebviewWindowBuilder, WindowEvent};

use crate::commands::{
    close_splashscreen, get_app_version, get_backend_port, get_backend_state, ping_backend,
    restart_backend, start_backend, stop_backend, AppState,
};
use crate::sidecar::SidecarManager;

/// 默认后端端口（与 `python/app/main.py` 中 uvicorn 启动端口保持一致）
pub const DEFAULT_BACKEND_PORT: u16 = 8000;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let _ = env_logger::try_init();

    // 清理 WebView2 残留锁文件，避免 HRESULT(0x800700AA) 错误。
    // 上次异常退出（如任务管理器强杀、崩溃）会留下 LOCK 文件，
    // 导致下次启动时 WebView2 创建失败，窗口变成 15×15 像素的空壳（白屏）。
    #[cfg(target_os = "windows")]
    {
        if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
            let identifier = "com.lingjing.manufacturing";
            let ebwebview_dir = std::path::Path::new(&local_app_data)
                .join(identifier)
                .join("EBWebView");
            if ebwebview_dir.exists() {
                log::info!("清理 WebView2 数据目录: {:?}", ebwebview_dir);
                if let Err(e) = std::fs::remove_dir_all(&ebwebview_dir) {
                    // 删除失败不阻塞启动，仅记录警告（可能是目录正在被其他进程占用）
                    log::warn!("清理 WebView2 数据目录失败: {e}");
                }
            }
        }
    }

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
            close_splashscreen,
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

            // 延迟创建主窗口：避免与 splashscreen 同时创建 WebView2
            // 导致 HRESULT(0x800700AA) "请求的资源在使用中" 错误。
            // splashscreen 的 WebView2 先独占 EBWebView 目录完成初始化，
            // 之后再创建 main 窗口的 WebView2，避免两个窗口争抢同一用户数据目录。
            #[cfg(desktop)]
            {
                let manager_for_close = manager_for_setup.clone();
                let app_for_close = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    // 等 splashscreen 的 WebView2 完全初始化（实测 500ms 足够）
                    tokio::time::sleep(std::time::Duration::from_millis(500)).await;

                    log::info!("开始延迟创建主窗口 main");
                    let main_window = match WebviewWindowBuilder::new(
                        &app_for_close,
                        "main",
                        tauri::WebviewUrl::App("index.html".into()),
                    )
                    .title("灵境制造 V4")
                    .inner_size(1440.0, 900.0)
                    .min_inner_size(1024.0, 700.0)
                    .resizable(true)
                    .fullscreen(false)
                    .center()
                    .decorations(true)
                    .transparent(false)
                    .visible(false)
                    .build()
                    {
                        Ok(w) => w,
                        Err(e) => {
                            log::error!("创建主窗口失败: {e}");
                            return;
                        }
                    };
                    log::info!("主窗口 main 创建成功");

                    // 诊断模式：自动打开 DevTools 以便排查白屏问题
                    #[cfg(debug_assertions)]
                    {
                        if let Some(win) = app_for_close.get_webview_window("main") {
                            let _ = win.open_devtools();
                        }
                    }
                    // release 模式下也打开 DevTools（devtools feature 已在 Cargo.toml 启用）
                    // 用于本次白屏问题排查，问题解决后可移除
                    {
                        if let Some(win) = app_for_close.get_webview_window("main") {
                            let _ = win.open_devtools();
                        }
                    }

                    // 为主窗口注册关闭事件：主窗口关闭 -> 优雅停止后端
                    let mgr = manager_for_close.clone();
                    let app_h = app_for_close.clone();
                    main_window.on_window_event(move |event| {
                        if let WindowEvent::CloseRequested { .. } = event {
                            let mgr = mgr.clone();
                            let app_h = app_h.clone();
                            tauri::async_runtime::block_on(async move {
                                if let Err(e) = mgr.stop(&app_h).await {
                                    log::warn!("停止 sidecar 时出现错误: {e}");
                                }
                            });
                        }
                    });

                    // 超时兜底：前端 close_splashscreen IPC 未在 10 秒内触发时
                    // （通常因后端未启动、前端初始化卡住或 IPC 调用失败），
                    // 强制 show main 窗口并关闭 splashscreen，确保用户始终能进入主界面。
                    let app_for_timeout = app_for_close.clone();
                    tauri::async_runtime::spawn(async move {
                        tokio::time::sleep(std::time::Duration::from_secs(10)).await;
                        let main_win = match app_for_timeout.get_webview_window("main") {
                            Some(w) => w,
                            None => {
                                log::warn!("[兜底] main 窗口不存在，跳过强制显示");
                                return;
                            }
                        };
                        let already_visible = main_win.is_visible().unwrap_or(false);
                        if already_visible {
                            return;
                        }
                        log::warn!("[兜底] 10 秒内 main 窗口未被前端 show，强制显示主窗口");
                        if let Err(e) = main_win.show() {
                            log::error!("[兜底] 强制 show main 窗口失败: {e}");
                        }
                        let _ = main_win.set_focus();
                        if let Some(splash) = app_for_timeout.get_webview_window("splashscreen") {
                            let _ = splash.close();
                        }
                    });
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
