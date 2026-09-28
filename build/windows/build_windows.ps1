param([switch]$PrepareOnly, [switch]$DownloadsReady, [switch]$CheckOnly, [switch]$ConsoleBuild)
$ErrorActionPreference = 'Stop'
if ($PrepareOnly -and ($CheckOnly -or $ConsoleBuild)) { throw 'Use preparation separately from check/build.' }
if ($PrepareOnly -and -not $DownloadsReady) {
    Write-Host 'Preparing the build may download Python packages and PyInstaller.'
    Write-Host 'Adjust your VPN first, then rerun with -DownloadsReady. Nothing was downloaded.'
    exit 0
}
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows executable on Windows.' }
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $projectRoot
foreach ($asset in @('app\assets\fonts\AttendanceCJK.otf', 'app\assets\fonts\LICENSE.txt', 'app\assets\fonts\FONT_INFO.txt', 'app\templates\attendance_blueprint.html', 'app\assets\icons\chu_red.png', 'app\assets\icons\chu_red.ico')) {
    if (-not (Test-Path $asset -PathType Leaf)) { throw "Required offline asset missing: $asset. Prepare licensed assets before building; no downloads started." }
}
$venvRoot = Join-Path $PSScriptRoot '.venv'
$python = Join-Path $venvRoot 'Scripts\python.exe'
if ($PrepareOnly) {
    if (-not (Test-Path $python)) {
        py -3.12 -c "import tkinter"
        if ($LASTEXITCODE) { throw 'Python 3.12 including Tk is required.' }
        py -3.12 -m venv $venvRoot
        if ($LASTEXITCODE) { throw 'venv failed; install Windows Python 3.12 including Tk.' }
    }
    & $python -c "import sys, tkinter; assert sys.version_info[:2] == (3, 12), 'Use Python 3.12 with Tk'"
    if ($LASTEXITCODE) { throw 'Build environment Python/Tk check failed.' }
    & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.txt')
    if ($LASTEXITCODE) { throw 'Dependency installation failed' }
    & $python -m pip check
    if ($LASTEXITCODE) { throw 'Installed dependency compatibility check failed' }
    Write-Host 'Build dependencies prepared. Installed Microsoft Edge is required; no browser downloaded.'
    exit 0
}
if (-not (Test-Path $python)) {
    throw 'Prepare the Windows environment first: .\build\windows\build_windows.ps1 -PrepareOnly -DownloadsReady'
}
& $python build/check_environment.py --require-build --browser msedge --prompt-browser
if ($LASTEXITCODE) {
    Write-Host 'Check installed Microsoft Edge and school/browser automation policies. No browser is bundled.'
    throw 'Preflight failed. Address the reported errors, then rerun. No downloads started.'
}
if ($CheckOnly) { exit 0 }
& $python -m unittest discover -s tests -p 'test_*.py'
if ($LASTEXITCODE) { throw 'Unit tests failed' }
& $python tests/check_gui.py
if ($LASTEXITCODE) { throw 'Tk integration checks failed' }
$appName = if ($ConsoleBuild) { 'AttendanceBookDebug' } else { 'AttendanceBook' }
$windowMode = if ($ConsoleBuild) { '--console' } else { '--windowed' }
& $python -m PyInstaller --noconfirm --clean --onefile $windowMode --noupx --additional-hooks-dir 'build/hooks' --collect-all tkinterdnd2 --add-data 'app/templates:templates' --add-data 'app/assets:assets' --icon 'app/assets/icons/chu_red.ico' --specpath $PSScriptRoot --workpath (Join-Path $PSScriptRoot 'work') --distpath (Join-Path $PSScriptRoot 'dist') --name $appName app/main.py
if ($LASTEXITCODE) { throw 'Executable build failed' }
$artifact = Join-Path $PSScriptRoot "dist\$appName.exe"
& $python build/check_environment.py --require-build --browser msedge --artifact $artifact --report (Join-Path $PSScriptRoot "$appName-build-report.json")
if ($LASTEXITCODE) { throw 'Post-build environment/artifact check failed' }
Write-Host "Draft created: build\windows\dist\$appName.exe. Clean-Windows login, clipboard, drop and offline PDF testing remain required."
