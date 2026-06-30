@echo off
setlocal
chcp 65001 >nul

:: ========================================
:: War3Tester WinProxy - Windows Service Uninstaller
:: 一键卸载 win_proxy 服务
:: ========================================

:: === UAC 自动提权 ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 需要管理员权限，正在提权...
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
    echo [INFO] 服务 %SERVICE_NAME% 不存在，无需卸载
    pause
    exit /b 0
)

echo [INFO] 停止服务...
if exist "%NSSM%" (
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    echo [INFO] 移除服务...
    "%NSSM%" remove %SERVICE_NAME% confirm
) else (
    :: nssm.exe 缺失，用 sc 兜底
    sc stop %SERVICE_NAME% >nul 2>&1
    sc delete %SERVICE_NAME%
)

echo.
echo [OK] 服务 %SERVICE_NAME% 已卸载
echo.
pause
