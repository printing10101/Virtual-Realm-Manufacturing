use serde::Serialize;
use std::fs;
use std::path::Path;
use tauri::Manager;

#[derive(Debug, Serialize)]
pub struct FileInfo {
    pub name: String,
    pub path: String,
    pub is_dir: bool,
    pub size: u64,
    pub modified_at: String,
    pub extension: Option<String>,
}

#[tauri::command]
pub fn get_app_data_dir(app_handle: tauri::AppHandle) -> Result<String, String> {
    let path = app_handle.path()
        .app_data_dir()
        .map_err(|e| format!("Failed to get app data dir: {}", e))?;
    
    path.to_str()
        .map(|s| s.to_string())
        .ok_or_else(|| "Invalid path encoding".to_string())
}

#[tauri::command]
pub fn save_file(file_path: String, content: String) -> Result<(), String> {
    fs::write(&file_path, &content)
        .map_err(|e| format!("Failed to save file '{}': {}", file_path, e))
}

#[tauri::command]
pub fn read_file(file_path: String) -> Result<String, String> {
    fs::read_to_string(&file_path)
        .map_err(|e| format!("Failed to read file '{}': {}", file_path, e))
}

#[tauri::command]
pub fn list_files(dir_path: String, extension: Option<String>) -> Result<Vec<FileInfo>, String> {
    let path = Path::new(&dir_path);
    
    if !path.exists() {
        return Err(format!("Directory '{}' does not exist", dir_path));
    }
    
    if !path.is_dir() {
        return Err(format!("'{}' is not a directory", dir_path));
    }
    
    let entries = fs::read_dir(path)
        .map_err(|e| format!("Failed to read directory '{}': {}", dir_path, e))?;
    
    let mut files = Vec::new();
    
    for entry in entries {
        let entry = entry.map_err(|e| format!("Failed to read entry: {}", e))?;
        let path = entry.path();
        let metadata = entry.metadata()
            .map_err(|e| format!("Failed to read metadata: {}", e))?;
        
        let file_name = entry.file_name()
            .to_string_lossy()
            .to_string();
        
        if let Some(ref ext_filter) = extension {
            if let Some(file_ext) = path.extension() {
                if file_ext.to_string_lossy() != *ext_filter {
                    continue;
                }
            } else {
                continue;
            }
        }
        
        let modified_at = metadata.modified()
            .map(|time| {
                use std::time::UNIX_EPOCH;
                let duration = time.duration_since(UNIX_EPOCH).unwrap_or_default();
                chrono::DateTime::from_timestamp(duration.as_secs() as i64, 0)
                    .map(|dt| dt.to_rfc3339())
                    .unwrap_or_else(|| "unknown".to_string())
            })
            .unwrap_or_else(|_| "unknown".to_string());
        
        let file_ext = path.extension()
            .map(|e| e.to_string_lossy().to_string());
        
        files.push(FileInfo {
            name: file_name,
            path: path.to_string_lossy().to_string(),
            is_dir: metadata.is_dir(),
            size: metadata.len(),
            modified_at,
            extension: file_ext,
        });
    }
    
    Ok(files)
}

#[tauri::command]
pub fn delete_file(file_path: String, recursive: bool) -> Result<(), String> {
    let path = Path::new(&file_path);
    
    if !path.exists() {
        return Err(format!("'{}' does not exist", file_path));
    }
    
    if path.is_dir() {
        if recursive {
            fs::remove_dir_all(&file_path)
                .map_err(|e| format!("Failed to delete directory '{}': {}", file_path, e))
        } else {
            fs::remove_dir(&file_path)
                .map_err(|e| format!("Failed to delete directory '{}': {}", file_path, e))
        }
    } else {
        fs::remove_file(&file_path)
            .map_err(|e| format!("Failed to delete file '{}': {}", file_path, e))
    }
}

#[tauri::command]
pub fn create_directory(dir_path: String, recursive: bool) -> Result<(), String> {
    if recursive {
        fs::create_dir_all(&dir_path)
            .map_err(|e| format!("Failed to create directory '{}': {}", dir_path, e))
    } else {
        fs::create_dir(&dir_path)
            .map_err(|e| format!("Failed to create directory '{}': {}", dir_path, e))
    }
}
