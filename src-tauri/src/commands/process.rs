use crate::models::SidecarStatus;
use crate::state::AppState;
use std::sync::Mutex;
use tauri::State;
use std::process::{Command, Stdio};
use chrono::Utc;
use tracing::{info, warn};

static START_TIME: Mutex<Option<String>> = Mutex::new(None);

#[derive(Debug, serde::Serialize)]
pub struct ProcessResult {
    pub success: bool,
    pub message: String,
    pub pid: Option<u32>,
}

#[tauri::command]
pub fn start_sidecar(state: State<AppState>) -> Result<ProcessResult, String> {
    let mut process = state.sidecar_process.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;

    if process.is_some() {
        return Ok(ProcessResult {
            success: false,
            message: "Sidecar is already running".to_string(),
            pid: None,
        });
    }

    let port = std::env::var("SIDECAR_PORT").unwrap_or_else(|_| "8000".to_string());

    let child = Command::new("python")
        .arg("-m")
        .arg("http.server")
        .arg(&port)
        .stdout(Stdio::null())
        .stderr(Stdio::null())
        .spawn()
        .map_err(|e| format!("Failed to start sidecar: {}", e))?;

    let pid = child.id();
    *process = Some(child);

    let start_time = Utc::now().to_rfc3339();
    if let Ok(mut st) = START_TIME.lock() {
        *st = Some(start_time.clone());
    }

    info!("Sidecar started with PID {} on port {}", pid, port);

    Ok(ProcessResult {
        success: true,
        message: "Sidecar started successfully".to_string(),
        pid: Some(pid),
    })
}

#[tauri::command]
pub fn stop_sidecar(state: State<AppState>) -> Result<ProcessResult, String> {
    let mut process = state.sidecar_process.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;

    if let Some(mut child) = process.take() {
        if let Err(e) = child.kill() {
            warn!("Failed to kill sidecar process: {}", e);
        }

        if let Err(e) = child.wait() {
            warn!("Failed to wait for sidecar: {}", e);
        }

        if let Ok(mut st) = START_TIME.lock() {
            *st = None;
        }

        Ok(ProcessResult {
            success: true,
            message: "Sidecar stopped successfully".to_string(),
            pid: None,
        })
    } else {
        Ok(ProcessResult {
            success: false,
            message: "Sidecar is not running".to_string(),
            pid: None,
        })
    }
}

#[tauri::command]
pub fn check_sidecar_status(state: State<AppState>) -> Result<SidecarStatus, String> {
    let process = state.sidecar_process.lock().map_err(|e| {
        format!("Failed to lock process state: {}", e)
    })?;

    if let Some(child) = process.as_ref() {
        let start_time = START_TIME.lock().ok().and_then(|st| st.clone());
        Ok(SidecarStatus {
            running: true,
            pid: Some(child.id()),
            start_time,
        })
    } else {
        Ok(SidecarStatus {
            running: false,
            pid: None,
            start_time: None,
        })
    }
}
