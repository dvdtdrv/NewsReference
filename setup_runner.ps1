# Connects this PC to the NewsReference project on GitHub as a "self-hosted runner",
# so GitHub can read the outlets that refuse its own servers (see fetch_local.py).
# Started by setup_runner.bat, which asks for the one-time code from GitHub.
#
# What it does:
#   1. downloads GitHub's official runner program (from github.com/actions/runner) into
#      C:\Users\<you>\actions-runner
#   2. registers it with your project, using the code you paste
#   3. makes it start by itself when you log in to Windows, and starts it now

param([Parameter(Mandatory = $true)][string]$Code)

$ErrorActionPreference = "Stop"
$version = "2.338.2"
$dir = Join-Path $env:USERPROFILE "actions-runner"
$repo = "https://github.com/dvdtdrv/NewsReference"

New-Item -ItemType Directory -Force -Path $dir | Out-Null
Set-Location $dir

if (-not (Test-Path ".\config.cmd")) {
    Write-Host "Downloading GitHub's runner program..."
    $zip = Join-Path $dir "runner.zip"
    Invoke-WebRequest -Uri "https://github.com/actions/runner/releases/download/v$version/actions-runner-win-x64-$version.zip" -OutFile $zip
    Expand-Archive -Path $zip -DestinationPath $dir -Force
    Remove-Item $zip
}

Write-Host "Connecting this PC to your project..."
& .\config.cmd --unattended --url $repo --token $Code --name "david-pc" --labels "newsreference" --work "_work" --replace
if ($LASTEXITCODE -ne 0) { throw "Connecting failed. The code may have expired (it lasts 1 hour): get a new one and try again." }

Write-Host "Making it start when you log in to Windows..."
$startup = [Environment]::GetFolderPath("Startup")
$shell = New-Object -ComObject WScript.Shell
$link = $shell.CreateShortcut((Join-Path $startup "NewsReference runner.lnk"))
$link.TargetPath = Join-Path $dir "run.cmd"
$link.WorkingDirectory = $dir
$link.WindowStyle = 7   # minimized
$link.Save()

Write-Host "Starting it now (a minimized window called 'run' will stay open; leave it running)..."
Start-Process -FilePath (Join-Path $dir "run.cmd") -WorkingDirectory $dir -WindowStyle Minimized

Write-Host ""
Write-Host "Done. This PC now reads the blocked outlets for your site whenever it is on."
