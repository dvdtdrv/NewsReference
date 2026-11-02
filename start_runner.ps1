# Starts the runner (the program that reads the blocked outlets for the site) with NO window,
# so it can't be closed by accident. Also makes Windows start it the same hidden way at every login.
# Started by start_runner.bat. To stop it: stop_runner.bat.

$dir = Join-Path $env:USERPROFILE "actions-runner"
$here = Split-Path -Parent $MyInvocation.MyCommand.Path

# Start at login: a shortcut in the Startup folder that runs start_runner.bat hidden
$startup = [Environment]::GetFolderPath("Startup")
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $startup "NewsReference runner.lnk"))
$link.TargetPath = "powershell.exe"
$link.Arguments = "-NoProfile -WindowStyle Hidden -ExecutionPolicy Bypass -File `"$here\start_runner.ps1`""
$link.WorkingDirectory = $here
$link.WindowStyle = 7
$link.Save()

if (Get-Process -Name "Runner.Listener" -ErrorAction SilentlyContinue) {
    Write-Host "The runner is already running. Nothing to do."
} else {
    Start-Process -FilePath (Join-Path $dir "run.cmd") -WorkingDirectory $dir -WindowStyle Hidden
    Write-Host "The runner is running in the background (no window). It will also start by itself at every login."
}
