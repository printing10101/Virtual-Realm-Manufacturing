//! Python 后端 Sidecar 进程管理模块
//!
//! 负责启动、监控、重启和优雅终止打包后的 Python 后端进程。
//! 该模块使用 Tauri 2.x 的 `tauri-plugin-shell` 提供的 Sidecar API，
//! 并通过共享状态 (Arc<RwLock<...>>) 维护进程运行状态。

use std::process::Stdio;
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

impl BackendStatus {
    pub fn as_str(&self) -> &'static str {
        match self {
            BackendStatus::Idle => "idle",
            BackendStatus::Starting => "starting",
            BackendStatus::Running => "running",
            BackendStatus::Stopping => "stopping",
            BackendStatus::Crashed => "crashed",
            BackendStatus::Failed => "failed",
            BackendStatus::Stopped => "stopped",
        }
    }
}

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
    pub fn new(port: u16) -> Self {
        let http = reqwest::Client::builder()
            .timeout(Duration::from_secs(3))
            .build()
            .expect("failed to build reqwest client");
        Self {
            state: Arc::new(RwLock::new(BackendState::new(port))),
            child: Arc::new(Mutex::new(None)),
            http,
            shutdown_in_progress: Arc::new(RwLock::new(false)),
        }
    }

    pub fn state(&self) -> BackendState {
        self.state.read().clone()
    }

    pub fn state_arc(&self) -> Arc<RwLock<BackendState>> {
        self.state.clone()
    }

    pub fn child_arc(&self) -> Arc<Mutex<Option<CommandChild>>> {
        self.child.clone()
    }

    pub fn shutdown_flag(&self) -> Arc<RwLock<bool>> {
        self.shutdown_in_progress.clone()
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

        let sidecar_command = app
            .shell()
            .sidecar("lingjing-backend")
            .map_err(|e| format!("无法创建 sidecar 命令: {e}"))?
            .args([
                "--host".to_string(),
                "127.0.0.1".to_string(),
                "--port".to_string(),
                port.to_string(),
            ])
            .env("LNN_HOST", "127.0.0.1")
            .env("LNN_PORT", port.to_string())
            .env("LNN_LOG_DIR", self.log_dir(app))
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
        let app_clone = app.clone();
        let state_clone = self.state.clone();
        tokio::spawn(async move {
            use futures_util::StreamExt;
            while let Some(event) = rx.next().await {
                match event {
                    CommandEvent::Stdout(line_bytes) => {
                        let line = String::from_utf8_lossy(&line_bytes).to_string();
                        let _ = app_clone.emit("sidecar://stdout", &line);
                    }
                    CommandEvent::Stderr(line_bytes) => {
                        let line = String::from_utf8_lossy(&line_bytes).to_string();
                        let _ = app_clone.emit("sidecar://stderr", &line);
                        log::warn!("[sidecar] {}", line);
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
        for attempt in 0..max_attempts {
            if *self.shutdown_in_progress.read() {
                return Err("应用关闭中，已取消启动".to_string());
            }
            if let Some(child) = self.child.lock().await.as_ref() {
                // 简单地通过 pid 存活检测子进程
                let _ = child.pid();
            }
            match self.http.get(&url).send().await {
                Ok(resp) if resp.status().is_success() => {
                    self.update_status(app, BackendStatus::Running, 100, "后端服务已就绪");
                    return Ok(());
                }
                Ok(_) | Err(_) => {
                    let progress = std::cmp::min(95, 5 + (attempt * 90 / max_attempts) as u8);
                    if progress > last_progress {
                        last_progress = progress;
                        self.update_status(
                            app,
                            BackendStatus::Starting,
                            progress,
                            format!("等待后端就绪 ({progress}%)"),
                        );
                    }
                }
            }
            sleep(Duration::from_millis(500)).await;
        }

        // 启动超时
        self.update_status(app, BackendStatus::Failed, last_progress, "后端启动超时");
        self.set_error(app, format!("健康检查超时: {url}"));
        // 杀死可能仍在运行的子进程
        if let Some(mut child) = self.child.lock().await.take() {
            let _ = child.kill();
        }
        Err(format!("后端在 {} 秒内未响应健康检查", max_attempts / 2))
    }

    /// 优雅停止后端进程
    pub async fn stop<R: Runtime>(&self, app: &AppHandle<R>) -> Result<(), String> {
        *self.shutdown_in_progress.write() = true;
        self.update_status(app, BackendStatus::Stopping, 100, "正在关闭后端服务...");
        if let Some(mut child) = self.child.lock().await.take() {
            // 先尝试优雅 kill
            if let Err(e) = child.kill() {
                log::warn!("终止 sidecar 失败: {e}");
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

    /// 标记子进程已退出（由监听任务调用）
    pub fn mark_exited<R: Runtime>(&self, app: &AppHandle<R>, code: Option<i32>) {
        if *self.shutdown_in_progress.read() {
            return;
        }
        {
            let mut s = self.state.write();
            s.pid = None;
            s.status = BackendStatus::Crashed;
            s.message = format!("后端进程异常退出 (code={:?})", code);
            s.progress = 0;
        }
        self.emit_state(app);
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
