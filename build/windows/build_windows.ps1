param([switch]$Prepare, [switch]$DownloadsReady, [switch]$CheckOnly,
      [switch]$ConsoleBuild, [switch]$NonInteractive, [string]$Browser)
$ErrorActionPreference = 'Stop'
try {
    if ($env:OS -ne 'Windows_NT') { throw 'Build the Windows executable on Windows.' }
    $projectRoot = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
    Set-Location $projectRoot
    $venvRoot = Join-Path $PSScriptRoot '.venv'
    $python = Join-Path $venvRoot 'Scripts\python.exe'
    if ($Prepare) {
        if (-not $DownloadsReady) {
            Write-Host 'Preparation downloads Python packages including Selenium and PyInstaller, without a browser or Node.'
            Write-Host 'Run -Prepare -DownloadsReady when ready. Nothing downloaded.'
            exit 0
        }
        if (-not (Test-Path $python -PathType Leaf)) {
            if (Get-Command python -ErrorAction SilentlyContinue) {
                $bootstrap = 'python'
                $bootstrapArgs = @()
            } elseif (Get-Command py -ErrorAction SilentlyContinue) {
                $bootstrap = 'py'
                $bootstrapArgs = @('-3.12')
            } else { throw 'Python 3.12 with Tk is required.' }
            & $bootstrap @bootstrapArgs -c "import sys, tkinter; assert sys.version_info[:2] == (3, 12), 'Use Python 3.12 with Tk'"
            if ($LASTEXITCODE) { throw 'Python 3.12 with Tk is required.' }
            & $bootstrap @bootstrapArgs -m venv $venvRoot
            if ($LASTEXITCODE) { throw 'Could not create the Windows build environment.' }
        }
        & $python -m pip install -r (Join-Path $PSScriptRoot 'requirements-build.txt')
        if ($LASTEXITCODE) { throw 'Build dependency installation failed.' }
        & $python -m pip check
        if ($LASTEXITCODE) { throw 'Installed dependency compatibility check failed.' }
        Write-Host 'Dependencies prepared. No browser downloaded.'
        exit 0
    }
    if (-not (Test-Path $python -PathType Leaf)) {
        throw 'Missing build environment. First run -Prepare -DownloadsReady.'
    }
    $preflight = @('build/check_environment.py', '--require-build')
    if ($Browser) { $preflight += @('--browser', $Browser) }
    & $python @preflight
    if ($LASTEXITCODE) { throw 'Preflight failed. Nothing downloaded.' }
    if ($CheckOnly) { exit 0 }
    & $python -m unittest discover -s tests -p 'test_*.py'
    if ($LASTEXITCODE) { throw 'Unit tests failed.' }
    & $python tests/check_gui.py
    if ($LASTEXITCODE) { throw 'Tk integration checks failed.' }
    $appName = if ($ConsoleBuild) { 'AttendanceBookDebug' } else { 'AttendanceBook' }
    $windowMode = if ($ConsoleBuild) { '--console' } else { '--windowed' }
    $templatesSource = Join-Path $projectRoot 'app\templates'
    $assetsSource = Join-Path $projectRoot 'app\assets'
    $hooksSource = Join-Path $projectRoot 'build\hooks'
    $iconSource = Join-Path $projectRoot 'app\assets\icons\chu_red.ico'
    $mainScript = Join-Path $projectRoot 'app\main.py'
    & $python -m PyInstaller --noconfirm --clean --onefile $windowMode --noupx --additional-hooks-dir $hooksSource --collect-all tkinterdnd2 --exclude-module playwright --exclude-module pytest --add-data "${templatesSource}:templates" --add-data "${assetsSource}:assets" --icon $iconSource --specpath $PSScriptRoot --workpath (Join-Path $PSScriptRoot 'work') --distpath (Join-Path $PSScriptRoot 'dist') --name $appName $mainScript
    if ($LASTEXITCODE) { throw 'Executable build failed.' }
    $artifact = Join-Path $PSScriptRoot "dist\$appName.exe"
    & $python build/verify_package.py $artifact
    if ($LASTEXITCODE) { throw 'Frozen package content check failed.' }
    & $python build/run_frozen_self_test.py $artifact --output (Join-Path $PSScriptRoot 'frozen-self-test.json')
    if ($LASTEXITCODE) { throw 'Frozen runtime self-test failed.' }
    & $python build/check_environment.py --require-build --artifact $artifact --report (Join-Path $PSScriptRoot "$appName-build-report.json")
    if ($LASTEXITCODE) { throw 'Post-build artifact check failed.' }
    Write-Host "Package created: $artifact (unsigned)."
} catch {
    Write-Host 'BUILD FAILED' -ForegroundColor Red
    Write-Host ($_ | Out-String) -ForegroundColor Red
    try {
        if (-not $NonInteractive -and [Environment]::UserInteractive -and -not [Console]::IsInputRedirected) {
            [void](Read-Host 'Press Enter to close')
        }
    } catch { }
    exit 1
}
