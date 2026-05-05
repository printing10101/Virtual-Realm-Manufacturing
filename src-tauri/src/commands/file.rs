use crate::models::FileInfo;
use crate::storage;
use serde::Serialize;
use std::path::PathBuf;

#[derive(Debug, Serialize)]
pub struct FileOperationResult {
    pub success: bool,
    pub message: String,
    pub path: Option<String>,
}

#[tauri::command]
pub fn get_app_data_dir(app: tauri::AppHandle) -> Result<String, String> {
    let app_data_dir = crate::utils::get_app_data_dir(&app);
    Ok(app_data_dir.to_string_lossy().to_string())
}

#[tauri::command]
pub fn save_file(path: String, content: String) -> Result<FileOperationResult, String> {
    let path = PathBuf::from(path);
    storage::write_file_content(&path, &content)
        .map(|_| FileOperationResult {
            success: true,
            message: "File saved successfully".to_string(),
            path: Some(path.to_string_lossy().to_string()),
        })
        .map_err(|e| format!("Failed to save file: {}", e))
}

#[tauri::command]
pub fn read_file(path: String) -> Result<String, String> {
    let path = PathBuf::from(path);
    storage::read_file_content(&path)
        .map_err(|e| format!("Failed to read file: {}", e))
}

#[tauri::command]
pub fn list_files(directory: String) -> Result<Vec<FileInfo>, String> {
    let path = PathBuf::from(directory);
    let entries = storage::list_directory(&path)
        .map_err(|e| format!("Failed to list directory: {}", e))?;
    
    let mut files = Vec::new();
    for entry in entries {
        let metadata = entry.metadata().map_err(|e| {
            format!("Failed to get metadata for {}: {}", entry.display(), e)
        })?;
        
        let is_dir = metadata.is_dir();
        let name = entry.file_name()
            .map(|n| n.to_string_lossy().to_string())
            .unwrap_or_default();
        
        let created = metadata.created()
            .ok()
            .map(|t| crate::utils::format_timestamp(t.into()))
            .unwrap_or_default();
        
        let modified = metadata.modified()
            .ok()
            .map(|t| crate::utils::format_timestamp(t.into()))
            .unwrap_or_default();
        
        files.push(FileInfo {
            name,
            path: entry.to_string_lossy().to_string(),
            size: metadata.len(),
            is_directory: is_dir,
            created_at: created,
            modified_at: modified,
        });
    }
    
    Ok(files)
}

#[tauri::command]
pub fn delete_file(path: String) -> Result<FileOperationResult, String> {
    let path = PathBuf::from(path);
    storage::delete_path(&path)
        .map(|_| FileOperationResult {
            success: true,
            message: "File deleted successfully".to_string(),
            path: Some(path.to_string_lossy().to_string()),
        })
        .map_err(|e| format!("Failed to delete file: {}", e))
}

#[tauri::command]
pub fn create_directory(path: String) -> Result<FileOperationResult, String> {
    let path = PathBuf::from(path);
    storage::create_dir(&path)
        .map(|_| FileOperationResult {
            success: true,
            message: "Directory created successfully".to_string(),
            path: Some(path.to_string_lossy().to_string()),
        })
        .map_err(|e| format!("Failed to create directory: {}", e))
}
