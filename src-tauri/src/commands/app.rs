use serde::Serialize;

#[derive(Debug, Serialize)]
pub struct AppInfo {
    pub app_name: String,
    pub version: String,
    pub tauri_version: String,
    pub os: String,
    pub os_version: String,
    pub arch: String,
    pub hostname: String,
}

#[tauri::command]
pub fn get_app_info(app_handle: tauri::AppHandle) -> Result<AppInfo, String> {
    let package_info = app_handle.package_info();
    
    let os = std::env::consts::OS.to_string();
    let os_version = "unknown".to_string();
    let arch = std::env::consts::ARCH.to_string();
    let hostname = gethostname::gethostname()
        .to_string_lossy()
        .to_string();
    
    Ok(AppInfo {
        app_name: package_info.name.clone(),
        version: package_info.version.to_string(),
        tauri_version: "2".to_string(),
        os,
        os_version,
        arch,
        hostname,
    })
}

#[tauri::command]
pub fn open_external_url(_app_handle: tauri::AppHandle, url: String) -> Result<(), String> {
    open::that(&url)
        .map_err(|e| format!("Failed to open URL: {}", e))
}
