use serde::Serialize;
use std::net::TcpListener;
use std::process::Command;
use tracing::{info, warn};

#[derive(Debug, Clone, Serialize)]
pub struct HealthItem {
    pub id: String,
    pub name: String,
    pub status: String,
    pub message: String,
    pub details: String,
    pub version: Option<String>,
    pub fix_action: Option<String>,
    pub fix_description: Option<String>,
    pub fix_auto: bool,
}

fn make_item_ok(id: &str, name: &str, message: &str, details: &str, version: Option<&str>) -> HealthItem {
    HealthItem {
        id: id.to_string(),
        name: name.to_string(),
        status: "ok".to_string(),
        message: message.to_string(),
        details: details.to_string(),
        version: version.map(|v| v.to_string()),
        fix_action: None,
        fix_description: None,
        fix_auto: false,
    }
}

fn make_item_warn(id: &str, name: &str, message: &str, details: &str, fix_desc: &str, fix_auto: bool) -> HealthItem {
    HealthItem {
        id: id.to_string(),
        name: name.to_string(),
        status: "warning".to_string(),
        message: message.to_string(),
        details: details.to_string(),
        version: None,
        fix_action: if fix_auto { Some("auto_fix".to_string()) } else { None },
        fix_description: Some(fix_desc.to_string()),
        fix_auto,
    }
}

fn make_item_error(id: &str, name: &str, message: &str, details: &str, fix_desc: &str, fix_auto: bool) -> HealthItem {
    HealthItem {
        id: id.to_string(),
        name: name.to_string(),
        status: "error".to_string(),
        message: message.to_string(),
        details: details.to_string(),
        version: None,
        fix_action: if fix_auto { Some("auto_fix".to_string()) } else { None },
        fix_description: Some(fix_desc.to_string()),
        fix_auto,
    }
}

fn check_nodejs() -> HealthItem {
    info!("Checking Node.js installation...");
    match Command::new("node").arg("--version").output() {
        Ok(output) if output.status.success() => {
            let version = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let ver_clean = version.trim_start_matches('v');
            let major: u32 = ver_clean.split('.').next().and_then(|s| s.parse().ok()).unwrap_or(0);

            if major >= 18 {
                make_item_ok(
                    "nodejs",
                    "Node.js 运行环境",
                    &format!("Node.js {} 运行正常", version),
                    &format!("已安装版本: {}\n最低要求: v18.0.0\n当前版本满足兼容性要求", version),
                    Some(&ver_clean),
                )
            } else if major >= 16 {
                make_item_warn(
                    "nodejs",
                    "Node.js 运行环境",
                    &format!("Node.js {} 版本较低", version),
                    &format!("已安装版本: {}\n最低推荐: v18.0.0\n当前版本可运行但建议升级以获得最佳体验", version),
                    "建议从 https://nodejs.org 下载安装 Node.js 18+ LTS 版本",
                    false,
                )
            } else {
                make_item_error(
                    "nodejs",
                    "Node.js 运行环境",
                    &format!("Node.js {} 版本过低", version),
                    &format!("已安装版本: {}\n最低要求: v16.0.0\n当前版本不满足应用运行要求", version),
                    "请从 https://nodejs.org 下载安装 Node.js 18+ LTS 版本",
                    false,
                )
            }
        }
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            make_item_error(
                "nodejs",
                "Node.js 运行环境",
                "Node.js 命令执行失败",
                &format!("错误信息: {}", stderr),
                "请检查 Node.js 安装是否正确，或重新安装",
                false,
            )
        }
        Err(e) => {
            make_item_error(
                "nodejs",
                "Node.js 运行环境",
                "未检测到 Node.js",
                &format!("无法执行 node 命令: {}\n应用需要 Node.js 运行时环境", e),
                "请从 https://nodejs.org 下载安装 Node.js 18+ LTS 版本",
                false,
            )
        }
    }
}

fn check_python(handle: &tauri::AppHandle) -> HealthItem {
    info!("Checking Python installation...");

    let python_cmd = if cfg!(windows) { "python" } else { "python3" };

    match Command::new(python_cmd).arg("--version").output() {
        Ok(output) if output.status.success() => {
            let version = String::from_utf8_lossy(&output.stdout)
                .trim()
                .to_string()
                .replace("Python ", "");

            let parts: Vec<&str> = version.split('.').collect();
            let major = parts.first().and_then(|s| s.parse::<u32>().ok()).unwrap_or(0);
            let minor = parts.get(1).and_then(|s| s.parse::<u32>().ok()).unwrap_or(0);

            let sidecar_running = check_sidecar_health_internal(handle);

            if sidecar_running {
                if major >= 3 && minor >= 10 {
                    make_item_ok(
                        "python",
                        "Python 运行环境",
                        &format!("Python {} 运行正常，后端服务已连接", version),
                        &format!("已安装版本: {}\n最低要求: Python 3.10+\n后端服务状态: 运行中", version),
                        Some(&version),
                    )
                } else {
                    make_item_warn(
                        "python",
                        "Python 运行环境",
                        &format!("Python {} 版本较低，但后端服务运行中", version),
                        &format!("已安装版本: {}\n最低推荐: Python 3.10\n当前版本可运行但建议升级", version),
                        "建议从 https://python.org 下载 Python 3.10+ 版本",
                        false,
                    )
                }
            } else {
                make_item_error(
                    "python",
                    "Python 运行环境",
                    &format!("Python {} 已安装，但后端服务未启动", version),
                    &format!("已安装版本: {}\n后端服务状态: 未运行\n请检查服务启动日志了解详细原因", version),
                    "请尝试重启应用，或在终端中运行 python -m uvicorn app.main:app 启动后端服务",
                    true,
                )
            }
        }
        Ok(output) => {
            let stderr = String::from_utf8_lossy(&output.stderr).trim().to_string();
            make_item_error(
                "python",
                "Python 运行环境",
                "Python 命令执行失败",
                &format!("错误信息: {}\n请确认 Python 已正确安装并添加到系统 PATH", stderr),
                "请从 https://python.org 下载安装 Python 3.10+ 版本",
                false,
            )
        }
        Err(_) => {
            make_item_error(
                "python",
                "Python 运行环境",
                "未检测到 Python 环境",
                "无法执行 python 命令。应用后端服务依赖 Python 3.10+ 运行环境",
                "请从 https://python.org 下载安装 Python 3.10+ 版本，安装时勾选 'Add Python to PATH'",
                false,
            )
        }
    }
}

fn check_sidecar_health_internal(handle: &tauri::AppHandle) -> bool {
    if let Some(app_state) = handle.try_state::<crate::state::AppState>() {
        if let Ok(pid_lock) = app_state.sidecar_pid.lock() {
            if let Some(pid) = *pid_lock {
                return crate::sidecar_manager::HealthChecker::is_process_alive(pid);
            }
        }
    }

    let app_data_dir = handle
        .path()
        .app_data_dir()
        .unwrap_or_else(|_| dirs::home_dir().unwrap_or_default().join(".lingjing"));

    let manager = crate::sidecar_manager::SidecarManager::new(app_data_dir);
    if let Some(state) = manager.state_file_manager.read_state() {
        return crate::sidecar_manager::HealthChecker::is_process_alive(state.pid);
    }

    false
}

fn check_ollama() -> HealthItem {
    info!("Checking Ollama installation...");

    let ollama_cmd = if cfg!(windows) { "ollama" } else { "ollama" };

    match Command::new(ollama_cmd).arg("--version").output() {
        Ok(output) if output.status.success() => {
            let version = String::from_utf8_lossy(&output.stdout).trim().to_string();
            let ver_clean = version.trim_start_matches("ollama version is ").to_string();

            match check_ollama_running() {
                Ok(true) => {
                    make_item_ok(
                        "ollama",
                        "Ollama AI 服务",
                        &format!("Ollama {} 已安装并正常运行", ver_clean),
                        &format!("已安装版本: {}\n服务状态: 运行中\n端口: 11434 (默认)", ver_clean),
                        Some(&ver_clean),
                    )
                }
                Ok(false) => {
                    make_item_error(
                        "ollama",
                        "Ollama AI 服务",
                        &format!("Ollama {} 已安装但未运行", ver_clean),
                        &format!("已安装版本: {}\n服务状态: 未运行\n请启动 Ollama 服务后再使用 AI 功能", ver_clean),
                        "请在终端运行 ollama serve 启动服务，或从开始菜单启动 Ollama 应用",
                        true,
                    )
                }
                Err(e) => {
                    make_item_error(
                        "ollama",
                        "Ollama AI 服务",
                        &format!("Ollama {} 已安装但服务异常", ver_clean),
                        &format!("已安装版本: {}\n服务状态: 异常\n错误: {}", ver_clean, e),
                        "请尝试在终端运行 ollama serve 重新启动服务",
                        true,
                    )
                }
            }
        }
        Ok(_) => {
            make_item_error(
                "ollama",
                "Ollama AI 服务",
                "Ollama 命令执行异常",
                "ollama --version 命令返回了非预期的结果，可能安装已损坏",
                "请访问 https://ollama.com 下载重新安装 Ollama",
                false,
            )
        }
        Err(_) => {
            make_item_error(
                "ollama",
                "Ollama AI 服务",
                "未检测到 Ollama",
                "无法执行 ollama 命令。Ollama 是运行本地 AI 模型所必需的服务\n请确认 Ollama 已正确安装",
                "请访问 https://ollama.com 下载安装 Ollama，安装后重启应用",
                false,
            )
        }
    }
}

fn check_ollama_running() -> Result<bool, String> {
    let client = reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(5))
        .build()
        .map_err(|e| format!("无法创建 HTTP 客户端: {}", e))?;

    match client.get("http://localhost:11434/api/tags").send() {
        Ok(response) => Ok(response.status().is_success()),
        Err(e) => {
            if e.is_connect() {
                Ok(false)
            } else {
                Err(format!("{}", e))
            }
        }
    }
}

fn check_models() -> HealthItem {
    info!("Checking AI models...");

    let client = match reqwest::blocking::Client::builder()
        .timeout(std::time::Duration::from_secs(10))
        .build()
    {
        Ok(c) => c,
        Err(e) => {
            return make_item_error(
                "models",
                "AI 模型文件",
                "无法检查模型状态",
                &format!("无法初始化 HTTP 客户端: {}", e),
                "请确认 Ollama 服务正在运行后重新检查",
                false,
            );
        }
    };

    match client.get("http://localhost:11434/api/tags").send() {
        Ok(response) if response.status().is_success() => {
            match response.json::<serde_json::Value>() {
                Ok(json) => {
                    let models: Vec<String> = json["models"]
                        .as_array()
                        .map(|arr| {
                            arr.iter()
                                .filter_map(|m| {
                                    let name = m["name"].as_str().unwrap_or("?");
                                    let size = m["size"].as_u64().unwrap_or(0);
                                    let size_mb = size as f64 / 1_048_576.0;
                                    Some(format!("{} ({:.1}MB)", name, size_mb))
                                })
                                .collect()
                        })
                        .unwrap_or_default();

                    if models.is_empty() {
                        make_item_error(
                            "models",
                            "AI 模型文件",
                            "未检测到任何 AI 模型",
                            "Ollama 服务运行正常，但没有安装任何模型\n请至少安装一个模型以使用 AI 功能",
                            "请在终端运行：ollama pull qwen2.5:7b 下载推荐模型",
                            false,
                        )
                    } else {
                        let count = models.len();
                        let list = models.join("\n");
                        make_item_ok(
                            "models",
                            "AI 模型文件",
                            &format!("已加载 {} 个 AI 模型", count),
                            &format!("模型列表:\n{}", list),
                            Some(&count.to_string()),
                        )
                    }
                }
                Err(e) => {
                    make_item_error(
                        "models",
                        "AI 模型文件",
                        "模型信息解析失败",
                        &format!("Ollama 返回数据无法解析: {}", e),
                        "请尝试重启 Ollama 服务后重新检查",
                        false,
                    )
                }
            }
        }
        Ok(response) => {
            make_item_error(
                "models",
                "AI 模型文件",
                &format!("Ollama 服务异常 (HTTP {})", response.status().as_u16()),
                "请确认 Ollama 服务正常运行后再检查模型",
                "请先解决 Ollama 服务问题，然后重新检查",
                false,
            )
        }
        Err(e) => {
            make_item_error(
                "models",
                "AI 模型文件",
                "无法连接 Ollama 服务",
                &format!("连接失败: {}\n请确认 Ollama 服务正在运行", e),
                "请启动 Ollama 服务后重新检查",
                false,
            )
        }
    }
}

fn check_ports() -> HealthItem {
    info!("Checking port availability...");

    let required_ports = vec![
        (8000u16, "Python 后端服务 (uvicorn)"),
        (8001u16, "Python 后端服务备选"),
        (11434u16, "Ollama AI 服务"),
        (1420u16, "前端开发服务器 (Vite)"),
    ];

    let mut occupied = Vec::new();
    let mut free = Vec::new();

    for (port, desc) in &required_ports {
        match TcpListener::bind(("127.0.0.1", *port)) {
            Ok(_) => {
                free.push(format!("  ✓ 端口 {} ({}) — 可用", port, desc));
            }
            Err(_) => {
                occupied.push(format!("  ✗ 端口 {} ({}) — 已被占用", port, desc));
            }
        }
    }

    if occupied.is_empty() {
        make_item_ok(
            "ports",
            "网络端口检查",
            "所有必需端口均可用",
            &format!("检查了 {} 个端口:\n{}", required_ports.len(), free.join("\n")),
            None,
        )
    } else if occupied.len() < required_ports.len() {
        make_item_warn(
            "ports",
            "网络端口检查",
            &format!("{} 个端口被占用", occupied.len()),
            &format!("端口状态:\n{}\n{}", free.join("\n"), occupied.join("\n")),
            "被占用的端口可能导致对应服务无法启动。请关闭占用端口的程序或修改应用端口配置",
            false,
        )
    } else {
        make_item_error(
            "ports",
            "网络端口检查",
            "所有端口均被占用",
            &format!("端口状态:\n{}", occupied.join("\n")),
            "请关闭占用这些端口的程序后重启应用",
            false,
        )
    }
}

fn check_disk() -> HealthItem {
    info!("Checking disk space...");

    let check_path = std::env::current_dir().unwrap_or_else(|_| std::path::PathBuf::from("."));

    let (total_gb, free_gb, used_percent) = get_disk_info(&check_path);

    if total_gb == 0.0 {
        return make_item_warn(
            "disk",
            "系统磁盘空间",
            "无法获取磁盘信息",
            "磁盘信息查询失败，可能由于系统权限限制",
            "请手动检查磁盘空间，确保至少有 5GB 可用空间",
            false,
        );
    }

    if free_gb < 1.0 {
        make_item_error(
            "disk",
            "系统磁盘空间",
            &format!("磁盘空间严重不足 (可用 {:.1} GB / 总计 {:.1} GB)", free_gb, total_gb),
            &format!(
                "总容量: {:.1} GB\n可用空间: {:.1} GB\n已用: {:.1}% \n可用空间严重不足，可能导致应用无法正常运行",
                total_gb, free_gb, used_percent
            ),
            "请清理磁盘空间：删除临时文件、卸载不需要的应用、清空回收站",
            false,
        )
    } else if free_gb < 5.0 {
        make_item_warn(
            "disk",
            "系统磁盘空间",
            &format!("磁盘空间偏低 (可用 {:.1} GB / 总计 {:.1} GB)", free_gb, total_gb),
            &format!(
                "总容量: {:.1} GB\n可用空间: {:.1} GB\n已用: {:.1}% \n建议保持至少 5GB 可用空间",
                total_gb, free_gb, used_percent
            ),
            "建议清理不需要的文件或临时数据以释放磁盘空间",
            false,
        )
    } else {
        make_item_ok(
            "disk",
            "系统磁盘空间",
            &format!("磁盘空间充足 (可用 {:.1} GB / 总计 {:.1} GB)", free_gb, total_gb),
            &format!(
                "总容量: {:.1} GB\n可用空间: {:.1} GB\n已用: {:.1}%",
                total_gb, free_gb, used_percent
            ),
            None,
        )
    }
}

fn get_disk_info(path: &std::path::Path) -> (f64, f64, f64) {
    #[cfg(windows)]
    {
        let drive = path
            .to_str()
            .and_then(|s| s.chars().next())
            .map(|c| format!("{}:", c))
            .unwrap_or_else(|| "C:".to_string());

        match Command::new("wmic")
            .args([
                "logicaldisk",
                "where",
                &format!("DeviceID='{}'", drive),
                "get",
                "Size,FreeSpace",
                "/format:csv",
            ])
            .output()
        {
            Ok(output) if output.status.success() => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines().skip(1) {
                    let parts: Vec<&str> = line.split(',').collect();
                    if parts.len() >= 3 {
                        let free: f64 = parts.last().unwrap_or(&"0").trim().parse().unwrap_or(0.0);
                        let total: f64 = parts.get(parts.len() - 2).unwrap_or(&"0").trim().parse().unwrap_or(0.0);
                        if total > 0.0 {
                            let free_gb = free / 1_073_741_824.0;
                            let total_gb = total / 1_073_741_824.0;
                            let used_percent = ((total - free) / total) * 100.0;
                            return (total_gb, free_gb, used_percent);
                        }
                    }
                }
            }
            Ok(_) => {}
            Err(e) => warn!("WMIC disk check failed: {}", e),
        }

        (0.0, 0.0, 0.0)
    }

    #[cfg(not(windows))]
    {
        let mount = if cfg!(target_os = "macos") { "/" } else { "/" };

        match Command::new("df").arg("-B1").arg(mount).output() {
            Ok(output) if output.status.success() => {
                let stdout = String::from_utf8_lossy(&output.stdout);
                for line in stdout.lines().skip(1) {
                    let parts: Vec<&str> = line.split_whitespace().collect();
                    if parts.len() >= 4 {
                        let total: f64 = parts[1].parse().unwrap_or(0.0);
                        let used: f64 = parts[2].parse().unwrap_or(0.0);
                        let free: f64 = parts[3].parse().unwrap_or(0.0);
                        if total > 0.0 {
                            let free_gb = free / 1_073_741_824.0;
                            let total_gb = total / 1_073_741_824.0;
                            let used_percent = (used / total) * 100.0;
                            return (total_gb, free_gb, used_percent);
                        }
                    }
                }
            }
            Ok(_) => {}
            Err(e) => warn!("df disk check failed: {}", e),
        }

        (0.0, 0.0, 0.0)
    }
}

#[tauri::command]
pub fn run_health_check(app: tauri::AppHandle) -> Result<Vec<HealthItem>, String> {
    info!("Running full system health check...");

    let mut results = Vec::with_capacity(6);

    results.push(check_nodejs());
    results.push(check_python(&app));
    results.push(check_ollama());
    results.push(check_models());
    results.push(check_ports());
    results.push(check_disk());

    let ok_count = results.iter().filter(|r| r.status == "ok").count();
    let warn_count = results.iter().filter(|r| r.status == "warning").count();
    let err_count = results.iter().filter(|r| r.status == "error").count();

    info!(
        "Health check complete: {} ok, {} warning, {} error",
        ok_count, warn_count, err_count
    );

    Ok(results)
}

#[tauri::command]
pub fn run_single_health_check(app: tauri::AppHandle, component: String) -> Result<HealthItem, String> {
    info!("Running single health check for: {}", component);

    match component.as_str() {
        "nodejs" => Ok(check_nodejs()),
        "python" => Ok(check_python(&app)),
        "ollama" => Ok(check_ollama()),
        "models" => Ok(check_models()),
        "ports" => Ok(check_ports()),
        "disk" => Ok(check_disk()),
        _ => Err(format!("未知的检查项: {}", component)),
    }
}

#[tauri::command]
pub fn get_diagnostics_text(app: tauri::AppHandle) -> Result<String, String> {
    info!("Generating diagnostics report...");

    let results = run_health_check(app)?;
    let now = chrono::Utc::now().format("%Y-%m-%d %H:%M:%S UTC");

    let mut report = String::new();
    report.push_str("========================================\n");
    report.push_str("  灵境制造 V4 — 系统诊断报告\n");
    report.push_str("========================================\n");
    report.push_str(&format!("生成时间: {}\n", now));
    report.push_str(&format!("操作系统: {}\n", std::env::consts::OS));
    report.push_str(&format!("系统架构: {}\n", std::env::consts::ARCH));
    report.push_str("========================================\n\n");

    for item in &results {
        let icon = match item.status.as_str() {
            "ok" => "✅",
            "warning" => "⚠️",
            _ => "❌",
        };
        let status_label = match item.status.as_str() {
            "ok" => "正常",
            "warning" => "警告",
            _ => "异常",
        };

        report.push_str(&format!("{} [{}] {}\n", icon, status_label, item.name));
        report.push_str(&format!("   状态: {}\n", item.message));
        if let Some(ref v) = item.version {
            report.push_str(&format!("   版本: {}\n", v));
        }
        report.push_str(&format!("   详情: {}\n", item.details.replace('\n', "\n         ")));
        if let Some(ref fix) = item.fix_description {
            report.push_str(&format!("   建议: {}\n", fix));
        }
        report.push('\n');
    }

    report.push_str("========================================\n");
    report.push_str("  报告结束\n");
    report.push_str("========================================\n");

    Ok(report)
}

#[tauri::command]
pub fn auto_fix_health(app: tauri::AppHandle, component: String) -> Result<String, String> {
    info!("Attempting auto-fix for: {}", component);

    match component.as_str() {
        "python" => {
            if check_sidecar_health_internal(&app) {
                return Ok("Python 后端服务已在运行中，无需修复".to_string());
            }

            info!("Attempting to restart Python sidecar...");
            let manager = {
                let app_data_dir = app
                    .path()
                    .app_data_dir()
                    .unwrap_or_else(|_| dirs::home_dir().unwrap_or_default().join(".lingjing"));
                crate::sidecar_manager::SidecarManager::new(app_data_dir)
            };

            let version = "1.9.0";
            let python_script_path =
                std::env::var("SIDECAR_SCRIPT_PATH").unwrap_or_else(|_| "app.main:app".to_string());

            match manager.recover_or_start(version, &python_script_path) {
                Ok(result) => {
                    if let Some(app_state) = app.try_state::<crate::state::AppState>() {
                        if let Ok(mut pid) = app_state.sidecar_pid.lock() {
                            *pid = Some(result.pid);
                        }
                    }
                    Ok(format!(
                        "Python 后端服务已成功启动 (PID: {}, 端口: {})",
                        result.pid, result.port
                    ))
                }
                Err(e) => Err(format!("Python 后端服务启动失败: {}", e)),
            }
        }
        "ollama" => {
            if check_ollama_running().unwrap_or(false) {
                return Ok("Ollama 服务已在运行中".to_string());
            }

            let ollama_cmd = if cfg!(windows) { "ollama" } else { "ollama" };
            match Command::new(ollama_cmd).arg("serve").spawn() {
                Ok(_) => {
                    std::thread::sleep(std::time::Duration::from_secs(2));
                    Ok("Ollama 服务已尝试启动，请等待几秒后重新检查".to_string())
                }
                Err(e) => Err(format!("无法启动 Ollama: {}", e)),
            }
        }
        _ => Err(format!("组件 '{}' 不支持自动修复，请按照提示手动操作", component)),
    }
}