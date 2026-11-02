@echo off
rem Makes this folder's code exactly match GitHub (the main branch).
rem Your data\ and site\ folders are not touched. Any edits you made to the code files here are replaced.
cd /d "%~dp0"
set "GIT=git"
where git >nul 2>&1
if errorlevel 1 (
  for /d %%D in ("%LOCALAPPDATA%\GitHubDesktop\app-*") do if exist "%%D\resources\app\git\cmd\git.exe" set "GIT=%%D\resources\app\git\cmd\git.exe"
)
"%GIT%" fetch origin || (echo Could not reach GitHub. & pause & exit /b 1)
"%GIT%" reset --hard origin/main
echo.
echo Done: this folder now matches GitHub.
pause
