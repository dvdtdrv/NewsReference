@echo off
rem Double-click to collect new articles, group them into stories and build the website page.
cd /d "%~dp0"
set "PY=%USERPROFILE%\anaconda3\python.exe"
if not exist "%PY%" set "PY=python"
set PYTHONIOENCODING=utf-8

"%PY%" -m pip install -q -r requirements.txt > run_log.txt 2>&1

echo Step 1 of 3: collecting new articles...
"%PY%" collect.py >> run_log.txt 2>&1
echo Step 2 of 3: grouping them into stories...
"%PY%" group_stories.py >> run_log.txt 2>&1
echo Step 3 of 3: building the website page...
"%PY%" build_site.py >> run_log.txt 2>&1

type run_log.txt
echo.
echo Done. Open site\index.html to see the website.
pause
