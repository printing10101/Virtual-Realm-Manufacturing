# Trigger UAC elevation to run netsh winsock reset
# Uses ASCII-only to avoid encoding issues

Write-Host "=== UAC elevation for netsh winsock reset ==="
Write-Host "A UAC prompt will appear. Please click YES to authorize."
Write-Host ""

try {
    $proc = Start-Process -FilePath "netsh.exe" -ArgumentList "winsock", "reset" -Verb RunAs -Wait -PassThru -ErrorAction Stop
    Write-Host ("ExitCode: " + $proc.ExitCode)
    Write-Host "UAC process finished."
} catch {
    $msg = $_.Exception.Message
    Write-Host ("UAC launch failed: " + $msg)
    Write-Host "User may have cancelled the UAC prompt."
}

Write-Host ""
Write-Host "=== Check catalog changes ==="
$base = "HKLM:\SYSTEM\CurrentControlSet\Services\WinSock2\Parameters"
if (Test-Path "$base\Protocol_Catalog9\Catalog_Entries") {
    $count = (Get-ChildItem "$base\Protocol_Catalog9\Catalog_Entries").Count
    Write-Host ("Protocol_Catalog9 entries: " + $count)
}
if (Test-Path "$base\Protocol_Catalog_Before_Reset\Catalog_Entries") {
    $bcount = (Get-ChildItem "$base\Protocol_Catalog_Before_Reset\Catalog_Entries").Count
    Write-Host ("Protocol_Catalog_Before_Reset entries: " + $bcount)
}

Write-Host ""
Write-Host "=== Done ==="
