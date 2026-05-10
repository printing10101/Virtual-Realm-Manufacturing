# Build script for lingjing-v4 Tauri application
$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Set-Location "$PSScriptRoot\src-tauri"
cargo build --release 2>&1 | Tee-Object -FilePath "$PSScriptRoot\build.log"
Write-Host "Build completed. Check build.log for details."
