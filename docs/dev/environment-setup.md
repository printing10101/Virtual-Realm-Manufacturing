# 开发环境搭建指南

**版本**: 1.0.0  
**最后更新**: 2024-01-20  
**适用对象**: 新入职开发人员

---

## 目录

1. [环境要求](#环境要求)
2. [工具安装](#工具安装)
3. [项目克隆](#项目克隆)
4. [后端环境配置](#后端环境配置)
5. [前端环境配置](#前端环境配置)
6. [数据库初始化](#数据库初始化)
7. [启动服务](#启动服务)
8. [验证安装](#验证安装)
9. [常见问题](#常见问题)

---

## 环境要求

### 操作系统

- **Windows**: Windows 10/11 (64-bit)
- **macOS**: macOS 12+ (Monterey 或更高版本)
- **Linux**: Ubuntu 20.04+, CentOS 8+, Debian 11+

### 硬件要求

**最低配置**：
- CPU: 4 核
- 内存: 8 GB
- 存储: 20 GB 可用空间
- 网络: 稳定的互联网连接（用于下载依赖）

**推荐配置**：
- CPU: 8 核
- 内存: 16 GB
- 存储: 50 GB SSD
- 网络: 100 Mbps+

---

## 工具安装

### 1. Python 环境

**要求版本**: Python 3.10 或更高

#### Windows 安装

```powershell
# 方法 1: 使用官方安装包
# 访问 https://www.python.org/downloads/
# 下载 Python 3.10+ 安装包
# 安装时勾选 "Add Python to PATH"

# 方法 2: 使用 winget
winget install Python.Python.3.10

# 验证安装
python --version
# 预期输出: Python 3.10.x
```

#### macOS 安装

```bash
# 方法 1: 使用 Homebrew
brew install python@3.10

# 方法 2: 使用官方安装包
# 访问 https://www.python.org/downloads/

# 验证安装
python3 --version
# 预期输出: Python 3.10.x
```

#### Linux 安装

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install python3.10 python3.10-venv python3-pip

# CentOS/RHEL
sudo dnf install python3.10 python3.10-pip

# 验证安装
python3 --version
# 预期输出: Python 3.10.x
```

### 2. Node.js 环境

**要求版本**: Node.js 18 或更高

#### 使用 nvm 安装（推荐）

```bash
# 安装 nvm (Node Version Manager)
# macOS/Linux
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash

# 重新加载 shell 配置
source ~/.bashrc  # 或 ~/.zshrc

# 安装 Node.js 18
nvm install 18
nvm use 18
nvm alias default 18

# 验证安装
node --version
# 预期输出: v18.x.x

npm --version
# 预期输出: 9.x.x 或更高
```

#### Windows 安装

```powershell
# 方法 1: 使用 nvm-windows
# 下载 nvm-windows: https://github.com/coreybutler/nvm-windows/releases
# 安装后运行:
nvm install 18
nvm use 18

# 方法 2: 使用官方安装包
# 访问 https://nodejs.org/
# 下载 LTS 版本安装包
```

### 3. pnpm 包管理器

```bash
# 安装 pnpm
npm install -g pnpm

# 验证安装
pnpm --version
# 预期输出: 8.x.x 或更高
```

### 4. Git

```bash
# Windows
# 下载 Git for Windows: https://git-scm.com/download/win

# macOS
brew install git

# Linux
sudo apt install git  # Ubuntu/Debian
sudo dnf install git  # CentOS/RHEL

# 验证安装
git --version
# 预期输出: git version 2.x.x

# 配置 Git
git config --global user.name "你的名字"
git config --global user.email "你的邮箱"
```

### 5. SQLite

```bash
# Windows
# 下载 SQLite 工具: https://www.sqlite.org/download.html
# 解压并将 sqlite3.exe 添加到 PATH

# macOS
brew install sqlite

# Linux
sudo apt install sqlite3  # Ubuntu/Debian
sudo dnf install sqlite   # CentOS/RHEL

# 验证安装
sqlite3 --version
# 预期输出: 3.x.x
```

### 6. Docker（可选）

```bash
# Windows
# 下载 Docker Desktop: https://www.docker.com/products/docker-desktop

# macOS
brew install --cask docker

# Linux
# 参考: https://docs.docker.com/engine/install/

# 验证安装
docker --version
docker-compose --version
```

### 7. IDE 推荐

#### VS Code（推荐）

```bash
# 安装 VS Code
# 访问: https://code.visualstudio.com/

# 安装推荐扩展
code --install-extension ms-python.python
code --install-extension ms-python.vscode-pylance
code --install-extension ms-python.black-formatter
code --install-extension dbaeumer.vscode-eslint
code --install-extension esbenp.prettier-vscode
code --install-extension vue.volar
code --install-extension bradlc.vscode-tailwindcss
```

#### PyCharm

```bash
# 下载 PyCharm Professional（推荐）或 Community 版
# 访问: https://www.jetbrains.com/pycharm/

# 安装推荐插件
# - Vue.js
# - Black
# - Database Navigator
```

---

## 项目克隆

```bash
# 克隆项目
git clone https://github.com/your-org/lingjing-manufacturing.git

# 进入项目目录
cd lingjing-manufacturing

# 查看项目结构
ls -la
```

**项目结构概览**：

```
lingjing-manufacturing/
├── python/              # 后端代码
├── frontend/            # 前端代码
├── config/              # 配置文件
├── data/                # 数据文件
├── docs/                # 文档
├── deploy/              # 部署配置
└── scripts/             # 脚本工具
```

---

## 后端环境配置

### 1. 创建虚拟环境

```bash
# 进入后端目录
cd python

# 创建虚拟环境
python -m venv venv

# 激活虚拟环境
# Windows PowerShell
.\venv\Scripts\Activate.ps1

# Windows CMD
.\venv\Scripts\activate.bat

# macOS/Linux
source venv/bin/activate

# 验证虚拟环境
which python  # 应该指向 venv 目录
```

### 2. 安装 Python 依赖

```bash
# 升级 pip
python -m pip install --upgrade pip

# 安装项目依赖
pip install -r requirements.txt

# 如果网络慢，使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple
```

### 3. 配置环境变量

```bash
# 复制环境变量示例文件
cp ../.env.example ../.env

# 编辑环境变量
# Windows
notepad ../.env

# macOS/Linux
vim ../.env
```

**关键环境变量**：

```bash
# .env 文件内容
DATABASE_URL=sqlite:///./data/lingjing.db
JWT_SECRET=your-secret-key-change-in-production
REDIS_URL=redis://localhost:6379
LOG_LEVEL=INFO
DEBUG=True
```

### 4. 安装开发工具

```bash
# 安装开发工具
pip install black flake8 pytest pytest-cov mypy

# 安装 pre-commit hooks
pip install pre-commit
pre-commit install
```

---

## 前端环境配置

### 1. 安装依赖

```bash
# 进入前端目录
cd ../frontend

# 安装依赖
pnpm install

# 如果网络慢，配置国内镜像
pnpm config set registry https://registry.npmmirror.com
pnpm install
```

### 2. 配置环境变量

```bash
# 复制环境变量示例文件
cp .env.example .env.local

# 编辑环境变量
# Windows
notepad .env.local

# macOS/Linux
vim .env.local
```

**关键环境变量**：

```bash
# .env.local 文件内容
VITE_API_BASE_URL=http://localhost:8000
VITE_APP_TITLE=灵境制造系统
```

### 3. 安装开发工具

```bash
# 安装 ESLint 和 Prettier
pnpm add -D eslint prettier

# 安装 Vue 开发工具
# 在浏览器中安装 Vue DevTools 扩展
```

---

## 数据库初始化

### 1. 创建数据库目录

```bash
# 回到项目根目录
cd ..

# 创建数据目录
mkdir -p data
mkdir -p logs
```

### 2. 初始化数据库

```bash
# 进入后端目录
cd python

# 运行数据库迁移
alembic upgrade head

# 验证数据库创建
ls -lh ../data/
# 应该看到 lingjing.db 文件
```

### 3. 导入初始数据（可选）

```bash
# 导入示例数据
python scripts/import_sample_data.py

# 或导入测试数据
python scripts/import_test_data.py
```

---

## 启动服务

### 方式一：分别启动（开发环境推荐）

#### 启动后端服务

```bash
# 在第一个终端窗口
cd python

# 激活虚拟环境
# Windows
.\venv\Scripts\Activate.ps1
# macOS/Linux
source venv/bin/activate

# 启动后端服务
python start_server.py

# 或使用 uvicorn 直接启动
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

#### 启动前端服务

```bash
# 在第二个终端窗口
cd frontend

# 启动前端开发服务器
pnpm dev
```

### 方式二：使用 Docker Compose

```bash
# 在项目根目录
docker-compose up -d

# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f
```

### 方式三：使用脚本

```bash
# Windows
.\start_dev.ps1

# macOS/Linux
./start_dev.sh
```

---

## 验证安装

### 1. 检查后端服务

```bash
# 健康检查
curl http://localhost:8000/health

# 预期响应
{
  "status": "healthy",
  "version": "2.0.0",
  "database": "connected",
  "lnn_engine": "ready"
}
```

### 2. 检查前端服务

```bash
# 访问前端页面
# 在浏览器中打开: http://localhost:3000

# 或使用 curl
curl http://localhost:3000
# 应该返回 HTML 内容
```

### 3. 检查 API 文档

```bash
# 访问 Swagger UI
# 在浏览器中打开: http://localhost:8000/docs

# 访问 ReDoc
# 在浏览器中打开: http://localhost:8000/redoc
```

### 4. 运行测试

```bash
# 后端测试
cd python
pytest tests/unit/ -v

# 前端测试
cd ../frontend
pnpm test:unit
```

### 5. 检查数据库

```bash
# 进入数据库
sqlite3 data/lingjing.db

# 查看表
.tables

# 查看用户表
SELECT * FROM users LIMIT 5;

# 退出
.quit
```

---

## 常见问题

### Q1: pip install 失败

**问题**：安装依赖时出现网络错误或超时

**解决方案**：

```bash
# 使用国内镜像
pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple

# 或使用阿里云镜像
pip install -r requirements.txt -i https://mirrors.aliyun.com/pypi/simple/

# 配置永久镜像
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

### Q2: pnpm install 失败

**问题**：安装前端依赖时出现网络错误

**解决方案**：

```bash
# 配置国内镜像
pnpm config set registry https://registry.npmmirror.com

# 清除缓存重试
pnpm cache clean
pnpm install
```

### Q3: 端口被占用

**问题**：启动服务时提示端口 8000 或 3000 被占用

**解决方案**：

```bash
# Windows - 查找占用端口的进程
netstat -ano | findstr :8000
# 杀死进程
taskkill /PID <进程ID> /F

# macOS/Linux - 查找占用端口的进程
lsof -ti:8000 | xargs kill -9

# 或修改配置使用其他端口
# 后端: 修改 config/settings.yaml 中的 port
# 前端: 修改 frontend/vite.config.ts 中的 port
```

### Q4: 虚拟环境激活失败

**问题**：Windows PowerShell 无法激活虚拟环境

**解决方案**：

```powershell
# 修改执行策略
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser

# 重新激活
.\venv\Scripts\Activate.ps1
```

### Q5: 数据库迁移失败

**问题**：运行 `alembic upgrade head` 时出错

**解决方案**：

```bash
# 检查数据库文件权限
ls -lh data/lingjing.db

# 修复权限
chmod 664 data/lingjing.db

# 或删除数据库重新初始化
rm data/lingjing.db
alembic upgrade head
```

### Q6: 前端页面空白

**问题**：访问 http://localhost:3000 页面空白

**解决方案**：

```bash
# 检查浏览器控制台错误
# F12 打开开发者工具，查看 Console 标签

# 检查后端 API 是否启动
curl http://localhost:8000/health

# 检查环境变量配置
cat frontend/.env.local

# 重新构建前端
cd frontend
rm -rf node_modules
pnpm install
pnpm dev
```

### Q7: Python 版本不兼容

**问题**：提示 Python 版本过低

**解决方案**：

```bash
# 检查当前 Python 版本
python --version

# 如果版本低于 3.10，需要升级
# 或使用 pyenv 管理多个 Python 版本

# 安装 pyenv
# macOS/Linux
curl https://pyenv.run | bash

# 安装 Python 3.10
pyenv install 3.10.0
pyenv local 3.10.0

# 重新创建虚拟环境
rm -rf venv
python -m venv venv
```

---

## 开发工作流

### 1. 日常开发流程

```bash
# 1. 拉取最新代码
git pull origin main

# 2. 激活虚拟环境
cd python
source venv/bin/activate  # macOS/Linux
.\venv\Scripts\Activate.ps1  # Windows

# 3. 启动后端服务
python start_server.py

# 4. 在另一个终端启动前端
cd frontend
pnpm dev

# 5. 开始开发...

# 6. 提交代码
git add .
git commit -m "feat: 添加新功能"
git push origin feature/your-feature
```

### 2. 代码格式化

```bash
# 后端代码格式化
cd python
black app/
flake8 app/

# 前端代码格式化
cd frontend
pnpm run format
pnpm run lint
```

### 3. 运行测试

```bash
# 后端测试
cd python
pytest tests/ -v --cov=app

# 前端测试
cd frontend
pnpm test:unit
pnpm test:e2e
```

---

## 相关资源

### 内部资源

- [开发者指南 README](./README.md)
- [编码规范](./coding-standards.md)
- [API 开发指南](./api-development.md)
- [测试指南](./testing-guide.md)

### 外部资源

- [FastAPI 官方文档](https://fastapi.tiangolo.com/)
- [Vue 3 官方文档](https://vuejs.org/)
- [PyTorch 官方文档](https://pytorch.org/docs/)
- [SQLite 官方文档](https://www.sqlite.org/docs.html)

---

## 获取帮助

- **技术问题**: dev-support@your-company.com
- **文档问题**: docs@your-company.com
- **紧急问题**: +86-xxx-xxxx-xxxx

---

**最后更新**: 2024-01-20  
**维护者**: 开发团队
