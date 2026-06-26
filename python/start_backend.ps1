# 启动后端服务脚本
$env:LNN_JWT_SECRET = python -c "import secrets; print(secrets.token_urlsafe(32))"
Write-Host "JWT secret generated: $($env:LNN_JWT_SECRET.Substring(0,10))..."

Set-Location "c:\Users\Lenovo\Desktop\灵境制造（上线版）\python"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8765 --reload
