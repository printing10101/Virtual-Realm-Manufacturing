use std::path::{Path, PathBuf};
use std::fs;
use tracing::{info, warn};

#[derive(Debug)]
pub struct PathSecurityError {
    pub code: String,
    pub message: String,
}

pub struct PathSecurity {
    pub base_path: PathBuf,
}

impl PathSecurity {
    pub fn new(base_path: PathBuf) -> Self {
        Self { base_path }
    }

    pub fn sanitize_path<P: AsRef<Path>>(&self, requested: P) -> Result<PathBuf, PathSecurityError> {
        let requested = requested.as_ref();

        if requested.is_absolute() {
            return Err(PathSecurityError {
                code: "ABSOLUTE_PATH_DENIED".to_string(),
                message: "绝对路径访问被拒绝：仅允许相对路径访问。请提供相对于应用数据目录的路径。".to_string(),
            });
        }

        let components: Vec<&str> = requested
            .components()
            .filter_map(|c| {
                match c {
                    std::path::Component::Normal(s) => Some(s.to_string_lossy().to_string()),
                    std::path::Component::CurDir => None,
                    std::path::Component::ParentDir => {
                        None
                    }
                    _ => None,
                }
            })
            .collect();

        if components.is_empty() {
            return Err(PathSecurityError {
                code: "EMPTY_PATH".to_string(),
                message: "路径为空：请提供有效的文件路径。".to_string(),
            });
        }

        let mut resolved = self.base_path.clone();
        for component in &components {
            resolved = resolved.join(component);
        }

        let base_canonical = self.base_path
            .canonicalize()
            .map_err(|e| PathSecurityError {
                code: "BASE_PATH_ERROR".to_string(),
                message: format!("基础路径规范化失败: {}", e),
            })?;

        let resolved_canonical = resolved
            .canonicalize()
            .map_err(|e| PathSecurityError {
                code: "PATH_RESOLUTION_ERROR".to_string(),
                message: format!("路径解析失败: {}", e),
            })?;

        if !resolved_canonical.starts_with(&base_canonical) {
            warn!("Path traversal attempt detected: {:?} tried to escape {:?}", resolved, self.base_path);
            return Err(PathSecurityError {
                code: "PATH_TRAVERSAL_DENIED".to_string(),
                message: "路径遍历被拒绝：不允许访问应用数据目录外的路径。".to_string(),
            });
        }

        self.check_symlink(&resolved)?;

        info!("Path access audit: {:?}", resolved_canonical);

        Ok(resolved_canonical)
    }

    pub fn sanitize_path_for_write<P: AsRef<Path>>(&self, requested: P) -> Result<PathBuf, PathSecurityError> {
        let requested = requested.as_ref();

        if requested.is_absolute() {
            return Err(PathSecurityError {
                code: "ABSOLUTE_PATH_DENIED".to_string(),
                message: "绝对路径访问被拒绝：仅允许相对路径访问。请提供相对于应用数据目录的路径。".to_string(),
            });
        }

        let components: Vec<&str> = requested
            .components()
            .filter_map(|c| {
                match c {
                    std::path::Component::Normal(s) => Some(s.to_string_lossy().to_string()),
                    std::path::Component::CurDir => None,
                    std::path::Component::ParentDir => {
                        None
                    }
                    _ => None,
                }
            })
            .collect();

        if components.is_empty() {
            return Err(PathSecurityError {
                code: "EMPTY_PATH".to_string(),
                message: "路径为空：请提供有效的文件路径。".to_string(),
            });
        }

        let mut resolved = self.base_path.clone();
        for component in &components {
            resolved = resolved.join(component);
        }

        let base_canonical = self.base_path
            .canonicalize()
            .map_err(|e| PathSecurityError {
                code: "BASE_PATH_ERROR".to_string(),
                message: format!("基础路径规范化失败: {}", e),
            })?;

        let resolved_canonical = resolved
            .canonicalize()
            .map_err(|e| PathSecurityError {
                code: "PATH_RESOLUTION_ERROR".to_string(),
                message: format!("路径解析失败: {}", e),
            })?;

        if !resolved_canonical.starts_with(&base_canonical) {
            warn!("Path traversal attempt detected: {:?} tried to escape {:?}", resolved, self.base_path);
            return Err(PathSecurityError {
                code: "PATH_TRAVERSAL_DENIED".to_string(),
                message: "路径遍历被拒绝：不允许访问应用数据目录外的路径。".to_string(),
            });
        }

        self.check_symlink(&resolved)?;

        info!("Path write access audit: {:?}", resolved_canonical);

        Ok(resolved_canonical)
    }

    fn check_symlink(&self, path: &Path) -> Result<(), PathSecurityError> {
        #[cfg(unix)]
        {
            let metadata = fs::symlink_metadata(path)
                .map_err(|e| PathSecurityError {
                    code: "SYMLINK_CHECK_ERROR".to_string(),
                    message: format!("符号链接检查失败: {}", e),
                })?;

            if metadata.file_type().is_symlink() {
                let link_target = fs::read_link(path)
                    .map_err(|e| PathSecurityError {
                        code: "SYMLINK_READ_ERROR".to_string(),
                        message: format!("读取符号链接目标失败: {}", e),
                    })?;

                let base_canonical = self.base_path
                    .canonicalize()
                    .map_err(|e| PathSecurityError {
                        code: "BASE_PATH_ERROR".to_string(),
                        message: format!("基础路径规范化失败: {}", e),
                    })?;

                let target_canonical = link_target
                    .canonicalize()
                    .map_err(|e| PathSecurityError {
                        code: "SYMLINK_TARGET_ERROR".to_string(),
                        message: format!("符号链接目标规范化失败: {}", e),
                    })?;

                if !target_canonical.starts_with(&base_canonical) {
                    warn!("Symlink escape detected: {:?} points to {:?}", path, link_target);
                    return Err(PathSecurityError {
                        code: "SYMLINK_ESCAPE_DENIED".to_string(),
                        message: "符号链接路径逃逸被拒绝：不允许通过符号链接访问应用数据目录外的路径。".to_string(),
                    });
                }
            }
        }

        #[cfg(windows)]
        {
            let metadata = fs::metadata(path)
                .map_err(|e| PathSecurityError {
                    code: "SYMLINK_CHECK_ERROR".to_string(),
                    message: format!("路径检查失败: {}", e),
                })?;

            if metadata.file_type().is_symlink() {
                let link_target = fs::read_link(path)
                    .map_err(|e| PathSecurityError {
                        code: "SYMLINK_READ_ERROR".to_string(),
                        message: format!("读取符号链接目标失败: {}", e),
                    })?;

                let base_canonical = self.base_path
                    .canonicalize()
                    .map_err(|e| PathSecurityError {
                        code: "BASE_PATH_ERROR".to_string(),
                        message: format!("基础路径规范化失败: {}", e),
                    })?;

                let target_canonical = link_target
                    .canonicalize()
                    .map_err(|e| PathSecurityError {
                        code: "SYMLINK_TARGET_ERROR".to_string(),
                        message: format!("符号链接目标规范化失败: {}", e),
                    })?;

                if !target_canonical.starts_with(&base_canonical) {
                    warn!("Symlink escape detected on Windows: {:?} points to {:?}", path, link_target);
                    return Err(PathSecurityError {
                        code: "SYMLINK_ESCAPE_DENIED".to_string(),
                        message: "符号链接路径逃逸被拒绝：不允许通过符号链接访问应用数据目录外的路径。".to_string(),
                    });
                }
            }
        }

        Ok(())
    }

    pub fn audit_log(&self, operation: &str, path: &Path) {
        info!("PATH_AUDIT: {} on {:?}", operation, path);
    }
}
