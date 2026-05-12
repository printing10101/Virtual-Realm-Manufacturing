use crate::models::AppInfo;
use tauri::State;
use crate::version::VersionInfo;
use crate::state::AppState;
use serde::Serialize;
use std::sync::Mutex;
use tracing::warn;

#[derive(Serialize, Clone)]
pub struct VersionStatus {
    pub rust_version: String,
    pub rust_commit: String,
    pub python_version: Option<String>,
    pub python_commit: Option<String>,
    pub is_consistent: bool,
}

fn fetch_python_version() -> Option<(String, String)> {
    let port = std::env::var("SIDECAR_PORT").unwrap_or_else(|_| "8000".to_string());
    let url = format!("http://127.0.0.1:{}/api/v1/version", port);

    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(3))
        .build()
        .ok()?;

    let response = client.get(&url).send().ok()?;
    let status = response.status();
    if !status.is_success() {
        return None;
    }

    let body = response.text().ok()?;
    let json: serde_json::Value = serde_json::from_str(&body).ok()?;

    let version = json.get("version")?.as_str()?.to_string();
    let commit = json.get("commit")?.as_str()?.to_string();

    Some((version, commit))
}

#[tauri::command]
pub fn get_app_info() -> AppInfo {
    AppInfo {
        name: env!("CARGO_PKG_NAME").to_string(),
        version: env!("CARGO_PKG_VERSION").to_string(),
        description: env!("CARGO_PKG_DESCRIPTION").to_string(),
        platform: std::env::consts::OS.to_string(),
        arch: std::env::consts::ARCH.to_string(),
    }
}

#[tauri::command]
pub fn get_version_info(state: State<VersionInfo>) -> VersionStatus {
    let rust_version = state.version.clone();
    let rust_commit = state.commit.clone();

    let (python_version, python_commit) = fetch_python_version()
        .unwrap_or_else(|| (None, None));

    let is_consistent = python_version
        .as_ref()
        .map(|pv| pv == &rust_version)
        .unwrap_or(false);

    VersionStatus {
        rust_version,
        rust_commit,
        python_version,
        python_commit,
        is_consistent,
    }
}

#[tauri::command]
pub fn open_external_url(url: String) -> Result<bool, String> {
    open::that(&url)
        .map(|_| true)
        .map_err(|e| format!("外部链接打开失败：无法在浏览器中打开 URL '{}'。错误详情: {}。可能原因：1) 系统默认浏览器未配置；2) URL 格式无效；3) 系统安全策略阻止。请检查 URL 格式或手动在浏览器中访问。", url, e))
}
