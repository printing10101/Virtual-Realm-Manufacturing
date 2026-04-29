use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppSettings {
    pub python_backend_url: String,
    pub ollama_url: String,
    pub default_model: String,
    pub theme: String,
    pub auto_save: bool,
    pub language: String,
}

impl Default for AppSettings {
    fn default() -> Self {
        Self {
            python_backend_url: "http://localhost:8000".to_string(),
            ollama_url: "http://localhost:11434".to_string(),
            default_model: "qwen2.5-coder:7b".to_string(),
            theme: "light".to_string(),
            auto_save: true,
            language: "zh-CN".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct CloudApiSettings {
    pub api_key: String,
    pub base_url: String,
    pub model: String,
}

impl Default for CloudApiSettings {
    fn default() -> Self {
        Self {
            api_key: String::new(),
            base_url: "https://api.openai.com/v1".to_string(),
            model: "gpt-3.5-turbo".to_string(),
        }
    }
}

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct ProjectMeta {
    pub id: String,
    pub name: String,
    pub description: String,
    pub created_at: String,
    pub updated_at: String,
    pub status: String,
    pub model_path: String,
    pub nc_program_path: String,
}
