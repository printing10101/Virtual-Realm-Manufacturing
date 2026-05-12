use std::sync::Mutex;

pub struct AppState {
    pub sidecar_pid: Mutex<Option<u32>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            sidecar_pid: Mutex::new(None),
        }
    }
}
