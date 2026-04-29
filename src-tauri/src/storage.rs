use std::fs;
use std::path::PathBuf;

use crate::models::{AppSettings, ProjectMeta};

pub fn get_app_data_dir() -> PathBuf {
    let dir = dirs::data_local_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("lingjing-v4");
    
    if !dir.exists() {
        fs::create_dir_all(&dir).expect("Failed to create app data directory");
    }
    
    dir
}

pub fn save_settings(settings: &AppSettings) -> Result<(), String> {
    let dir = get_app_data_dir();
    let path = dir.join("settings.json");
    
    let content = serde_json::to_string_pretty(settings)
        .map_err(|e| format!("Failed to serialize settings: {}", e))?;
    
    fs::write(&path, content)
        .map_err(|e| format!("Failed to write settings file: {}", e))?;
    
    Ok(())
}

pub fn load_settings() -> Result<AppSettings, String> {
    let dir = get_app_data_dir();
    let path = dir.join("settings.json");
    
    if !path.exists() {
        return Ok(AppSettings::default());
    }
    
    let content = fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read settings file: {}", e))?;
    
    let settings: AppSettings = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to deserialize settings: {}", e))?;
    
    Ok(settings)
}

pub fn save_projects(projects: &[ProjectMeta]) -> Result<(), String> {
    let dir = get_app_data_dir();
    let path = dir.join("projects.json");
    
    let content = serde_json::to_string_pretty(projects)
        .map_err(|e| format!("Failed to serialize projects: {}", e))?;
    
    fs::write(&path, content)
        .map_err(|e| format!("Failed to write projects file: {}", e))?;
    
    Ok(())
}

pub fn load_projects() -> Result<Vec<ProjectMeta>, String> {
    let dir = get_app_data_dir();
    let path = dir.join("projects.json");
    
    if !path.exists() {
        return Ok(Vec::new());
    }
    
    let content = fs::read_to_string(&path)
        .map_err(|e| format!("Failed to read projects file: {}", e))?;
    
    let projects: Vec<ProjectMeta> = serde_json::from_str(&content)
        .map_err(|e| format!("Failed to deserialize projects: {}", e))?;
    
    Ok(projects)
}
