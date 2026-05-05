use crate::models::AppInfo;

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
pub fn open_external_url(url: String) -> Result<bool, String> {
    open::that(&url)
        .map(|_| true)
        .map_err(|e| format!("Failed to open URL: {}", e))
}
