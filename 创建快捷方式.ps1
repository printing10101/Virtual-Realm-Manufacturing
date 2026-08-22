$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\灵境制造.lnk")
$Shortcut.TargetPath = "$env:USERPROFILE\Desktop\灵境制造（上线版）\灵境制造.bat"
$Shortcut.WorkingDirectory = "$env:USERPROFILE\Desktop\灵境制造（上线版）"
$Shortcut.Description = "Lingjing - Manufacturing AI Platform"
$Shortcut.Save()
Write-Host "Desktop shortcut created: Lingjing.lnk"
