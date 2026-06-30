@echo off
setlocal enabledelayedexpansion

:: ========================================
:: War3Tester WinProxy - Windows Service Installer (NSSM)
:: Install win_proxy.py as a Windows service (auto-start, no UAC, auto-restart)
:: ========================================

:: === UAC elevation ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Administrator required, elevating...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: === Locate plugin root (script in scripts/, parent is plugin root) ===
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "PLUGIN_ROOT=%%~fI"
set "NSSM=%PLUGIN_ROOT%\bin\nssm.exe"
set "WIN_PROXY=%PLUGIN_ROOT%\win_proxy.py"
set "LOGS_DIR=%PLUGIN_ROOT%\logs"
set "SERVICE_NAME=War3TesterWinProxy"

:: === Check nssm.exe ===
if not exist "%NSSM%" (
    echo [ERROR] nssm.exe not found: %NSSM%
    echo         Download nssm-2.24.zip from https://nssm.cc/download,
    echo         extract win64\nssm.exe to %PLUGIN_ROOT%\bin\
    pause
    exit /b 1
)

:: === Check win_proxy.py ===
if not exist "%WIN_PROXY%" (
    echo [ERROR] win_proxy.py not found: %WIN_PROXY%
    pause
    exit /b 1
)

:: === Detect python.exe (PYTHON env -^> where python -^> py -3) ===
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
    echo [ERROR] python.exe not found. Install Python, or set PYTHON env var to python.exe path.
    pause
    exit /b 1
)
echo [INFO] Python: %PYTHON_EXE%

:: === Create logs dir ===
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"

:: === Remove existing service if present (idempotent) ===
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Service already exists, removing old instance...
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM%" remove %SERVICE_NAME% confirm >nul 2>&1
)

:: === NSSM install and configure ===
echo [INFO] Installing service %SERVICE_NAME% ...
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

:: === Start ===
echo [INFO] Starting service...
"%NSSM%" start %SERVICE_NAME%

:: === Verify ===
timeout /t 2 >nul
sc query %SERVICE_NAME% | findstr "STATE"
echo.
echo [OK] Service installed: %SERVICE_NAME%
echo      Status:     sc query %SERVICE_NAME%
echo      Start/Stop: nssm start/stop %SERVICE_NAME%
echo      Uninstall:  run uninstall_service.bat
echo.
pause
