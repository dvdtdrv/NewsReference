@echo off
rem Starts the runner (the program that reads the blocked outlets for the site) in a minimized window.
rem It also starts by itself when you log in to Windows. Leave its window open; closing it stops it.
start "NewsReference runner - leave open" /min /d "%USERPROFILE%\actions-runner" "%USERPROFILE%\actions-runner\run.cmd"
