# Cleanup scripts for workspace architecture
# Run this in PowerShell

# Delete src-frontend-only directory
if (Test-Path "src-frontend-only") {
    Remove-Item -Path "src-frontend-only" -Recurse -Force
    Write-Host "✓ Deleted src-frontend-only"
}

# Delete .dsh-workspaces directory  
if (Test-Path ".dsh-workspaces") {
    Remove-Item -Path ".dsh-workspaces" -Recurse -Force
    Write-Host "✓ Deleted .dsh-workspaces"
}

# Show cleanup complete message
Write-Host "`n=== Cleanup Complete ===" -ForegroundColor Green
Write-Host "All workspace architecture files have been deleted." -ForegroundColor Green
Write-Host "`nNote: You need to empty Recycle Bin manually through Windows File Explorer." -ForegroundColor Yellow
