use crate::models::SidecarStatus;
use crate::state::AppState;
use tauri::State;
use std::process::{Command, Stdio};
use chrono::Utc;

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

    let child = Command::new("python")
        .arg("-m")
        .arg("http.server")
        .arg("8000")
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .spawn()
        .map_err(|e| format!("Failed to start sidecar: {}", e))?;

    let pid = child.id();
    *process = Some(child);

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
        child.kill().map_err(|e| {
            format!("Failed to stop sidecar: {}", e)
        })?;
        
        child.wait().map_err(|e| {
            format!("Failed to wait for sidecar: {}", e)
        })?;

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
        Ok(SidecarStatus {
            running: true,
            pid: Some(child.id()),
            start_time: Some(Utc::now().to_rfc3339()),
        })
    } else {
        Ok(SidecarStatus {
            running: false,
            pid: None,
            start_time: None,
        })
    }
}
