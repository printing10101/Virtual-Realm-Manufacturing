$wd = 'c:\Users\Lenovo\Desktop\灵境制造（上线版）'
$py = 'C:\Users\Lenovo\AppData\Local\Programs\Python\Python311\python.exe'
$script = Join-Path $wd 'research\papers\论文相关\脚本\ablation_experiment.py'
$ts = Get-Date -Format 'yyyyMMdd_HHmmss'
$log = Join-Path $wd "research\experiments\results\ablation_v4_${ts}.log"
$err = Join-Path $wd "research\experiments\results\ablation_v4_${ts}.err.log"
$pidFile = Join-Path $wd "research\experiments\results\ablation_v4_${ts}.pid"

$args = @(
    '-u', $script,
    '--dataset', 'synthetic',
    '--ablations', 'Full','A1','A2','A3',
    'A4_lam0.01','A4_lam0.05','A4_lam0.1','A4_lam0.5','A4_lam1.0',
    'A6_fixed0.0','A6_fixed0.25','A6_fixed0.5','A6_fixed0.75','A6_fixed1.0',
    'A7_MLP','A7_CNN',
    '--stage1_epochs', '50',
    '--stage2_epochs', '100',
    '--output_dir', 'research\papers\论文相关\脚本\results\ablation',
    '--fresh'
)

$p = Start-Process -FilePath $py -ArgumentList $args -WorkingDirectory $wd `
    -RedirectStandardOutput $log -RedirectStandardError $err `
    -PassThru -WindowStyle Hidden
$p.Id | Out-File -FilePath $pidFile -Encoding ascii
Write-Output ("PID=" + $p.Id)
Write-Output ("LOG=" + $log)
Write-Output ("ERR=" + $err)
