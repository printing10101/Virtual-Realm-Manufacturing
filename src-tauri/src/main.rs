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

use state::AppState;
use tauri::Manager;
use tracing::{info, warn};

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

      let db_path = app_data_dir.join("app.db");
      match database::Database::new(&db_path) {
        database => {
          database::migrate_from_json(&database);
          app.manage(database);
          info!("Database initialized at {}", db_path.display());
        }
      }

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
      commands::get_app_info,
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
    .expect("error while running tauri application");
}
