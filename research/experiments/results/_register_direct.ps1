$ErrorActionPreference = "Stop"

# 删除旧任务
try { Unregister-ScheduledTask -TaskName "AblationV4" -Confirm:$false -ErrorAction Stop | Out-Null } catch { Write-Host "old task not exist (ok)" }

# 直接调用 python.exe（无 cmd wrapper）
$pyExe = "C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe"
$scriptPath = "c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\ablation_experiment.py"
$wd = "c:\Users\Lenovo\Desktop\灵境制造（上线版）"

# 参数以空格分隔的字符串
$arguments = "-u `"$scriptPath`" --dataset synthetic --ablations Full A1 A2 A3 A4_lam0.01 A4_lam0.05 A4_lam0.1 A4_lam0.5 A4_lam1.0 A6_fixed0.0 A6_fixed0.25 A6_fixed0.5 A6_fixed0.75 A6_fixed1.0 A7_MLP A7_CNN --stage1_epochs 30 --stage2_epochs 60 --output_dir `"research\papers\论文相关\脚本\results\ablation`" --resume"

$action = New-ScheduledTaskAction -Execute $pyExe -Argument $arguments -WorkingDirectory $wd
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -DontStopOnIdleEnd -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 5)

Register-ScheduledTask -TaskName "AblationV4" -Action $action -Trigger $trigger -Settings $settings -Description "ablation v4 resume" -Force | Out-Null
Write-Host "Task registered"

Start-ScheduledTask -TaskName "AblationV4"
Write-Host "Task started"

Start-Sleep -Seconds 8
$info = Get-ScheduledTask -TaskName "AblationV4" | Get-ScheduledTaskInfo
Write-Host "LastRunTime: $($info.LastRunTime)"
Write-Host "LastTaskResult: 0x$('{0:X}' -f $info.LastTaskResult)"

# 检查 python 进程
$proc = Get-Process -Name python -ErrorAction SilentlyContinue
if ($proc) {
    Write-Host "Python process running:"
    $proc | Select-Object Id, CPU, WorkingSet64 | Format-Table
} else {
    Write-Host "No python process!"
}
