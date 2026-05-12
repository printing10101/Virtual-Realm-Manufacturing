use serde::Serialize;

include!(concat!(env!("OUT_DIR"), "/version.rs"));

#[derive(Serialize, Clone, Debug)]
pub struct VersionInfo {
    pub version: String,
    pub commit: String,
}

impl VersionInfo {
    pub fn rust_version() -> Self {
        Self {
            version: APP_VERSION.to_string(),
            commit: APP_COMMIT.to_string(),
        }
    }
}
