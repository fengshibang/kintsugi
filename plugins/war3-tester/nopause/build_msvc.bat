@echo off
cd /d "%~dp0"
call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars32.bat" >nul
if errorlevel 1 (echo VCVARS FAILED & exit /b 1)
cl /LD /O2 /MT /nologo nopause.c /link user32.lib /out:nopause.dll
echo CL_EXIT=%errorlevel%
