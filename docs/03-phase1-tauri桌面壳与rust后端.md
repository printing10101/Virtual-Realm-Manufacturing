# Phase 1: Tauri 桌面壳与 Rust 后端

> **预计工期**: 3-4 小时 | **前置依赖**: Phase 0 | **下一步**: Phase 2 - Python AI 后端

## 目标

实现 Tauri Rust 后端核心功能，包括文件系统操作、Sidecar 进程管理、应用信息查询，并提供前端 TypeScript 类型定义和服务封装层。

## 验证标准

- [ ] `cargo build` 在 `src-tauri/` 目录下编译通过
- [ ] `pnpm tauri dev` 正常启动
- [ ] 前端可调用 `get_app_data_dir` 获取应用数据目录路径
- [ ] 前端可调用 `get_app_info` 获取应用版本信息
- [ ] 前端可调用 `open_external_url` 打开外部链接
- [ ] TypeScript 类型定义完整，无编译错误
- [ ] Tauri 服务封装层可正常导入

---

## 步骤概览

| 步骤 | 内容 |
|------|------|
| 1 | 添加 Rust 依赖 (Cargo.toml) |
| 2 | 创建 Rust 模块结构 |
| 3 | 实现进程管理器状态 |
| 4 | 实现文件系统命令 |
| 5 | 实现进程管理命令 |
| 6 | 实现应用信息命令 |
| 7 | 注册命令和插件 |
| 8 | 创建前端 TypeScript 类型定义 |
| 9 | 创建前端 Tauri 服务封装 |
| 10 | 安装 Tauri API 前端依赖 |
| 11 | 创建 Tauri 服务测试 |

---

## 核心模块

### 文件系统命令 (`src-tauri/src/commands/file.rs`)

```rust
#[tauri::command]
pub fn get_app_data_dir(app_handle: tauri::AppHandle) -> Result<String, String>

#[tauri::command]
pub fn save_file(file_path: String, content: String) -> Result<(), String>

#[tauri::command]
pub fn read_file(file_path: String) -> Result<String, String>

#[tauri::command]
pub fn list_files(dir_path: String, extension: Option<String>) -> Result<Vec<FileInfo>, String>

#[tauri::command]
pub fn delete_file(file_path: String, recursive: bool) -> Result<(), String>

#[tauri::command]
pub fn create_directory(dir_path: String, recursive: bool) -> Result<(), String>
```

### 进程管理命令 (`src-tauri/src/commands/process.rs`)

```rust
#[tauri::command]
pub fn start_sidecar(state: State<'_, AppState>, port: Option<u16>) -> Result<u32, String>

#[tauri::command]
pub fn stop_sidecar(state: State<'_, AppState>) -> Result<(), String>

#[tauri::command]
pub fn check_sidecar_status(state: State<'_, AppState>) -> Result<SidecarStatusResponse, String>
```

### 应用信息命令 (`src-tauri/src/commands/app.rs`)

```rust
#[tauri::command]
pub fn get_app_info(app_handle: tauri::AppHandle) -> Result<AppInfo, String>

#[tauri::command]
pub async fn open_external_url(app_handle: tauri::AppHandle, url: String) -> Result<(), String>
```

---

## 前端类型定义

```typescript
// src/types/tauri.ts
export interface FileInfo {
  name: string
  path: string
  is_dir: boolean
  size: number
  modified_at: string
  extension: string | null
}

export interface SidecarStatusResponse {
  is_running: boolean
  status: string
  pid: number | null
  port: number
  started_at: string | null
}

export interface AppInfo {
  app_name: string
  version: string
  tauri_version: string
  os: string
  os_version: string
  arch: string
  hostname: string
}
```

---

## 验证清单

1. **Rust 编译验证**：在 `src-tauri/` 目录下执行 `cargo build`，确认编译通过
2. **应用启动验证**：执行 `pnpm tauri dev`，确认：
   - 桌面窗口正常启动
   - 控制台无 Rust panic 或错误
3. **TypeScript 编译验证**：执行 `pnpm build`，确认无类型错误
4. **类型完整性验证**：确认类型定义与 Rust 命令参数/返回值完全匹配
5. **服务封装验证**：确认 `src/services/tauri.ts` 可以正常导入且无编译错误

---

## 相关文档

- [Phase 0 - 项目初始化](../02-Phase0-项目初始化与脚手架.md)
- [Phase 2 - Python AI 后端](../04-Phase2-Python-AI后端.md)
