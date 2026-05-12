use crate::models::{AppSettings, Project};
use serde::Serialize;
use std::fs;
use std::path::PathBuf;
use std::sync::Mutex;
use tracing::info;

static SETTINGS_LOCK: Mutex<()> = Mutex::new(());
static PROJECTS_LOCK: Mutex<()> = Mutex::new(());

#[derive(Debug, Serialize)]
pub struct PersistenceResult {
    pub success: bool,
    pub message: String,
}

fn get_base_dir() -> Result<PathBuf, String> {
    let home = dirs::home_dir().ok_or("无法获取用户主目录：系统无法确定当前用户的主目录路径。可能原因：1) HOME 环境变量未设置；2) 系统配置异常。请设置 HOME 环境变量或检查系统用户配置。")?;
    let base_dir = home.join(".lingjing");
    if !base_dir.exists() {
        fs::create_dir_all(&base_dir)
            .map_err(|e| format!("基础目录创建失败：无法创建数据目录 '{}'。错误详情: {}。可能原因：1) 磁盘空间不足；2) 用户目录无写入权限。请检查磁盘空间和目录权限。", base_dir.display(), e))?;
    }
    Ok(base_dir)
}

fn get_settings_path() -> Result<PathBuf, String> {
    Ok(get_base_dir()?.join("settings.json"))
}

fn get_projects_path() -> Result<PathBuf, String> {
    Ok(get_base_dir()?.join("projects.json"))
}

#[tauri::command]
pub fn get_settings() -> Result<AppSettings, String> {
    let path = get_settings_path()?;

    if path.exists() {
        let content = fs::read_to_string(&path)
            .map_err(|e| format!("配置文件读取失败：无法读取配置文件 '{}'。错误详情: {}。可能原因：1) 文件不存在；2) 无读取权限；3) 文件已损坏。请检查文件状态。", path.display(), e))?;

        serde_json::from_str(&content)
            .map_err(|e| format!("配置文件解析失败：无法解析配置内容。错误详情: {}。可能原因：1) 配置文件 JSON 格式不正确；2) 配置字段类型不匹配。请检查配置文件格式是否符合预期。", e))
    } else {
        let default_settings = AppSettings::default();
        save_settings_internal(&default_settings, &path)?;
        Ok(default_settings)
    }
}

#[tauri::command]
pub fn save_settings_cmd(settings: AppSettings) -> Result<PersistenceResult, String> {
    let _lock = SETTINGS_LOCK.lock().map_err(|e| format!("配置保存失败：无法获取配置锁。错误详情: {}。可能原因：1) 并发写入冲突；2) 互斥锁状态异常。请等待其他配置操作完成后再试。", e))?;
    let path = get_settings_path()?;
    save_settings_internal(&settings, &path)?;

    Ok(PersistenceResult {
        success: true,
        message: "Settings saved successfully".to_string(),
    })
}

fn save_settings_internal(settings: &AppSettings, path: &PathBuf) -> Result<(), String> {
    let content = serde_json::to_string_pretty(settings)
        .map_err(|e| format!("配置序列化失败：无法将配置对象转换为 JSON 格式。错误详情: {}。可能原因：配置数据包含不支持序列化的类型。请检查配置对象的数据结构。", e))?;

    fs::write(path, content)
        .map_err(|e| format!("配置保存失败：无法将配置写入文件 '{}'。错误详情: {}。可能原因：1) 磁盘空间不足；2) 文件被其他进程占用；3) 无写入权限。请检查磁盘状态和文件权限。", path.display(), e))
}

#[tauri::command]
pub fn get_projects() -> Result<Vec<Project>, String> {
    let path = get_projects_path()?;

    if path.exists() {
        let content = fs::read_to_string(&path)
            .map_err(|e| format!("项目列表读取失败：无法读取项目数据文件 '{}'。错误详情: {}。可能原因：1) 文件不存在；2) 无读取权限。请检查文件状态。", path.display(), e))?;

        serde_json::from_str(&content)
            .map_err(|e| format!("项目数据解析失败：无法解析项目数据。错误详情: {}。可能原因：1) 项目数据 JSON 格式不正确；2) 项目数据结构与预期不符。请检查项目数据文件格式。", e))
    } else {
        Ok(Vec::new())
    }
}

#[tauri::command]
pub fn add_project_cmd(project: Project) -> Result<PersistenceResult, String> {
    let _lock = PROJECTS_LOCK.lock().map_err(|e| format!("项目创建失败：无法获取项目锁。错误详情: {}。可能原因：1) 并发写入冲突；2) 互斥锁状态异常。请等待其他项目操作完成后再试。", e))?;
    let mut projects = get_projects()?;
    projects.push(project);
    save_projects(&projects)
}

#[tauri::command]
pub fn delete_project_cmd(project_id: String) -> Result<PersistenceResult, String> {
    let _lock = PROJECTS_LOCK.lock().map_err(|e| format!("项目删除失败：无法获取项目锁。错误详情: {}。可能原因：1) 并发写入冲突；2) 互斥锁状态异常。请等待其他项目操作完成后再试。", e))?;
    let mut projects = get_projects()?;
    projects.retain(|p| p.id != project_id);
    save_projects(&projects)
}

fn save_projects(projects: &[Project]) -> Result<PersistenceResult, String> {
    let path = get_projects_path()?;
    let content = serde_json::to_string_pretty(projects)
        .map_err(|e| format!("项目数据序列化失败：无法将项目列表转换为 JSON 格式。错误详情: {}。请检查项目数据结构。", e))?;

    fs::write(&path, content)
        .map_err(|e| format!("项目数据保存失败：无法将项目数据写入文件 '{}'。错误详情: {}。可能原因：1) 磁盘空间不足；2) 文件被其他进程占用；3) 无写入权限。请检查磁盘状态和文件权限。", path.display(), e))?;

    info!("Projects saved to {}", path.display());

    Ok(PersistenceResult {
        success: true,
        message: "Projects saved successfully".to_string(),
    })
}
