# Windows build

Build on Windows with Python 3.12 including Tk and the Python launcher (`py`).
Copy the project source/assets, not the Mac `.venv` symlink, to Windows. Run these
commands from the copied project's root in PowerShell.

1. Prepare dependencies yourself when your connection is ready. This downloads
   Python packages including Playwright and PyInstaller, but no browsers:

   ```powershell
   .\build\windows\build_windows.ps1 -PrepareOnly -DownloadsReady
   ```

2. Ensure Microsoft Edge is installed. It is required on both the build machine
   and recipient machines for visible login and background PDF rendering.
   Do not run `playwright install`; no browser runtime is bundled.

3. Build without dependency/browser downloads:

   ```powershell
   .\build\windows\build_windows.ps1
   ```

Output: `build\windows\dist\AttendanceBook.exe`. Generated spec and work files,
and the Windows virtual environment, also stay under `build\windows\`.
Run the EXE on a clean Windows machine with Edge installed and test login, clipboard/drop, offline
PDF creation, Chinese text, icon display and next-student session cleanup.

If PowerShell blocks a locally copied script, use the same arguments with
`powershell -NoProfile -ExecutionPolicy Bypass -File .\build\windows\build_windows.ps1`.
This affects that process only; do not change machine-wide execution policy.
