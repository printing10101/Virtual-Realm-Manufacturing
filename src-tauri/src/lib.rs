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
    auto_fix_health, close_splashscreen, export_logs_cmd, get_app_version, get_backend_port,
    get_backend_state, get_diagnostics_text, get_version_info, ping_backend, restart_backend,
    retry_launch_step, run_health_check, run_single_health_check, start_backend, stop_backend,
    AppState,
};
use crate::sidecar::SidecarManager;

/// 默认后端端口（与 `python/app/main.py` 中 uvicorn 启动端口保持一致）
// P0-9 修复：原本为 8000，与 Python 端 config.server.port=8765 不一致，
// 导致 Tauri 默认连接 8000 端口而 Python 监听 8765，前端调用全部失败。
pub const DEFAULT_BACKEND_PORT: u16 = 8765;

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    let _ = env_logger::try_init();

    // 注意：不要在启动时清理整个 EBWebView 目录！
    // 之前的实现会 remove_dir_all(EBWebView)，但 tauri::Builder::build() 紧接着
    // 会创建 splashscreen 窗口，splashscreen 的 WebView2 会异步重建 EBWebView 目录。
    // 此时 setup 回调中 500ms 后创建 main 窗口，main 窗口的 WebView2 与 splashscreen
    // 共享同一用户数据目录，但目录正在被 splashscreen 重建，导致 main 窗口 WebView2
    // 创建时报 HRESULT(0x80070057) "参数错误"。
    //
    // 现在改为：只清理 Default 子目录下可能残留的 LOCK 文件（仅当无进程占用时才安全）。
    // LOCK 文件是 SQLite/LevelDB 的进程独占锁，进程正常退出时会释放，异常退出后残留。
    // 只删除 LOCK 文件不会破坏 EBWebView 目录结构，避免与 splashscreen 重建冲突。
    #[cfg(target_os = "windows")]
    {
        if let Ok(local_app_data) = std::env::var("LOCALAPPDATA") {
            let identifier = "com.lingjing.manufacturing";
            let default_dir = std::path::Path::new(&local_app_data)
                .join(identifier)
                .join("EBWebView")
                .join("Default");
            if default_dir.exists() {
                // 递归查找并删除 LOCK 文件（不删除目录结构）
                let mut removed = 0u32;
                let mut failed = 0u32;
                for entry in walkdir(&default_dir) {
                    if entry.file_name() == Some(std::ffi::OsStr::new("LOCK")) {
                        match std::fs::remove_file(&entry) {
                            Ok(_) => removed += 1,
                            Err(_) => failed += 1,
                        }
                    }
                }
                if removed > 0 || failed > 0 {
                    log::info!(
                        "清理 WebView2 LOCK 文件: 成功 {} 个, 失败 {} 个 (失败多为正在被占用，可忽略)",
                        removed,
                        failed
                    );
                }
            }
        }
    }

    let manager = Arc::new(match SidecarManager::new(DEFAULT_BACKEND_PORT) {
        Ok(m) => m,
        Err(e) => {
            log::error!("创建 SidecarManager 失败: {e}");
            return;
        }
    });
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
            get_version_info,
            get_backend_port,
            close_splashscreen,
            // 健康检查与日志导出（前端 HealthCheck.vue + useSettings.ts 调用）
            run_health_check,
            run_single_health_check,
            auto_fix_health,
            get_diagnostics_text,
            export_logs_cmd,
            retry_launch_step,
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
                            // 即使 main 窗口创建失败，也要关闭 splashscreen，
                            // 否则用户会卡在"启动中"画面永远进不去。
                            // 关闭后用户至少看到桌面，可以查看日志或重新启动。
                            if let Some(splash) = app_for_close.get_webview_window("splashscreen") {
                                let _ = splash.close();
                            }
                            return;
                        }
                    };
                    log::info!("主窗口 main 创建成功");

                    // 诊断模式：仅在 debug 构建下打开 DevTools
                    // release 构建不再打开 DevTools，避免暴露 __TAURI__ 全局对象与开发工具入口
                    // （devtools feature 仍保留在 Cargo.toml，是为了 release 出包后通过环境变量
                    //   或快捷键按需打开；这里仅控制默认行为）
                    #[cfg(debug_assertions)]
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
                });

                // 超时兜底：独立于 main 窗口创建逻辑。
                // 无论 main 窗口是否创建成功，10 秒后都强制关闭 splashscreen 并尝试 show main。
                // 这避免了 main 窗口创建失败时 splashscreen 永远卡死的问题。
                let app_for_timeout = app_handle.clone();
                tauri::async_runtime::spawn(async move {
                    tokio::time::sleep(std::time::Duration::from_secs(10)).await;
                    log::warn!("[兜底] 10 秒到达，开始强制切换窗口");

                    // 先尝试 show main 窗口（如果存在且未显示）
                    if let Some(main_win) = app_for_timeout.get_webview_window("main") {
                        let already_visible = main_win.is_visible().unwrap_or(false);
                        if !already_visible {
                            log::warn!("[兜底] 强制显示 main 窗口");
                            if let Err(e) = main_win.show() {
                                log::error!("[兜底] 强制 show main 窗口失败: {e}");
                            }
                            let _ = main_win.set_focus();
                        } else {
                            log::info!("[兜底] main 窗口已可见，无需强制显示");
                        }
                    } else {
                        log::warn!("[兜底] main 窗口不存在（创建失败或仍在创建中）");
                    }

                    // 无论 main 窗口状态如何，都关闭 splashscreen
                    // （如果 main 不存在，用户会回到桌面；如果 main 存在，用户进入主界面）
                    if let Some(splash) = app_for_timeout.get_webview_window("splashscreen") {
                        log::info!("[兜底] 关闭 splashscreen 窗口");
                        let _ = splash.close();
                    }
                });
            }

            Ok(())
        })
        .build(tauri::generate_context!());

    // 安全修复：避免 .expect() 在 build 失败时直接 panic 导致进程异常终止。
    // 改为 match 返回 Result，记录错误日志后以非零码优雅退出。
    let app = match app {
        Ok(a) => a,
        Err(e) => {
            log::error!("启动 Tauri 应用失败: {e}");
            eprintln!("启动 Tauri 应用失败: {e}");
            std::process::exit(1);
        }
    };

    let manager_for_run = manager.clone();
    app.run(move |_app_handle, event| match event {
        RunEvent::ExitRequested { .. } => {
            log::info!("收到 ExitRequested，进程即将退出");
        }
        RunEvent::Exit => {
            // 进程退出阶段：同步强制终止后端子进程，避免残留
            // 注意：此处不能 await，使用 force_kill_sync 非阻塞终止
            log::info!("Tauri RunEvent::Exit 已触发，强制终止后端进程");
            manager_for_run.force_kill_sync();
        }
        _ => {}
    });
}

/// 递归遍历目录，返回所有文件和子目录的路径列表。
/// 这是个最小化的实现，避免引入 `walkdir` crate 依赖。
/// 仅用于启动时清理 WebView2 Default 目录下的 LOCK 文件。
///
/// 安全修复：原实现无深度限制，遇到符号链接环（symlink loop）会无限递归导致栈溢出。
/// 现添加 max_depth 限制（默认 10 层）并跳过符号链接，避免栈溢出风险。
fn walkdir(dir: &std::path::Path) -> Vec<std::path::PathBuf> {
    walkdir_inner(dir, 0, 10)
}

fn walkdir_inner(dir: &std::path::Path, depth: u32, max_depth: u32) -> Vec<std::path::PathBuf> {
    let mut result = Vec::new();
    // 深度超限直接返回，避免恶意构造的深层嵌套目录导致栈溢出
    if depth >= max_depth {
        return result;
    }
    if let Ok(entries) = std::fs::read_dir(dir) {
        for entry in entries.flatten() {
            let path = entry.path();
            // 跳过符号链接，避免符号链接环导致无限递归栈溢出
            // （使用 symlink_metadata 不跟踪符号链接目标）
            let is_symlink = std::fs::symlink_metadata(&path)
                .map(|m| m.file_type().is_symlink())
                .unwrap_or(false);
            if is_symlink {
                continue;
            }
            result.push(path.clone());
            if path.is_dir() {
                result.extend(walkdir_inner(&path, depth + 1, max_depth));
            }
        }
    }
    result
}
