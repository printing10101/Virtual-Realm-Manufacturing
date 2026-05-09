use crate::models::AppSettings;
use std::path::PathBuf;
use tracing::{info, warn};

pub struct Database {
    db_path: PathBuf,
}

impl Database {
    pub fn new(db_path: &PathBuf) -> Self {
        if let Some(parent) = db_path.parent() {
            if let Err(e) = std::fs::create_dir_all(parent) {
                warn!("Failed to create database directory {}: {}", parent.display(), e);
            }
        }
        Self {
            db_path: db_path.clone(),
        }
    }

    pub fn save_settings(&self, settings: &AppSettings) -> Result<(), anyhow::Error> {
        let path = self.settings_path();
        let content = serde_json::to_string_pretty(settings)?;
        std::fs::write(&path, content)?;
        Ok(())
    }

    pub fn load_settings(&self) -> Result<AppSettings, anyhow::Error> {
        let path = self.settings_path();
        if path.exists() {
            let content = std::fs::read_to_string(&path)?;
            Ok(serde_json::from_str(&content)?)
        } else {
            Ok(AppSettings::default())
        }
    }

    fn settings_path(&self) -> PathBuf {
        self.db_path.parent().map_or_else(
            || PathBuf::from("settings.json"),
            |p| p.join("settings.json"),
        )
    }
}

pub fn migrate_from_json(db: &Database) {
    let app_data = get_app_data_dir_static();
    let settings_path = app_data.join("settings.json");

    if !settings_path.exists() {
        return;
    }

    match std::fs::read_to_string(&settings_path) {
        Ok(content) => match serde_json::from_str::<AppSettings>(&content) {
            Ok(settings) => {
                if let Err(e) = db.save_settings(&settings) {
                    warn!("Failed to save migrated settings: {}", e);
                    return;
                }
                if let Err(e) = std::fs::rename(&settings_path, settings_path.with_extension("json.bak")) {
                    warn!("Failed to backup old settings file: {}", e);
                } else {
                    info!("Settings migrated from JSON to database");
                }
            }
            Err(e) => warn!("Failed to parse old settings file: {}", e),
        },
        Err(e) => warn!("Failed to read old settings file: {}", e),
    }
}

fn get_app_data_dir_static() -> PathBuf {
    dirs::data_dir()
        .unwrap_or_else(|| PathBuf::from("."))
        .join("lingjing")
}
