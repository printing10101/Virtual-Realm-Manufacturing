# Phase 7: 数据持久化与设置系统

> **预计工期**: 3-4 小时 | **前置依赖**: Phase 6 | **下一步**: Phase 8 - 测试打包发布

## 目标

实现完整的数据持久化系统，包括 Rust 端应用设置与项目元数据存储、Pinia Stores 状态管理、前端服务层封装、双向同步机制。

## 验证标准

- [ ] 修改设置后重启应用，设置保持
- [ ] 创建项目后重启应用，项目列表保持
- [ ] Store 状态变更自动持久化到本地存储
- [ ] 应用启动时正确加载持久化数据

---

## Rust 端持久化

### 数据结构

```rust
// src-tauri/src/models.rs
pub struct AppSettings {
    pub python_backend_url: String,
    pub ollama_url: String,
    pub default_model: String,
    pub theme: String,
    pub auto_save: bool,
    pub language: String,
}

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
```

### 存储模块

```rust
// src-tauri/src/storage.rs
pub fn get_app_data_dir() -> PathBuf
pub fn save_settings(settings: &AppSettings) -> Result<(), String>
pub fn load_settings() -> Result<AppSettings, String>
pub fn save_projects(projects: &[ProjectMeta]) -> Result<(), String>
pub fn load_projects() -> Result<Vec<ProjectMeta>, String>
```

### Tauri 命令

```rust
#[tauri::command]
fn get_settings() -> Result<AppSettings, String>

#[tauri::command]
fn save_settings_cmd(settings: AppSettings) -> Result<(), String>

#[tauri::command]
fn get_projects() -> Result<Vec<ProjectMeta>, String>

#[tauri::command]
fn add_project_cmd(name: String, description: String) -> Result<ProjectMeta, String>

#[tauri::command]
fn delete_project_cmd(project_id: String) -> Result<(), String>
```

---

## Pinia Stores

### settingsStore

```typescript
// src/stores/settingsStore.ts
export const useSettingsStore = defineStore('settings', () => {
  const settings = ref<AppSettings>({...})
  const isLoaded = ref(false)

  const loadSettings = async () => {...}
  const saveSettings = async () => {...}
  const updateSetting = <K>(key: K, value: AppSettings[K]) => {...}

  // watch 自动保存
  watch(settings, () => {
    if (isLoaded.value && settings.value.auto_save) {
      saveSettings()
    }
  }, { deep: true })
}, { persist: true })
```

### projectStore

```typescript
// src/stores/projectStore.ts
export const useProjectStore = defineStore('project', () => {
  const projects = ref<ProjectMeta[]>([])
  const currentProject = ref<ProjectMeta | null>(null)

  const loadProjects = async () => {...}
  const createProject = async (name: string, desc: string) => {...}
  const deleteProject = async (id: string) => {...}
  const selectProject = (project: ProjectMeta) => {...}
}, { persist: true })
```

### appStore

```typescript
// src/stores/appStore.ts
export const useAppStore = defineStore('app', () => {
  const loading = ref(false)
  const errorMessage = ref('')
  const statusMessage = ref('就绪')
  // ...
})
```

---

## 前端服务层

```typescript
// src/services/backend.ts
export async function checkHealth(): Promise<boolean>
export async function checkOllama(): Promise<boolean>

// src/services/settings.ts
export async function getSettings(): Promise<AppSettings>
export async function saveSettings(settings: AppSettings): Promise<void>

// src/services/project.ts
export async function getProjects(): Promise<ProjectMeta[]>
export async function createProject(name: string, desc: string): Promise<ProjectMeta>
export async function deleteProject(projectId: string): Promise<void>
```

---

## 验证清单

1. 设置修改后持久化保存
2. 项目列表持久化保存
3. 应用重启后正确加载数据
4. 自动保存功能正常

---

## 相关文档

- [Phase 6 - 用户界面](../08-Phase6-用户界面.md)
- [Phase 8 - 测试打包发布](../10-Phase8-测试打包发布.md)
