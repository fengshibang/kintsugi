@echo off
setlocal

:: ========================================
:: War3Tester WinProxy - Windows Service Uninstaller
:: Remove the win_proxy service and clean up the local install dir.
::
:: Uses the LOCAL install dir (%ProgramData%\War3Tester) for nssm.exe, so this
:: works even if the plugin cache (WSL path) is gone.
:: ========================================

:: === UAC elevation ===
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Administrator required, elevating...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

set "INSTALL_DIR=%ProgramData%\War3Tester"
set "NSSM=%INSTALL_DIR%\nssm.exe"
set "SERVICE_NAME=War3TesterWinProxy"

sc query %SERVICE_NAME% >nul 2>&1
if %errorlevel% neq 0 (
    echo [INFO] Service %SERVICE_NAME% does not exist, nothing to uninstall.
) else (
    echo [INFO] Stopping service...
    if exist "%NSSM%" (
        "%NSSM%" stop %SERVICE_NAME% >nul 2>&1
        echo [INFO] Removing service...
        "%NSSM%" remove %SERVICE_NAME% confirm
    ) else (
        :: Fallback to sc if local nssm.exe is missing
        sc stop %SERVICE_NAME% >nul 2>&1
        sc delete %SERVICE_NAME%
    )
)

:: === Clean up local install dir ===
if exist "%INSTALL_DIR%" (
    echo [INFO] Removing install dir %INSTALL_DIR% ...
    rmdir /S /Q "%INSTALL_DIR%"
    if exist "%INSTALL_DIR%" (
        echo [WARN] Could not fully remove %INSTALL_DIR% (files may be in use). Reboot and retry.
    ) else (
        echo [OK] Install dir removed.
    )
)

echo.
echo [OK] Uninstall complete.
echo.
pause
