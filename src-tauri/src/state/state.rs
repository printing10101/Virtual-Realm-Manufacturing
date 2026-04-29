use serde::Serialize;
use std::sync::atomic::{AtomicU32, Ordering};
use chrono::Utc;

#[derive(Debug)]
pub struct AppState {
    pub sidecar_pid: AtomicU32,
    pub sidecar_running: AtomicU32,
    pub sidecar_port: AtomicU32,
    pub sidecar_started_at: std::sync::Mutex<Option<String>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            sidecar_pid: AtomicU32::new(0),
            sidecar_running: AtomicU32::new(0),
            sidecar_port: AtomicU32::new(0),
            sidecar_started_at: std::sync::Mutex::new(None),
        }
    }

    pub fn get_pid(&self) -> u32 {
        self.sidecar_pid.load(Ordering::SeqCst)
    }

    pub fn set_pid(&self, pid: u32) {
        self.sidecar_pid.store(pid, Ordering::SeqCst);
    }

    pub fn is_running(&self) -> bool {
        self.sidecar_running.load(Ordering::SeqCst) == 1
    }

    pub fn set_running(&self, running: bool) {
        self.sidecar_running.store(if running { 1 } else { 0 }, Ordering::SeqCst);
    }

    pub fn get_port(&self) -> u16 {
        self.sidecar_port.load(Ordering::SeqCst) as u16
    }

    pub fn set_port(&self, port: u16) {
        self.sidecar_port.store(port as u32, Ordering::SeqCst);
    }

    pub fn get_started_at(&self) -> Option<String> {
        self.sidecar_started_at.lock().unwrap().clone()
    }

    pub fn set_started_at(&self, time: Option<String>) {
        *self.sidecar_started_at.lock().unwrap() = time;
    }

    #[allow(dead_code)]
    pub fn mark_started(&self, pid: u32, port: u16) {
        self.set_pid(pid);
        self.set_running(true);
        self.set_port(port);
        self.set_started_at(Some(Utc::now().to_rfc3339()));
    }

    pub fn mark_stopped(&self) {
        self.set_pid(0);
        self.set_running(false);
        self.set_port(0);
        self.set_started_at(None);
    }
}

#[derive(Debug, Serialize)]
pub struct SidecarStatusResponse {
    pub is_running: bool,
    pub status: String,
    pub pid: Option<u32>,
    pub port: u16,
    pub started_at: Option<String>,
}

impl SidecarStatusResponse {
    pub fn from_state(state: &AppState) -> Self {
        let is_running = state.is_running();
        Self {
            is_running,
            status: if is_running { "running".to_string() } else { "stopped".to_string() },
            pid: if is_running { Some(state.get_pid()) } else { None },
            port: state.get_port(),
            started_at: state.get_started_at(),
        }
    }
}
