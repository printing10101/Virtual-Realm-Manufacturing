@echo off
REM P0-6 修复：补充 LNN_JWT_SECRET 设置，避免跨进程 JWT 失效
if "%LNN_JWT_SECRET%"=="" (
    for /f "delims=" %%i in ('python -c "import secrets; print(secrets.token_urlsafe(32))"') do set LNN_JWT_SECRET=%%i
    echo [startup] LNN_JWT_SECRET 未配置，已生成临时密钥（重启后失效）
    echo [startup] 警告：生产环境请在 .env 中固定 LNN_JWT_SECRET
) else (
    echo [startup] LNN_JWT_SECRET 已从环境变量加载
)
cd /d c:\Users\Lenovo\Desktop\灵境制造（上线版）\python
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765 --log-level info
