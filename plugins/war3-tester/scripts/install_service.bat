@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul

:: ========================================
:: War3Tester WinProxy - Windows Service Installer (NSSM)
:: 一键安装 win_proxy.py 为 Windows 服务（开机自启/无UAC/崩溃重启）
:: ========================================

:: === UAC 自动提权 ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] 需要管理员权限，正在提权...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: === 定位插件根（脚本在 scripts/，上级是插件根）===
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "PLUGIN_ROOT=%%~fI"
set "NSSM=%PLUGIN_ROOT%\bin\nssm.exe"
set "WIN_PROXY=%PLUGIN_ROOT%\win_proxy.py"
set "LOGS_DIR=%PLUGIN_ROOT%\logs"
set "SERVICE_NAME=War3TesterWinProxy"

:: === 检查 nssm.exe ===
if not exist "%NSSM%" (
    echo [ERROR] 未找到 nssm.exe: %NSSM%
    echo         请从 https://nssm.cc/download 下载 nssm-2.24.zip，
    echo         解压取 win64\nssm.exe 放到 %PLUGIN_ROOT%\bin\
    pause
    exit /b 1
)

:: === 检查 win_proxy.py ===
if not exist "%WIN_PROXY%" (
    echo [ERROR] 未找到 win_proxy.py: %WIN_PROXY%
    pause
    exit /b 1
)

:: === 探测 python.exe（PYTHON 环境变量 → where python → py -3）===
set "PYTHON_EXE=%PYTHON%"
if not defined PYTHON_EXE (
    where python >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%P in ('where python') do set "PYTHON_EXE=%%P"
    ) else (
        where py >nul 2>&1
        if !errorlevel! equ 0 (
            for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%P"
        )
    )
)
if not defined PYTHON_EXE (
    echo [ERROR] 未找到 python.exe。请装 Python，或设 PYTHON 环境变量指向 python.exe
    pause
    exit /b 1
)
echo [INFO] Python: %PYTHON_EXE%

:: === 创建日志目录 ===
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: === 若服务已存在，先移除 ===
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] 服务已存在，先停止并移除旧服务...
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM%" remove %SERVICE_NAME% confirm >nul 2>&1
)

:: === NSSM 安装与配置 ===
echo [INFO] 安装服务 %SERVICE_NAME% ...
"%NSSM%" install %SERVICE_NAME% "%PYTHON_EXE%" "win_proxy.py start"
"%NSSM%" set %SERVICE_NAME% AppDirectory "%PLUGIN_ROOT%"
"%NSSM%" set %SERVICE_NAME% Start SERVICE_AUTO_START
"%NSSM%" set %SERVICE_NAME% AppStdout "%LOGS_DIR%\win_proxy.out.log"
"%NSSM%" set %SERVICE_NAME% AppStderr "%LOGS_DIR%\win_proxy.err.log"
"%NSSM%" set %SERVICE_NAME% AppRotateFiles 1
"%NSSM%" set %SERVICE_NAME% AppRotateBytes 1048576
"%NSSM%" set %SERVICE_NAME% AppExit Default Restart
"%NSSM%" set %SERVICE_NAME% DisplayName "War3 Tester Windows Proxy"
"%NSSM%" set %SERVICE_NAME% Description "War3 Tester Windows Proxy (TCP 8767, NSSM-managed)"

:: === 启动 ===
echo [INFO] 启动服务...
"%NSSM%" start %SERVICE_NAME%

:: === 验证 ===
timeout /t 2 >nul
sc query %SERVICE_NAME% | findstr "STATE"
echo.
echo [OK] 服务安装完成: %SERVICE_NAME%
echo      查询状态: sc query %SERVICE_NAME%
echo      启动/停止: nssm start/stop %SERVICE_NAME%
echo      卸载: 运行 uninstall_service.bat
echo.
pause
