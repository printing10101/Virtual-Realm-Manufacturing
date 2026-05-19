use crate::sidecar_manager::{SidecarManager, SidecarStartResult};
use crate::state::AppState;
use chrono::Utc;
use serde::Serialize;
use std::sync::mpsc;
use std::time::{Duration, Instant};
use tauri::Emitter;
use tracing::{error, info, warn};

#[derive(Debug, Clone, Serialize)]
pub struct LaunchProgress {
    pub step: String,
    pub progress: u8,
    pub description: String,
    pub status: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error: Option<String>,
    #[serde(skip_serializing_if = "Option::is_none")]
    pub error_detail: Option<String>,
    pub elapsed_seconds: u64,
}

fn make_progress(
    step: &str,
    progress: u8,
    description: &str,
    status: &str,
    start: &Instant,
) -> LaunchProgress {
    LaunchProgress {
        step: step.to_string(),
        progress,
        description: description.to_string(),
        status: status.to_string(),
        error: None,
        error_detail: None,
        elapsed_seconds: start.elapsed().as_secs(),
    }
}

fn make_error(
    step: &str,
    progress: u8,
    error: &str,
    detail: &str,
    start: &Instant,
) -> LaunchProgress {
    LaunchProgress {
        step: step.to_string(),
        progress,
        description: String::new(),
        status: "error".to_string(),
        error: Some(error.to_string()),
        error_detail: Some(detail.to_string()),
        elapsed_seconds: start.elapsed().as_secs(),
    }
}

fn emit(handle: &tauri::AppHandle, progress: &LaunchProgress) {
    if let Err(e) = handle.emit("launch-progress", progress) {
        error!("Failed to emit launch-progress event: {}", e);
    } else {
        info!(
            "Launch progress: step={} progress={}% status={}",
            progress.step, progress.progress, progress.status
        );
    }
}

fn get_sidecar_manager(handle: &tauri::AppHandle) -> SidecarManager {
    let app_data_dir = handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| {
            dirs::home_dir()
                .unwrap_or_default()
                .join(".lingjing")
        });
    SidecarManager::new(app_data_dir)
}

fn reset_sidecar_state(handle: &tauri::AppHandle) {
    let manager = get_sidecar_manager(handle);
    if let Some(state_file) = manager.state_file_manager.read_state() {
        manager.cleanup_stale_process(state_file.pid);
        manager.state_file_manager.clear_state().ok();
    }
    if let Some(app_state) = handle.try_state::<AppState>() {
        if let Ok(mut pid) = app_state.sidecar_pid.lock() {
            *pid = None;
        }
    }
}

struct RetryLoop {
    rx: mpsc::Receiver<()>,
}

impl RetryLoop {
    fn new(rx: mpsc::Receiver<()>) -> Self {
        Self { rx }
    }

    fn wait_with_timeout(&self, timeout_secs: u64) -> bool {
        match self.rx.recv_timeout(Duration::from_secs(timeout_secs)) {
            Ok(_) => {
                info!("Retry signal received");
                true
            }
            Err(mpsc::RecvTimeoutError::Timeout) => {
                warn!("Retry wait timed out after {}s", timeout_secs);
                false
            }
            Err(mpsc::RecvTimeoutError::Disconnected) => {
                warn!("Retry channel disconnected");
                false
            }
        }
    }
}

fn step_framework_init(
    handle: &tauri::AppHandle,
    start: &Instant,
    retry: &RetryLoop,
) -> bool {
    loop {
        emit(
            handle,
            &make_progress("framework_init", 0, "应用框架初始化中...", "loading", start),
        );

        match do_framework_init(handle) {
            Ok(_) => {
                emit(
                    handle,
                    &make_progress("framework_init", 20, "应用框架初始化完成", "success", start),
                );
                return true;
            }
            Err(e) => {
                let error_msg = format!("框架初始化失败：{}", e);
                let detail = format!(
                    "错误类型: FrameworkInitError\n原因: {}\n时间: {}",
                    e,
                    Utc::now().to_rfc3339()
                );
                emit(handle, &make_error("framework_init", 0, &error_msg, &detail, start));

                if !retry.wait_with_timeout(300) {
                    return false;
                }
            }
        }
    }
}

fn do_framework_init(_handle: &tauri::AppHandle) -> Result<(), String> {
    info!("Framework init step acknowledged (already initialized in setup)");
    Ok(())
}

fn step_python_backend(
    handle: &tauri::AppHandle,
    start: &Instant,
    retry: &RetryLoop,
) -> bool {
    loop {
        emit(
            handle,
            &make_progress("python_backend", 20, "后端服务启动中...", "loading", start),
        );

        match do_start_python_backend(handle) {
            Ok(result) => {
                emit(
                    handle,
                    &make_progress(
                        "python_backend",
                        50,
                        "后端服务启动完成",
                        "success",
                        start,
                    ),
                );
                info!(
                    "Python backend started: PID={}, Port={}, Recovered={}",
                    result.pid, result.port, result.recovered
                );
                return true;
            }
            Err(e) => {
                let error_msg = format!("Python服务启动失败：{}", e);
                let detail = format!(
                    "错误类型: PythonServiceError\n原因: {}\n端口范围: 10000-60000\n时间: {}",
                    e,
                    Utc::now().to_rfc3339()
                );
                emit(
                    handle,
                    &make_error("python_backend", 20, &error_msg, &detail, start),
                );

                reset_sidecar_state(handle);

                if !retry.wait_with_timeout(300) {
                    return false;
                }
            }
        }
    }
}

fn do_start_python_backend(handle: &tauri::AppHandle) -> Result<SidecarStartResult, String> {
    let manager = get_sidecar_manager(handle);
    let version = "1.9.0";

    let python_script_path = std::env::var("SIDECAR_SCRIPT_PATH")
        .unwrap_or_else(|_| "app.main:app".to_string());

    let result = manager
        .recover_or_start(version, &python_script_path)
        .map_err(|e| format!("{}", e))?;

    if let Some(app_state) = handle.try_state::<AppState>() {
        let mut pid_lock = app_state
            .sidecar_pid
            .lock()
            .map_err(|e| format!("状态锁获取失败: {}", e))?;
        *pid_lock = Some(result.pid);
    }

    Ok(result)
}

fn step_ollama_service(
    handle: &tauri::AppHandle,
    start: &Instant,
    retry: &RetryLoop,
) -> bool {
    loop {
        emit(
            handle,
            &make_progress("ollama_service", 50, "AI服务准备中...", "loading", start),
        );

        match do_check_ollama() {
            Ok(_) => {
                emit(
                    handle,
                    &make_progress(
                        "ollama_service",
                        75,
                        "AI服务就绪",
                        "success",
                        start,
                    ),
                );
                return true;
            }
            Err(e) => {
                let error_msg = format!("Ollama服务检查失败：{}", e);
                let detail = format!(
                    "错误类型: OllamaServiceError\n原因: {}\n请确保Ollama已安装并正在运行（默认端口11434）\n时间: {}",
                    e,
                    Utc::now().to_rfc3339()
                );
                emit(
                    handle,
                    &make_error("ollama_service", 50, &error_msg, &detail, start),
                );

                if !retry.wait_with_timeout(300) {
                    return false;
                }

                std::thread::sleep(Duration::from_secs(2));
            }
        }
    }
}

fn do_check_ollama() -> Result<(), String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(10))
        .build()
        .map_err(|e| format!("无法创建HTTP客户端: {}", e))?;

    let response = client
        .get("http://localhost:11434/api/tags")
        .send()
        .map_err(|e| {
            if e.is_connect() {
                "Ollama服务未运行，请先启动Ollama (https://ollama.com)".to_string()
            } else if e.is_timeout() {
                "Ollama服务响应超时，请检查服务状态".to_string()
            } else {
                format!("Ollama服务连接失败: {}", e)
            }
        })?;

    let status = response.status();
    if !status.is_success() {
        return Err(format!("Ollama服务返回异常状态码: {}", status));
    }

    info!("Ollama service is healthy");
    Ok(())
}

fn step_model_loading(
    handle: &tauri::AppHandle,
    start: &Instant,
    retry: &RetryLoop,
) -> bool {
    loop {
        emit(
            handle,
            &make_progress("model_loading", 75, "模型文件加载中...", "loading", start),
        );

        match do_check_models() {
            Ok(models) => {
                let model_list = models.join(", ");
                let description = if models.len() == 1 {
                    format!("模型加载完成 ({})", model_list)
                } else {
                    format!("模型加载完成 ({}个模型: {})", models.len(), model_list)
                };
                emit(
                    handle,
                    &make_progress("model_loading", 100, &description, "success", start),
                );
                return true;
            }
            Err(e) => {
                let error_msg = format!("模型加载失败：{}", e);
                let detail = format!(
                    "错误类型: ModelLoadingError\n原因: {}\n建议: 运行 'ollama pull <model_name>' 下载所需模型\n时间: {}",
                    e,
                    Utc::now().to_rfc3339()
                );
                emit(
                    handle,
                    &make_error("model_loading", 75, &error_msg, &detail, start),
                );

                if !retry.wait_with_timeout(300) {
                    return false;
                }

                std::thread::sleep(Duration::from_secs(3));
            }
        }
    }
}

fn do_check_models() -> Result<Vec<String>, String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(Duration::from_secs(30))
        .build()
        .map_err(|e| format!("无法创建HTTP客户端: {}", e))?;

    let response = client
        .get("http://localhost:11434/api/tags")
        .send()
        .map_err(|e| {
            if e.is_timeout() {
                "模型列表查询超时（30秒），网络环境可能较差".to_string()
            } else {
                format!("Ollama API请求失败: {}", e)
            }
        })?;

    let json: serde_json::Value = response
        .json()
        .map_err(|e| format!("解析模型列表JSON失败: {}", e))?;

    let models: Vec<String> = json["models"]
        .as_array()
        .map(|arr| {
            arr.iter()
                .filter_map(|m| m["name"].as_str().map(String::from))
                .collect()
        })
        .unwrap_or_default();

    if models.is_empty() {
        return Err(
            "未检测到任何AI模型。请通过 'ollama pull <model>' 下载至少一个模型".to_string(),
        );
    }

    info!("Detected {} model(s): {:?}", models.len(), models);
    Ok(models)
}

pub fn run_startup_sequence(handle: tauri::AppHandle, retry_rx: mpsc::Receiver<()>) {
    let start = Instant::now();
    info!("=== Launch sequence started ===");

    let retry = RetryLoop::new(retry_rx);

    if !step_framework_init(&handle, &start, &retry) {
        error!("Framework init failed, aborting launch");
        return;
    }

    if !step_python_backend(&handle, &start, &retry) {
        error!("Python backend failed, aborting launch");
        return;
    }

    if !step_ollama_service(&handle, &start, &retry) {
        error!("Ollama service check failed, aborting launch");
        return;
    }

    if !step_model_loading(&handle, &start, &retry) {
        error!("Model loading failed, aborting launch");
        return;
    }

    emit(
        &handle,
        &make_progress("complete", 100, "启动完成", "complete", &start),
    );

    info!(
        "=== Launch sequence completed in {}s ===",
        start.elapsed().as_secs()
    );

    std::thread::sleep(Duration::from_millis(300));

    if let Some(main_window) = handle.get_webview_window("main") {
        main_window.show().ok();
        info!("Main window shown");
    }

    std::thread::sleep(Duration::from_millis(500));

    if let Some(splash) = handle.get_webview_window("splashscreen") {
        splash.close().ok();
        info!("Splashscreen closed");
    }
}

#[tauri::command]
pub fn retry_launch_step(
    step: String,
    state: tauri::State<'_, AppState>,
) -> Result<(), String> {
    info!("Retry requested for step: {}", step);

    let sender = state.retry_tx.lock().map_err(|e| {
        format!("无法获取重试通道锁: {}", e)
    })?;

    if let Some(ref tx) = *sender {
        tx.send(()).map_err(|e| {
            format!("重试信号发送失败: {}", e)
        })?;
        info!("Retry signal sent for step: {}", step);
        Ok(())
    } else {
        Err("重试通道未初始化".to_string())
    }
}