$token = Get-Content ".lnn_token"
$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

$body = @{
    model_name = "cutting_force"
    data_path = "C:\Users\Lenovo\AppData\Local\Temp\uniwear.csv"
    hyperparameters = @{
        epochs = 3
        batch_size = 32
        learning_rate = 0.001
        optimizer = "adam"
    }
    device = "cpu"
} | ConvertTo-Json -Depth 4

Write-Host "Testing train endpoint..."
$start = Get-Date
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/lnn/train" -Method POST -Headers $headers -Body $body -TimeoutSec 30
    $elapsed = ((Get-Date) - $start).TotalSeconds
    Write-Host "Train response: $($resp | ConvertTo-Json -Compress)"
    Write-Host "Elapsed: ${elapsed}s"
} catch {
    Write-Host "Train failed: $_"
}

Write-Host "`nTesting ping..."
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/health/ping" -TimeoutSec 5
    Write-Host "Ping: $($resp | ConvertTo-Json -Compress)"
} catch {
    Write-Host "Ping failed: $_"
}

Write-Host "`nTesting jobs list..."
try {
    $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/v1/jobs" -Headers $headers -TimeoutSec 10
    Write-Host "Jobs: $($resp | ConvertTo-Json -Depth 3 -Compress)"
} catch {
    Write-Host "Jobs failed: $_"
}
