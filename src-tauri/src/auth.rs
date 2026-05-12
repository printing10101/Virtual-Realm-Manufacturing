use std::path::PathBuf;
use std::sync::Mutex;
use uuid::Uuid;

#[cfg(unix)]
use std::os::unix::fs::PermissionsExt;

pub struct TokenManager {
    token: Mutex<Option<String>>,
    token_file_path: PathBuf,
}

impl TokenManager {
    pub fn new(token_file_path: PathBuf) -> Self {
        Self {
            token: Mutex::new(None),
            token_file_path,
        }
    }

    pub fn initialize(&self) -> Result<String, String> {
        let existing = self.load()?;
        if let Some(t) = existing {
            let mut guard = self.token.lock().map_err(|e| format!("Token lock error: {}", e))?;
            *guard = Some(t.clone());
            return Ok(t);
        }

        let new_token = Uuid::new_v4().to_string();
        self.save(&new_token)?;

        let mut guard = self.token.lock().map_err(|e| format!("Token lock error: {}", e))?;
        *guard = Some(new_token.clone());
        Ok(new_token)
    }

    pub fn get_token(&self) -> Result<Option<String>, String> {
        let guard = self.token.lock().map_err(|e| format!("Token lock error: {}", e))?;
        Ok(guard.clone())
    }

    fn save(&self, token: &str) -> Result<(), String> {
        std::fs::write(&self.token_file_path, token)
            .map_err(|e| format!("Failed to write token file: {}", e))?;

        #[cfg(unix)]
        {
            let mut perms = std::fs::metadata(&self.token_file_path)
                .map_err(|e| format!("Failed to read token file metadata: {}", e))?
                .permissions();
            perms.set_mode(0o600);
            std::fs::set_permissions(&self.token_file_path, perms)
                .map_err(|e| format!("Failed to set token file permissions: {}", e))?;
        }

        Ok(())
    }

    fn load(&self) -> Result<Option<String>, String> {
        if !self.token_file_path.exists() {
            return Ok(None);
        }

        let content = std::fs::read_to_string(&self.token_file_path)
            .map_err(|e| format!("Failed to read token file: {}", e))?;

        let trimmed = content.trim().to_string();
        if trimmed.is_empty() {
            return Ok(None);
        }

        Ok(Some(trimmed))
    }
}
