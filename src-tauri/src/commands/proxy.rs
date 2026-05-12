use reqwest::{Client, Method, header::HeaderName};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;
use once_cell::sync::Lazy;
use tracing::{info, error};

static HTTP_CLIENT: Lazy<Client> = Lazy::new(|| {
    Client::builder()
        .timeout(Duration::from_secs(30))
        .connect_timeout(Duration::from_secs(10))
        .pool_max_idle_per_host(10)
        .tcp_keepalive(Duration::from_secs(60))
        .build()
        .expect("HTTP 客户端初始化失败：无法创建 HTTP 客户端实例。可能原因：1) 系统网络配置异常；2) TLS 证书验证失败。请检查系统网络连接和 TLS 证书配置。")
});

static AUTH_TOKEN: std::sync::LazyLock<Option<String>> = std::sync::LazyLock::new(|| {
    std::env::var("LNN_AUTH_TOKEN").ok()
});

const MAX_CONCURRENT_BATCH_REQUESTS: usize = 10;
static ACTIVE_BATCH_REQUESTS: AtomicUsize = AtomicUsize::new(0);

#[derive(Debug, Deserialize)]
pub struct ProxyRequest {
    pub method: String,
    pub url: String,
    #[serde(default)]
    pub headers: HashMap<String, String>,
    #[serde(default)]
    pub body: Option<serde_json::Value>,
    #[serde(default = "default_timeout")]
    pub timeout_ms: u64,
}

#[derive(Debug, Serialize)]
pub struct ProxyResponse {
    pub status: u16,
    pub headers: HashMap<String, String>,
    pub body: serde_json::Value,
    pub duration_ms: u128,
}

#[derive(Debug, Serialize)]
pub struct ProxyError {
    pub code: String,
    pub message: String,
    pub status: Option<u16>,
}

fn default_timeout() -> u64 {
    30000
}

#[derive(Debug, Deserialize)]
pub struct BatchRequest {
    pub requests: Vec<ProxyRequest>,
}

#[derive(Debug, Serialize)]
pub struct BatchResponse {
    pub responses: Vec<Result<ProxyResponse, ProxyError>>,
    pub total_duration_ms: u128,
}

fn is_localhost_url(url: &str) -> bool {
    url.contains("localhost") || url.contains("127.0.0.1")
}

#[tauri::command]
pub async fn proxy_http_request(request: ProxyRequest) -> Result<ProxyResponse, ProxyError> {
    info!("Proxying {} request to {}", request.method, request.url);
    let start = std::time::Instant::now();

    let method = parse_method(&request.method).map_err(|e| {
        let mut enhanced = e.clone();
        enhanced.message = format!("HTTP 代理请求失败：不支持的 HTTP 方法 '{}'。支持的方法包括：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS。请检查请求中的 method 字段配置。原始错误: {}", request.method, e.message);
        enhanced
    })?;
    let mut req_builder = HTTP_CLIENT.request(method, &request.url);

    for (key, value) in &request.headers {
        if let Ok(header_name) = HeaderName::try_from(key) {
            req_builder = req_builder.header(header_name, value);
        }
    }

    if is_localhost_url(&request.url) {
        if let Some(ref token) = *AUTH_TOKEN {
            req_builder = req_builder.header("Authorization", format!("Bearer {}", token));
        }
    }

    if let Some(ref body) = request.body {
        req_builder = req_builder.json(body);
    }

    let request_timeout = Duration::from_millis(request.timeout_ms);
    let client = Client::builder()
        .timeout(request_timeout)
        .connect_timeout(Duration::from_secs(10))
        .build()
        .map_err(|e| ProxyError {
            code: "CLIENT_BUILD_ERROR".to_string(),
            message: format!("HTTP 代理请求失败：无法创建 HTTP 客户端实例。错误详情: {}。可能原因：1) 请求超时配置无效；2) 系统资源不足。请检查请求的 timeout_ms 参数配置。", e),
            status: None,
        })?;

    let response = client
        .execute(req_builder.build().map_err(|e| ProxyError {
            code: "REQUEST_BUILD_ERROR".to_string(),
            message: format!("HTTP 代理请求失败：无法构建 HTTP 请求。错误详情: {}。可能原因：1) URL 格式不正确；2) 请求头配置有误。请检查请求的 url 和 headers 字段。", e),
            status: None,
        })?)
        .await
        .map_err(|e| {
            error!("Request failed: {}", e);
            if e.is_timeout() {
                ProxyError {
                    code: "TIMEOUT".to_string(),
                    message: format!("HTTP 代理请求超时：请求 '{}' 在 {}ms 内未收到响应。可能原因：1) 目标服务器响应缓慢；2) 网络连接不稳定。请尝试增加 timeout_ms 参数值，或检查目标服务器状态。", request.url, request.timeout_ms),
                    status: None,
                }
            } else if e.is_connect() {
                ProxyError {
                    code: "CONNECTION_ERROR".to_string(),
                    message: format!("HTTP 代理连接失败：无法连接到目标服务器 '{}'。错误详情: {}。可能原因：1) 目标服务器不可达；2) DNS 解析失败；3) 防火墙阻止连接。请检查 URL 是否正确，目标服务器是否运行正常。", request.url, e),
                    status: None,
                }
            } else {
                ProxyError {
                    code: "REQUEST_ERROR".to_string(),
                    message: format!("HTTP 代理请求失败：向 '{}' 发送请求时出现异常。错误详情: {}。请检查网络连接和目标服务器状态。", request.url, e),
                    status: None,
                }
            }
        })?;

    let status = response.status().as_u16();
    let mut response_headers = HashMap::new();
    for (name, value) in response.headers() {
        if let Ok(val_str) = value.to_str() {
            response_headers.insert(name.to_string(), val_str.to_string());
        }
    }

    let body: serde_json::Value = response.json().await.map_err(|e| {
        error!("Failed to parse response body: {}", e);
        ProxyError {
            code: "PARSE_ERROR".to_string(),
            message: format!("HTTP 代理响应解析失败：无法将目标服务器响应解析为 JSON 格式。目标 URL: '{}'，HTTP 状态码: {}。错误详情: {}。可能原因：1) 目标服务器返回了非 JSON 格式的响应；2) 响应数据已损坏。请检查目标服务器的响应格式。", request.url, status, e),
            status: Some(status),
        }
    })?;

    let duration = start.elapsed().as_millis();
    info!("Request completed in {}ms with status {}", duration, status);

    Ok(ProxyResponse {
        status,
        headers: response_headers,
        body,
        duration_ms: duration,
    })
}

#[tauri::command]
pub async fn proxy_batch_request(batch: BatchRequest) -> Result<BatchResponse, ProxyError> {
    info!("Processing batch of {} requests", batch.requests.len());

    let current = ACTIVE_BATCH_REQUESTS.fetch_add(1, Ordering::SeqCst);
    if current >= MAX_CONCURRENT_BATCH_REQUESTS {
        ACTIVE_BATCH_REQUESTS.fetch_sub(1, Ordering::SeqCst);
        return Err(ProxyError {
            code: "TOO_MANY_REQUESTS".to_string(),
            message: format!(
                "HTTP 代理请求限流：并发请求数超过上限（最大 {} 个并发）。可能原因：1) 短时间内发送了大量请求；2) 其他客户端占用了并发配额。请稍后重试，或减少并发请求数量。",
                MAX_CONCURRENT_BATCH_REQUESTS
            ),
            status: Some(429),
        });
    }

    let _decrement = DecrementOnDrop;
    let start = std::time::Instant::now();

    let futures = batch.requests.into_iter().map(proxy_single_request);
    let responses = futures::future::join_all(futures).await;

    let total_duration = start.elapsed().as_millis();
    info!("Batch completed in {}ms", total_duration);

    Ok(BatchResponse {
        responses,
        total_duration_ms: total_duration,
    })
}

struct DecrementOnDrop;
impl Drop for DecrementOnDrop {
    fn drop(&mut self) {
        ACTIVE_BATCH_REQUESTS.fetch_sub(1, Ordering::SeqCst);
    }
}

async fn proxy_single_request(request: ProxyRequest) -> Result<ProxyResponse, ProxyError> {
    let start = std::time::Instant::now();

    let method = parse_method(&request.method).map_err(|e| {
        let mut enhanced = e.clone();
        enhanced.message = format!("HTTP 代理请求失败：不支持的 HTTP 方法 '{}'。支持的方法包括：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS。请检查请求中的 method 字段配置。原始错误: {}", request.method, e.message);
        enhanced
    })?;
    let mut req_builder = HTTP_CLIENT.request(method, &request.url);

    for (key, value) in &request.headers {
        if let Ok(header_name) = HeaderName::try_from(key) {
            req_builder = req_builder.header(header_name, value);
        }
    }

    if is_localhost_url(&request.url) {
        if let Some(ref token) = *AUTH_TOKEN {
            req_builder = req_builder.header("Authorization", format!("Bearer {}", token));
        }
    }

    if let Some(ref body) = request.body {
        req_builder = req_builder.json(body);
    }

    let request_timeout = Duration::from_millis(request.timeout_ms);
    let client = Client::builder()
        .timeout(request_timeout)
        .connect_timeout(Duration::from_secs(10))
        .build()
        .map_err(|e| ProxyError {
            code: "CLIENT_BUILD_ERROR".to_string(),
            message: format!("HTTP 代理请求失败：无法创建 HTTP 客户端实例。错误详情: {}。可能原因：1) 请求超时配置无效；2) 系统资源不足。请检查请求的 timeout_ms 参数配置。", e),
            status: None,
        })?;

    let response = client
        .execute(req_builder.build().map_err(|e| ProxyError {
            code: "REQUEST_BUILD_ERROR".to_string(),
            message: format!("HTTP 代理请求失败：无法构建 HTTP 请求。错误详情: {}。可能原因：1) URL 格式不正确；2) 请求头配置有误。请检查请求的 url 和 headers 字段。", e),
            status: None,
        })?)
        .await
        .map_err(|e| {
            error!("Request failed for {}: {}", request.url, e);
            if e.is_timeout() {
                ProxyError {
                    code: "TIMEOUT".to_string(),
                    message: format!("HTTP 代理请求超时：请求 '{}' 在 {}ms 内未收到响应。可能原因：1) 目标服务器响应缓慢；2) 网络连接不稳定。请尝试增加 timeout_ms 参数值，或检查目标服务器状态。", request.url, request.timeout_ms),
                    status: None,
                }
            } else if e.is_connect() {
                ProxyError {
                    code: "CONNECTION_ERROR".to_string(),
                    message: format!("HTTP 代理连接失败：无法连接到目标服务器 '{}'。错误详情: {}。可能原因：1) 目标服务器不可达；2) DNS 解析失败；3) 防火墙阻止连接。请检查 URL 是否正确，目标服务器是否运行正常。", request.url, e),
                    status: None,
                }
            } else {
                ProxyError {
                    code: "REQUEST_ERROR".to_string(),
                    message: format!("HTTP 代理请求失败：向 '{}' 发送请求时出现异常。错误详情: {}。请检查网络连接和目标服务器状态。", request.url, e),
                    status: None,
                }
            }
        })?;

    let status = response.status().as_u16();
    let mut response_headers = HashMap::new();
    for (name, value) in response.headers() {
        if let Ok(val_str) = value.to_str() {
            response_headers.insert(name.to_string(), val_str.to_string());
        }
    }

    let body: serde_json::Value = response.json().await.map_err(|e| {
        error!("Failed to parse response body for {}: {}", request.url, e);
        ProxyError {
            code: "PARSE_ERROR".to_string(),
            message: format!("HTTP 代理响应解析失败：无法将目标服务器响应解析为 JSON 格式。目标 URL: '{}'，HTTP 状态码: {}。错误详情: {}。可能原因：1) 目标服务器返回了非 JSON 格式的响应；2) 响应数据已损坏。请检查目标服务器的响应格式。", request.url, status, e),
            status: Some(status),
        }
    })?;

    let duration = start.elapsed().as_millis();

    Ok(ProxyResponse {
        status,
        headers: response_headers,
        body,
        duration_ms: duration,
    })
}

fn parse_method(method: &str) -> Result<Method, ProxyError> {
    match method.to_uppercase().as_str() {
        "GET" => Ok(Method::GET),
        "POST" => Ok(Method::POST),
        "PUT" => Ok(Method::PUT),
        "DELETE" => Ok(Method::DELETE),
        "PATCH" => Ok(Method::PATCH),
        "HEAD" => Ok(Method::HEAD),
        "OPTIONS" => Ok(Method::OPTIONS),
        _ => Err(ProxyError {
            code: "INVALID_METHOD".to_string(),
            message: format!("HTTP 代理请求失败：不支持的 HTTP 方法 '{}'。支持的方法包括：GET、POST、PUT、DELETE、PATCH、HEAD、OPTIONS。请检查请求中的 method 字段配置。", method),
            status: None,
        }),
    }
}

#[tauri::command]
pub async fn proxy_health_check(url: String) -> Result<serde_json::Value, ProxyError> {
    info!("Health check: {}", url);
    let start = std::time::Instant::now();

    let response = HTTP_CLIENT
        .get(&url)
        .send()
        .await
        .map_err(|e| ProxyError {
            code: "HEALTH_CHECK_FAILED".to_string(),
            message: format!("HTTP 代理健康检查失败：无法连接到目标服务 '{}'。错误详情: {}。可能原因：1) 目标服务未启动或不可达；2) URL 配置错误；3) 网络连接异常。请确认目标服务正在运行，并检查 URL 配置。", url, e),
            status: None,
        })?;

    let status = response.status();
    let duration = start.elapsed().as_millis();

    Ok(serde_json::json!({
        "url": url,
        "status": status.as_u16(),
        "reachable": status.is_success(),
        "response_time_ms": duration
    }))
}
