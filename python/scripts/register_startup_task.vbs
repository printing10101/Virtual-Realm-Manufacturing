' Register a one-time startup task to run post_reboot_recovery.py after reboot
' This is a backup in case the user forgets to double-click the .bat file

Option Explicit

Dim shell, startupPath, shortcutPath, fso, wshShell

Set wshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
Set shell = CreateObject("WScript.Shell")

' Get the Startup folder path
startupPath = wshShell.SpecialFolders("Startup")
shortcutPath = startupPath & "\post_reboot_recovery.lnk"

' Create a shortcut that runs the recovery .bat file
Dim shortcut
Set shortcut = wshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = "C:\Users\Lenovo\Desktop\重启后运行此文件.bat"
shortcut.WorkingDirectory = "C:\Users\Lenovo\Desktop"
shortcut.WindowStyle = 1
shortcut.Description = "Post-reboot WinSock recovery + torch install"
shortcut.Save

WScript.Echo "Startup shortcut created: " & shortcutPath
WScript.Echo "After reboot, the recovery script will run automatically."
WScript.Echo "The shortcut will be auto-deleted after successful run."
