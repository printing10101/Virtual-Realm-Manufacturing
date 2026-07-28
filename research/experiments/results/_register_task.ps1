# 注册 Windows 任务计划程序（用户登录会话内运行，但不受应用关闭事件影响）
$taskName = "AblationV4"

# 删除已存在的同名任务
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action = New-ScheduledTaskAction `
    -Execute "cmd.exe" `
    -Argument '/c "c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\_run_ablation_v4.cmd"' `
    -WorkingDirectory "c:\Users\Lenovo\Desktop\灵境制造（上线版）"

$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(10)

$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

# 用当前用户（Lenovo），Interactive 级别（可访问 GPU）
$principal = New-ScheduledTaskPrincipal `
    -UserId "Lenovo" `
    -LogonType Interactive `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "ablation v4 resume - 2026-07-18" `
    -Force

Write-Host "Task registered: $taskName"
Write-Host "Starting task..."
Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 3
Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo | Select-Object LastRunTime, LastTaskResult, NumberOfMissedRuns
