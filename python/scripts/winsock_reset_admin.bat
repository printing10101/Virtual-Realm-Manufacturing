@echo off
REM ============================================================
REM WinSock Reset Script - Run as Administrator
REM ============================================================
REM Right-click this file and select "Run as administrator"
REM ============================================================

echo ============================================================
echo  WinSock Reset Script
echo ============================================================
echo.

REM Check if running as admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script requires administrator privileges.
    echo.
    echo Please right-click this file and select "Run as administrator"
    echo.
    pause
    exit /b 1
)

echo Running as administrator: YES
echo.
echo Executing: netsh winsock reset
echo ------------------------------------------------------------
netsh winsock reset
echo ------------------------------------------------------------
echo Exit code: %errorlevel%
echo.
echo ============================================================
echo  WinSock reset completed.
echo ============================================================
echo.
echo IMPORTANT: You MUST restart your computer for the changes
echo to take effect. After restart, network should work.
echo.
echo Press any key to close this window...
pause >nul
