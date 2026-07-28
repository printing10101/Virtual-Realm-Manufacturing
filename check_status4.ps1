$ErrorActionPreference = "SilentlyContinue"
Write-Host "=== GUARD process detail ==="
Get-Process -Id 27756 | Select-Object Id, Name, StartTime, CPU, @{N='WS_MB';E={[int]($_.WorkingSet/1MB)}}, @{N='Threads';E={$_.Threads.Count}} | Format-List

Write-Host "=== GUARD log files in results dir ==="
Get-ChildItem 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\guard_wps_*' | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

Write-Host "=== AR-02 log file (raw path) ==="
$ar02log = 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\lomo_loco_ar02_full\ar02_run_20260719_203451.log'
if (Test-Path $ar02log) {
    $item = Get-Item $ar02log
    Write-Host "Size: $($item.Length) bytes, mtime: $($item.LastWriteTime)"
} else {
    Write-Host "AR-02 log not found!"
}

Write-Host ""
Write-Host "=== AR-02 results dir contents ==="
Get-ChildItem 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\lomo_loco_ar02_full' | Select-Object Name, Length, LastWriteTime | Format-Table -AutoSize

Write-Host ""
Write-Host "=== checkpoint status ==="
$ckpt = 'C:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\results\lomo_loco_ar02_full\lomo_ckpt_DL-LNN_physics_aware.json'
Get-Item $ckpt | Select-Object Length, LastWriteTime
