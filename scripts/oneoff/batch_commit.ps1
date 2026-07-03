# PowerShell script for batch commits by functional modules
# Commit Batch 1: Infrastructure & Build Configuration

Write-Host "=== Batch 1: Infrastructure & Build Configuration ===" -ForegroundColor Cyan

git reset

# Infrastructure files
git add VERSION package.json vite.config.ts vitest.config.ts
git add Dockerfile .dockerignore .pre-commit-config.yaml requirements.txt
git add src-tauri/Cargo.toml src-tauri/Cargo.lock src-tauri/tauri.conf.json
git add docs/api/openapi.json

git diff --cached --stat
Write-Host "`nReady for commit. Run: git commit -m '...'" -ForegroundColor Green
