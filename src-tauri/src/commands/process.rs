use tauri::State;
use crate::state::AppState;
use crate::state::SidecarStatusResponse;

#[tauri::command]
pub fn start_sidecar(state: State<'_, AppState>, port: Option<u16>) -> Result<u32, String> {
    if state.is_running() {
        return Err("Sidecar is already running".to_string());
    }

    let port = port.unwrap_or(8080);
    
    state.set_port(port);
    state.set_running(true);
    state.set_started_at(Some(chrono::Utc::now().to_rfc3339()));
    
    state.set_pid(0);
    
    Ok(0)
}

#[tauri::command]
pub fn stop_sidecar(state: State<'_, AppState>) -> Result<(), String> {
    if !state.is_running() {
        return Err("Sidecar is not running".to_string());
    }

    let pid = state.get_pid();
    if pid > 0 {
        #[cfg(unix)]
        {
            use std::process::Command;
            Command::new("kill")
                .arg(pid.to_string())
                .output()
                .map_err(|e| format!("Failed to kill process: {}", e))?;
        }
        
        #[cfg(windows)]
        {
            use std::process::Command;
            Command::new("taskkill")
                .args(["/F", "/PID", &pid.to_string()])
                .output()
                .map_err(|e| format!("Failed to kill process: {}", e))?;
        }
    }
    
    state.mark_stopped();
    
    Ok(())
}

#[tauri::command]
pub fn check_sidecar_status(state: State<'_, AppState>) -> Result<SidecarStatusResponse, String> {
    Ok(SidecarStatusResponse::from_state(&state))
}
