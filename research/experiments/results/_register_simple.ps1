$ErrorActionPreference = "Stop"

# 路径常量
$taskName = "AblationV4"
$cmdPath = "c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results\_run_ablation_v4.cmd"
$wd = "c:\Users\Lenovo\Desktop\灵境制造（上线版）"

# 删除旧任务
try { Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction Stop | Out-Null } catch { Write-Host "old task not exist (ok)" }

# 创建任务
$action = New-ScheduledTaskAction -Execute "cmd.exe" -Argument "/c `"$cmdPath`"" -WorkingDirectory $wd
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description "ablation v4" -Force | Out-Null
Write-Host "Task registered: $taskName"

# 启动
Start-ScheduledTask -TaskName $taskName
Write-Host "Task started"

# 等待并检查
Start-Sleep -Seconds 5
$info = Get-ScheduledTask -TaskName $taskName | Get-ScheduledTaskInfo
Write-Host "LastRunTime: $($info.LastRunTime)"
Write-Host "LastTaskResult: 0x$('{0:X}' -f $info.LastTaskResult)"
