# WinSock 诊断脚本：分析 catalog 状态、对比 Before_Reset 备份、检测未重启状态
# 输出明确结论，不修改任何系统状态

$ErrorActionPreference = "SilentlyContinue"

Write-Host "=== [1] WinSock Catalog 顶层键 ==="
$base = "HKLM:\SYSTEM\CurrentControlSet\Services\WinSock2\Parameters"
Get-ChildItem $base | Select-Object -ExpandProperty PSChildName

Write-Host ""
Write-Host "=== [2] Protocol_Catalog9 Catalog_Entries 数量 ==="
$pc9 = "$base\Protocol_Catalog9\Catalog_Entries"
if (Test-Path $pc9) {
    $entries = Get-ChildItem $pc9
    Write-Host ("Protocol_Catalog9 条目数: " + $entries.Count)
    Write-Host "前 5 条 PackedCatalogItem 摘要:"
    $entries | Select-Object -First 5 | ForEach-Object {
        $name = $_.PSChildName
        $item = Get-ItemProperty $_.PSPath
        $packed = $item.PackedCatalogItem
        if ($packed) {
            # PackedCatalogItem 是二进制，前 64 字节含 dll 路径（UTF-16）
            $bytes = [System.Text.Encoding]::Unicode.GetString($packed[0..127])
            $clean = ($bytes -replace "[`\0]", "").Trim()
            Write-Host ("  " + $name + " -> " + $clean)
        } else {
            Write-Host ("  " + $name + " -> (no PackedCatalogItem)")
        }
    }
} else {
    Write-Host "Protocol_Catalog9\Catalog_Entries 不存在"
}

Write-Host ""
Write-Host "=== [3] Protocol_Catalog_Before_Reset (备份) 数量 ==="
$pcbr = "$base\Protocol_Catalog_Before_Reset\Catalog_Entries"
if (Test-Path $pcbr) {
    $bkEntries = Get-ChildItem $pcbr
    Write-Host ("Before_Reset 条目数: " + $bkEntries.Count)
} else {
    Write-Host "Protocol_Catalog_Before_Reset\Catalog_Entries 不存在"
}

Write-Host ""
Write-Host "=== [4] NameSpace_Catalog5 ==="
$ns5 = "$base\NameSpace_Catalog5\Catalog_Entries"
if (Test-Path $ns5) {
    $nsEntries = Get-ChildItem $ns5
    Write-Host ("NameSpace 条目数: " + $nsEntries.Count)
    $nsEntries | ForEach-Object {
        $item = Get-ItemProperty $_.PSPath
        Write-Host ("  " + $_.PSChildName + " -> " + $item.DisplayString + " (" + $item.LibraryPath + ")")
    }
}

Write-Host ""
Write-Host "=== [5] 上次启动时间（判断 WinSock reset 后是否重启）==="
$boot = (Get-CimInstance Win32_OperatingSystem).LastBootUpTime
Write-Host ("上次启动: " + $boot)
$now = Get-Date
$uptime = $now - $boot
Write-Host ("运行时长: " + [int]$uptime.TotalHours + " 小时 " + [int]$uptime.Minutes + " 分钟")

Write-Host ""
Write-Host "=== [6] Protocol_Catalog9 vs Before_Reset 对比 ==="
if ((Test-Path $pc9) -and (Test-Path $pcbr)) {
    $cur = Get-ChildItem $pc9 | Select-Object -ExpandProperty PSChildName | Sort-Object
    $old = Get-ChildItem $pcbr | Select-Object -ExpandProperty PSChildName | Sort-Object
    if (Compare-Object $cur $old -SyncWindow 0) {
        Write-Host "DIFF: 当前 catalog 与备份不一致 — 说明 reset 后未重启或 reset 未完成"
    } else {
        Write-Host "SAME: 当前 catalog 与备份完全一致"
    }
}

Write-Host ""
Write-Host "=== [7] WinHTTP 直接测试 (WinHttpOpenRequest) ==="
try {
    $sig = @"
using System;
using System.Runtime.InteropServices;
public class WinHttp {
    [DllImport("winhttp.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr WinHttpOpen(string userAgent, int accessType, string proxy, string bypass, int flags);
    [DllImport("winhttp.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr WinHttpConnect(IntPtr hSession, string server, short port, int reserved);
    [DllImport("winhttp.dll", SetLastError=true, CharSet=CharSet.Unicode)]
    public static extern IntPtr WinHttpOpenRequest(IntPtr hConnect, string verb, string objectName, string version, string referer, string accept, int flags);
    [DllImport("winhttp.dll", SetLastError=true)]
    public static extern bool WinHttpCloseHandle(IntPtr hInternet);
}
"@
    Add-Type -TypeDefinition $sig -Language CSharp 2>$null
    $hSession = [WinHttp]::WinHttpOpen("diag", 0, $null, $null, 0)
    Write-Host ("WinHttpOpen 句柄: " + $hSession + " LastError: " + [System.Runtime.InteropServices.Marshal]::GetLastWin32Error())
    if ($hSession -ne [IntPtr]::Zero) {
        $hConn = [WinHttp]::WinHttpConnect($hSession, "pypi.org", 443, 0)
        Write-Host ("WinHttpConnect 句柄: " + $hConn + " LastError: " + [System.Runtime.InteropServices.Marshal]::GetLastWin32Error())
        if ($hConn -ne [IntPtr]::Zero) {
            $hReq = [WinHttp]::WinHttpOpenRequest($hConn, "GET", "/simple/", "HTTP/1.1", $null, $null, 0x00800000)
            Write-Host ("WinHttpOpenRequest 句柄: " + $hReq + " LastError: " + [System.Runtime.InteropServices.Marshal]::GetLastWin32Error())
            [WinHttp]::WinHttpCloseHandle($hReq) | Out-Null
        }
        [WinHttp]::WinHttpCloseHandle($hConn) | Out-Null
    }
    [WinHttp]::WinHttpCloseHandle($hSession) | Out-Null
} catch {
    Write-Host ("WinHTTP test exception: " + $_.Exception.Message)
}

Write-Host ""
Write-Host "=== [8] mswsock.dll 完整性 ==="
$dll = Get-Item "C:\Windows\System32\mswsock.dll" -ErrorAction SilentlyContinue
if ($dll) {
    Write-Host ("路径: " + $dll.FullName)
    Write-Host ("大小: " + $dll.Length + " bytes")
    Write-Host ("修改时间: " + $dll.LastWriteTime)
    $ver = (Get-ItemProperty $dll.FullName).VersionInfo
    Write-Host ("版本: " + $ver.FileVersion)
    Write-Host ("产品: " + $ver.ProductName)
}

Write-Host ""
Write-Host "=== [9] 关键系统文件 SFC 状态 ==="
$sfcLog = "C:\Windows\Logs\CBS\CBS.log"
if (Test-Path $sfcLog) {
    $recent = Get-Content $sfcLog -Tail 50 | Select-String -Pattern "WinSock|mswsock|winsock" -SimpleMatch
    if ($recent) {
        Write-Host "CBS.log 中含 WinSock 相关条目（最后 50 行）:"
        $recent | ForEach-Object { Write-Host ("  " + $_.Line) }
    } else {
        Write-Host "CBS.log 最后 50 行无 WinSock 相关条目"
    }
}

Write-Host ""
Write-Host "=== [10] 最近 system 事件日志中的 WinSock 错误 ==="
Get-WinEvent -FilterHashtable @{LogName='System'; Level=1,2,3; StartTime=(Get-Date).AddDays(-7)} -MaxEvents 200 -ErrorAction SilentlyContinue |
    Where-Object { $_.Message -match "WinSock|winsock|10038|socket" } |
    Select-Object -First 10 TimeCreated, Id, LevelDisplayName, ProviderName, Message |
    Format-List

Write-Host ""
Write-Host "=== 诊断完成 ==="
