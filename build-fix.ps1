Set-Location "c:\Users\Lenovo\Desktop\灵境制造（上线版）"

Write-Host "Building frontend..."
pnpm build
if ($LASTEXITCODE -ne 0) { Write-Error "Frontend build failed"; exit 1 }
Write-Host "Frontend build done."

Write-Host "Building Rust backend with clean target dir..."
$env:CARGO_TARGET_DIR = "C:\Users\Lenovo\Desktop\lingjing-build"
Set-Location "src-tauri"

cargo build --release
if ($LASTEXITCODE -ne 0) { Write-Error "Rust build failed"; exit 1 }

Write-Host "Build successful!"
$exePath = "C:\Users\Lenovo\Desktop\lingjing-build\release\lingjing-v4.exe"
$targetPath = "..\src-tauri\target\release\lingjing-v4.exe"
if (Test-Path $exePath) {
    New-Item -ItemType Directory -Force -Path (Split-Path $targetPath -Parent) | Out-Null
    Copy-Item $exePath $targetPath -Force
    Write-Host "Done! exe at: $targetPath"
} else {
    Write-Error "exe not found at $exePath"
}
