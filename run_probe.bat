@echo off
rem Double-click to look for ways to read BTA, Club Z and the other missing outlets.
cd /d "%~dp0"
set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
set PYTHONIOENCODING=utf-8
echo Probing missing outlets slowly (a few minutes)...
"%PY%" probe_missing.py
echo.
echo Done. Results are in probe_report.txt
pause
