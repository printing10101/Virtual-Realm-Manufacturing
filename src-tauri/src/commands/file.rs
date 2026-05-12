use crate::models::FileInfo;
use crate::path_security::PathSecurity;
use crate::storage;
use serde::Serialize;
use std::path::PathBuf;
use tauri::State;

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

fn sanitize_and_validate(path: &str, path_security: &PathSecurity) -> Result<PathBuf, String> {
    path_security
        .sanitize_path(path)
        .map_err(|e| format!("路径安全检查失败：{} (代码: {})", e.message, e.code))
}

fn sanitize_and_validate_for_write(path: &str, path_security: &PathSecurity) -> Result<PathBuf, String> {
    path_security
        .sanitize_path_for_write(path)
        .map_err(|e| format!("路径安全检查失败：{} (代码: {})", e.message, e.code))
}

#[tauri::command]
pub fn save_file(
    path: String,
    content: String,
    path_security: State<PathSecurity>,
) -> Result<FileOperationResult, String> {
    let validated_path = sanitize_and_validate_for_write(&path, &path_security)?;
    storage::write_file_content(&validated_path, &content)
        .map(|_| FileOperationResult {
            success: true,
            message: "File saved successfully".to_string(),
            path: Some(validated_path.to_string_lossy().to_string()),
        })
        .map_err(|e| format!("文件保存失败：无法将内容写入文件 '{}'。错误详情: {}。可能原因：1) 目标目录不存在且无创建权限；2) 磁盘空间不足；3) 文件被其他进程占用。请检查文件路径权限和磁盘状态。", validated_path.display(), e))
}

#[tauri::command]
pub fn read_file(
    path: String,
    path_security: State<PathSecurity>,
) -> Result<String, String> {
    let validated_path = sanitize_and_validate(&path, &path_security)?;
    storage::read_file_content(&validated_path)
        .map_err(|e| format!("文件读取失败：无法读取文件 '{}'。错误详情: {}。可能原因：1) 文件不存在；2) 无读取权限；3) 文件已损坏。请确认文件路径正确且有读取权限。", validated_path.display(), e))
}

#[tauri::command]
pub fn list_files(
    directory: String,
    path_security: State<PathSecurity>,
) -> Result<Vec<FileInfo>, String> {
    let validated_path = sanitize_and_validate(&directory, &path_security)?;
    let entries = storage::list_directory(&validated_path)
        .map_err(|e| format!("目录列表获取失败：无法列出目录 '{}' 的内容。错误详情: {}。可能原因：1) 目录不存在；2) 无访问权限；3) 目录路径不正确。请确认路径存在且可访问。", validated_path.display(), e))?;
    
    let mut files = Vec::new();
    for entry in entries {
        let metadata = entry.metadata().map_err(|e| {
            format!("文件元数据获取失败：无法获取 '{}' 的元数据信息。错误详情: {}。可能原因：1) 文件已被删除；2) 权限不足。请检查文件状态。", entry.display(), e)
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
pub fn delete_file(
    path: String,
    path_security: State<PathSecurity>,
) -> Result<FileOperationResult, String> {
    let validated_path = sanitize_and_validate(&path, &path_security)?;
    storage::delete_path(&validated_path)
        .map(|_| FileOperationResult {
            success: true,
            message: "File deleted successfully".to_string(),
            path: Some(validated_path.to_string_lossy().to_string()),
        })
        .map_err(|e| format!("文件删除失败：无法删除文件 '{}'。错误详情: {}。可能原因：1) 文件不存在；2) 无删除权限；3) 文件被其他进程占用。请检查文件状态和权限。", validated_path.display(), e))
}

#[tauri::command]
pub fn create_directory(
    path: String,
    path_security: State<PathSecurity>,
) -> Result<FileOperationResult, String> {
    let validated_path = sanitize_and_validate_for_write(&path, &path_security)?;
    storage::create_dir(&validated_path)
        .map(|_| FileOperationResult {
            success: true,
            message: "Directory created successfully".to_string(),
            path: Some(validated_path.to_string_lossy().to_string()),
        })
        .map_err(|e| format!("目录创建失败：无法创建目录 '{}'。错误详情: {}。可能原因：1) 父目录不存在且无创建权限；2) 目录已存在；3) 磁盘空间不足。请检查路径和磁盘状态。", validated_path.display(), e))
}
