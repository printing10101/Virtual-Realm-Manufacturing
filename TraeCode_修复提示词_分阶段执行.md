# 灵境制造系统 - Trae Code 修复提示词（分阶段执行）

> **使用说明**：将每个阶段的提示词完整复制到 Trae Code 模式，按顺序执行。每步执行后运行对应的检测命令验证效果。

---

## 阶段一：P0 紧急安全修复（必须立即执行）

### Step 1.1 - 修复路径遍历漏洞（3处文件下载端点）

**提示词（复制到Trae Code）**：

```
请修复以下3个文件中的路径遍历漏洞。当前代码直接将用户传入的file_name拼接到路径中，攻击者可以使用"../"遍历到任意目录下载服务器文件。

需要修改的文件和位置：
1. python/app/dxf/api.py 第281-298行 - download_model函数
2. python/app/step_import/api.py 第305-328行 - get_output_file函数  
3. python/app/simulation/api.py 第515-539行 - get_simulation_output函数

修复要求：
- 使用 pathlib.PurePosixPath(file_name).name 提取纯文件名，拒绝包含路径分隔符的输入
- 使用 Path.resolve() 和 is_relative_to() 验证最终路径是否在允许的输出目录内
- 如果检测到路径遍历，返回 HTTP 400 错误
- 保持原有功能不变（文件存在性检查、媒体类型判断、FileResponse返回）

检测方法（执行后验证）：
1. 运行：python -c "from pathlib import Path, PurePosixPath; print(PurePosixPath('../etc/passwd').name)"
   预期输出：passwd
2. 运行以下测试脚本验证路径遍历被阻止：
   ```python
   import requests
   # 测试1: 正常文件请求应返回404（文件不存在）
   r1 = requests.get('http://localhost:8000/api/model/download/test.stl')
   assert r1.status_code in [404, 400], f"正常请求异常: {r1.status_code}"
   # 测试2: 路径遍历请求应返回400
   r2 = requests.get('http://localhost:8000/api/model/download/../etc/passwd')
   assert r2.status_code == 400, f"路径遍历未被阻止: {r2.status_code}"
   print("路径遍历漏洞修复验证通过！")
   ```
```

---

### Step 1.2 - 修复 exec() 沙箱逃逸漏洞

**提示词（复制到Trae Code）**：

```
请修复 python/app/core/skill_loader.py 中的沙箱逃逸漏洞。

当前问题（第764行）：
_SAFE_BUILTINS 字典中包含了 "__import__": __import__，攻击者可以通过 __import__('os') 导入任意模块，绕过沙箱限制。

修复要求：
1. 从 _SAFE_BUILTINS 中移除 "__import__"
2. 同时移除 type、vars、dir、getattr 等可用于内省和绕过沙箱的内置函数
3. 考虑使用 RestrictedPython 库替代当前方案，或在独立进程中执行不受信任的代码
4. 如果保留当前方案，确保 _SAFE_BUILTINS 中只包含真正安全的函数（如 abs、len、range、str、int、float、sum、min、max 等纯计算函数）
5. 添加代码注释说明安全沙箱的限制

检测方法（执行后验证）：
1. 检查 _SAFE_BUILTINS 中不再包含 __import__、type、vars、dir、getattr
2. 运行以下测试：
   ```python
   from app.core.skill_loader import SkillLoader
   loader = SkillLoader()
   # 测试1: __import__ 不可用
   code1 = "result = __import__('os').system('echo hacked')"
   try:
       loader._compile_code(code1, "test1")
       print("FAIL: __import__ 仍可用")
   except Exception:
       print("PASS: __import__ 已被阻止")
   # 测试2: type 绕过不可用
   code2 = "result = type('').__bases__[0].__subclasses__()"
   try:
       loader._compile_code(code2, "test2")
       print("FAIL: type 绕过仍可用")
   except Exception:
       print("PASS: type 绕过已被阻止")
   ```
```

---

### Step 1.3 - 替换 eval() 为安全替代方案

**提示词（复制到Trae Code）**：

```
请修复 python/app/rules/safety_constraint_rules.py 中的 eval() 调用。

当前问题（第519-521行）：
```python
tokens = re.findall(r'[\d.]+|[+\-*/]', result)
if tokens and len(tokens) >= 3:
    return float(eval("".join(tokens)))
```

修复要求：
1. 使用 ast.literal_eval() 或编写一个简单的数学表达式解析器替代 eval()
2. 解析器只支持 +、-、*、/ 四则运算和浮点数
3. 保持原有功能：将传感器数据替换后的表达式计算为浮点数结果
4. 如果表达式无法解析，返回 0.0（保持原有降级行为）

检测方法（执行后验证）：
1. 确认文件中不再包含 eval( 调用
2. 运行以下测试：
   ```python
   from app.rules.safety_constraint_rules import SafetyConstraintRules
   rules = SafetyConstraintRules()
   # 测试正常计算
   result = rules._evaluate_expression("10.5+20.3*2", {"sensor1": 10.5})
   assert result == 51.1, f"计算错误: {result}"
   # 测试恶意代码被阻止
   try:
       rules._evaluate_expression("__import__('os').system('echo hack')", {})
       print("FAIL: 恶意代码未阻止")
   except:
       print("PASS: 恶意代码被阻止")
   print("eval() 替换验证通过！")
   ```
```

---

### Step 1.4 - 关闭开放注册 + 启用权限强制检查

**提示词（复制到Trae Code）**：

```
请修复以下两个安全问题：

问题1：python/app/api/v1/auth.py 第56-77行
/register 端点对所有人开放，攻击者可批量注册账号。

修复要求：
- 添加注册邀请码机制（环境变量 LNN_REGISTRATION_CODE 控制）
- 如果未设置邀请码环境变量，注册端点返回 403 禁止注册
- 保留现有用户存在性检查
- 添加注册速率限制（同一IP每小时最多5次注册尝试）

问题2：python/app/config.py 第336-337行
LNN_PERMISSION_ENFORCED 默认值为 False，权限检查默认关闭。

修复要求：
- 将默认值从 False 改为 True
- 添加启动时警告日志：如果权限检查被关闭，输出 WARNING 级别日志
- 确保权限中间件在权限关闭时仍然记录访问日志

检测方法（执行后验证）：
1. 检查 config.py 中 permission_enforced 默认值为 True
2. 运行以下测试：
   ```python
   import requests
   # 测试1: 无邀请码注册应返回403
   r1 = requests.post('http://localhost:8000/api/v1/auth/register', 
                      json={"username": "test_hacker", "password": "test123"})
   assert r1.status_code == 403, f"开放注册未关闭: {r1.status_code}"
   # 测试2: 有邀请码注册应成功（假设邀请码为"INVITE2024"）
   r2 = requests.post('http://localhost:8000/api/v1/auth/register',
                      json={"username": "test_user", "password": "test123", "invite_code": "INVITE2024"})
   assert r2.status_code in [200, 409], f"邀请码注册失败: {r2.status_code}"
   print("注册安全修复验证通过！")
   ```
```

---

### Step 1.5 - 修复 Token 默认最高权限

**提示词（复制到Trae Code）**：

```
请修复 python/app/core/middleware/unified_auth.py 中的权限默认问题。

当前问题（第94-109行）：
当 token 元数据文件不存在时，系统默认返回 {"level": "T"}（最高执行权限）。

修复要求：
1. 将默认权限从 "T" 改为 "R"（最低只读权限）
2. 添加日志记录：当使用默认权限时，输出 WARNING 日志提示管理员配置 token 元数据
3. 保持现有 token 元数据文件解析逻辑不变
4. 确保现有已配置 token 的用户不受影响

检测方法（执行后验证）：
1. 检查 unified_auth.py 第97行返回值为 {"level": "R"}
2. 运行以下测试：
   ```python
   from app.core.middleware.unified_auth import _get_token_metadata
   import os
   # 临时移除元数据文件
   meta_file = os.environ.get("LNN_TOKEN_META_FILE", ".lnn_token_meta.json")
   if os.path.exists(meta_file):
       os.rename(meta_file, meta_file + ".bak")
   try:
       result = _get_token_metadata("any_token")
       assert result.get("level") == "R", f"默认权限不是R: {result}"
       print("PASS: 默认权限已改为R")
   finally:
       if os.path.exists(meta_file + ".bak"):
           os.rename(meta_file + ".bak", meta_file)
   ```
```

---

## 阶段二：P1 高优先级修复（尽快执行）

### Step 2.1 - 修复 Workspace.vue 绕过 HTTP 拦截器

**提示词（复制到Trae Code）**：

```
请修复 src/views/Workspace.vue 中直接使用 axios 而非封装 http 客户端的问题。

当前问题：
- 第487行：import axios from 'axios'
- 第683行：axios.post('/api/v1/lnn/predict', ...)
- 这导致：Token 不自动附带、Token 刷新失效、统一错误提示不生效、制造业错误冲突对话框不触发

修复要求：
1. 将 import axios from 'axios' 替换为 import http from '@/utils/http'
2. 将所有 axios.post/axios.get 调用替换为 http.post/http.get
3. 检查 Workspace.vue 中是否还有其他直接使用 axios 的地方，一并替换
4. 保持原有请求参数和响应处理逻辑不变
5. 确保错误处理仍然有效（http 拦截器会自动处理401/403等错误）

检测方法（执行后验证）：
1. 检查 Workspace.vue 中不再包含 "import axios"
2. 检查所有 API 调用使用 http 而非 axios
3. 运行前端构建：npm run build
4. 在浏览器开发者工具中验证：
   - 打开 Workspace 页面
   - 执行一次推理请求
   - 检查请求头中包含 Authorization: Bearer <token>
   - 检查网络错误时显示统一错误提示而非原始错误
```

---

### Step 2.2 - 修复首页硬编码数据

**提示词（复制到Trae Code）**：

```
请修复 src/views/Home.vue 中硬编码的系统状态数据。

当前问题（第15-24行）：
- AI服务状态硬编码为"运行中"
- 模型注册数硬编码为 4
- 不调用任何 API 获取真实状态

修复要求：
1. 在 script setup 中添加 onMounted 生命周期钩子
2. 调用 /api/health 端点获取真实系统状态
3. 调用 /api/v1/lnn/models 端点获取真实模型注册数
4. 添加 loading 状态，数据加载前显示骨架屏或加载动画
5. 如果 API 调用失败，显示"状态获取失败"而非硬编码数据
6. 保持原有UI布局和样式

检测方法（执行后验证）：
1. 打开首页，观察系统状态卡片
2. 检查浏览器开发者工具 Network 面板：
   - 应有 /api/health 和 /api/v1/lnn/models 请求
   - 状态数据应来自 API 响应而非硬编码
3. 模拟 API 失败（如停止后端服务），确认显示"状态获取失败"
```

---

### Step 2.3 - 修复 docker-compose 硬编码密码和端口暴露

**提示词（复制到Trae Code）**：

```
请修复 docker-compose.yml 中的安全配置问题。

当前问题：
1. 第16行：DB_URL=postgresql://lnn:lnn_password@postgres:5432/lnn_db
2. 第69行：POSTGRES_PASSWORD=lnn_password
3. 第108行：GF_SECURITY_ADMIN_PASSWORD=admin
4. 第48行：Redis 端口 6379 映射到主机
5. 第66行：PostgreSQL 端口 5432 映射到主机

修复要求：
1. 使用 Docker secrets 或 .env 文件管理密码
2. 创建 .env.example 模板文件（包含所有需要的环境变量，密码留空）
3. 将 docker-compose.yml 中的硬编码密码替换为 ${VAR_NAME} 语法
4. 移除 Redis 和 PostgreSQL 的端口映射（只在容器网络内通信）
5. 保留 API 端口 8000、Grafana 3000、Prometheus 9090 的映射
6. 更新 .gitignore，确保 .env 文件不被提交
7. 添加 docker-compose.yml 顶部注释说明如何使用 .env 文件

检测方法（执行后验证）：
1. 检查 docker-compose.yml 中不再包含明文密码
2. 检查 .env.example 存在且包含所有必要变量
3. 运行：docker compose config
   预期：能正确解析环境变量，无硬编码密码
4. 检查 .gitignore 包含 .env
```

---

### Step 2.4 - 启用全局速率限制

**提示词（复制到Trae Code）**：

```
请修复 python/app/config.py 中速率限制默认关闭的问题。

当前问题（第324-325行）：
RATE_LIMIT_ENABLED 默认值为 False

修复要求：
1. 将 RATE_LIMIT_ENABLED 默认值改为 True
2. 在 main.py 中为关键端点添加速率限制：
   - /api/v1/auth/login: 5次/分钟
   - /api/v1/auth/register: 3次/小时
   - /api/v1/lnn/predict: 60次/分钟
   - /api/v1/lnn/train: 5次/小时
3. 使用 slowapi 或 FastAPI-limiter 库实现
4. 添加速率限制超出时的友好错误提示（中文）
5. 保留 Agent API 独立的速率限制逻辑

检测方法（执行后验证）：
1. 检查 config.py 中 rate_limit_enabled 默认值为 True
2. 运行以下测试：
   ```python
   import requests, time
   # 快速发送6次登录请求
   for i in range(6):
       r = requests.post('http://localhost:8000/api/v1/auth/login',
                         json={"username": "test", "password": "wrong"})
       if i < 5:
           assert r.status_code == 401, f"第{i+1}次请求异常: {r.status_code}"
       else:
           assert r.status_code == 429, f"速率限制未生效: {r.status_code}"
           print("PASS: 速率限制已生效")
   ```
```

---

### Step 2.5 - 修复 CORS 配置风险

**提示词（复制到Trae Code）**：

```
请修复 python/app/core/cors_config.py 中的 CORS 配置风险。

当前问题（第24-28行）：
开发模式使用通配符 *，同时 allow_credentials=True，存在安全风险。

修复要求：
1. 移除开发模式中的通配符 *，改为明确的 localhost 端口列表
2. 添加启动时 CORS 配置验证：如果 origins 包含 * 且 allow_credentials=True，输出 ERROR 日志并拒绝启动
3. 生产模式只允许配置的域名
4. 添加 CORS 配置文档注释说明安全风险

检测方法（执行后验证）：
1. 检查 cors_config.py 中 DEVELOPMENT_ORIGINS 不包含 *
2. 运行以下测试：
   ```python
   from app.core.cors_config import get_cors_config
   config = get_cors_config()
   assert "*" not in config.allow_origins, "CORS仍包含通配符"
   print("PASS: CORS配置安全")
   ```
```

---

### Step 2.6 - 修复仿真 API 接受任意文件路径

**提示词（复制到Trae Code）**：

```
请修复 python/app/simulation/api.py 中接受任意文件路径的问题。

当前问题（第254-267行）：
stock_stl_path 和 source_file_path 直接从用户请求获取，可指向服务器任意文件。

修复要求：
1. 限制 stock_stl_path 和 source_file_path 必须在预定义的输出目录或上传目录内
2. 使用 Path.resolve() 和 is_relative_to() 验证
3. 如果路径不在允许范围内，返回 HTTP 400 错误
4. 保持默认 stock STL 路径逻辑不变

检测方法（执行后验证）：
1. 运行以下测试：
   ```python
   import requests
   # 测试1: 正常路径（相对路径）
   r1 = requests.post('http://localhost:8000/api/simulation/run',
                      json={"stock_stl_path": "uploads/test.stl", ...})
   # 测试2: 恶意路径
   r2 = requests.post('http://localhost:8000/api/simulation/run',
                      json={"stock_stl_path": "/etc/passwd", ...})
   assert r2.status_code == 400, f"任意路径未被阻止: {r2.status_code}"
   print("PASS: 仿真API路径验证已生效")
   ```
```

---

### Step 2.7 - 升级依赖修复 CVE 漏洞

**提示词（复制到Trae Code）**：

```
请升级 requirements.txt 中的依赖以修复已知 CVE 漏洞。

当前问题：
pip-audit 发现 39 个已知 CVE，包括 cryptography、python-jose、python-multipart、langchain 等高危漏洞。

修复要求：
1. 检查 pip-audit-report.txt 中的漏洞列表
2. 将以下依赖升级到安全版本：
   - cryptography >= 48.0.0
   - python-jose >= 3.5.0
   - python-multipart >= 0.0.28
   - langchain >= 1.3.0
   - langchain-community >= 0.4.1
   - protobuf >= 5.29.6
   - requests >= 2.34.2
   - urllib3 >= 2.7.0
3. 运行 pip-audit 确认无高危漏洞
4. 运行现有测试套件确认兼容性

检测方法（执行后验证）：
1. 运行：pip-audit -r requirements.txt
   预期：无 HIGH/CRITICAL 级别漏洞
2. 运行：pytest tests/ -x
   预期：所有测试通过
```

---

## 阶段三：P2/P3 改进项（逐步执行）

### Step 3.1 - 统一健康检查端点

**提示词（复制到Trae Code）**：

```
请统一 python/app/main.py 和 python/app/api/v1/health.py 中的健康检查端点。

当前问题：
- /health 返回 {"status": "healthy", ...}
- /api/health 返回 {"status": "ok", "version": "2.0.0"}
- /api/health/ping 返回 {"ping": True}
- Dockerfile HEALTHCHECK 使用 /api/v1/health（不存在）

修复要求：
1. 保留 /api/health 作为主健康检查端点
2. /api/health/ping 作为轻量级 ping 检查
3. 移除 /health 端点（避免重复）
4. 更新 Dockerfile HEALTHCHECK 使用 /api/health/ping
5. 统一响应格式为 {"status": "ok", "version": "x.x.x", "timestamp": "..."}

检测方法：
1. 运行：curl http://localhost:8000/api/health
   预期：返回统一格式JSON
2. 运行：curl http://localhost:8000/api/health/ping
   预期：返回 {"ping": true}
3. 确认 Dockerfile 中 HEALTHCHECK 路径正确
```

---

### Step 3.2 - 添加 404 兜底路由

**提示词（复制到Trae Code）**：

```
请在 src/router/index.ts 中添加 404 兜底路由。

修复要求：
1. 添加路由：{ path: '/:pathMatch(.*)*', name: 'NotFound', component: () => import('@/views/NotFound.vue') }
2. 创建 src/views/NotFound.vue 组件，包含：
   - 404 图标或插图
   - "页面不存在"提示
   - 返回首页按钮
   - 保持与系统UI风格一致
3. 确保 NotFound 页面不需要认证即可访问

检测方法：
1. 访问不存在的 URL（如 /nonexistent-page）
2. 预期：显示 404 页面而非空白页
```

---

### Step 3.3 - 权限不足时添加提示

**提示词（复制到Trae Code）**：

```
请修复 src/router/index.ts 中权限不足时无提示的问题。

当前问题（第96-103行）：
权限不足时直接 next('/') 跳转首页，无提示。

修复要求：
1. 在跳转前添加 ElMessage.warning('权限不足，无法访问该页面')
2. 保持跳转逻辑不变
3. 确保 ElMessage 已导入

检测方法：
1. 登录普通用户账号
2. 尝试访问需要管理员权限的页面（如 /admin/users）
3. 预期：显示"权限不足"提示后跳转首页
```

---

### Step 3.4 - 清理未注册的 API 模块导入

**提示词（复制到Trae Code）**：

```
请清理 python/app/api/v1/__init__.py 中已导入但未在 main.py 中注册的模块。

当前问题：
__init__.py 导入了 plugins, skills, cost_budget, governance, goal_alignment, heartbeat, task_checkout, template_* 等模块，但 main.py 中没有 include_router。

修复要求：
1. 检查哪些模块是计划中的功能但尚未完成
2. 对于已完成但未注册的模块，在 main.py 中添加 include_router
3. 对于未完成的实验性功能，从 __init__.py 中移除导入，或添加 TODO 注释说明状态
4. 确保不会引入循环依赖

检测方法：
1. 运行：python -c "from app.main import app; print([r.path for r in app.routes])"
2. 确认所有应有路由都已注册
```

---

### Step 3.5 - 补充国际化覆盖

**提示词（复制到Trae Code）**：

```
请为以下组件中的硬编码中文添加国际化支持。

需要处理的文件：
1. src/App.vue - 导航菜单项（工艺规则、刀路编辑、用户管理、文件菜单等）
2. src/views/Workspace.vue - 工作区标题、标签页名称、按钮文字
3. src/views/Home.vue - 欢迎语、系统状态标签
4. src/components/step_import/StepImportDialog.vue - 上传提示、状态文字
5. src/views/RuleEditor.vue - 编辑器标题和描述

修复要求：
1. 在 src/locales/zh-CN.ts 和 src/locales/en.ts 中添加对应的翻译键
2. 将硬编码中文替换为 $t('key') 调用
3. 保持原有UI布局和样式不变
4. 确保英文翻译准确、专业

检测方法：
1. 切换语言为英文
2. 检查上述页面中不再显示中文
3. 切换回中文，确认中文显示正常
```

---

### Step 3.6 - 清理临时脚本

**提示词（复制到Trae Code）**：

```
请清理根目录和 python/ 目录下的临时/调试脚本。

需要处理的文件：
- python/_test_predict.py, debug_train.py, deep_diag.py, diagnose.py, diagnose2.py, diagnose3.py
- python/quick_diag.py, quick_test.py, run_8step_test.py, test_*.py（非 tests/ 目录下的）
- 根目录下的 launch_test.py, run_agent_test.py, check_server.py 等
- package.json.bak.* 文件

修复要求：
1. 有用的测试脚本迁移到 tests/ 目录并规范化命名
2. 一次性诊断脚本删除
3. 启动脚本整合为单一入口（保留 start_server.py 或类似）
4. .bak 文件删除
5. 更新 .gitignore 防止未来临时文件被提交

检测方法：
1. 运行：ls python/*.py | grep -E "(test_|debug_|diagnose|quick_|run_8)"
   预期：无匹配结果（除 tests/ 目录外）
2. 运行：ls *.bak* 2>/dev/null
   预期：无匹配结果
```

---

### Step 3.7 - 修复体素仿真性能瓶颈

**提示词（复制到Trae Code）**：

```
请优化 python/app/simulation/voxel_cutter.py 中的性能瓶颈。

当前问题：
1. 三重嵌套循环生成刀具掩码（第340-383行）- 纯Python，无向量化
2. 逐点碰撞检测串行处理（第718-740行）
3. 网格重建为每个体素创建独立box mesh（第1112-1141行）

修复要求：
1. 使用 NumPy 向量化操作替代三重嵌套循环
2. 考虑使用 Numba @jit 装饰器加速热点函数
3. 网格重建改用 Marching Cubes 算法（使用 scikit-image 或自定义实现）
4. 保持原有API接口和输出格式不变
5. 添加性能基准测试

检测方法：
1. 运行优化前后的基准测试对比
2. 对于 100x100x100 体素网格，处理时间应减少至少50%
3. 输出STL文件应与优化前几何一致
```

---

## 附录：批量检测脚本

将以下内容保存为 `verify_all_fixes.py`，每阶段修复后运行：

```python
#!/usr/bin/env python3
"""验证所有修复是否生效的综合检测脚本"""

import sys
import os
import subprocess
import requests

BASE_URL = "http://localhost:8000"
ERRORS = []

def check(condition, message):
    if not condition:
        ERRORS.append(message)
        print(f"  [FAIL] {message}")
    else:
        print(f"  [PASS] {message}")

def main():
    print("=" * 60)
    print("灵境制造系统 - 修复验证脚本")
    print("=" * 60)

    # === P0 安全修复验证 ===
    print("\n[阶段一] P0 紧急安全修复验证")

    # 1.1 路径遍历
    print("\n1.1 路径遍历漏洞修复:")
    try:
        r = requests.get(f'{BASE_URL}/api/model/download/../etc/passwd', timeout=5)
        check(r.status_code == 400, "DXF下载路径遍历被阻止")
    except Exception as e:
        check(False, f"DXF路径遍历测试异常: {e}")

    # 1.2 eval() 移除
    print("\n1.2 eval() 安全替换:")
    with open('python/app/rules/safety_constraint_rules.py', 'r') as f:
        content = f.read()
    check('eval(' not in content, "safety_constraint_rules.py 中无 eval() 调用")

    # 1.3 权限默认开启
    print("\n1.3 权限强制检查默认开启:")
    with open('python/app/config.py', 'r') as f:
        content = f.read()
    check('LNN_PERMISSION_ENFORCED", False)' not in content,
          "permission_enforced 默认不为 False")

    # 1.4 Token 默认权限
    print("\n1.4 Token 默认最低权限:")
    with open('python/app/core/middleware/unified_auth.py', 'r') as f:
        content = f.read()
    check('return {"level": "R"}' in content or 'return {"level": "R"}' in content,
          "Token默认权限为R")

    # === P1 修复验证 ===
    print("\n[阶段二] P1 高优先级修复验证")

    # 2.1 Workspace 使用 http
    print("\n2.1 Workspace.vue 使用封装http:")
    with open('src/views/Workspace.vue', 'r') as f:
        content = f.read()
    check('import axios' not in content, "Workspace.vue 不直接导入axios")
    check("import http from '@/utils/http'" in content or "from '@/utils/http'" in content,
          "Workspace.vue 导入封装的http")

    # 2.2 首页动态数据
    print("\n2.2 首页使用真实API数据:")
    with open('src/views/Home.vue', 'r') as f:
        content = f.read()
    check('onMounted' in content, "Home.vue 使用onMounted获取数据")
    check('/api/health' in content, "Home.vue 调用健康检查API")

    # 2.3 docker-compose 密码
    print("\n2.3 docker-compose 无硬编码密码:")
    with open('docker-compose.yml', 'r') as f:
        content = f.read()
    check('lnn_password' not in content, "docker-compose.yml 无硬编码密码")
    check('${' in content, "docker-compose.yml 使用环境变量")

    # 2.4 速率限制
    print("\n2.4 速率限制已启用:")
    with open('python/app/config.py', 'r') as f:
        content = f.read()
    check('RATE_LIMIT_ENABLED", False)' not in content,
          "速率限制默认不为False")

    # === P2/P3 改进验证 ===
    print("\n[阶段三] P2/P3 改进项验证")

    # 3.1 健康检查统一
    print("\n3.1 健康检查端点统一:")
    try:
        r = requests.get(f'{BASE_URL}/api/health', timeout=5)
        check(r.status_code == 200, "/api/health 可访问")
        data = r.json()
        check('status' in data and 'version' in data, "健康检查返回统一格式")
    except Exception as e:
        check(False, f"健康检查测试异常: {e}")

    # 3.2 404页面
    print("\n3.2 404兜底路由:")
    with open('src/router/index.ts', 'r') as f:
        content = f.read()
    check('pathMatch' in content, "路由配置包含404兜底")

    # 3.3 临时脚本清理
    print("\n3.3 临时脚本已清理:")
    temp_files = [f for f in os.listdir('python') if f.startswith(('test_', 'debug_', 'diagnose', 'quick_')) and f.endswith('.py')]
    check(len(temp_files) == 0, f"python/ 根目录无临时脚本 (发现{len(temp_files)}个)")

    # === 汇总 ===
    print("\n" + "=" * 60)
    if ERRORS:
        print(f"验证完成: {len(ERRORS)} 项未通过")
        for e in ERRORS:
            print(f"  - {e}")
        sys.exit(1)
    else:
        print("所有验证通过！")
        sys.exit(0)

if __name__ == '__main__':
    main()
```

---

## 执行顺序建议

| 顺序 | 步骤 | 预计时间 | 风险 |
|------|------|----------|------|
| 1 | Step 1.1 路径遍历修复 | 30分钟 | 低 |
| 2 | Step 1.2 exec()沙箱修复 | 45分钟 | 中 |
| 3 | Step 1.3 eval()替换 | 30分钟 | 低 |
| 4 | Step 1.4 注册+权限 | 45分钟 | 中 |
| 5 | Step 1.5 Token默认权限 | 15分钟 | 低 |
| 6 | Step 2.1 Workspace HTTP | 30分钟 | 低 |
| 7 | Step 2.2 首页动态数据 | 30分钟 | 低 |
| 8 | Step 2.3 docker-compose | 30分钟 | 中 |
| 9 | Step 2.4 速率限制 | 45分钟 | 中 |
| 10 | Step 2.5 CORS | 20分钟 | 低 |
| 11 | Step 2.6 仿真路径验证 | 20分钟 | 低 |
| 12 | Step 2.7 依赖升级 | 30分钟 | 中 |
| 13 | Step 3.x 改进项 | 按需 | 低 |

> **重要**：每执行完一个步骤，运行对应的检测方法验证。全部完成后运行 `verify_all_fixes.py` 进行综合验证。
