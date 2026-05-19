use std::sync::mpsc;
use std::sync::Mutex;

pub struct AppState {
    pub sidecar_pid: Mutex<Option<u32>>,
    pub retry_tx: Mutex<Option<mpsc::Sender<()>>>,
    pub restart_attempts: Mutex<usize>,
}

impl AppState {
    pub fn new() -> Self {
        Self {
            sidecar_pid: Mutex::new(None),
            retry_tx: Mutex::new(None),
            restart_attempts: Mutex::new(0),
        }
    }
}