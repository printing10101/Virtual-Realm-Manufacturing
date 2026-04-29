use std::fs;

use crate::models::CloudApiSettings;

fn get_api_key_path() -> std::path::PathBuf {
    crate::storage::get_app_data_dir().join("cloud_api_key.dat")
}

fn get_settings_path() -> std::path::PathBuf {
    crate::storage::get_app_data_dir().join("cloud_api_settings.json")
}

#[cfg(target_os = "windows")]
fn encrypt_with_machine_key(data: &[u8]) -> Vec<u8> {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let hostname = gethostname::gethostname()
        .to_string_lossy()
        .to_string();
    
    let mut hasher = DefaultHasher::new();
    hostname.hash(&mut hasher);
    let machine_seed = hasher.finish().to_le_bytes();
    
    let mut encrypted = Vec::with_capacity(data.len() + machine_seed.len());
    encrypted.extend_from_slice(&machine_seed);
    
    for (i, &byte) in data.iter().enumerate() {
        let key_byte = machine_seed[i % machine_seed.len()];
        encrypted.push(byte.wrapping_add(key_byte));
    }
    
    encrypted
}

#[cfg(target_os = "windows")]
fn decrypt_with_machine_key(encrypted: &[u8]) -> Result<Vec<u8>, String> {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    if encrypted.len() < 8 {
        return Err("Invalid encrypted data".to_string());
    }
    
    let hostname = gethostname::gethostname()
        .to_string_lossy()
        .to_string();
    
    let mut hasher = DefaultHasher::new();
    hostname.hash(&mut hasher);
    let machine_seed = encrypted[..8].to_vec();
    
    if machine_seed != hostname_to_seed(&hostname) {
        return Err("Machine mismatch".to_string());
    }
    
    let data = &encrypted[8..];
    let mut decrypted = Vec::with_capacity(data.len());
    
    for (i, &byte) in data.iter().enumerate() {
        let key_byte = machine_seed[i % machine_seed.len()];
        decrypted.push(byte.wrapping_sub(key_byte));
    }
    
    Ok(decrypted)
}

#[cfg(target_os = "windows")]
fn hostname_to_seed(hostname: &str) -> Vec<u8> {
    use std::collections::hash_map::DefaultHasher;
    use std::hash::{Hash, Hasher};
    
    let mut hasher = DefaultHasher::new();
    hostname.hash(&mut hasher);
    hasher.finish().to_le_bytes().to_vec()
}

#[cfg(not(target_os = "windows"))]
fn encrypt_with_machine_key(data: &[u8]) -> Vec<u8> {
    data.to_vec()
}

#[cfg(not(target_os = "windows"))]
fn decrypt_with_machine_key(data: &[u8]) -> Result<Vec<u8>, String> {
    Ok(data.to_vec())
}

pub fn save_cloud_api_settings(settings: &CloudApiSettings) -> Result<(), String> {
    let api_key_path = get_api_key_path();
    let settings_path = get_settings_path();
    
    if !settings.api_key.is_empty() {
        let encrypted_key = encrypt_with_machine_key(settings.api_key.as_bytes());
        fs::write(&api_key_path, encrypted_key)
            .map_err(|e| format!("Failed to save API key: {}", e))?;
    } else if api_key_path.exists() {
        let _ = fs::remove_file(&api_key_path);
    }
    
    let settings_to_save = serde_json::to_string_pretty(&CloudApiSettings {
        api_key: String::new(),
        base_url: settings.base_url.clone(),
        model: settings.model.clone(),
    }).map_err(|e| format!("Failed to serialize settings: {}", e))?;
    
    fs::write(&settings_path, settings_to_save)
        .map_err(|e| format!("Failed to save cloud API settings: {}", e))?;
    
    Ok(())
}

pub fn load_cloud_api_settings() -> Result<CloudApiSettings, String> {
    let settings_path = get_settings_path();
    let api_key_path = get_api_key_path();
    
    let mut settings = if settings_path.exists() {
        let content = fs::read_to_string(&settings_path)
            .map_err(|e| format!("Failed to read cloud API settings: {}", e))?;
        
        serde_json::from_str(&content)
            .map_err(|e| format!("Failed to deserialize cloud API settings: {}", e))?
    } else {
        CloudApiSettings::default()
    };
    
    if api_key_path.exists() {
        let encrypted_key = fs::read(&api_key_path)
            .map_err(|e| format!("Failed to read encrypted API key: {}", e))?;
        
        let decrypted_key = decrypt_with_machine_key(&encrypted_key)?;
        settings.api_key = String::from_utf8(decrypted_key)
            .map_err(|e| format!("Invalid API key encoding: {}", e))?;
    }
    
    Ok(settings)
}

pub fn clear_cloud_api_settings() -> Result<(), String> {
    let settings_path = get_settings_path();
    let api_key_path = get_api_key_path();
    
    if settings_path.exists() {
        fs::remove_file(&settings_path)
            .map_err(|e| format!("Failed to remove settings file: {}", e))?;
    }
    
    if api_key_path.exists() {
        fs::remove_file(&api_key_path)
            .map_err(|e| format!("Failed to remove API key file: {}", e))?;
    }
    
    Ok(())
}
