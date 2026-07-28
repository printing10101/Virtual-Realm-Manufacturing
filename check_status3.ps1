$ErrorActionPreference = "SilentlyContinue"
Write-Host "=== AR-02 / GUARD process status ==="
$ar02 = Get-Process -Id 29356
$guard = Get-Process -Id 27756
if ($ar02) {
    Write-Host "AR-02 PID 29356: ALIVE (CPU=$([int]$ar02.CPU)s, WS=$([int]($ar02.WorkingSet/1MB))MB)"
} else {
    Write-Host "AR-02 PID 29356: DEAD"
}
if ($guard) {
    Write-Host "GUARD PID 27756: ALIVE (CPU=$([int]$guard.CPU)s, WS=$([int]($guard.WorkingSet/1MB))MB)"
} else {
    Write-Host "GUARD PID 27756: DEAD"
}

Write-Host ""
Write-Host "=== AR-02 log file size ==="
$f = 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\lomo_loco_ar02_full\ar02_run_20260719_203451.log'
Get-Item $f | Select-Object Length, LastWriteTime

Write-Host ""
Write-Host "=== GUARD log file size ==="
$g = 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\guard_wps_20260719_203451.log'
if (Test-Path $g) {
    Get-Item $g | Select-Object Length, LastWriteTime
    Write-Host "GUARD log content (last 20 lines):"
    Get-Content $g -Tail 20 -Encoding UTF8
} else {
    Write-Host "GUARD log not found"
}
