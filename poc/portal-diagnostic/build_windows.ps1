param([switch]$DownloadsReady)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows executable on Windows.' }
if (-not $DownloadsReady) {
    Write-Host 'This build downloads Python packages and Chromium.'
    Write-Host 'Adjust your VPN first, then run: .\build_windows.ps1 -DownloadsReady'
    exit 0
}
Set-Location $PSScriptRoot
py -3.12 -m venv .venv-build
if ($LASTEXITCODE -ne 0) { throw 'Install Python 3.12 with Tkinter and the Python launcher.' }
$python = Join-Path $PSScriptRoot '.venv-build\Scripts\python.exe'
& $python -m pip install -r requirements.txt 'pyinstaller>=6,<7'
if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
# Place full Chromium inside the Playwright package so PyInstaller embeds it.
$env:PLAYWRIGHT_BROWSERS_PATH = '0'
& $python -m playwright install chromium --no-shell
if ($LASTEXITCODE -ne 0) { throw 'Chromium installation failed.' }
& $python -m PyInstaller --noconfirm --clean --onefile --windowed `
    --name AttendancePortalDiagnostic --collect-all playwright app.py
if ($LASTEXITCODE -ne 0) { throw 'Executable build failed.' }
Write-Host 'Built dist\AttendancePortalDiagnostic.exe. Check both retrieval modes on Windows.'
