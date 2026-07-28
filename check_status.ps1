$ErrorActionPreference = "SilentlyContinue"
$end = Get-Date
$start = $end.AddHours(-10)
Write-Host "=== 系统 Error/Warning 事件 ($start ~ $end) ==="
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$start; Level=1,2,3} -MaxEvents 40 |
    Select-Object TimeCreated, Id, ProviderName, LevelDisplayName, @{N='Msg';E={($_.Message -split "`n")[0]}} |
    Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "=== 关机/重启事件 (6005/6006/6008/1074/41) ==="
Get-WinEvent -FilterHashtable @{LogName='System'; StartTime=$start} -MaxEvents 200 |
    Where-Object { $_.Id -in 6005,6006,6008,1074,41,109 } |
    Select-Object TimeCreated, Id, ProviderName, @{N='Msg';E={($_.Message -split "`n")[0]}} |
    Format-Table -AutoSize -Wrap

Write-Host ""
Write-Host "=== 当前所有 python/pythonw 进程 ==="
Get-Process python,pythonw -ErrorAction SilentlyContinue | Select-Object Id, ProcessName, StartTime, @{N='CPU';E={[int]$_.CPU}} | Format-Table -AutoSize

Write-Host ""
Write-Host "=== 系统启动时间 ==="
$os = Get-CimInstance Win32_OperatingSystem
Write-Host "LastBoot: $($os.LastBootUpTime)"
Write-Host "Now:      $(Get-Date)"
Write-Host "Uptime:   $((Get-Date) - $os.LastBootUpTime)"
