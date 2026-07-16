# Trigger UAC elevation for netsh winsock reset (v2)
# ASCII-only, with countdown and retry

Write-Host "=================================================="
Write-Host " UAC ELEVATION FOR netsh winsock reset"
Write-Host "=================================================="
Write-Host ""
Write-Host "IMPORTANT: A UAC prompt will appear on screen."
Write-Host "Please click YES to authorize the admin elevation."
Write-Host "If you click NO, the fix will fail."
Write-Host ""
Write-Host "Starting in 3 seconds..."
Start-Sleep -Seconds 1
Write-Host "3..."
Start-Sleep -Seconds 1
Write-Host "2..."
Start-Sleep -Seconds 1
Write-Host "1..."
Start-Sleep -Seconds 1
Write-Host "Triggering UAC now!"
Write-Host ""

$maxRetries = 3
$success = $false

for ($i = 1; $i -le $maxRetries; $i++) {
    Write-Host ("=== Attempt " + $i + " of " + $maxRetries + " ===")
    try {
        $proc = Start-Process -FilePath "netsh.exe" -ArgumentList "winsock", "reset" -Verb RunAs -Wait -PassThru -ErrorAction Stop
        Write-Host ("ExitCode: " + $proc.ExitCode)
        if ($proc.ExitCode -eq 0) {
            Write-Host "netsh winsock reset executed successfully!"
            $success = $true
            break
        }
    } catch {
        $msg = $_.Exception.Message
        Write-Host ("UAC attempt " + $i + " failed: " + $msg)
    }

    if ($i -lt $maxRetries) {
        Write-Host "Retrying in 2 seconds... Please click YES on the UAC prompt."
        Start-Sleep -Seconds 2
    }
}

Write-Host ""
Write-Host "=== Check catalog changes ==="
$base = "HKLM:\SYSTEM\CurrentControlSet\Services\WinSock2\Parameters"
$curCount = 0
$brcount = 0
if (Test-Path "$base\Protocol_Catalog9\Catalog_Entries") {
    $curCount = (Get-ChildItem "$base\Protocol_Catalog9\Catalog_Entries").Count
    Write-Host ("Protocol_Catalog9 entries: " + $curCount)
}
if (Test-Path "$base\Protocol_Catalog_Before_Reset\Catalog_Entries") {
    $brcount = (Get-ChildItem "$base\Protocol_Catalog_Before_Reset\Catalog_Entries").Count
    Write-Host ("Protocol_Catalog_Before_Reset entries: " + $brcount)
}

Write-Host ""
if ($success) {
    Write-Host "=== SUCCESS: WinSock reset completed ==="
    Write-Host "NEXT STEP: You MUST restart the system for the reset to take effect."
    Write-Host "After restart, run the verification script."
} else {
    Write-Host "=== FAILED: All UAC attempts were cancelled ==="
    Write-Host "Manual alternative:"
    Write-Host "  1. Right-click Start button"
    Write-Host "  2. Select 'Windows PowerShell (Admin)' or 'Terminal (Admin)'"
    Write-Host "  3. Run: netsh winsock reset"
    Write-Host "  4. Restart the system"
}
