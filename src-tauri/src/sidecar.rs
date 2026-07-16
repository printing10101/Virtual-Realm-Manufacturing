//! Python 后端 Sidecar 进程管理模块
//!
//! 负责启动、监控、重启和优雅终止打包后的 Python 后端进程。
//! 该模块使用 Tauri 2.x 的 `tauri-plugin-shell` 提供的 Sidecar API，
//! 并通过共享状态 (Arc<RwLock<...>>) 维护进程运行状态。

use std::sync::Arc;
use std::time::Duration;

use chrono::{DateTime, Utc};
use parking_lot::RwLock;
use serde::{Deserialize, Serialize};
use tauri::{AppHandle, Emitter, Manager, Runtime};
use tauri_plugin_shell::process::{CommandChild, CommandEvent};
use tauri_plugin_shell::ShellExt;
use tokio::sync::Mutex;
use tokio::time::sleep;

/// 后端进程运行状态
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq, Eq)]
#[serde(rename_all = "snake_case")]
pub enum BackendStatus {
    /// 尚未启动
    Idle,
    /// 正在启动（启动中、等待监听端口）
    Starting,
    /// 正常运行
    Running,
    /// 正在停止
    Stopping,
    /// 异常退出
    Crashed,
    /// 启动失败
    Failed,
    /// 已被用户终止
    Stopped,
}

impl BackendStatus {}

/// 后端进程状态信息
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct BackendState {
    pub status: BackendStatus,
    pub pid: Option<u32>,
    /// 0-100 启动进度
    pub progress: u8,
    pub message: String,
    pub last_error: Option<String>,
    pub started_at: Option<DateTime<Utc>>,
    pub restart_count: u32,
    pub port: u16,
}

impl BackendState {
    pub fn new(port: u16) -> Self {
        Self {
            status: BackendStatus::Idle,
            pid: None,
            progress: 0,
            message: "等待启动后端服务".to_string(),
            last_error: None,
            started_at: None,
            restart_count: 0,
            port,
        }
    }
}

/// Sidecar 管理器
pub struct SidecarManager {
    state: Arc<RwLock<BackendState>>,
    /// 当前正在运行的子进程句柄
    child: Arc<Mutex<Option<CommandChild>>>,
    /// 健康检查客户端
    http: reqwest::Client,
    /// 是否在用户主动关闭过程中（用于抑制崩溃事件）
    shutdown_in_progress: Arc<RwLock<bool>>,
}

impl SidecarManager {
    pub fn new(port: u16) -> Result<Self, String> {
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()
            .map_err(|e| format!("failed to build reqwest client: {e}"))?;
        Ok(Self {
            state: Arc::new(RwLock::new(BackendState::new(port))),
            child: Arc::new(Mutex::new(None)),
            http,
            shutdown_in_progress: Arc::new(RwLock::new(false)),
        })
    }

    pub fn state(&self) -> BackendState {
        self.state.read().clone()
    }

    /// 更新状态并通过事件总线推送给前端
    pub fn update_status<R: Runtime>(
        &self,
        app: &AppHandle<R>,
        status: BackendStatus,
        progress: u8,
        message: impl Into<String>,
    ) {
        {
            let mut s = self.state.write();
            s.status = status.clone();
            s.progress = progress;
            s.message = message.into();
        }
        self.emit_state(app);
    }

    pub fn set_error<R: Runtime>(&self, app: &AppHandle<R>, err: impl Into<String>) {
        {
            let mut s = self.state.write();
            s.last_error = Some(err.into());
        }
        self.emit_state(app);
    }

    pub fn emit_state<R: Runtime>(&self, app: &AppHandle<R>) {
        let snapshot = self.state();
        let _ = app.emit("sidecar://state", &snapshot);
    }

    /// 发射 `launch-progress` 事件供 splashscreen 监听
    ///
    /// splashscreen.html 的 `onProgress(payload)` 期望 payload 结构：
    ///   - step: 步骤标识（如 "start_backend"、"wait_ready"、"ready"、"failed"）
    ///   - progress: 0-100 进度数值
    ///   - description: 人类可读的描述文本
    ///   - status: "loading" | "success" | "error" | "complete"
    ///
    /// 之前 splashscreen 设计了真实进度接收逻辑但 Rust 端从未 emit，
    /// 导致进度条永远走模拟值。此方法在 sidecar 生命周期关键节点调用，
    /// 让 splashscreen 显示真实启动进度。
    fn emit_launch_progress<R: Runtime>(
        &self,
        app: &AppHandle<R>,
        step: &str,
        progress: u8,
        description: &str,
        status: &str,
    ) {
        let payload = serde_json::json!({
            "step": step,
            "progress": progress,
            "description": description,
            "status": status,
        });
        let _ = app.emit("launch-progress", &payload);
    }

    /// 启动 Python 后端 Sidecar
    pub async fn start<R: Runtime>(&self, app: &AppHandle<R>) -> Result<(), String> {
        {
            let current = self.state.read().status.clone();
            if matches!(
                current,
                BackendStatus::Starting | BackendStatus::Running | BackendStatus::Stopping
            ) {
                return Err(format!("后端进程当前处于 {:?} 状态，无法重复启动", current));
            }
        }

        let port = self.state.read().port;
        self.update_status(app, BackendStatus::Starting, 5, "正在启动 Python 后端进程...");
        self.emit_launch_progress(
            app,
            "start_backend",
            5,
            "正在启动 Python 后端进程...",
            "loading",
        );

        // 清理上一次启动的 sidecar.json 和后端日志文件，避免读到旧状态干扰诊断
        {
            let log_dir_path = self.log_dir(app);
            let log_dir = std::path::Path::new(&log_dir_path);
            let state_file = log_dir.join("sidecar.json");
            if state_file.exists() {
                let _ = std::fs::remove_file(&state_file);
            }
            // 清空旧的后端 stdout/stderr 日志（覆盖写入）
            for name in ["backend.stdout.log", "backend.stderr.log"] {
                let p = log_dir.join(name);
                if p.exists() {
                    let _ = std::fs::remove_file(&p);
                }
            }
        }

        // P0-11 修复：显式传 --state-file 参数，确保 Python 端写入的 sidecar.json
        // 路径与 Rust 端 wait_ready 读取的路径完全一致（都是 log_dir/sidecar.json）。
        // 同时通过 LNN_LOG_DIR / LNN_STATE_FILE 两个环境变量传递，作为命令行参数缺失时的兜底。
        let log_dir_for_sidecar = self.log_dir(app);
        let state_file_arg = std::path::Path::new(&log_dir_for_sidecar)
            .join("sidecar.json")
            .to_string_lossy()
            .to_string();

        let sidecar_command = app
            .shell()
            .sidecar("lingjing-backend")
            .map_err(|e| format!("无法创建 sidecar 命令: {e}"))?
            .args([
                "--host".to_string(),
                "127.0.0.1".to_string(),
                "--port".to_string(),
                port.to_string(),
                "--state-file".to_string(),
                state_file_arg.clone(),
            ])
            .env("LNN_HOST", "127.0.0.1")
            .env("LNN_PORT", port.to_string())
            .env("LNN_LOG_DIR", log_dir_for_sidecar.clone())
            .env("LNN_STATE_FILE", state_file_arg)
            .env("PYTHONUNBUFFERED", "1")
            .env("PYTHONIOENCODING", "utf-8");

        let (mut rx, child) = sidecar_command
            .spawn()
            .map_err(|e| {
                let msg = format!("Sidecar 启动失败: {e}");
                self.set_error(app, &msg);
                msg
            })?;

        let pid = child.pid();
        {
            let mut s = self.state.write();
            s.pid = Some(pid);
            s.started_at = Some(Utc::now());
            s.last_error = None;
        }
        *self.child.lock().await = Some(child);
        self.emit_state(app);

        // 启动子任务：读取 stdout/stderr 并发出日志事件
        // 同时将 stdout/stderr 写入文件，便于 release 模式下排查后端启动失败原因
        let app_clone = app.clone();
        let state_clone = self.state.clone();
        let log_dir_for_io = self.log_dir(app).to_string();
        tokio::spawn(async move {
            let stdout_path = std::path::Path::new(&log_dir_for_io).join("backend.stdout.log");
            let stderr_path = std::path::Path::new(&log_dir_for_io).join("backend.stderr.log");
            while let Some(event) = rx.recv().await {
                match event {
                    CommandEvent::Stdout(line_bytes) => {
                        let line = String::from_utf8_lossy(&line_bytes).to_string();
                        let _ = app_clone.emit("sidecar://stdout", &line);
                        append_log_line(&stdout_path, &line);
                    }
                    CommandEvent::Stderr(line_bytes) => {
                        let line = String::from_utf8_lossy(&line_bytes).to_string();
                        let _ = app_clone.emit("sidecar://stderr", &line);
                        log::warn!("[sidecar] {}", line);
                        append_log_line(&stderr_path, &line);
                    }
                    CommandEvent::Terminated(payload) => {
                        log::info!(
                            "Sidecar 进程已退出: code={:?}, signal={:?}",
                            payload.code, payload.signal
                        );
                        let mut s = state_clone.write();
                        s.pid = None;
                        let _ = app_clone.emit(
                            "sidecar://terminated",
                            &serde_json::json!({
                                "code": payload.code,
                                "signal": payload.signal,
                            }),
                        );
                    }
                    CommandEvent::Error(err) => {
                        log::error!("Sidecar 错误: {err}");
                        let _ = app_clone.emit("sidecar://error", &err);
                    }
                    _ => {}
                }
            }
        });

        // 健康检查轮询：等待后端就绪
        self.wait_ready(app).await
    }

    /// 轮询健康检查端点直到就绪或超时
    async fn wait_ready<R: Runtime>(&self, app: &AppHandle<R>) -> Result<(), String> {
        let port = self.state.read().port;
        let url = format!("http://127.0.0.1:{port}/api/health/ping");
        let mut last_progress: u8 = 5;
        let max_attempts: u32 = 90; // 90 * 500ms = 45s
        let state_file_path = std::path::Path::new(&self.log_dir(app)).join("sidecar.json");
        for attempt in 0..max_attempts {
            if *self.shutdown_in_progress.read() {
                return Err("应用关闭中，已取消启动".to_string());
            }
            // 检测 sidecar.json 文件：如果 Python 端已写入 failed/stopped，立即返回
            if state_file_path.exists() {
                if let Ok(content) = std::fs::read_to_string(&state_file_path) {
                    if let Ok(json) = serde_json::from_str::<serde_json::Value>(&content) {
                        if let Some(status) = json.get("status").and_then(|v| v.as_str()) {
                            if status == "failed" {
                                let err = json
                                    .get("error")
                                    .and_then(|v| v.as_str())
                                    .unwrap_or("后端启动失败")
                                    .to_string();
                                log::error!("[sidecar] Python 端报告启动失败: {}", err);
                                self.update_status(
                                    app,
                                    BackendStatus::Failed,
                                    last_progress,
                                    "后端启动失败",
                                );
                                self.set_error(app, err.clone());
                                self.emit_launch_progress(
                                    app,
                                    "backend_failed",
                                    last_progress,
                                    &format!("后端启动失败: {err}"),
                                    "error",
                                );
                                if let Some(child) = self.child.lock().await.take() {
                                    let _ = child.kill();
                                }
                                return Err(format!("后端启动失败: {err}"));
                            }
                            if status == "stopped" {
                                log::warn!("[sidecar] Python 端报告已停止");
                                self.update_status(
                                    app,
                                    BackendStatus::Crashed,
                                    last_progress,
                                    "后端进程意外停止",
                                );
                                self.emit_launch_progress(
                                    app,
                                    "backend_stopped",
                                    last_progress,
                                    "后端进程意外停止",
                                    "error",
                                );
                                if let Some(child) = self.child.lock().await.take() {
                                    let _ = child.kill();
                                }
                                return Err("后端进程意外停止".to_string());
                            }
                        }
                    }
                }
            }
            if let Some(child) = self.child.lock().await.as_ref() {
                // 简单地通过 pid 存活检测子进程
                let _ = child.pid();
            }
            match self.http.get(&url).send().await {
                Ok(resp) if resp.status().is_success() => {
                    self.update_status(app, BackendStatus::Running, 100, "后端服务已就绪");
                    self.emit_launch_progress(
                        app,
                        "ready",
                        100,
                        "后端服务已就绪",
                        "complete",
                    );
                    return Ok(());
                }
                Ok(_) | Err(_) => {
                    let progress = std::cmp::min(95, 5 + (attempt * 90 / max_attempts) as u8);
                    if progress > last_progress {
                        last_progress = progress;
                        let desc = format!("等待后端就绪 ({progress}%)");
                        self.update_status(
                            app,
                            BackendStatus::Starting,
                            progress,
                            desc.as_str(),
                        );
                        // 节流：每 5 次尝试才发射一次 launch-progress，避免事件洪流
                        if attempt % 5 == 0 {
                            self.emit_launch_progress(
                                app,
                                "wait_ready",
                                progress,
                                &desc,
                                "loading",
                            );
                        }
                    }
                }
            }
            sleep(Duration::from_millis(500)).await;
        }

        // 启动超时
        self.update_status(app, BackendStatus::Failed, last_progress, "后端启动超时");
        self.set_error(app, format!("健康检查超时: {url}"));
        self.emit_launch_progress(
            app,
            "timeout",
            last_progress,
            "后端启动超时，请检查日志",
            "error",
        );
        // 杀死可能仍在运行的子进程
        if let Some(child) = self.child.lock().await.take() {
            let _ = child.kill();
        }
        Err(format!("后端在 {} 秒内未响应健康检查", max_attempts / 2))
    }

    /// 优雅停止后端进程
    ///
    /// P1-4 修复：采用"HTTP 通知 → 等待 → fallback kill"三层关闭策略：
    /// 1. 先 POST /api/v1/admin/shutdown 通知 Python 端触发 graceful shutdown，
    ///    让其执行 shutdown_event（释放 ring_log/sse_manager/Redis/DB/ChromaDB）
    /// 2. 固定等待 5 秒（足够 SQLite WAL checkpoint 和资源释放）
    /// 3. 然后 child.kill() 兜底（若进程已退出则无副作用）
    ///
    /// 注：Tauri 2.0 的 CommandChild 不暴露 try_wait()，无法轮询进程状态，
    ///     故采用固定等待策略。5 秒是 SQLite WAL checkpoint + asyncio 任务
    ///     完成的经验值（实测通常 1-2 秒内完成）。
    pub async fn stop<R: Runtime>(&self, app: &AppHandle<R>) -> Result<(), String> {
        *self.shutdown_in_progress.write() = true;
        self.update_status(app, BackendStatus::Stopping, 100, "正在关闭后端服务...");

        let port = self.state.read().port;
        let shutdown_url = format!("http://127.0.0.1:{}/api/v1/admin/shutdown", port);

        // 第 1 步：尝试 HTTP 通知 Python 端优雅关闭
        let mut graceful_succeeded = false;
        match reqwest::Client::builder()
            .timeout(std::time::Duration::from_secs(2))
            .build()
        {
            Ok(client) => {
                match client.post(&shutdown_url).send().await {
                    Ok(resp) => {
                        log::info!(
                            "[stop] graceful shutdown endpoint responded: {}",
                            resp.status()
                        );
                        graceful_succeeded = true;
                    }
                    Err(e) => {
                        // 端点不存在（非桌面模式）或后端已停止，进入 fallback
                        log::debug!("[stop] HTTP shutdown 通知失败（可能后端已停止或非桌面模式）: {e}");
                    }
                }
            }
            Err(e) => {
                log::warn!("[stop] 构建 HTTP 客户端失败: {e}");
            }
        }

        if let Some(child) = self.child.lock().await.take() {
            if graceful_succeeded {
                // 第 2 步：固定等待 5 秒，让 Python 端完成 graceful shutdown
                // （足够 SQLite WAL checkpoint + asyncio 任务完成）
                sleep(Duration::from_secs(5)).await;
                log::info!("[stop] 等待 5s 完成，调用 kill 兜底");
            }
            // 第 3 步：kill 兜底（若进程已退出则无副作用）
            if let Err(e) = child.kill() {
                log::debug!("[stop] kill 返回错误（进程可能已退出）: {e}");
            }
        }
        {
            let mut s = self.state.write();
            s.status = BackendStatus::Stopped;
            s.pid = None;
            s.message = "后端服务已停止".to_string();
            s.progress = 0;
        }
        self.emit_state(app);
        *self.shutdown_in_progress.write() = false;
        Ok(())
    }

    /// 重启后端进程
    pub async fn restart<R: Runtime>(&self, app: &AppHandle<R>) -> Result<(), String> {
        {
            let mut s = self.state.write();
            s.restart_count = s.restart_count.saturating_add(1);
        }
        // 先尽力停止
        let _ = self.stop(app).await;
        // 短暂等待端口释放
        sleep(Duration::from_millis(800)).await;
        self.start(app).await
    }

    /// 同步强制终止后端进程（用于 RunEvent::Exit 等无法 await 的场景）
    ///
    /// 使用 `try_lock` 非阻塞获取子进程锁，避免在进程退出阶段死锁 tokio 运行时。
    /// - 若锁被占用（例如正在 restart/stop 中），则跳过并依赖 OS 进程组清理
    /// - Windows 下 Tauri sidecar 默认绑定 Job Object，父进程退出时子进程会被强制终止
    /// - Unix 下若 try_lock 失败，子进程可能短暂残留，但通常会在端口释放后被 systemd/launchd 回收
    pub fn force_kill_sync(&self) {
        match self.child.try_lock() {
            Ok(mut guard) => {
                if let Some(child) = guard.take() {
                    match child.kill() {
                        Ok(()) => log::info!("[force_kill_sync] 后端子进程已终止"),
                        Err(e) => log::warn!("[force_kill_sync] 终止子进程失败: {e}"),
                    }
                } else {
                    log::info!("[force_kill_sync] 子进程句柄为空，无需清理");
                }
            }
            Err(_) => {
                log::warn!("[force_kill_sync] 子进程锁被占用，跳过同步终止（依赖 OS 清理）");
            }
        }
    }

    fn log_dir<R: Runtime>(&self, app: &AppHandle<R>) -> String {
        if let Ok(dir) = app.path().app_log_dir() {
            return dir.to_string_lossy().to_string();
        }
        std::env::temp_dir()
            .join("lingjing")
            .to_string_lossy()
            .to_string()
    }
}

/// 将一行日志追加写入文件，用于持久化后端 stdout/stderr
/// 在 release 模式下，前端可能尚未加载无法接收事件，此时文件日志是排查后端启动失败的关键
fn append_log_line(path: &std::path::Path, line: &str) {
    use std::io::Write;
    let ts = chrono::Utc::now().format("%H:%M:%S%.3f");
    let content = format!("[{ts}] {line}\n");
    if let Ok(mut f) = std::fs::OpenOptions::new()
        .create(true)
        .append(true)
        .open(path)
    {
        let _ = f.write_all(content.as_bytes());
    }
}
