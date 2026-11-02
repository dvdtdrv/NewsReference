@echo off
rem Starts the runner (the program that reads the blocked outlets for the site) in the background,
rem with no window. It also starts by itself at every login. To stop it, use stop_runner.bat.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start_runner.ps1"
timeout /t 5
