# AttendanceBook / 国际学生考勤册

Built for the administration to automatically generate attendance sheets while
the student is present and can log in to the university portal.

## Requirements

- Windows: Windows 11 x64 with Microsoft Edge installed.
- macOS: macOS 14 or newer with Google Chrome installed.
- Running from source or building: Python 3.12 with Tkinter.

Packaged applications do not require Python or LaTeX. Browsers are not bundled.
The application checks the required browser at startup and provides
**Check browser / retry** if it cannot launch. A successful check shows a green
checkmark, a confirmation message and the browser version. It never downloads a browser.

## Setup and launch

Run all commands from the repository root. Dependency preparation downloads
Python packages; the launch and build steps do not install anything.
Dependencies are pinned in [requirements.txt](requirements.txt) and
[build/requirements-build.txt](build/requirements-build.txt).

### Windows

Install Python 3.12 with Tkinter and the Python launcher (`py`), then run in
PowerShell:

```powershell
.\build\windows\build_windows.ps1 -PrepareOnly -DownloadsReady
.\build\windows\.venv\Scripts\python.exe app/main.py
```

### macOS

With Python 3.12 available as `python3`:

```sh
./build/macos/build_macos.command --prepare --downloads-ready
./build/macos/.venv/bin/python app/main.py
```

If needed, select a Python 3.12 executable during preparation:

```sh
PYTHON_BIN=/path/to/python3.12 ./build/macos/build_macos.command --prepare --downloads-ready
```

For a demonstration without portal retrieval, append `--demo` to the launch
command. Add `--photo-popup` to open the photo importer immediately.

## Usage

1. Wait for the startup browser check. If it fails, install or repair the required
   browser, or resolve its automation restrictions, then click
   **Check browser / retry**.
2. Click **Open browser / log in** and let the student sign in.
3. Select the academic start year, semester and inclusive week range.
4. Retrieve student number/major, student name and weekly timetables separately.
   Click or hover over a result status to inspect the retrieved information.
   Each input has an ⓘ button and bilingual hover help.
5. Confirm the Chinese name and passport name, cover major, 班主任, contact
   number and issue date. The portal's 姓名 is not automatically treated as a
   Chinese or passport name. 班主任 is the role used on the attendance sheet.
6. Add a photograph by selecting a file, dragging a local image into the popup,
   or choosing **Copy image** in the browser and pasting while the popup is active.
   Use Ctrl+V on Windows or Command+V on macOS. Copy image address is not supported.
7. Click **Create PDF** and choose a destination. The suggested filename is
   `<student_id>_长安大学国际学生考勤册.pdf`. Alternatively, use
   **Open in default browser / print** to save an HTML preview and print it.
8. Click **End student session** before starting with another student.

For academic year 2026–2027, enter **2026**, not the current calendar year.
Teaching weeks range from 1 to 20; the default range is 1–18. Empty weeks are
valid. Changing the semester/year clears retrieved results; changing the week
range clears timetables.

Enable **Omit empty weeks / 省略无课周** to leave weeks with no classes out of the
PDF/HTML and summary table. Every week in the selected range is still retrieved
and checked. Remaining weeks keep their original numbers. This option is on by
default and can be changed after retrieval without scanning again.

| English semester | Chinese semester | Internal portal code |
| --- | --- | --- |
| First semester | 第一学期 | 11 |
| Second semester | 第二学期 | 12 |
| Short semester | 短学期 | 13 |

No manual semester-code entry is required. The issue date defaults to today and
can be edited; the cover prints its year and month.

Supported photographs: PNG, JPEG, WebP, BMP, TIFF and GIF, up to 20 MB and
25 million pixels. For animated images, only the first frame is used.
Cancelling the photo popup preserves the previous photograph.

Teachers sign directly in the relevant class cells. The book includes the cover,
original attendance instructions, weekly schedules, summary table and leave-slip
page. There is no separate bottom signature table.

## Project structure and rendering

```text
app/
  main.py               Tkinter interface
  browser_config.py     installed-browser selection and startup check
  service.py            login session and HTTP retrieval
  portal.py             timetable and profile parsers
  document.py           document generation and PDF export
  field_help.py         bilingual field descriptions
  photo.py              photo import
  branding.py           application icon
  templates/            shared HTML/CSS and layout logic
  assets/               icons, Chinese font and font licence
build/
  check_environment.py  dependency, asset and browser checks
  export_source.py      portable source archive
  generate_icons.py     regenerate PNG/ICO from SVG
  hooks/                packaging hooks
  windows/              Windows build recipe and requirements
  macos/                macOS build recipe and requirements
tests/                  automated checks and sample generators
poc/                    earlier portal experiments
reference/latex/        unused LaTeX draft
```

Playwright opens a separate Edge/Chrome login window. Subsequent retrieval uses
HTTP requests in that browser session. The application requests each selected
teaching week sequentially.

PDFs are rendered from the shared HTML/CSS blueprint using the installed browser
in headless mode. No LaTeX engine is used. Output is A4 landscape with embedded
Chinese typography; browser previews fit within 80% of the viewport width.
Oversized pages are reported instead of silently clipping course text.

## Building

Build on the target operating system after completing its setup step. Build
recipes check dependencies, assets and browser availability before packaging.
Platform environments, generated specs, work directories, reports and packaged
outputs stay under `build/windows/` or `build/macos/`.

### Windows: single EXE

```powershell
.\build\windows\build_windows.ps1 -CheckOnly
.\build\windows\build_windows.ps1
```

Output: `build/windows/dist/AttendanceBook.exe`.

The EXE includes Python/Tkinter, Playwright's driver, fonts, icons and native
drag-and-drop support, but not Edge. Recipients must have Edge installed.

For a console-enabled diagnostic build:

```powershell
.\build\windows\build_windows.ps1 -ConsoleBuild
```

Output: `build/windows/dist/AttendanceBookDebug.exe`.

If PowerShell blocks a script, use a process-scoped override with the desired
arguments:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\windows\build_windows.ps1 -CheckOnly
```

### macOS: APP bundle

```sh
./build/macos/build_macos.command --check
./build/macos/build_macos.command
```

Output: `build/macos/dist/AttendanceBook.app`.

Keep the complete APP bundle together. Recipients must have Chrome installed.
Apple Silicon and Intel require separate builds using the matching Python
architecture.

### Optional source archive

Using the prepared platform Python environment, run:

```sh
python build/export_source.py
```

Replace `python` with `build/macos/.venv/bin/python` on macOS or
`build/windows/.venv/Scripts/python.exe` on Windows.
Output: `build/source/AttendanceBook-source.zip`.

## Troubleshooting

- **Browser check fails:** confirm Edge on Windows or Chrome on macOS is
  installed and usable. Organization policies may restrict automation. After
  resolving the problem, click **Check browser / retry**.
- **Different browser for an explicit run:** use `--browser msedge` or
  `--browser chrome`; that browser must already be installed.
- **Tkinter or drag-and-drop fails:** use Python 3.12 with Tkinter and the correct
  platform/architecture. Tkinter is not installed through pip.
- **Login expires or student changes:** end the student session and sign in again.
- **Cannot paste a photograph:** use **Copy image**, not **Copy image address**,
  and focus the photo popup before pasting.
- **PDF overflow:** inspect the page/week identified in the error and adjust the
  template for the course content.
- **Wrong timetable:** check the academic start year, semester and teaching-week
  range. Empty weeks are valid.
- **Packaged application fails:** use the Windows console build to inspect the
  error and check the generated platform build report.

## Release status

Build recipes are prepared, but packaged Windows and macOS releases have not
yet been built and validated on clean target machines. Windows Edge behavior
still needs native Windows verification. Complete live retrieval, native
clipboard/drag-and-drop and final printed layout need release validation.

Code signing and macOS notarization are not configured.

## Licensing

The application does not yet declare a source-code licence.

The bundled Noto Serif SC font uses SIL Open Font License 1.1. Its licence and
provenance are included under [app/assets/fonts](app/assets/fonts) and are
available through **Font licence / 字体许可** in the application.

## Author

Emir Aydemir · Chang'an University

[aydemir.emir@icloud.com](mailto:aydemir.emir@icloud.com)
