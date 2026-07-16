# 以管理员身份执行 netsh winsock reset，输出重定向到文件
$logFile = "C:\Users\Lenovo\Desktop\灵境制造（上线版）\python\scripts\winsock_reset_result.log"

"=== netsh winsock reset 执行日志 ===" | Out-File -FilePath $logFile -Encoding UTF8
"时间: $(Get-Date)" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"用户: $env:USERNAME" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"管理员: $((New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator))" | Out-File -FilePath $logFile -Encoding UTF8 -Append

"" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"=== netsh winsock reset 输出 ===" | Out-File -FilePath $logFile -Encoding UTF8 -Append
$output = & netsh winsock reset 2>&1
$output | Out-File -FilePath $logFile -Encoding UTF8 -Append
"exit code: $LASTEXITCODE" | Out-File -FilePath $logFile -Encoding UTF8 -Append

"" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"=== 验证 catalog 变化 ===" | Out-File -FilePath $logFile -Encoding UTF8 -Append
$base = "HKLM:\SYSTEM\CurrentControlSet\Services\WinSock2\Parameters"
"Protocol_Catalog9 子键:" | Out-File -FilePath $logFile -Encoding UTF8 -Append
if (Test-Path "$base\Protocol_Catalog9\Catalog_Entries") {
    $count = (Get-ChildItem "$base\Protocol_Catalog9\Catalog_Entries").Count
    "  条目数: $count" | Out-File -FilePath $logFile -Encoding UTF8 -Append
}
"Protocol_Catalog_Before_Reset 子键:" | Out-File -FilePath $logFile -Encoding UTF8 -Append
if (Test-Path "$base\Protocol_Catalog_Before_Reset\Catalog_Entries") {
    $bcount = (Get-ChildItem "$base\Protocol_Catalog_Before_Reset\Catalog_Entries").Count
    "  条目数: $bcount" | Out-File -FilePath $logFile -Encoding UTF8 -Append
}

"" | Out-File -FilePath $logFile -Encoding UTF8 -Append
"=== 完成，需要重启系统 ===" | Out-File -FilePath $logFile -Encoding UTF8 -Append
