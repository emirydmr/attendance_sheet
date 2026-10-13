# Windows build

Build on Windows x64 with Python 3.12, Tkinter and the Python launcher (`py`).
Copy the project source and assets to Windows, including the bundled font;
virtual environments from macOS cannot be reused. From the repository root in
PowerShell:

```powershell
.\build\windows\build_windows.ps1 -Prepare -DownloadsReady
.\build\windows\build_windows.ps1
```

The preparation command creates `build\windows\.venv` and installs the pinned
dependencies. `-DownloadsReady` explicitly allows those downloads. The build
command then checks the required resources, runs the repository checks and
packages a single executable without inspecting an installed browser by default.
Existing build environments are reused. Preparation needs network access;
packaging does not download dependencies or browsers. The packaged app includes
Python/Tkinter, Selenium, fonts, templates, icons and drag-and-drop support,
without a Playwright or Node.js runtime.

Output: `build\windows\dist\AttendanceBook.exe`. Generated specifications, work
files and reports remain under `build\windows\`.

## Optional build diagnostics

```powershell
.\build\windows\build_windows.ps1 -CheckOnly
.\build\windows\build_windows.ps1 -ConsoleBuild
```

After preparation, `-CheckOnly` runs preflight without packaging or downloading.
`-ConsoleBuild` produces `build\windows\dist\AttendanceBookDebug.exe` with console
output. CI uses `-NonInteractive` so failures do not wait for Enter.

CI also runs a local browser and PDF smoke check using loopback fixtures; it
does not access the university portal. A live portal smoke check is opt-in,
requires a student-present session on the target machine, and is separate from
the package build. See the [repository README](../../README.md) for the
developer-only command and safeguards.

If PowerShell blocks the script, allow this invocation only:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\windows\build_windows.ps1 -Prepare -DownloadsReady
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\windows\build_windows.ps1
```

This does not change the machine-wide execution policy.

## Run and distribute

Recipients need an installed browser, but no separate Python installation or
administrator installation for normal app use. **Browser Settings** opens
automatically when no profile is active. Create a named profile and select an
installed browser; the app detects its executable and chooses the driver kind.
Click **Apply** to explicitly allow matching-driver acquisition when needed.
Configuration and drivers live in `%LOCALAPPDATA%\AttendanceBook`, outside the
EXE. Advanced manual
overrides and the driver library are in the same dialog. Builds do not assign a
runtime browser default; a failed selection never launches another browser.

Chrome and Edge support automatic PDF export; Firefox uses WebDriver printing
when available. Chromium/360e/custom builds require compatible drivers and are
experimental. Neither packaging nor first-run setup downloads a full browser.

Before distribution, check the EXE on a clean target machine: student-present
manual login, full timetable retrieval, Chinese PDF output, photo clipboard/drop
and next-student session cleanup. Windows/teacher-computer live validation has
not been established by the build checks.

The [GitHub workflow](../../.github/workflows/build-release.yml) produces the
Windows x64 artifact on `main`, pull requests and manual runs; pushing a `v*`
version tag automatically publishes a GitHub Release after both platform builds
pass. See the [repository README](../../README.md) for release status, usage and
browser limitations.
