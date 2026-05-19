use serde::Serialize;
use std::fs;
use std::io::Write;
use std::path::PathBuf;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{info, warn};

#[derive(Debug, Serialize)]
pub struct LogExportResult {
    pub success: bool,
    pub message: String,
    pub output_path: Option<String>,
    pub file_count: usize,
    pub total_size_bytes: u64,
}

fn get_log_dir(app_handle: &tauri::AppHandle) -> PathBuf {
    let app_data = crate::utils::get_app_data_dir(app_handle);
    app_data.join("logs")
}

fn collect_log_files(
    log_dir: &PathBuf,
    days: u32,
) -> Result<(Vec<(PathBuf, String)>, u64), String> {
    let mut files: Vec<(PathBuf, String)> = Vec::new();
    let mut total_size: u64 = 0;

    let now = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap_or_default()
        .as_secs();

    let cutoff_secs = now.saturating_sub((days as u64) * 86400);

    if !log_dir.exists() {
        return Ok((files, total_size));
    }

    let entries = fs::read_dir(log_dir).map_err(|e| {
        format!("无法读取日志目录 '{}': {}", log_dir.display(), e)
    })?;

    for entry in entries {
        let entry = entry.map_err(|e| {
            format!("无法读取目录条目: {}", e)
        })?;

        let path = entry.path();

        if path.is_dir() {
            let dir_name = path.file_name()
                .and_then(|n| n.to_str())
                .unwrap_or("");

            if dir_name.len() == 10 && dir_name.chars().filter(|c| *c == '-').count() == 2 {
                let log_entries = fs::read_dir(&path).map_err(|e| {
                    format!("无法读取日期目录 '{}': {}", path.display(), e)
                })?;

                for log_entry in log_entries {
                    let log_entry = log_entry.map_err(|e| {
                        format!("无法读取日志条目: {}", e)
                    })?;
                    let log_path = log_entry.path();

                    if log_path.is_file() {
                        if let Ok(metadata) = log_path.metadata() {
                            let modified = metadata.modified()
                                .unwrap_or(UNIX_EPOCH)
                                .duration_since(UNIX_EPOCH)
                                .unwrap_or_default()
                                .as_secs();

                            if modified >= cutoff_secs {
                                let archive_name = format!(
                                    "{}/{}",
                                    dir_name,
                                    log_path.file_name()
                                        .and_then(|n| n.to_str())
                                        .unwrap_or("unknown")
                                );
                                total_size += metadata.len();
                                files.push((log_path, archive_name));
                            }
                        }
                    }
                }
            }
        } else if path.is_file() {
            if let Ok(metadata) = path.metadata() {
                let modified = metadata.modified()
                    .unwrap_or(UNIX_EPOCH)
                    .duration_since(UNIX_EPOCH)
                    .unwrap_or_default()
                    .as_secs();

                if modified >= cutoff_secs {
                    let archive_name = path.file_name()
                        .and_then(|n| n.to_str())
                        .unwrap_or("unknown")
                        .to_string();
                    total_size += metadata.len();
                    files.push((path, archive_name));
                }
            }
        }
    }

    Ok((files, total_size))
}

#[tauri::command]
pub fn export_logs_cmd(
    app: tauri::AppHandle,
    days: Option<u32>,
) -> Result<LogExportResult, String> {
    let days = days.unwrap_or(7);
    let log_dir = get_log_dir(&app);
    let app_data = crate::utils::get_app_data_dir(&app);
    let export_dir = app_data.join("exports");

    let _ = fs::create_dir_all(&export_dir);

    info!("Exporting logs: dir={}, days={}", log_dir.display(), days);

    let (files, total_size) = collect_log_files(&log_dir, days)?;

    if files.is_empty() {
        return Ok(LogExportResult {
            success: true,
            message: "最近 {} 天内没有日志文件".to_string(),
            output_path: None,
            file_count: 0,
            total_size_bytes: 0,
        });
    }

    let timestamp = chrono::Utc::now().format("%Y%m%d_%H%M%S");
    let zip_name = format!("logs_export_{}.zip", timestamp);
    let zip_path = export_dir.join(&zip_name);

    let zip_file = fs::File::create(&zip_path).map_err(|e| {
        format!("无法创建ZIP文件 '{}': {}", zip_path.display(), e)
    })?;

    let mut zip_writer = zip::ZipWriter::new(zip_file);
    let options = zip::write::FileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated)
        .unix_permissions(0o644);

    for (file_path, archive_name) in &files {
        match fs::read(file_path) {
            Ok(content) => {
                if let Err(e) = zip_writer.start_file(archive_name, options) {
                    warn!("Failed to add file to zip: {}: {}", archive_name, e);
                    continue;
                }
                if let Err(e) = zip_writer.write_all(&content) {
                    warn!("Failed to write file to zip: {}: {}", archive_name, e);
                    continue;
                }
            }
            Err(e) => {
                warn!("Failed to read log file '{}': {}", file_path.display(), e);
                continue;
            }
        }
    }

    zip_writer.finish().map_err(|e| {
        format!("无法完成ZIP打包: {}", e)
    })?;

    let result = LogExportResult {
        success: true,
        message: format!(
            "日志导出完成：{} 个文件，共 {} KB",
            files.len(),
            total_size / 1024
        ),
        output_path: Some(zip_path.to_string_lossy().to_string()),
        file_count: files.len(),
        total_size_bytes: total_size,
    };

    info!(
        "Logs exported: {} files, {} bytes -> {}",
        files.len(),
        total_size,
        zip_path.display()
    );

    Ok(result)
}

#[tauri::command]
pub fn get_log_dir_cmd(app: tauri::AppHandle) -> Result<String, String> {
    let log_dir = get_log_dir(&app);
    Ok(log_dir.to_string_lossy().to_string())
}