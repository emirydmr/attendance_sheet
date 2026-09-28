# Windows build

Build on Windows with Python 3.12 including Tk and the Python launcher (`py`).
Copy the project source/assets, not a macOS virtual environment, to Windows.
Run this from the project's root in PowerShell:

```powershell
.\build\windows\build_windows.ps1
```

The script creates `build\windows\.venv` if necessary, installs the pinned Python
dependencies, verifies the assets and browser, runs the tests, and packages the EXE.
Existing environments are reused. Microsoft Edge is required but is not bundled;
if the browser preflight cannot launch it, a file picker lets you select its
executable. No separate preparation command is needed.

Output: `build\windows\dist\AttendanceBook.exe`. Generated spec files,
work files, build reports and the virtual environment remain under
`build\windows\`.

Optional commands:

```powershell
.\build\windows\build_windows.ps1 -CheckOnly
.\build\windows\build_windows.ps1 -ConsoleBuild
```

`-CheckOnly` prepares the environment and runs the preflight without packaging;
`-ConsoleBuild` produces `AttendanceBookDebug.exe` with console output.

Test the EXE on a clean Windows machine with Edge installed, including login,
clipboard/drop, offline PDF creation, Chinese text, icon display and
next-student session cleanup.

If PowerShell blocks the script, use a process-scoped override:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\windows\build_windows.ps1
```

This does not change the machine-wide execution policy.
