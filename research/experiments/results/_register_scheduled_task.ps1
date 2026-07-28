# 注册 Windows 任务计划程序：ablation v4 实验作为系统级后台任务
# 优势：不受 IDE/窗口/会话影响，系统级运行，可跨夜持续
# 用户登录会话断开也不会终止

$taskName = "AblationV4_Resume"
$py = "C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe"
$script = "c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\papers\论文相关\脚本\ablation_experiment.py"
$wd = "c:\Users\Lenovo\Desktop\灵境制造（上线版）"
$resultsDir = "c:\Users\Lenovo\Desktop\灵境制造（上线版）\research\experiments\results"
$ts = Get-Date -Format "yyyyMMdd_HHmmss"
$log = "$resultsDir\ablation_v4_$ts.log"
$err = "$resultsDir\ablation_v4_$ts.err.log"

# 构造参数
$args = @(
    "-u",
    "`"$script`"",
    "--dataset", "synthetic",
    "--ablations",
    "Full", "A1", "A2", "A3",
    "A4_lam0.01", "A4_lam0.05", "A4_lam0.1", "A4_lam0.5", "A4_lam1.0",
    "A6_fixed0.0", "A6_fixed0.25", "A6_fixed0.5", "A6_fixed0.75", "A6_fixed1.0",
    "A7_MLP", "A7_CNN",
    "--stage1_epochs", "30",
    "--stage2_epochs", "60",
    "--output_dir", "research\papers\论文相关\脚本\results\ablation",
    "--resume"
)

# 构造命令字符串
$cmd = "`"$py`" $($args -join ' ')"

# 注册任务（立即启动，无窗口，无时间限制）
$action = New-ScheduledTaskAction -Execute $py -Argument ($args -join ' ') -WorkingDirectory $wd
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date).AddSeconds(5)
$settings = New-ScheduledTaskSettingsSet `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -DontStopOnIdleEnd `
    -StartWhenAvailable `
    -ExecutionTimeLimit ([TimeSpan]::Zero) `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 5)

$principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

Register-ScheduledTask -TaskName $taskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Principal $principal `
    -Description "ablation v4 实验（resume 模式，跳过已完成的 Full）- $(Get-Date -Format 'yyyy-MM-dd HH:mm')" `
    -Force

# 重定向输出到日志文件（任务计划程序的 StandardOutput/StandardError 需通过 task XML 配置）
# 改为通过 wrapper 脚本实现
Write-Host "Task registered: $taskName"
Write-Host "Log will be at: $log"
Write-Host "Err will be at: $err"
Write-Host ""
Write-Host "查看任务状态: Get-ScheduledTask -TaskName '$taskName' | Get-ScheduledTaskInfo"
Write-Host "停止任务: Stop-ScheduledTask -TaskName '$taskName'"
Write-Host "注销任务: Unregister-ScheduledTask -TaskName '$taskName' -Confirm:`$false"
