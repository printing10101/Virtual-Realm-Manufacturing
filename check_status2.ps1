$ErrorActionPreference = "SilentlyContinue"
Write-Host "=== python/powershell processes ==="
Get-Process | Where-Object { $_.Name -match 'python|powershell|pwsh' } |
    Select-Object Id, ProcessName, StartTime, @{N='CPU';E={[int]$_.CPU}}, @{N='WS_MB';E={[int]($_.WorkingSet/1MB)}} |
    Format-Table -AutoSize

Write-Host ""
Write-Host "=== PID 8344 / 31448 / 20252 / 29212 status ==="
foreach ($p in 8344, 31448, 20252, 29212) {
    $proc = Get-Process -Id $p -ErrorAction SilentlyContinue
    if ($proc) {
        Write-Host "PID $p : ALIVE ($($proc.Name), start=$($proc.StartTime))"
    } else {
        Write-Host "PID $p : DEAD"
    }
}

Write-Host ""
Write-Host "=== Schannel errors in last 5 min (guard alive?) ==="
$now = Get-Date
$recent = Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$now.AddMinutes(-5); Id=36871} -MaxEvents 5
if ($recent) {
    $recent | Select-Object TimeCreated, Id | Format-Table -AutoSize
    Write-Host "Guard may be ALIVE (Schannel errors still firing)"
} else {
    Write-Host "No Schannel errors in last 5 min - guard likely DEAD"
}

Write-Host ""
Write-Host "=== checkpoint mtime ==="
$ckpt = 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\lomo_loco_ar02_full\lomo_ckpt_DL-LNN_physics_aware.json'
Get-Item $ckpt | Select-Object LastWriteTime, Length

Write-Host ""
Write-Host "=== now ==="
Get-Date
