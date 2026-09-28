param([switch]$CheckOnly, [switch]$ConsoleBuild)
$ErrorActionPreference = 'Stop'
try {
if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows executable on Windows.' }
$projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
Set-Location $projectRoot
foreach ($asset in @('app\assets\fonts\AttendanceCJK.otf', 'app\assets\fonts\LICENSE.txt', 'app\assets\fonts\FONT_INFO.txt', 'app\templates\attendance_blueprint.html', 'app\assets\icons\chu_red.png', 'app\assets\icons\chu_red.ico')) {
    if (-not (Test-Path $asset -PathType Leaf)) { throw "Required offline asset missing: $asset. Restore the required project assets before building." }
}
$venvRoot = Join-Path $PSScriptRoot '.venv'
$python = Join-Path $venvRoot 'Scripts\python.exe'
# A normal build also bootstraps the environment when needed.
if (-not (Test-Path $python -PathType Leaf)) {
    if (-not (Get-Command py -ErrorAction SilentlyContinue)) {
        throw 'Python launcher (py) with Python 3.12 is required. Install Python 3.12 with Tk.'
    }
    & py -3.12 -c "import tkinter"
    if ($LASTEXITCODE) { throw 'Python 3.12 including Tk is required.' }
    & py -3.12 -m venv $venvRoot
    if ($LASTEXITCODE) { throw 'Could not create the Windows build environment.' }
}
& $python -c "import sys, tkinter; assert sys.version_info[:2] == (3, 12), 'Use Python 3.12 with Tk'"
if ($LASTEXITCODE) { throw 'Build environment requires Python 3.12 with Tk. Check build\windows\.venv.' }
& $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.txt')
if ($LASTEXITCODE) { throw 'Build dependency installation failed.' }
& $python -m pip check
if ($LASTEXITCODE) { throw 'Installed dependency compatibility check failed.' }

& $python build/check_environment.py --require-build --browser msedge --prompt-browser
if ($LASTEXITCODE) {
    Write-Host 'Check the selected Microsoft Edge executable and browser automation policies.'
    throw 'Preflight failed. Address the reported errors, then rerun.'
}
if ($CheckOnly) { exit 0 }
& $python -m unittest discover -s tests -p 'test_*.py'
if ($LASTEXITCODE) { throw 'Unit tests failed' }
& $python tests/check_gui.py
if ($LASTEXITCODE) { throw 'Tk integration checks failed' }
$appName = if ($ConsoleBuild) { 'AttendanceBookDebug' } else { 'AttendanceBook' }
$windowMode = if ($ConsoleBuild) { '--console' } else { '--windowed' }
# Data sources in generated specs are resolved relative to --specpath.
# Use absolute source paths so keeping specs under build/windows is safe.
$templatesSource = Join-Path $projectRoot 'app\templates'
$assetsSource = Join-Path $projectRoot 'app\assets'
$hooksSource = Join-Path $projectRoot 'build\hooks'
$iconSource = Join-Path $projectRoot 'app\assets\icons\chu_red.ico'
$mainScript = Join-Path $projectRoot 'app\main.py'
& $python -m PyInstaller --noconfirm --clean --onefile $windowMode --noupx --additional-hooks-dir $hooksSource --collect-all tkinterdnd2 --add-data "${templatesSource}:templates" --add-data "${assetsSource}:assets" --icon $iconSource --specpath $PSScriptRoot --workpath (Join-Path $PSScriptRoot 'work') --distpath (Join-Path $PSScriptRoot 'dist') --name $appName $mainScript
if ($LASTEXITCODE) { throw 'Executable build failed' }
$artifact = Join-Path $PSScriptRoot "dist\$appName.exe"
& $python build/check_environment.py --require-build --browser msedge --artifact $artifact --report (Join-Path $PSScriptRoot "$appName-build-report.json")
if ($LASTEXITCODE) { throw 'Post-build environment/artifact check failed' }
Write-Host "Draft created: build\windows\dist\$appName.exe. Clean-Windows login, clipboard, drop and offline PDF testing remain required."

} catch {
    Write-Host ""
    Write-Host "BUILD FAILED" -ForegroundColor Red
    Write-Host ($_ | Out-String) -ForegroundColor Red

    # Keep an interactive PowerShell window open so the error can be read.
    # Do not block redirected/non-interactive builds.
    try {
        if ([Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
            [void](Read-Host "Press Enter to close")
        }
    } catch { }
    exit 1
}
