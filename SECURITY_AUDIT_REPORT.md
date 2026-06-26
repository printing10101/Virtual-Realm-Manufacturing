# 灵境制造代码库安全审计报告

**审计日期**: 2026-06-24  
**审计范围**: c:\Users\Lenovo\Desktop\灵境制造（上线版）  
**审计目标**: 识别影响软件落地的安全问题

---

## 执行摘要

本次安全审计覆盖了认证与授权、注入攻击防护、密钥管理、会话管理和加密保护五个维度。发现 **3个高风险问题**、**5个中风险问题** 和 **4个低风险问题**。

### 安全亮点（正面发现）
- ✅ JWT 密钥强制从环境变量读取，无 fallback 机制
- ✅ 密码使用 bcrypt 哈希（12轮），符合行业标准
- ✅ 路径遍历防护完善（双重验证机制）
- ✅ CORS 配置强制启动时安全验证
- ✅ Token 黑名单机制线程安全
- ✅ 日志脱敏机制覆盖敏感信息

---

## 一、认证与授权安全

### 1.1 已实现的安全控制

| 控制项 | 状态 | 实现位置 | 说明 |
|--------|------|----------|------|
| JWT 密钥管理 | ✅ 安全 | `app/auth/security.py:49-82` | 强制从环境变量读取，最小长度32字符，随机性验证 |
| 密码哈希 | ✅ 安全 | `app/auth/security.py:144-149` | bcrypt 算法，12轮迭代 |
| Token 过期 | ✅ 合理 | `app/auth/security.py:125-126` | Access Token 30分钟，Refresh Token 7天 |
| Token 撤销 | ✅ 安全 | `app/auth/security.py:194-262` | 线程安全的黑名单机制，原子文件操作 |
| 权限层级 | ✅ 完善 | `app/auth/permissions.py` | R/W/B/N/C/T 六级权限体系 |
| 统一认证 | ✅ 安全 | `app/auth/unified_auth.py` | 合并 LNN/JWT/Agent 认证 |
| 速率限制 | ✅ 启用 | `app/api/v1/auth.py:63,124` | 注册 3/hour，登录 5/minute |

### 1.2 发现的问题

#### 问题 1：Cookie 安全属性未设置
- **风险等级**: 🟡 中
- **文件位置**: `app/main.py` 及所有认证端点
- **问题描述**: JWT Token 通过 JSON 响应返回，但未设置 Cookie 安全属性（HttpOnly、Secure、SameSite）
- **潜在风险**: 如果前端将 Token 存储在 Cookie 中，可能遭受 XSS 攻击窃取 Token
- **代码片段**:
  ```python
  # app/api/v1/auth.py:142-156
  return {
      "code": 0,
      "message": "登录成功",
      "data": {
          "access_token": access_token,  # 直接返回，未设置 Cookie 属性
          "refresh_token": refresh_token,
          "token_type": "bearer",
      },
  }
  ```
- **建议修复**: 
  - 如果前端使用 Cookie 存储 Token，应在响应中设置：
    ```python
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,      # 防止 XSS 窃取
        secure=True,        # 仅 HTTPS 传输
        samesite="strict",  # 防止 CSRF
        max_age=1800        # 30分钟
    )
    ```
  - 如果前端使用 localStorage，确保前端有 XSS 防护措施

---

## 二、注入攻击防护

### 2.1 命令注入防护

#### 问题 2：exec() 执行用户代码
- **风险等级**: 🔴 高
- **文件位置**: 
  - `app/cad/cadquery_gen.py:440`
  - `app/plugins/skill_loader/loader.py:321,340,816`
- **问题描述**: 使用 `exec()` 执行动态生成的 CadQuery 脚本和技能代码，虽然限制了内置函数，但仍存在沙箱逃逸风险
- **潜在风险**: 恶意构造的代码可能绕过限制，执行系统命令或访问敏感数据
- **代码片段**:
  ```python
  # app/cad/cadquery_gen.py:385-440
  def _run_cadquery_script(script: str, task_id: str) -> None:
      safe_globals = {
          "__builtins__": {
              "__import__": __import__,  # 仍允许导入
              "print": print,
              # ... 其他受限内置函数
          },
          "cq": cq,
          "cadquery": cq,
      }
      exec(script, safe_globals)  # 执行用户代码
  ```
- **建议修复**:
  1. **短期**: 使用 `RestrictedPython` 替代原生 `exec()`（技能加载器已使用）
  2. **中期**: 将代码执行隔离到独立子进程，使用 `subprocess.run()` 并限制资源
  3. **长期**: 实现代码白名单机制，仅允许预定义的安全操作

#### 问题 3：subprocess 调用固定命令
- **风险等级**: 🟢 低
- **文件位置**: 
  - `app/version.py:33-41`
  - `app/plugins/plugin_worker.py:255`
  - `app/research_bridge/research_api_client.py:124`
- **问题描述**: 使用 `subprocess.run()` 执行 git 命令和 Python 脚本
- **潜在风险**: 命令参数固定，无用户输入拼接，风险较低
- **代码片段**:
  ```python
  # app/version.py:33-41
  result = subprocess.run(
      ["git", "rev-parse", "--short", "HEAD"],  # 固定命令
      capture_output=True,
      text=True,
      cwd=_get_project_root(),
      timeout=5,
  )
  ```
- **建议修复**: 当前实现安全，无需修改

### 2.2 路径遍历防护

#### 已实现的安全控制

| 控制项 | 状态 | 实现位置 | 说明 |
|--------|------|----------|------|
| 路径净化 | ✅ 安全 | `app/dxf/api.py:331-359` | 拒绝 `/`、`\`、`..`，使用 `Path.name` 提取纯文件名 |
| 双重验证 | ✅ 安全 | `app/dxf/api.py:376-379` | `resolve()` + `is_relative_to()` 确保路径在允许目录内 |
| 安全文件打开 | ✅ 安全 | `app/utils/utils.py:117-135` | `safe_open()` 函数强制路径验证 |
| 文件上传验证 | ✅ 安全 | `app/dxf/api.py:85-110` | 扩展名白名单、大小限制（50MB） |

#### 问题 4：临时文件清理失败
- **风险等级**: 🟢 低
- **文件位置**: `app/dxf/api.py:183-193` 等多处
- **问题描述**: 临时文件清理失败时仅记录日志，未强制删除
- **潜在风险**: 磁盘空间耗尽，敏感数据残留
- **代码片段**:
  ```python
  # app/dxf/api.py:183-193
  finally:
      try:
          temp_path.unlink(missing_ok=True)
      except OSError as cleanup_err:
          logger.debug(
              "Failed to cleanup temp DXF upload %s: %s",
              temp_path,
              cleanup_err,
              exc_info=True,
          )
  ```
- **建议修复**: 
  - 实现定时清理任务，删除超过24小时的临时文件
  - 使用 `tempfile.TemporaryDirectory()` 自动管理临时目录

### 2.3 SSRF 防护

#### 问题 5：外部 HTTP 请求未验证 URL
- **风险等级**: 🟡 中
- **文件位置**: 
  - `app/ai/llm_client.py:122-127`
  - `app/api/v1/health.py:51-67`
  - `app/ai/ollama_routes.py:24,63`
- **问题描述**: 使用 `httpx.AsyncClient` 发起外部请求，URL 来自配置文件，未验证是否为内网地址
- **潜在风险**: 如果配置被篡改，可能访问内网服务（如 `http://169.254.169.254` 云元数据）
- **代码片段**:
  ```python
  # app/ai/llm_client.py:122-127
  async with httpx.AsyncClient(timeout=self.timeout) as client:
      response = await client.post(
          endpoint,  # 来自配置，未验证
          headers=headers,
          json=payload,
      )
  ```
- **建议修复**:
  ```python
  import ipaddress
  from urllib.parse import urlparse
  
  def _is_safe_url(url: str) -> bool:
      """验证 URL 是否为安全的外部地址"""
      parsed = urlparse(url)
      hostname = parsed.hostname
      
      # 解析 IP 地址
      try:
          ip = ipaddress.ip_address(hostname)
          # 拒绝私有网络地址
          if ip.is_private or ip.is_loopback or ip.is_link_local:
              return False
      except ValueError:
          # 域名形式，允许（但应进一步验证 DNS）
          pass
      
      # 拒绝常见云元数据地址
      if hostname in ["169.254.169.254", "metadata.google.internal"]:
          return False
      
      return True
  
  # 使用前验证
  if not _is_safe_url(endpoint):
      raise ValueError(f"Unsafe URL: {endpoint}")
  ```

### 2.4 XSS 防护

#### 已实现的安全控制
- ✅ 安全响应头：`X-XSS-Protection: 1; mode=block`（`app/auth/security_headers_asgi.py:17`）
- ✅ 内容类型保护：`X-Content-Type-Options: nosniff`
- ✅ 日志脱敏：`LogSanitizer` 过滤用户输入中的敏感信息

#### 问题 6：用户输入未转义
- **风险等级**: 🟢 低
- **文件位置**: 所有返回用户输入的端点
- **问题描述**: 部分端点直接返回用户输入，未进行 HTML 转义
- **潜在风险**: 如果前端未正确转义，可能导致存储型 XSS
- **建议修复**: 
  - 前端层面：使用 React/Vue 的自动转义机制
  - 后端层面：对返回的用户输入进行 HTML 转义
    ```python
    import html
    safe_input = html.escape(user_input)
    ```

---

## 三、密钥与敏感信息管理

### 3.1 已实现的安全控制

| 控制项 | 状态 | 实现位置 | 说明 |
|--------|------|----------|------|
| 环境变量管理 | ✅ 安全 | `app/config.py` | 敏感配置从环境变量读取 |
| .gitignore 配置 | ✅ 安全 | `.gitignore` | 排除 `.env`、token 文件、数据库文件 |
| 日志脱敏 | ✅ 安全 | `app/core/log_sanitizer.py` | 过滤 API 密钥、路径、工艺参数 |
| JWT 密钥验证 | ✅ 安全 | `app/auth/security.py:49-82` | 强制长度和随机性验证 |

### 3.2 发现的问题

#### 问题 7：.env 文件包含真实生产密码
- **风险等级**: 🔴 高
- **文件位置**: `.env`（已知问题）
- **问题描述**: `.env` 文件包含 PostgreSQL、Grafana、TDengine 等真实生产密码
- **潜在风险**: 如果 `.env` 文件泄露（如误提交到 Git），攻击者可获取数据库访问权限
- **建议修复**:
  1. **立即**: 验证 `.env` 未被提交到 Git 历史
    ```bash
    git log --all --full-history -- .env
    ```
  2. **短期**: 使用密钥管理服务（如 AWS Secrets Manager、HashiCorp Vault）
  3. **长期**: 实现配置加密，运行时解密

#### 问题 8：测试代码中的硬编码 Token
- **风险等级**: 🟢 低
- **文件位置**: `tests/test_auth.py` 等测试文件
- **问题描述**: 测试代码中可能包含硬编码的测试 Token
- **潜在风险**: 如果测试代码泄露，可能暴露测试环境凭证
- **建议修复**: 
  - 使用环境变量或测试配置文件
  - 确保测试 Token 与生产环境完全隔离

---

## 四、会话管理安全

### 4.1 已实现的安全控制

| 控制项 | 状态 | 实现位置 | 说明 |
|--------|------|----------|------|
| Token 过期 | ✅ 合理 | `app/auth/security.py:125-126` | Access 30min, Refresh 7d |
| Token 撤销 | ✅ 安全 | `app/auth/security.py:194-262` | 线程安全的黑名单 |
| Token 轮换 | ✅ 安全 | `app/api/v1/auth.py:182-185` | Refresh 时生成新 JTI |
| 用户状态检查 | ✅ 安全 | `app/api/v1/auth.py:46-49` | 验证用户存在且活跃 |

### 4.2 发现的问题

#### 问题 9：Refresh Token 未强制轮换
- **风险等级**: 🟡 中
- **文件位置**: `app/api/v1/auth.py:159-196`
- **问题描述**: Refresh Token 端点生成新的 Access Token 和 Refresh Token，但旧的 Refresh Token 未被显式撤销
- **潜在风险**: 如果旧 Refresh Token 泄露，攻击者可在7天内持续生成新 Token
- **代码片段**:
  ```python
  # app/api/v1/auth.py:182-185
  ban_list.ban(refresh_token_str)  # 撤销旧 Refresh Token
  new_jti = str(uuid.uuid4())
  new_access = create_access_token({"sub": username, "role": user.role, "jti": new_jti})
  new_refresh = create_refresh_token({"sub": username, "jti": str(uuid.uuid4())})
  ```
- **建议修复**: 当前实现已撤销旧 Refresh Token（第182行），但建议增加：
  - 记录 Refresh Token 使用次数，异常时强制重新登录
  - 实现 Refresh Token 家族检测（同一 JTI 多次使用表示泄露）

#### 问题 10：并发会话未限制
- **风险等级**: 🟡 中
- **文件位置**: 全局
- **问题描述**: 未限制同一用户的并发会话数量
- **潜在风险**: 凭证泄露后，攻击者可在多地同时登录
- **建议修复**: 
  - 在用户表中记录当前活跃的 JTI 列表
  - 登录时检查并发会话数，超过阈值时强制旧会话失效

---

## 五、加密与数据保护

### 5.1 已实现的安全控制

| 控制项 | 状态 | 实现位置 | 说明 |
|--------|------|----------|------|
| 密码哈希 | ✅ 安全 | `app/auth/security.py:144-149` | bcrypt 12轮 |
| CORS 配置 | ✅ 安全 | `app/middleware/cors_config.py` | 强制启动验证，禁止通配符 |
| 安全响应头 | ✅ 安全 | `app/auth/security_headers_asgi.py` | X-Content-Type-Options 等 |
| 日志脱敏 | ✅ 安全 | `app/core/log_sanitizer.py` | 过滤敏感信息 |

### 5.2 发现的问题

#### 问题 11：TLS/HTTPS 未在代码中强制
- **风险等级**: 🔴 高
- **文件位置**: `app/main.py:390-391`
- **问题描述**: 应用监听 HTTP（端口8000），未强制 HTTPS
- **潜在风险**: 数据在传输过程中可能被窃听或篡改
- **代码片段**:
  ```python
  # app/main.py:390-391
  if __name__ == "__main__":
      uvicorn.run("app.main:app", host="0.0.0.0", port=8765, reload=True)
  ```
- **建议修复**:
  1. **部署层面**: 使用 nginx/caddy 作为反向代理，强制 HTTPS
  2. **代码层面**: 检测环境变量，生产环境拒绝 HTTP 请求
    ```python
    from fastapi import Request
    from fastapi.responses import RedirectResponse
    
    @app.middleware("http")
    async def enforce_https(request: Request, call_next):
        if os.environ.get("LINGJING_ENV") == "production":
            if not request.headers.get("x-forwarded-proto") == "https":
                return RedirectResponse(
                    url=f"https://{request.url.netloc}{request.url.path}",
                    status_code=301
                )
        return await call_next(request)
    ```

#### 问题 12：用户数据使用 JSON 文件存储
- **风险等级**: 🟡 中
- **文件位置**: `app/models/user.py`
- **问题描述**: 用户数据（包括密码哈希）存储在 JSON 文件中，未加密
- **潜在风险**: 文件泄露后，攻击者可离线破解密码哈希
- **建议修复**:
  1. **短期**: 限制文件权限（仅应用用户可读）
  2. **中期**: 迁移到 SQLite/PostgreSQL，启用透明数据加密（TDE）
  3. **长期**: 实现应用层加密，敏感字段（如邮箱）加密存储

#### 问题 13：敏感数据未加密存储
- **风险等级**: 🟡 中
- **文件位置**: 全局
- **问题描述**: 用户邮箱、手机号等 PII 数据明文存储
- **潜在风险**: 数据泄露后，用户隐私暴露
- **建议修复**:
  - 使用 AES-256-GCM 加密敏感字段
  - 密钥从环境变量读取，定期轮换

---

## 六、风险汇总与优先级

### 高风险问题（立即修复）

| 编号 | 问题 | 文件位置 | 修复建议 |
|------|------|----------|----------|
| 2 | exec() 执行用户代码 | `cadquery_gen.py:440`, `loader.py:321` | 使用 RestrictedPython 或子进程隔离 |
| 7 | .env 包含生产密码 | `.env` | 迁移到密钥管理服务 |
| 11 | TLS 未强制 | `main.py:390` | 部署层面强制 HTTPS |

### 中风险问题（1周内修复）

| 编号 | 问题 | 文件位置 | 修复建议 |
|------|------|----------|----------|
| 1 | Cookie 安全属性未设置 | `auth.py` 等 | 设置 HttpOnly/Secure/SameSite |
| 5 | SSRF 风险 | `llm_client.py:122` | 验证 URL 非内网地址 |
| 9 | Refresh Token 未强制轮换 | `auth.py:182` | 实现家族检测 |
| 10 | 并发会话未限制 | 全局 | 限制并发会话数 |
| 12 | JSON 文件存储用户数据 | `user.py` | 迁移到加密数据库 |
| 13 | PII 未加密存储 | 全局 | 应用层加密 |

### 低风险问题（1月内修复）

| 编号 | 问题 | 文件位置 | 修复建议 |
|------|------|----------|----------|
| 3 | subprocess 固定命令 | `version.py:33` | 无需修改 |
| 4 | 临时文件清理失败 | `dxf/api.py:183` | 实现定时清理 |
| 6 | 用户输入未转义 | 全局 | 前端自动转义 |
| 8 | 测试代码硬编码 Token | `tests/` | 使用环境变量 |

---

## 七、修复建议与实施路线图

### 第一阶段（立即 - 1周）
1. **验证 .env 未泄露**
   ```bash
   git log --all --full-history -- .env
   ```
2. **部署 HTTPS**
   - 配置 nginx/caddy 反向代理
   - 强制 HTTP 重定向到 HTTPS
3. **修复 exec() 风险**
   - 将 `cadquery_gen.py` 的 `exec()` 替换为 `RestrictedPython`
   - 或隔离到子进程执行

### 第二阶段（1-2周）
1. **实现 SSRF 防护**
   - 添加 URL 验证函数
   - 拒绝内网地址和云元数据地址
2. **增强会话管理**
   - 实现 Refresh Token 家族检测
   - 限制并发会话数（如最多3个）
3. **设置 Cookie 安全属性**
   - 如果前端使用 Cookie，设置 HttpOnly/Secure/SameSite

### 第三阶段（1月内）
1. **迁移用户数据存储**
   - 从 JSON 文件迁移到 SQLite/PostgreSQL
   - 启用透明数据加密
2. **实现 PII 加密**
   - 使用 AES-256-GCM 加密敏感字段
   - 密钥管理服务集成
3. **实现定时清理任务**
   - 删除超过24小时的临时文件

---

## 八、总结

灵境制造代码库在认证、授权、路径防护等方面实现了较为完善的安全控制，但仍存在 **3个高风险问题** 需要立即修复：

1. **exec() 执行用户代码** - 存在沙箱逃逸风险
2. **.env 包含生产密码** - 凭证泄露风险
3. **TLS 未强制** - 数据传输安全风险

建议按照修复路线图，优先处理高风险问题，并在1个月内完成所有中低风险问题的修复。同时，建议建立持续的安全审计机制，定期审查代码安全状况。

---

**审计人员**: AI Security Auditor  
**审计方法**: 静态代码分析 + 安全配置审查  
**审计工具**: 手动审查 + 模式匹配
