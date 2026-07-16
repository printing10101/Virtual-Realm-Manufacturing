# 启动后端服务脚本
# P0-5 修复：仅在 LNN_JWT_SECRET 未配置时生成临时密钥
if (-not $env:LNN_JWT_SECRET) {
    $env:LNN_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(32))"
    Write-Host "[startup] LNN_JWT_SECRET 未配置，已生成临时密钥（重启后失效）" -ForegroundColor Yellow
    Write-Host "[startup] JWT secret (前10位): $($env:LNN_JWT_SECRET.Substring(0,10))..."
    Write-Host "[startup] 警告：生产环境请在 .env 中固定 LNN_JWT_SECRET" -ForegroundColor Yellow
} else {
    Write-Host "[startup] LNN_JWT_SECRET 已从环境变量加载"
}

Set-Location "c:\Users\Lenovo\Desktop\灵境制造（上线版）\python"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
