@echo off
setlocal

:: ========================================
:: War3Tester WinProxy - Windows Service Uninstaller
:: Remove the win_proxy service
:: ========================================

:: === UAC elevation ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Administrator required, elevating...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "PLUGIN_ROOT=%%~fI"
set "NSSM=%PLUGIN_ROOT%\bin\nssm.exe"
set "SERVICE_NAME=War3TesterWinProxy"

sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Service %SERVICE_NAME% does not exist, nothing to uninstall.
    pause
    exit /b 0
)

echo [INFO] Stopping service...
if exist "%NSSM%" (
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    echo [INFO] Removing service...
    "%NSSM%" remove %SERVICE_NAME% confirm
) else (
    :: Fallback to sc if nssm.exe is missing
    sc stop %SERVICE_NAME% >nul 2>&1
    sc delete %SERVICE_NAME%
)

echo.
echo [OK] Service %SERVICE_NAME% uninstalled.
echo.
pause
