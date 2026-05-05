use std::fs;
use std::path::{Path, PathBuf};
use anyhow::{Result, Context};

pub fn read_file_content(path: &Path) -> Result<String> {
    fs::read_to_string(path)
        .with_context(|| format!("Failed to read file: {}", path.display()))
}

pub fn write_file_content(path: &Path, content: &str) -> Result<()> {
    if let Some(parent) = path.parent() {
        fs::create_dir_all(parent)?;
    }
    fs::write(path, content)
        .with_context(|| format!("Failed to write file: {}", path.display()))
}

pub fn list_directory(path: &Path) -> Result<Vec<PathBuf>> {
    let entries = fs::read_dir(path)
        .with_context(|| format!("Failed to read directory: {}", path.display()))?;
    
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
            .with_context(|| format!("Failed to delete directory: {}", path.display()))
    } else {
        fs::remove_file(path)
            .with_context(|| format!("Failed to delete file: {}", path.display()))
    }
}

pub fn create_dir(path: &Path) -> Result<()> {
    fs::create_dir_all(path)
        .with_context(|| format!("Failed to create directory: {}", path.display()))
}
