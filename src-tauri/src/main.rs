#![cfg_attr(
  all(not(debug_assertions), target_os = "windows"),
  windows_subsystem = "windows"
)]

mod commands;
mod models;
mod state;
mod storage;
mod utils;

use state::AppState;
use tauri::Manager;

fn main() {
  let app_state = AppState::new();
  
  tauri::Builder::default()
    .manage(app_state)
    .setup(|app| {
      let app_data_dir = app.path().app_data_dir()
        .expect("Failed to get app data dir");
      std::fs::create_dir_all(&app_data_dir)
        .expect("Failed to create app data directory");
      
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
