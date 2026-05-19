use anyhow::{Context, Result, anyhow};
use chrono::Utc;
use serde::{Deserialize, Serialize};
use std::fs;
use std::net::TcpListener;
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicUsize, Ordering};
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tracing::{info, warn, error};

/// Sidecar 状态文件结构
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SidecarStateFile {
    pub pid: u32,
    pub port: u16,
    pub token: String,
    pub started_at: String,
    pub version: String,
    #[serde(default)]
    pub status: SidecarProcessStatus,
}

/// Sidecar 进程状态枚举
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "snake_case")]
pub enum SidecarProcessStatus {
    Running,
    ShuttingDown,
    Stopped,
}

impl Default for SidecarProcessStatus {
    fn default() -> Self {
        Self::Running
    }
}

/// 动态端口分配器
pub struct PortAllocator {
    min_port: u16,
    max_port: u16,
    last_port: AtomicUsize,
}

impl PortAllocator {
    pub fn new(min_port: u16, max_port: u16) -> Self {
        Self {
            min_port,
            max_port,
            last_port: AtomicUsize::new(0),
        }
    }

    pub fn allocate_port(&self) -> u16 {
        use std::time::SystemTime;
        let seed = SystemTime::now()
            .duration_since(SystemTime::UNIX_EPOCH)
            .map(|d| d.as_nanos() as usize)
            .unwrap_or(0);

        let range = (self.max_port - self.min_port) as usize;
        let port_offset = seed % range;
        self.min_port + port_offset as u16
    }

    pub fn is_port_available(&self, port: u16) -> bool {
        TcpListener::bind(("127.0.0.1", port)).is_ok()
    }

    pub fn find_available_port(&self, max_attempts: usize) -> Option<u16> {
        for _ in 0..max_attempts {
            let port = self.allocate_port();
            if self.is_port_available(port) {
                info!("Allocated available port: {}", port);
                return Some(port);
            }
            warn!("Port {} is in use, retrying...", port);
        }
        error!("Failed to find available port after {} attempts", max_attempts);
        None
    }
}

/// 状态文件管理器
pub struct StateFileManager {
    pub state_file_path: PathBuf,
}

impl StateFileManager {
    pub fn new(state_file_path: PathBuf) -> Self {
        Self { state_file_path }
    }

    pub fn write_state(&self, state: &SidecarStateFile) -> Result<()> {
        if let Some(parent) = self.state_file_path.parent() {
            fs::create_dir_all(parent).context("Failed to create state directory")?;
        }

        let content = serde_json::to_string_pretty(state)
            .context("Failed to serialize state")?;

        let tmp_path = self.state_file_path.with_extension("tmp");

        fs::write(&tmp_path, &content)
            .context("Failed to write temporary state file")?;

        fs::rename(&tmp_path, &self.state_file_path)
            .context("Failed to atomically replace state file")?;

        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            let mut perms = fs::metadata(&self.state_file_path)?.permissions();
            perms.set_mode(0o600);
            fs::set_permissions(&self.state_file_path, perms)?;
        }

        info!("State file written: {}", self.state_file_path.display());
        Ok(())
    }

    pub fn read_state(&self) -> Option<SidecarStateFile> {
        match fs::read_to_string(&self.state_file_path) {
            Ok(content) => {
                match serde_json::from_str::<SidecarStateFile>(&content) {
                    Ok(state) => Some(state),
                    Err(e) => {
                        warn!("Failed to parse state file: {}", e);
                        None
                    }
                }
            }
            Err(_) => None,
        }
    }

    pub fn clear_state(&self) -> Result<()> {
        if self.state_file_path.exists() {
            fs::remove_file(&self.state_file_path)
                .context("Failed to remove state file")?;
            info!("State file cleared: {}", self.state_file_path.display());
        }
        Ok(())
    }

    pub fn update_status(&self, status: SidecarProcessStatus) -> Result<()> {
        if let Some(mut state) = self.read_state() {
            state.status = status;
            self.write_state(&state)?;
        }
        Ok(())
    }
}

/// 健康检查客户端
pub struct HealthChecker;

impl HealthChecker {
    pub fn check_health(port: u16, timeout_secs: u64) -> Result<bool> {
        let url = format!("http://127.0.0.1:{}/health", port);

        let client = reqwest::blocking::Client::builder()
            .timeout(Duration::from_secs(timeout_secs))
            .build()
            .context("Failed to create HTTP client")?;

        let response = client.get(&url).send();

        match response {
            Ok(resp) => Ok(resp.status().is_success()),
            Err(_) => {
                warn!("Health check failed: process not responding at port {}", port);
                Ok(false)
            }
        }
    }

    pub fn is_process_alive(pid: u32) -> bool {
        #[cfg(windows)]
        {
            use std::process::Command;
            let output = Command::new("tasklist")
                .args(["/FI", &format!("PID eq {}", pid), "/NH"])
                .output();

            match output {
                Ok(output) => {
                    let stdout = String::from_utf8_lossy(&output.stdout);
                    stdout.contains(&pid.to_string())
                }
                Err(_) => false,
            }
        }

        #[cfg(unix)]
        {
            unsafe {
                libc::kill(pid as i32, 0) == 0
            }
        }
    }
}

/// 优雅关闭管理器
pub struct GracefulShutdownManager;

impl GracefulShutdownManager {
    pub fn send_shutdown_signal(pid: u32, port: u16) -> Result<()> {
        info!("Sending graceful shutdown signal to PID {}", pid);

        #[cfg(windows)]
        {
            let output = Command::new("taskkill")
                .args(["/PID", &pid.to_string(), "/T"])
                .output()
                .context("Failed to execute taskkill")?;

            if !output.status.success() {
                let stderr = String::from_utf8_lossy(&output.stderr);
                return Err(anyhow!("taskkill failed: {}", stderr));
            }
        }

        #[cfg(unix)]
        {
            let output = Command::new("kill")
                .args(["-TERM", &pid.to_string()])
                .output()
                .context("Failed to send SIGTERM")?;

            if !output.status.success() {
                let stderr = String::from_utf8_lossy(&output.stderr);
                return Err(anyhow!("kill -TERM failed: {}", stderr));
            }
        }

        info!("Shutdown signal sent to PID {}", pid);
        Ok(())
    }

    pub fn wait_for_exit(pid: u32, timeout_secs: u64) -> bool {
        let start = std::time::Instant::now();
        let timeout = Duration::from_secs(timeout_secs);

        while start.elapsed() < timeout {
            if !HealthChecker::is_process_alive(pid) {
                info!("Process {} exited gracefully within timeout", pid);
                return true;
            }
            thread::sleep(Duration::from_millis(200));
        }

        warn!("Process {} did not exit within {}s timeout, forcing kill", pid, timeout_secs);
        false
    }

    pub fn force_kill(pid: u32) -> Result<()> {
        info!("Force killing PID {}", pid);

        #[cfg(windows)]
        {
            Command::new("taskkill")
                .args(["/F", "/PID", &pid.to_string(), "/T"])
                .output()
                .context("Failed to force kill process")?;
        }

        #[cfg(unix)]
        {
            Command::new("kill")
                .args(["-9", &pid.to_string()])
                .output()
                .context("Failed to send SIGKILL")?;
        }

        info!("Process {} force killed", pid);
        Ok(())
    }

    pub fn graceful_shutdown(pid: u32, port: u16, timeout_secs: u64) -> Result<()> {
        match Self::send_shutdown_signal(pid, port) {
            Ok(_) => {
                if Self::wait_for_exit(pid, timeout_secs) {
                    return Ok(());
                }

                warn!("Graceful shutdown timed out, forcing kill");
                Self::force_kill(pid)
            }
            Err(e) => {
                warn!("Failed to send shutdown signal: {}, forcing kill", e);
                Self::force_kill(pid)
            }
        }
    }
}

/// Sidecar 管理器（核心）
pub struct SidecarManager {
    pub port_allocator: PortAllocator,
    pub state_file_manager: StateFileManager,
    pub max_port_attempts: usize,
    pub health_check_timeout: u64,
    pub graceful_shutdown_timeout: u64,
}

impl SidecarManager {
    pub fn new(app_data_dir: PathBuf) -> Self {
        let state_file_path = app_data_dir.join(".gstack").join("sidecar.json");

        Self {
            port_allocator: PortAllocator::new(10000, 60000),
            state_file_manager: StateFileManager::new(state_file_path),
            max_port_attempts: 5,
            health_check_timeout: 5,
            graceful_shutdown_timeout: 5,
        }
    }

    pub fn recover_or_start(
        &self,
        version: &str,
        python_script_path: &str,
    ) -> Result<SidecarStartResult> {
        if let Some(existing_state) = self.state_file_manager.read_state() {
            info!(
                "Found existing state file: PID={}, Port={}, Status={:?}",
                existing_state.pid, existing_state.port, existing_state.status
            );

            if existing_state.status == SidecarProcessStatus::ShuttingDown {
                info!("Process was shutting down, cleaning up...");
                self.state_file_manager.clear_state().ok();
                return self.start_fresh(version, python_script_path);
            }

            if HealthChecker::is_process_alive(existing_state.pid) {
                match HealthChecker::check_health(existing_state.port, self.health_check_timeout) {
                    Ok(true) => {
                        info!("Existing sidecar process is healthy at port {}", existing_state.port);
                        return Ok(SidecarStartResult {
                            pid: existing_state.pid,
                            port: existing_state.port,
                            token: existing_state.token,
                            started_at: existing_state.started_at,
                            recovered: true,
                        });
                    }
                    _ => {
                        warn!("Existing process is unhealthy, cleaning up...");
                        self.cleanup_stale_process(existing_state.pid);
                    }
                }
            } else {
                info!("Existing process is dead, cleaning up state file...");
            }

            self.state_file_manager.clear_state().ok();
        }

        self.start_fresh(version, python_script_path)
    }

    pub fn start_fresh(&self, version: &str, python_script_path: &str) -> Result<SidecarStartResult> {
        let port = self
            .port_allocator
            .find_available_port(self.max_port_attempts)
            .context("Failed to find available port")?;

        info!("Starting sidecar on port {} with script: {}", port, python_script_path);

        let python_dir = std::env::current_exe()
            .ok()
            .and_then(|p| p.parent().map(|p| p.to_path_buf()))
            .unwrap_or_else(|| std::env::current_dir().unwrap_or_default());

        let python_path = python_dir.join("python").join("app");
        let working_dir = python_path.parent().unwrap_or(&python_dir);

        let log_dir = self.state_file_manager.state_file_path
            .parent()
            .and_then(|p| p.parent())
            .map(|p| p.join("logs"))
            .unwrap_or_else(|| {
                dirs::home_dir()
                    .unwrap_or_default()
                    .join(".lingjing")
                    .join("logs")
            });

        let child = Command::new("python")
            .arg("-m")
            .arg("uvicorn")
            .arg("app.main:app")
            .arg("--host")
            .arg("127.0.0.1")
            .arg("--port")
            .arg(&port.to_string())
            .arg("--log-level")
            .arg("warning")
            .env("LNN_LOG_DIR", log_dir.to_string_lossy().to_string())
            .current_dir(working_dir)
            .stdout(Stdio::piped())
            .stderr(Stdio::piped())
            .spawn()
            .context("Failed to start Python sidecar process")?;

        let pid = child.id();
        info!("Sidecar started with PID {} on port {}", pid, port);

        let token = uuid::Uuid::new_v4().to_string();
        let started_at = Utc::now().to_rfc3339();

        let state = SidecarStateFile {
            pid,
            port,
            token: token.clone(),
            started_at: started_at.clone(),
            version: version.to_string(),
            status: SidecarProcessStatus::Running,
        };

        self.state_file_manager
            .write_state(&state)
            .context("Failed to write state file after startup")?;

        thread::sleep(Duration::from_secs(2));

        match HealthChecker::check_health(port, 10) {
            Ok(true) => {
                info!("Sidecar health check passed after startup");
            }
            _ => {
                warn!("Sidecar health check failed after startup, process may not be healthy");
            }
        }

        Ok(SidecarStartResult {
            pid,
            port,
            token,
            started_at,
            recovered: false,
        })
    }

    pub fn graceful_shutdown(&self, pid: u32, port: u16) -> Result<()> {
        self.state_file_manager
            .update_status(SidecarProcessStatus::ShuttingDown)
            .ok();

        GracefulShutdownManager::graceful_shutdown(
            pid,
            port,
            self.graceful_shutdown_timeout,
        )?;

        self.state_file_manager.clear_state().ok();
        info!("Sidecar process {} shut down gracefully", pid);
        Ok(())
    }

    pub fn cleanup_stale_process(&self, pid: u32) {
        if HealthChecker::is_process_alive(pid) {
            warn!("Cleaning up stale process PID {}", pid);
            GracefulShutdownManager::force_kill(pid).ok();
        }
    }
}

/// Sidecar 启动结果
#[derive(Debug, Clone, Serialize)]
pub struct SidecarStartResult {
    pub pid: u32,
    pub port: u16,
    pub token: String,
    pub started_at: String,
    pub recovered: bool,
}
