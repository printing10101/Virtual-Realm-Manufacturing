use std::sync::Mutex;

pub struct AppState {
    pub sidecar_process: Mutex<Option<std::process::Child>>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            sidecar_process: Mutex::new(None),
        }
    }
}
