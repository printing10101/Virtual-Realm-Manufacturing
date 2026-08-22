@echo off
cd /d "%~dp0"

> "%temp%\create_lnk.vbs" echo Set WshShell = CreateObject("WScript.Shell")
>> "%temp%\create_lnk.vbs" echo Set oLink = WshShell.CreateShortcut("%USERPROFILE%\Desktop\灵境制造.lnk")
>> "%temp%\create_lnk.vbs" echo oLink.TargetPath = "%~dp0灵境制造.bat"
>> "%temp%\create_lnk.vbs" echo oLink.WorkingDirectory = "%~dp0"
>> "%temp%\create_lnk.vbs" echo oLink.Description = "Lingjing - Manufacturing AI Platform"
>> "%temp%\create_lnk.vbs" echo oLink.Save()
cscript //nologo "%temp%\create_lnk.vbs"
del "%temp%\create_lnk.vbs"
echo.
echo [Created] Desktop shortcut: 灵境制造.lnk
echo.
pause
