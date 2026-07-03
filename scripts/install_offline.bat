@echo off
chcp 65001 >nul
REM ============================================================
REM 灵境制造（上线版）离线安装脚本 - 国内工厂版
REM ============================================================
REM 使用说明：
REM   1. 将整个 灵境制造_离线安装包 文件夹拷贝到目标机器
REM   2. 双击运行此脚本
REM   3. 等待安装完成，启动服务
REM
REM 前提条件：
REM   - Windows 10/11 或 Windows Server 2016+
REM   - 已安装 Docker Desktop（如未安装，脚本会提示）
REM   - 至少 8GB 内存，20GB 磁盘空间
REM ============================================================

echo ============================================================
echo  灵境制造（上线版）离线安装程序
echo  版本：v2.4.0 - 国内工厂版
echo ============================================================
echo.

REM 检查是否以管理员权限运行
net session >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] 建议以管理员权限运行此脚本
    echo 右键点击脚本，选择"以管理员身份运行"
    echo.
    pause
)

REM 检查 Docker 是否已安装
echo [1/6] 检查 Docker 环境...
docker --version >nul 2>&1
if %errorLevel% neq 0 (
    echo [错误] 未检测到 Docker
    echo.
    echo 请先安装 Docker Desktop：
    echo 1. 从安装包中的 docker-installer 目录找到 Docker Desktop 安装程序
    echo 2. 双击安装并重启电脑
    echo 3. 重新运行此脚本
    echo.
    echo 如果没有 Docker 安装包，请从以下地址下载（需要网络）：
    echo https://www.docker.com/products/docker-desktop
    echo.
    pause
    exit /b 1
)

echo [√] Docker 已安装
docker --version
echo.

REM 检查 Docker 是否正在运行
echo [2/6] 检查 Docker 服务状态...
docker ps >nul 2>&1
if %errorLevel% neq 0 (
    echo [警告] Docker 服务未启动，正在尝试启动...
    start /b "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    timeout /t 15 /nobreak >nul
    docker ps >nul 2>&1
    if %errorLevel% neq 0 (
        echo [错误] 无法启动 Docker 服务
        echo 请手动启动 Docker Desktop 后重试
        pause
        exit /b 1
    )
)
echo [√] Docker 服务正常运行
echo.

REM 加载离线镜像
echo [3/6] 加载 Docker 镜像（从离线包）...
if not exist "docker-images" (
    echo [错误] 未找到 docker-images 目录
    echo 请确保离线安装包完整
    pause
    exit /b 1
)

for %%f in (docker-images\*.tar) do (
    echo 正在加载：%%~nxf
    docker load -i "%%f"
    if %errorLevel% neq 0 (
        echo [警告] 加载 %%~nxf 失败，继续...
    ) else (
        echo [√] %%~nxf 加载成功
    )
)
echo.

REM 安装 Python 依赖（离线 wheel 包）
echo [4/6] 安装 Python 依赖...
if exist "wheels" (
    if exist "python\python.exe" (
        echo 从离线 wheel 包安装...
        python\python.exe -m pip install --no-index --find-links=wheels -r requirements.txt
        if %errorLevel% neq 0 (
            echo [警告] Python 依赖安装失败，将使用 Docker 容器运行
        )
    ) else (
        echo [跳过] 未找到嵌入式 Python，将完全使用 Docker 模式
    )
) else (
    echo [跳过] 未找到 wheels 目录，将完全使用 Docker 模式
)
echo.

REM 下载 AI 模型（如果未包含在离线包中）
echo [5/6] 检查 AI 模型...
if not exist "models\lnn" (
    echo [警告] 未找到预下载的 AI 模型
    echo.
    echo 如需使用本地 AI 模型，请执行以下步骤：
    echo 1. 确保有网络连接
    echo 2. 运行命令：python scripts\download_models.py --all
    echo 3. 或手动从魔搭社区下载模型到 models 目录
    echo.
    echo 也可以使用云端 API 模式（需要 API Key）：
    echo 编辑 .env 文件，设置 AI_MODE=cloud
    echo.
) else (
    echo [√] AI 模型已就绪
)
echo.

REM 初始化配置文件
echo [6/6] 初始化配置...
if not exist ".env" (
    if exist ".env.example" (
        copy .env.example .env >nul
        echo [√] 已创建 .env 配置文件
        echo.
        echo [重要] 请编辑 .env 文件，设置以下关键配置：
        echo   - POSTGRES_PASSWORD：数据库密码
        echo   - REDIS_PASSWORD：Redis 密码
        echo   - CLOUD_API_KEY：AI 云端 API Key（如使用云端模式）
        echo.
    ) else (
        echo [警告] 未找到 .env.example 模板文件
    )
) else (
    echo [√] .env 配置文件已存在
)
echo.

REM 启动服务
echo ============================================================
echo  安装完成！
echo ============================================================
echo.
echo 请选择启动模式：
echo.
echo   [1] 完整模式（推荐）：PostgreSQL + Redis + TDengine + API
echo   [2] 轻量模式：仅 SQLite（适合单机/开发）
echo   [3] 暂不启动，手动启动
echo.
set /p choice="请输入选项 (1/2/3): "

if "%choice%"=="1" (
    echo.
    echo 正在启动完整服务栈...
    docker compose -f docker-compose-cn.yml --profile full up -d
    if %errorLevel% equ 0 (
        echo.
        echo ============================================================
        echo  [√] 启动成功！
        echo ============================================================
        echo.
        echo 访问地址：http://localhost:8765
        echo API 文档：http://localhost:8765/docs
        echo.
        echo 查看日志：docker compose -f docker-compose-cn.yml logs -f
        echo 停止服务：docker compose -f docker-compose-cn.yml down
        echo.
    ) else (
        echo [错误] 启动失败，请检查日志
        docker compose -f docker-compose-cn.yml logs
    )
) else if "%choice%"=="2" (
    echo.
    echo 正在启动轻量模式（SQLite）...
    docker compose -f docker-compose-sqlite.yml up -d
    if %errorLevel% equ 0 (
        echo.
        echo ============================================================
        echo  [√] 启动成功！
        echo ============================================================
        echo.
        echo 访问地址：http://localhost:8765
        echo 数据目录：.\data
        echo.
        echo 查看日志：docker compose -f docker-compose-sqlite.yml logs -f
        echo 停止服务：docker compose -f docker-compose-sqlite.yml down
        echo.
    ) else (
        echo [错误] 启动失败，请检查日志
        docker compose -f docker-compose-sqlite.yml logs
    )
) else (
    echo.
    echo 稍后可手动启动：
    echo   完整模式：docker compose -f docker-compose-cn.yml --profile full up -d
    echo   轻量模式：docker compose -f docker-compose-sqlite.yml up -d
    echo.
)

pause
