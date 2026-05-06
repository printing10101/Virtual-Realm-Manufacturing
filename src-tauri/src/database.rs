use rusqlite::{Connection, Result, OptionalExtension};
use std::path::PathBuf;
use std::sync::Mutex;

use crate::models::{AppSettings, ProjectMeta};

pub struct Database {
    conn: Mutex<Connection>,
}

impl Database {
    pub fn new(db_path: &PathBuf) -> Result<Self> {
        if let Some(parent) = db_path.parent() {
            std::fs::create_dir_all(parent).ok();
        }

        let conn = Connection::open(db_path)?;
        
        conn.execute_batch(
            "BEGIN;
            
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            
            CREATE TABLE IF NOT EXISTS projects (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                model_path TEXT NOT NULL DEFAULT '',
                nc_program_path TEXT NOT NULL DEFAULT ''
            );
            
            COMMIT;"
        )?;
        
        Ok(Self {
            conn: Mutex::new(conn),
        })
    }
    
    pub fn save_setting(&self, key: &str, value: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT OR REPLACE INTO settings (key, value) VALUES (?1, ?2)",
            (key, value),
        )?;
        Ok(())
    }
    
    pub fn load_setting(&self, key: &str) -> Result<Option<String>> {
        let conn = self.conn.lock().unwrap();
        conn.query_row(
            "SELECT value FROM settings WHERE key = ?1",
            [key],
            |row| row.get(0),
        ).optional()
    }
    
    pub fn save_settings(&self, settings: &AppSettings) -> Result<()> {
        self.save_setting("python_backend_url", &settings.python_backend_url)?;
        self.save_setting("ollama_url", &settings.ollama_url)?;
        self.save_setting("default_model", &settings.default_model)?;
        self.save_setting("theme", &settings.theme)?;
        self.save_setting("auto_save", &settings.auto_save.to_string())?;
        self.save_setting("language", &settings.language)?;
        Ok(())
    }
    
    pub fn load_settings(&self) -> Result<AppSettings> {
        let mut settings = AppSettings::default();
        
        if let Some(val) = self.load_setting("python_backend_url")? {
            settings.python_backend_url = val;
        }
        if let Some(val) = self.load_setting("ollama_url")? {
            settings.ollama_url = val;
        }
        if let Some(val) = self.load_setting("default_model")? {
            settings.default_model = val;
        }
        if let Some(val) = self.load_setting("theme")? {
            settings.theme = val;
        }
        if let Some(val) = self.load_setting("auto_save")? {
            settings.auto_save = val.parse().unwrap_or(true);
        }
        if let Some(val) = self.load_setting("language")? {
            settings.language = val;
        }
        
        Ok(settings)
    }
    
    pub fn save_project(&self, project: &ProjectMeta) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute(
            "INSERT OR REPLACE INTO projects 
             (id, name, description, created_at, updated_at, status, model_path, nc_program_path) 
             VALUES (?1, ?2, ?3, ?4, ?5, ?6, ?7, ?8)",
            (
                &project.id,
                &project.name,
                &project.description,
                &project.created_at,
                &project.updated_at,
                &project.status,
                &project.model_path,
                &project.nc_program_path,
            ),
        )?;
        Ok(())
    }
    
    pub fn delete_project(&self, id: &str) -> Result<()> {
        let conn = self.conn.lock().unwrap();
        conn.execute("DELETE FROM projects WHERE id = ?1", [id])?;
        Ok(())
    }
    
    pub fn load_projects(&self) -> Result<Vec<ProjectMeta>> {
        let conn = self.conn.lock().unwrap();
        let mut stmt = conn.prepare(
            "SELECT id, name, description, created_at, updated_at, status, model_path, nc_program_path 
             FROM projects ORDER BY created_at DESC"
        )?;
        
        let projects = stmt.query_map([], |row| {
            Ok(ProjectMeta {
                id: row.get(0)?,
                name: row.get(1)?,
                description: row.get(2)?,
                created_at: row.get(3)?,
                updated_at: row.get(4)?,
                status: row.get(5)?,
                model_path: row.get(6)?,
                nc_program_path: row.get(7)?,
            })
        })?;
        
        projects.collect()
    }
}

pub fn migrate_from_json(db: &Database) {
    let json_dir = crate::storage::get_app_data_dir();
    
    let settings_path = json_dir.join("settings.json");
    if settings_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&settings_path) {
            if let Ok(settings) = serde_json::from_str::<AppSettings>(&content) {
                if db.save_settings(&settings).is_ok() {
                    let _ = std::fs::rename(&settings_path, settings_path.with_extension("json.bak"));
                }
            }
        }
    }
    
    let projects_path = json_dir.join("projects.json");
    if projects_path.exists() {
        if let Ok(content) = std::fs::read_to_string(&projects_path) {
            if let Ok(projects) = serde_json::from_str::<Vec<ProjectMeta>>(&content) {
                for project in &projects {
                    let _ = db.save_project(project);
                }
                let _ = std::fs::rename(&projects_path, projects_path.with_extension("json.bak"));
            }
        }
    }
}
