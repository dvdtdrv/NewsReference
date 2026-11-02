@echo off
rem Stops the runner until the next login (or until you run start_runner.bat).
taskkill /im Runner.Listener.exe /t /f >nul 2>&1 && echo Runner stopped. || echo The runner was not running.
timeout /t 5
