@echo off
rem Double-click this file to install the libraries and run the feed checker.
cd /d "%~dp0"

rem Use Anaconda's Python if it's in the usual place, otherwise whatever "python" is.
set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
set PYTHONIOENCODING=utf-8

echo Installing libraries (only slow the first time)...
"%PY%" -m pip install -q -r requirements.txt > run_log.txt 2>&1

echo Checking outlets, this takes about a minute...
"%PY%" check_feeds.py >> run_log.txt 2>&1

type run_log.txt
echo.
echo Done. Results are in feed_report.csv and articles.json
pause
