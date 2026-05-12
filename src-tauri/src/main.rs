#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

mod commands;
mod database;
mod models;
mod state;
mod storage;
mod utils;
mod auth;
mod path_security;
mod version;
mod sidecar_manager;

use state::AppState;
use tauri::Manager;
use tracing::{info, warn};
use version::VersionInfo;

fn main() {
  let app_state = AppState::new();

  tauri::Builder::default()
    .manage(app_state)
    .setup(|app| {
      let app_data_dir = match app.path().app_data_dir() {
        Ok(dir) => dir,
        Err(e) => {
          warn!("Failed to get app data dir: {}. Using fallback.", e);
          dirs::home_dir()
            .unwrap_or_default()
            .join(".lingjing")
        }
      };

      if let Err(e) = std::fs::create_dir_all(&app_data_dir) {
        warn!("Failed to create app data directory: {}", e);
      }

      let token_file = app_data_dir.join(".lnn_token");
      let token_manager = auth::TokenManager::new(token_file.clone());
      let token = match token_manager.initialize() {
        Ok(t) => {
          info!("Token initialized successfully");
          t
        }
        Err(e) => {
          warn!("Token initialization failed: {}. Using fallback.", e);
          String::new()
        }
      };
      app.manage(token_manager);

      let path_security = path_security::PathSecurity::new(app_data_dir.clone());
      app.manage(path_security);

      let version_info = VersionInfo::rust_version();
      app.manage(version_info.clone());
      info!("Application version: {} (commit: {})", version_info.version, version_info.commit);

      let db_path = app_data_dir.join("app.db");
      let db = database::Database::new(&db_path);
      database::migrate_from_json(&db);
      app.manage(db);
      info!("Database initialized at {}", db_path.display());
      info!("Security token file: {}", token_file.display());

      Ok(())
    })
    .invoke_handler(tauri::generate_handler![
      commands::get_app_data_dir,
      commands::save_file,
      commands::read_file,
      commands::list_files,
      commands::delete_file,
      commands::create_directory,
      commands::start_sidecar,
      commands::stop_sidecar,
      commands::check_sidecar_status,
      commands::restart_sidecar,
      commands::auto_reconnect_sidecar,
      commands::force_restart_sidecar,
      commands::get_app_info,
      commands::get_version_info,
      commands::open_external_url,
      commands::get_settings,
      commands::save_settings_cmd,
      commands::get_projects,
      commands::add_project_cmd,
      commands::delete_project_cmd,
      commands::proxy_http_request,
      commands::proxy_batch_request,
      commands::proxy_health_check,
    ])
    .run(tauri::generate_context!())
    .expect("Tauri 应用启动失败：无法初始化桌面应用运行时。可能原因：1) Tauri 配置文件（tauri.conf.json）格式错误；2) 前端资源文件缺失；3) 系统依赖不满足。请检查 src-tauri/tauri.conf.json 配置，或查看日志获取详细错误信息。");
}
