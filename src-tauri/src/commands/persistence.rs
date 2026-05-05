use crate::models::{AppSettings, Project};
use serde::Serialize;
use std::fs;
use std::path::PathBuf;

#[derive(Debug, Serialize)]
pub struct PersistenceResult {
    pub success: bool,
    pub message: String,
}

fn get_settings_path() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or("Failed to get home directory")?;
    let settings_dir = home.join(".lingjing");
    if !settings_dir.exists() {
        fs::create_dir_all(&settings_dir)
            .map_err(|e| format!("Failed to create settings directory: {}", e))?;
    }
    Ok(settings_dir.join("settings.json"))
}

#[tauri::command]
pub fn get_settings() -> Result<AppSettings, String> {
    let path = get_settings_path()?;
    
    if path.exists() {
        let content = fs::read_to_string(&path)
            .map_err(|e| format!("Failed to read settings: {}", e))?;
        
        serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse settings: {}", e))
    } else {
        let default_settings = AppSettings {
            theme: "light".to_string(),
            language: "zh-CN".to_string(),
            auto_save: true,
            max_file_size: 100 * 1024 * 1024,
        };
        
        save_settings_internal(&default_settings, &path)?;
        Ok(default_settings)
    }
}

#[tauri::command]
pub fn save_settings_cmd(settings: AppSettings) -> Result<PersistenceResult, String> {
    let path = get_settings_path()?;
    save_settings_internal(&settings, &path)?;
    
    Ok(PersistenceResult {
        success: true,
        message: "Settings saved successfully".to_string(),
    })
}

fn save_settings_internal(settings: &AppSettings, path: &PathBuf) -> Result<(), String> {
    let content = serde_json::to_string_pretty(settings)
        .map_err(|e| format!("Failed to serialize settings: {}", e))?;
    
    fs::write(path, content)
        .map_err(|e| format!("Failed to save settings: {}", e))
}

#[tauri::command]
pub fn get_projects() -> Result<Vec<Project>, String> {
    let path = get_projects_path()?;
    
    if path.exists() {
        let content = fs::read_to_string(&path)
            .map_err(|e| format!("Failed to read projects: {}", e))?;
        
        serde_json::from_str(&content)
            .map_err(|e| format!("Failed to parse projects: {}", e))
    } else {
        Ok(Vec::new())
    }
}

#[tauri::command]
pub fn add_project_cmd(project: Project) -> Result<PersistenceResult, String> {
    let mut projects = get_projects()?;
    projects.push(project);
    save_projects(&projects)
}

#[tauri::command]
pub fn delete_project_cmd(project_id: String) -> Result<PersistenceResult, String> {
    let mut projects = get_projects()?;
    projects.retain(|p| p.id != project_id);
    save_projects(&projects)
}

fn get_projects_path() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or("Failed to get home directory")?;
    let projects_dir = home.join(".lingjing");
    if !projects_dir.exists() {
        fs::create_dir_all(&projects_dir)
            .map_err(|e| format!("Failed to create projects directory: {}", e))?;
    }
    Ok(projects_dir.join("projects.json"))
}

fn save_projects(projects: &[Project]) -> Result<PersistenceResult, String> {
    let path = get_projects_path()?;
    let content = serde_json::to_string_pretty(projects)
        .map_err(|e| format!("Failed to serialize projects: {}", e))?;
    
    fs::write(&path, content)
        .map_err(|e| format!("Failed to save projects: {}", e))?;
    
    Ok(PersistenceResult {
        success: true,
        message: "Projects saved successfully".to_string(),
    })
}
