use std::fs;
use std::path::{Path, PathBuf};
use anyhow::{Result, Context};

pub fn read_file_content(path: &Path) -> Result<String> {
    fs::read_to_string(path)
        .with_context(|| format!("文件读取失败：无法读取文件 '{}'。可能原因：1) 文件不存在；2) 无读取权限；3) 文件已损坏。请确认文件路径正确且有读取权限。", path.display()))
}

pub fn write_file_content(path: &Path, content: &str) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, content)
        .with_context(|| format!("文件写入失败：无法将内容写入文件 '{}'。可能原因：1) 目标目录不存在且无创建权限；2) 磁盘空间不足；3) 文件被其他进程占用。请检查文件路径权限和磁盘状态。", path.display()))
}

pub fn list_directory(path: &Path) -> Result<Vec<PathBuf>> {
    let entries = fs::read_dir(path)
        .with_context(|| format!("目录列表获取失败：无法列出目录 '{}' 的内容。可能原因：1) 目录不存在；2) 无访问权限；3) 目录路径不正确。请确认路径存在且可访问。", path.display()))?;
    
    let mut files = Vec::new();
    for entry in entries {
        let entry = entry?;
        files.push(entry.path());
    }
    Ok(files)
}

pub fn delete_path(path: &Path) -> Result<()> {
    if path.is_dir() {
        fs::remove_dir_all(path)
            .with_context(|| format!("目录删除失败：无法删除目录 '{}'。可能原因：1) 目录不存在；2) 无删除权限；3) 目录中有被占用的文件。请检查目录状态和权限。", path.display()))
    } else {
        fs::remove_file(path)
            .with_context(|| format!("文件删除失败：无法删除文件 '{}'。可能原因：1) 文件不存在；2) 无删除权限；3) 文件被其他进程占用。请检查文件状态和权限。", path.display()))
    }
}

pub fn create_dir(path: &Path) -> Result<()> {
    fs::create_dir_all(path)
        .with_context(|| format!("目录创建失败：无法创建目录 '{}'。可能原因：1) 父目录不存在且无创建权限；2) 目录已存在；3) 磁盘空间不足。请检查路径和磁盘状态。", path.display()))
}
