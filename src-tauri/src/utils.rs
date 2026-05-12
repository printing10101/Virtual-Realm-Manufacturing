use std::path::PathBuf;
use tauri::Manager;

pub fn get_app_data_dir(app: &tauri::AppHandle) -> PathBuf {
    app.path().app_data_dir()
        .expect("获取应用数据目录失败：无法确定应用程序的数据存储路径。可能原因：1) 操作系统权限限制；2) 用户目录配置异常。请检查应用程序是否有足够的文件系统访问权限。")
}

pub fn format_timestamp(timestamp: chrono::DateTime<chrono::Utc>) -> String {
    timestamp.format("%Y-%m-%d %H:%M:%S").to_string()
}
