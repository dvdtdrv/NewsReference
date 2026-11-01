@echo off
rem Connects this PC to GitHub so it can read the outlets that block GitHub's servers.
rem You need a one-time code from GitHub (see the steps below). Run this file only once.
cd /d "%~dp0"
echo.
echo  1. In your browser, open:
echo     https://github.com/dvdtdrv/NewsReference/settings/actions/runners/new?arch=x64^&os=win
echo  2. Under "Configure", find the line that contains  --token  and copy the long code
echo     that comes right after it (only the code, nothing else).
echo.
set /p CODE=Paste the code here and press Enter:
if "%CODE%"=="" (echo No code entered. & pause & exit /b 1)
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0setup_runner.ps1" -Code "%CODE%"
echo.
pause
