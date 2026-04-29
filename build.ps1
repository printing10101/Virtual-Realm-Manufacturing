$env:PATH = "$env:USERPROFILE\.cargo\bin;$env:PATH"
Set-Location "C:\Users\Lenovo\Desktop\灵境制造（上线版）\src-tauri"
Remove-Item -Recurse -Force target -ErrorAction SilentlyContinue
cargo build 2>&1 | Tee-Object -FilePath "C:\Users\Lenovo\Desktop\灵境制造（上线版）\build.log"
