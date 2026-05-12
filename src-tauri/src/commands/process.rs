use crate::models::SidecarStatus;
use crate::sidecar_manager::{
    SidecarManager, SidecarProcessStatus,
};
use crate::state::AppState;
use crate::version::VersionInfo;
use std::sync::Mutex;
use std::thread;
use std::time::Duration;
use tauri::State;
use tracing::{error, info, warn};

static RESTART_ATTEMPTS: Mutex<usize> = Mutex::new(0);
const MAX_RESTART_ATTEMPTS: usize = 3;
const RETRY_DELAYS: [Duration; MAX_RESTART_ATTEMPTS] = [
    Duration::from_secs(1),
    Duration::from_secs(3),
    Duration::from_secs(5),
];

#[derive(Debug, serde::Serialize)]
pub struct ProcessResult {
    pub success: bool,
    pub message: String,
    pub pid: Option<u32>,
    pub port: Option<u16>,
    pub token: Option<String>,
}

fn get_sidecar_manager(app: &tauri::AppHandle) -> SidecarManager {
    let app_data_dir = app
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| {
            dirs::home_dir()
                .unwrap_or_default()
                .join(".lingjing")
        });

    SidecarManager::new(app_data_dir)
}

#[tauri::command]
pub fn start_sidecar(
    app: tauri::AppHandle,
    state: State<AppState>,
    version_info: State<VersionInfo>,
) -> Result<ProcessResult, String> {
    let manager = get_sidecar_manager(&app);
    let version = version_info.version.clone();

    let python_script_path = std::env::var("SIDECAR_SCRIPT_PATH")
        .unwrap_or_else(|_| "app.main:app".to_string());

    match manager.recover_or_start(&version, &python_script_path) {
        Ok(result) => {
            let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
                format!("Failed to lock process state: {}", e)
            })?;
            *pid_lock = Some(result.pid);
            drop(pid_lock);

            info!(
                "Sidecar started: PID={}, Port={}, Recovered={}",
                result.pid, result.port, result.recovered
            );

            let message = if result.recovered {
                "Recovered existing healthy sidecar process".to_string()
            } else {
                "Sidecar started successfully with health verification".to_string()
            };

            Ok(ProcessResult {
                success: true,
                message,
                pid: Some(result.pid),
                port: Some(result.port),
                token: Some(result.token),
            })
        }
        Err(e) => {
            error!("Failed to start sidecar: {}", e);
            Err(format!("Failed to start sidecar: {}", e))
        }
    }
}

#[tauri::command]
pub fn stop_sidecar(app: tauri::AppHandle, state: State<AppState>) -> Result<ProcessResult, String> {
    let manager = get_sidecar_manager(&app);

    let pid_lock = state.sidecar_pid.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;

    let pid = match pid_lock.as_ref() {
        Some(p) => *p,
        None => {
            manager.state_file_manager.clear_state().ok();
            return Ok(ProcessResult {
                success: false,
                message: "Sidecar is not running".to_string(),
                pid: None,
                port: None,
                token: None,
            });
        }
    };
    drop(pid_lock);

    if let Some(state_file) = manager.state_file_manager.read_state() {
        match manager.graceful_shutdown(pid, state_file.port) {
            Ok(_) => {
                let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
                    format!("Failed to lock process state: {}", e)
                })?;
                *pid_lock = None;

                return Ok(ProcessResult {
                    success: true,
                    message: "Sidecar stopped gracefully".to_string(),
                    pid: Some(pid),
                    port: Some(state_file.port),
                    token: Some(state_file.token),
                });
            }
            Err(e) => {
                warn!("Graceful shutdown failed: {}, forcing kill", e);
            }
        }
    }

    manager.cleanup_stale_process(pid);
    manager.state_file_manager.clear_state().ok();

    let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;
    *pid_lock = None;

    Ok(ProcessResult {
        success: true,
        message: "Sidecar force stopped".to_string(),
        pid: Some(pid),
        port: None,
        token: None,
    })
}

#[tauri::command]
pub fn check_sidecar_status(
    app: tauri::AppHandle,
    state: State<AppState>,
) -> Result<SidecarStatus, String> {
    let manager = get_sidecar_manager(&app);

    if let Some(state_file) = manager.state_file_manager.read_state() {
        let is_alive = crate::sidecar_manager::HealthChecker::is_process_alive(state_file.pid);

        if is_alive {
            let is_healthy = crate::sidecar_manager::HealthChecker::check_health(
                state_file.port,
                manager.health_check_timeout,
            )
            .unwrap_or(false);

            return Ok(SidecarStatus {
                running: is_healthy,
                pid: Some(state_file.pid),
                port: Some(state_file.port),
                token: Some(state_file.token),
                start_time: Some(state_file.started_at.clone()),
                recovered: state_file.status == SidecarProcessStatus::Running,
            });
        } else {
            warn!("Sidecar process {} is not alive, cleaning up", state_file.pid);
            manager.cleanup_stale_process(state_file.pid);
            manager.state_file_manager.clear_state().ok();
        }
    }

    let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;
    *pid_lock = None;

    Ok(SidecarStatus {
        running: false,
        pid: None,
        port: None,
        token: None,
        start_time: None,
        recovered: false,
    })
}

#[tauri::command]
pub fn restart_sidecar(
    app: tauri::AppHandle,
    state: State<AppState>,
    version_info: State<VersionInfo>,
) -> Result<ProcessResult, String> {
    let manager = get_sidecar_manager(&app);
    let version = version_info.version.clone();

    if let Some(state_file) = manager.state_file_manager.read_state() {
        info!("Restarting sidecar PID {}", state_file.pid);
        manager.cleanup_stale_process(state_file.pid);
        manager.state_file_manager.clear_state().ok();
    }

    let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;
    *pid_lock = None;
    drop(pid_lock);

    let python_script_path = std::env::var("SIDECAR_SCRIPT_PATH")
        .unwrap_or_else(|_| "app.main:app".to_string());

    match manager.recover_or_start(&version, &python_script_path) {
        Ok(result) => {
            let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
                format!("Failed to lock process state: {}", e)
            })?;
            *pid_lock = Some(result.pid);

            Ok(ProcessResult {
                success: true,
                message: "Sidecar restarted successfully".to_string(),
                pid: Some(result.pid),
                port: Some(result.port),
                token: Some(result.token),
            })
        }
        Err(e) => {
            error!("Failed to restart sidecar: {}", e);
            Err(format!("Failed to restart sidecar: {}", e))
        }
    }
}

#[tauri::command]
pub fn auto_reconnect_sidecar(
    app: tauri::AppHandle,
    state: State<AppState>,
    version_info: State<VersionInfo>,
) -> Result<ProcessResult, String> {
    let manager = get_sidecar_manager(&app);
    let version = version_info.version.clone();

    let mut attempts = {
        let mut lock = RESTART_ATTEMPTS.lock().map_err(|e| e.to_string())?;
        let current = *lock;
        if current >= MAX_RESTART_ATTEMPTS {
            *lock = 0;
            return Err(format!(
                "Maximum restart attempts ({}) exceeded. Please restart manually.",
                MAX_RESTART_ATTEMPTS
            ));
        }
        *lock = current + 1;
        current
    };

    info!(
        "Auto-reconnecting sidecar (attempt {}/{})",
        attempts + 1,
        MAX_RESTART_ATTEMPTS
    );

    let delay = RETRY_DELAYS[attempts];
    thread::sleep(delay);

    if let Some(state_file) = manager.state_file_manager.read_state() {
        manager.cleanup_stale_process(state_file.pid);
        manager.state_file_manager.clear_state().ok();
    }

    let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;
    *pid_lock = None;
    drop(pid_lock);

    let python_script_path = std::env::var("SIDECAR_SCRIPT_PATH")
        .unwrap_or_else(|_| "app.main:app".to_string());

    match manager.recover_or_start(&version, &python_script_path) {
        Ok(result) => {
            let mut pid_lock = state.sidecar_pid.lock().map_err(|e| {
                format!("Failed to lock process state: {}", e)
            })?;
            *pid_lock = Some(result.pid);

            {
                let mut lock = RESTART_ATTEMPTS.lock().map_err(|e| e.to_string())?;
                *lock = 0;
            }

            Ok(ProcessResult {
                success: true,
                message: format!(
                    "Sidecar auto-reconnected successfully on attempt {}",
                    attempts + 1
                ),
                pid: Some(result.pid),
                port: Some(result.port),
                token: Some(result.token),
            })
        }
        Err(e) => {
            error!("Auto-reconnect attempt {} failed: {}", attempts + 1, e);

            if attempts + 1 >= MAX_RESTART_ATTEMPTS {
                {
                    let mut lock = RESTART_ATTEMPTS.lock().map_err(|e| e.to_string())?;
                    *lock = 0;
                }
                Err(format!(
                    "All {} auto-reconnect attempts failed. Last error: {}. Please restart manually.",
                    MAX_RESTART_ATTEMPTS, e
                ))
            } else {
                Err(format!("Auto-reconnect attempt {} failed: {}", attempts + 1, e))
            }
        }
    }
}

#[tauri::command]
pub fn force_restart_sidecar(
    app: tauri::AppHandle,
    state: State<AppState>,
    version_info: State<VersionInfo>,
) -> Result<ProcessResult, String> {
    {
        let mut lock = RESTART_ATTEMPTS.lock().map_err(|e| e.to_string())?;
        *lock = 0;
    }

    restart_sidecar(app, state, version_info)
}
