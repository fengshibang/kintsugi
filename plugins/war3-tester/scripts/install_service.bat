@echo off
setlocal enabledelayedexpansion

:: ========================================
:: War3Tester WinProxy - Windows Service Installer (NSSM)
:: Install win_proxy.py as a Windows service (auto-start, no UAC, auto-restart)
::
:: Why copy to a local dir: Claude Code may cache the plugin under a WSL path
:: (\\wsl.localhost\...). Windows SCM cannot reliably load an exe from a WSL/UNC
:: path -> service fails to start ("network path not found"). So we copy
:: nssm.exe + win_proxy.py to %ProgramData%\War3Tester\ (local, service-accessible)
:: and point the service there.
:: ========================================

:: === UAC elevation ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Administrator required, elevating...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

:: === Locate plugin root (script in scripts/, parent is plugin root) ===
:: Source files. May live on WSL/UNC path - that's fine, we only READ them.
set "SCRIPT_DIR=%~dp0"
set "SCRIPT_DIR=%SCRIPT_DIR:~0,-1%"
for %%I in ("%SCRIPT_DIR%\..") do set "PLUGIN_ROOT=%%~fI"
set "SRC_NSSM=%PLUGIN_ROOT%\bin\nssm.exe"
set "SRC_WIN_PROXY=%PLUGIN_ROOT%\win_proxy.py"

:: === Local install dir (service-accessible, machine-wide) ===
set "INSTALL_DIR=%ProgramData%\War3Tester"
set "NSSM=%INSTALL_DIR%\nssm.exe"
set "WIN_PROXY=%INSTALL_DIR%\win_proxy.py"
set "LOGS_DIR=%INSTALL_DIR%\logs"
set "SERVICE_NAME=War3TesterWinProxy"

:: === Check source files exist ===
if not exist "%SRC_NSSM%" (
    echo [ERROR] Source nssm.exe not found: %SRC_NSSM%
    echo         Download nssm-2.24.zip from https://nssm.cc/download,
    echo         extract win64\nssm.exe to %PLUGIN_ROOT%\bin\
    pause
    exit /b 1
)
if not exist "%SRC_WIN_PROXY%" (
    echo [ERROR] Source win_proxy.py not found: %SRC_WIN_PROXY%
    pause
    exit /b 1
)

:: === Detect python.exe (PYTHON env -> where python -> py -3) ===
:: Skip Windows Store alias (WindowsApps\python.exe) - it's a redirect stub that
:: does NOT work under LocalSystem service account (no user session) -> service
:: fails to start (SERVICE_EXIT_CODE 3, empty stdout/stderr).
set "PYTHON_EXE=%PYTHON%"
if not defined PYTHON_EXE (
    for /f "delims=" %%P in ('where python 2^>nul') do (
        echo %%P | findstr /I "WindowsApps" >nul || set "PYTHON_EXE=%%P"
    )
)
if not defined PYTHON_EXE (
    where py >nul 2>&1
    if !errorlevel! equ 0 (
        for /f "delims=" %%P in ('py -3 -c "import sys; print(sys.executable)"') do set "PYTHON_EXE=%%P"
    )
)
if not defined PYTHON_EXE (
    echo [ERROR] python.exe not found. Install Python, or set PYTHON env var to python.exe path.
    pause
    exit /b 1
)
echo [INFO] Python: %PYTHON_EXE%

:: === Copy nssm.exe + win_proxy.py to local install dir ===
echo [INFO] Installing files to %INSTALL_DIR% ...
if not exist "%INSTALL_DIR%" mkdir "%INSTALL_DIR%"
if not exist "%LOGS_DIR%" mkdir "%LOGS_DIR%"
copy /Y "%SRC_NSSM%" "%NSSM%" >nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to copy nssm.exe to %INSTALL_DIR%
    pause
    exit /b 1
)
copy /Y "%SRC_WIN_PROXY%" "%WIN_PROXY%" >nul
if %errorlevel% neq 0 (
    echo [ERROR] Failed to copy win_proxy.py to %INSTALL_DIR%
    pause
    exit /b 1
)
echo [OK] Files copied to %INSTALL_DIR%

:: === Remove existing service if present (idempotent) ===
sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% equ 0 (
    echo [INFO] Service already exists, removing old instance...
    "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
    "%NSSM%" remove %SERVICE_NAME% confirm >nul 2>&1
    :: If service was DISABLED from prior failures, remove may need a moment
    timeout /t 1 >nul
)

:: === NSSM install and configure (all paths local) ===
echo [INFO] Installing service %SERVICE_NAME% ...
:: nssm install <svc> <exe> [args...]: script name and its args must be SEPARATE
:: args (quoted as one string "win_proxy.py start" -> python sees a single filename
:: with a space -> file not found -> service fails to start). Split them.
"%NSSM%" install %SERVICE_NAME% "%PYTHON_EXE%" "win_proxy.py" "start"
:: Belt-and-suspenders: explicitly set AppParameters too
"%NSSM%" set %SERVICE_NAME% AppParameters "win_proxy.py start"
"%NSSM%" set %SERVICE_NAME% AppDirectory "%INSTALL_DIR%"
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
echo      Install dir: %INSTALL_DIR%
echo      Logs:        %LOGS_DIR%
echo      Status:      sc query %SERVICE_NAME%
echo      Start/Stop:  nssm start/stop %SERVICE_NAME%
echo      Uninstall:   run uninstall_service.bat
echo.
pause
