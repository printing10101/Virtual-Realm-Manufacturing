use crate::models::{AppSettings, ProjectMeta};
use crate::storage;
use chrono::Utc;
use uuid::Uuid;

#[tauri::command]
pub fn get_settings() -> Result<AppSettings, String> {
    storage::load_settings()
}

#[tauri::command]
pub fn save_settings_cmd(settings: AppSettings) -> Result<(), String> {
    storage::save_settings(&settings)
}

#[tauri::command]
pub fn get_projects() -> Result<Vec<ProjectMeta>, String> {
    storage::load_projects()
}

#[tauri::command]
pub fn add_project_cmd(name: String, description: String) -> Result<ProjectMeta, String> {
    let mut projects = storage::load_projects()?;
    
    let now = Utc::now().to_rfc3339();
    let project = ProjectMeta {
        id: Uuid::new_v4().to_string(),
        name,
        description,
        created_at: now.clone(),
        updated_at: now,
        status: "active".to_string(),
        model_path: String::new(),
        nc_program_path: String::new(),
    };
    
    projects.push(project.clone());
    storage::save_projects(&projects)?;
    
    Ok(project)
}

#[tauri::command]
pub fn delete_project_cmd(project_id: String) -> Result<(), String> {
    let mut projects = storage::load_projects()?;
    
    let initial_len = projects.len();
    projects.retain(|p| p.id != project_id);
    
    if projects.len() == initial_len {
        return Err(format!("Project not found: {}", project_id));
    }
    
    storage::save_projects(&projects)
}
