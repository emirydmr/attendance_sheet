# AttendanceBook / 国际学生考勤册

A bilingual Tkinter desktop application for preparing Chang’an University
international-student attendance books. A student signs in manually; the app
retrieves their own identity and weekly schedules using the authenticated browser
session, accepts a manually supplied photograph, and exports a PDF.

Production target: one Windows executable. macOS also has a development launcher
and a prepared packaging recipe. Neither packaged release has been built or
clean-machine tested yet. Do not treat the source ZIP as a finished application.

Browser policy: **installed Microsoft Edge on Windows, installed Google Chrome
on macOS**, for both visible student login and headless PDF rendering. Playwright
and its driver are packaged, but browsers are not. No browser download occurs
at app startup; recipients must have the appropriate browser installed.

## 1. Current status and remaining work

Verified locally on 2026-09-28:

- Portal proof of concept: normal authenticated HTTP GET retrieval of identity,
  portal 姓名 and weekly timetable; visible/headless comparisons passed for week 3.
- HTML/CSS printing with embedded Noto Serif SC; an eight-page fictitious photo
  sample was rendered and every page visually checked previously.
- English/Chinese UI, independent retryable retrieval actions, result inspection,
  stale-selection rejection, student-session cleanup, manual photo normalization.
- Input-help/layout revision: 39 unit tests, Tk integration and responsive-layout
  checks passed; normal/dense eight-page samples were visually checked. PDF pixel
  margin checks guard against scaled-table fragments spilling onto the next page.
- Offline development preflight: Python 3.12.14, Tk 9.0.4, tkdnd 2.10.2, installed
  Chrome 153; no missing assets or mismatched runtime dependency pins.
- Platform recipes prepared. Mac shell syntax, launcher and no-download guards
  checked. Windows PowerShell is not available in this development environment.
- Installed-browser policy revision: 43 unit tests and Tk integration passed;
  Windows Edge dispatch is mock-tested, not yet tested on a Windows machine.

Still required before release:

- Ensure Edge (Windows) / Chrome (macOS) is installed and prepare native build dependencies.
- Run PyInstaller on Windows for the EXE; optionally on Mac for the APP.
- Test packaged apps on clean machines without Python, with Edge on Windows or
  Chrome on macOS installed.
- Test the new production GUI against a real logged-in student and the complete
  selected week range (not only the proof of concept’s checked week).
- Manually test Chrome Copy image → Paste and native file drag-and-drop on Windows.
- Confirm visual approval against the teacher’s form, including signatures and
  which portal course-status/conflict entries should be included.
- Confirm the school permits this student-consented workflow and personal-data
  handling. Code signing/notarization is not prepared.

## 2. Project layout

```text
attendance_sheet/
  README.md
  requirements.txt                 pinned runtime dependencies
  app/
    main.py                        Tkinter application
    portal.py                      server-rendered HTML parsers
    service.py                     session and read-only HTTP retrieval
    document.py                    escaping, validation and PDF printing
    photo.py                       foreground-only manual image import
    branding.py                    bundled window icon
    templates/attendance_blueprint.html
    assets/icons/chu_red.svg        original, editable icon source
    assets/icons/chu_red.png        Tk icon
    assets/icons/chu_red.ico        Windows executable icon
    assets/fonts/                  font, licence and provenance
  build/
    requirements-build.txt         shared pinned builder requirements
    check_environment.py           offline preflight/report
    generate_icons.py              local SVG-to-PNG/ICO utility
    export_source.py               safe source ZIP generation
    macos/                         launcher, recipe, requirements, notes
    windows/                       recipe, requirements, notes
    source/AttendanceBook-source.zip  generated source handoff
  tests/                           offline unit/GUI/sample checks
  poc/portal-diagnostic/           preserved experiments; not production imports
  reference/latex/                 preserved unused LaTeX draft
  work/                           internal fictitious PDF/layout QA
  硕博考勤册简易版.docx             original reference, unchanged
```

Platform virtual environments, generated specs, build work directories and
packaged outputs stay under `build/macos/` or `build/windows/`.
The root `.venv` is an existing Mac development symlink, not portable.
The compatibility `portal-diagnostic` symlink is only for older diagnostic windows.

### Git and repository publishing

Commit the source, tests, PoC source, reference `.tex`, build recipes and bundled
assets (including the font licence and provenance). `.gitignore` deliberately
does **not** ignore the entire `build/` directory. It excludes virtual
environments, build outputs/reports, QA files, the compatibility symlink, the
original DOCX, PDFs, diagnostic/session reports and local secrets. The original
DOCX contains student information and stays local; a clone does not need it to
run or build the application. Store any future student photos/records under
`private/`, `student-data/`, `photos/` or `exports/`, all of which are ignored.
Do not place personal data in tracked source or in `app/assets/`.

Git is already initialized locally. To prepare the first commit, from the
project directory:

```sh
git status --short --ignored
git add .
git diff --cached --stat
git diff --cached
git commit -m "Initial AttendanceBook source"
```

Review the staged files for personal data before committing. Ignore rules are
not a secret scanner, do not remove previously committed files, and can be
bypassed by `git add -f`. After creating an empty remote repository, replace
`YOUR_REPOSITORY_URL` with its actual URL:

```sh
git remote add origin YOUR_REPOSITORY_URL
git push -u origin main
```

If `origin` already exists, inspect `git remote -v` before changing it. No remote
has been configured or pushed by the preparation step. `.gitattributes` preserves
binary assets and enforces suitable script line endings across Windows/macOS.
The font has its own bundled SIL OFL licence; this project does not yet declare
an overall source-code licence. Choose one before inviting public reuse rather
than assuming the font licence covers the application.

## 3. Dependency audit

Checked against the official PyPI metadata on 2026-09-28. The four runtime pins
already match the current releases; the build dependency is now pinned too.

| Package | Pin | Used for |
| --- | --- | --- |
| playwright | 1.63.0 | manual browser login, session HTTP requests, Chromium PDF |
| beautifulsoup4 | 4.15.0 | timetable/profile HTML parsing |
| Pillow | 12.3.0 | image normalization, clipboard input, icon conversion |
| tkinterdnd2 | 0.6.3 | native file drag-and-drop |
| pyinstaller | 6.22.3 | packaging only, not runtime source requirement |

Sources: [Playwright](https://pypi.org/project/playwright/),
[Beautiful Soup](https://pypi.org/project/beautifulsoup4/),
[Pillow](https://pypi.org/project/Pillow/),
[tkinterdnd2](https://pypi.org/project/tkinterdnd2/),
[PyInstaller](https://pypi.org/project/pyinstaller/).

Tkinter is part of the Python installation, not a pip dependency. Use Python 3.12
with working Tk. Transitive packages are resolved by pip; direct pins are not a
complete hash-locked dependency tree. Build reports record the actual installed
versions and asset hashes. Updating Playwright or the installed browser requires
retesting login, HTTP retrieval and PDF rendering.

Download policy: startup, checks and default builds never install dependencies
or browsers. Preparation needs explicit download opt-in. The Windows Playwright
wheel alone is about 39 MB. Browsers are not downloaded or bundled. Run package downloads
yourself when your connection/VPN is ready. The approximately 11 MB Chinese font
and its licence are already present; no additional font download is required.

## 4. Run on this Mac now — no downloads

In Terminal:

```sh
cd /Users/emirydmr/attendance_sheet
./build/macos/run_local.command
```

Fictitious UI/photo test:

```sh
./build/macos/run_local.command --demo --photo-popup
```

The launcher uses installed Chrome. It prefers `build/macos/.venv` when prepared,
otherwise reuses the existing root development environment and the already
bundled Pillow. The latter fallback is specific to this development Mac and is
not suitable for redistribution.

To run source directly after preparing the Mac build environment (installed
Chrome is the default):

```sh
./build/macos/.venv/bin/python app/main.py --demo
```

## 5. Teacher workflow / 教师使用流程

1. Open browser / log in — 打开浏览器 / 登录. Let the student sign in themselves.
   Do not collect or enter their password in the application.
2. Select academic start year, semester and week range. For 2026–2027 use 2026.
   The semester dropdown shows First semester / Second semester / Short semester
   in English, or 第一学期 / 第二学期 / 短学期 in Chinese. Portal codes 11 / 12 / 13
   are sent automatically. Switching language preserves the selected semester
   and retrieved data; choosing a different semester clears stale results.
   Default range is 1–16; supported maximum 20.
3. Retrieve student number/major, name and weekly timetables separately.
   Hover a status for a preview or click it to inspect full results.
   Every input has a small ⓘ button and delayed bilingual hover help. The internal
   semester code is URL parameter xj: 11＝第一学期, 12＝第二学期, 13＝短学期. In
   培养 → 我的课表 select both academic year and semester, then read xj from
   the updated URL if you want to verify it; no manual code entry is needed.
   The academic-year value is xn and the teaching-week value zc.
4. Confirm 中文名 and 护照名 manually. Portal 姓名 is not assumed to mean either.
   Cover 专业 is editable: a research direction is not automatically substituted
   for the portal’s major.
5. Confirm 班主任, 联系电话 and the issue date. Defaults retain 李冠楠 and 02968578129
   from the reference. 班主任 is not the same role as academic 导师.
6. Add / change photo — 添加 / 更换照片. Select a file, drop one file into the
   popup, or in Chrome choose **Copy image**, then paste while the popup is active.
   Ctrl+V on Windows / Command+V on Mac. Copy image address does not work.
   Use photo commits the change; Cancel preserves the previous photo.
7. Create PDF — 生成 PDF. The save dialog suggests
   `<student_id>_长安大学国际学生考勤册.pdf`.
   An asterisk is not used because Windows filenames cannot contain it.
   Export without a photograph asks for confirmation and leaves a blank photo box.
8. End student session — 结束学生会话 before the next student. This closes the
   browser and clears retrieved data and the photograph.

Empty weeks are valid successful retrievals. Partial week ranges never become
successful results. Changing selections invalidates stale results; mismatched
student IDs are rejected. Failed groups can be retried independently.

Supported photos: PNG, JPEG, WebP, BMP, TIFF and GIF; first animation frame only.
Limits: 20 MB / 25 million pixels. Orientation is corrected, metadata removed,
transparency flattened on white, and dimensions reduced to at most 1600 pixels
without cropping or stretching.

## 6. Build the Windows single EXE

Use a native Windows 11 x64 machine with x64 Python 3.12 including Tk and the
`py` launcher. This Mac cannot cross-compile the Windows executable.
The upstream browser baseline is documented in
[Playwright system requirements](https://playwright.dev/python/docs/intro#system-requirements).

Transfer the prepared `build/source/AttendanceBook-source.zip`, extract it, and
open PowerShell in its `AttendanceBook` folder. The source archive excludes the
Mac venv, original DOCX, PoC/student reports, exported PDFs and session data.
The original DOCX is not a runtime requirement.

### A. Prepare Python dependencies — downloads

```powershell
.\build\windows\build_windows.ps1 -PrepareOnly -DownloadsReady
```

Creates `build/windows/.venv`, installs runtime/build requirements and runs
`pip check`. Does not download any browser.

### B. Confirm installed Microsoft Edge

Edge must be installed on both the build machine and recipients’ Windows
machines. Login uses `channel="msedge", headless=False`; PDF export uses the
same installed browser with `headless=True`. Do not run `playwright install`.
Missing/blocked Edge produces an error, not a browser download or silent fallback.

### C. Check without packaging — no downloads

```powershell
.\build\windows\build_windows.ps1 -CheckOnly
```

Checks Python/pins/assets, native Tk/tkdnd loading, icon loading, a headless browser
launch and embedded-font rendering. It does not access the university portal.

### D. Build — no downloads

```powershell
.\build\windows\build_windows.ps1
```

Runs preflight, unit tests and Tk integration tests before PyInstaller.
Outputs:

- `build/windows/dist/AttendanceBook.exe`
- `build/windows/AttendanceBook.spec`
- `build/windows/work/`
- `build/windows/AttendanceBook-build-report.json` with dependency/asset versions
  and final EXE SHA-256.

The EXE bundles Python/Tk, Playwright’s driver, application assets and native
drag-and-drop, but **not a browser**. A packaging hook excludes any cached
Playwright browser installations. Recipients need Microsoft Edge, but not
Python, Google Chrome or LaTeX installed. One-file packaging
extracts resources to a temporary directory at launch, so it is not “zero disk
usage” and may start more slowly. Portal retrieval still requires Internet access;
PDF creation uses offline embedded resources.

Run a fictitious packaged test:

```powershell
.\build\windows\dist\AttendanceBook.exe --demo --photo-popup
```

For a console-enabled diagnostic build:

```powershell
.\build\windows\build_windows.ps1 -ConsoleBuild
.\build\windows\dist\AttendanceBookDebug.exe --demo
```

If PowerShell blocks the script, use a process-scoped override (not a machine-wide
policy change), retaining the desired arguments:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\build\windows\build_windows.ps1 -PrepareOnly -DownloadsReady
```

See [Playwright installed browser channels](https://playwright.dev/python/docs/browsers#google-chrome--microsoft-edge)
and [PyInstaller usage](https://pyinstaller.org/en/stable/usage.html).

## 7. Optional macOS APP build

Use macOS 14+ and Python 3.12 including Tk. Build for the architecture of the
Python interpreter: Apple Silicon and Intel are separate targets; this recipe
does not create a universal binary or a signed/notarized release.

### A. Prepare dependencies yourself — downloads

```sh
./build/macos/build_macos.command --prepare --downloads-ready
```

If `python3` is not Python 3.12, specify an installed Python 3.12 executable:

```sh
PYTHON_BIN=/path/to/python3.12 ./build/macos/build_macos.command --prepare --downloads-ready
```

This creates a separate `build/macos/.venv`; it does not alter the legacy root
development environment. Python itself must already be installed.

### B. Confirm installed Google Chrome

Google Chrome must be installed on the build machine and recipient Macs. Login
and headless PDF export use `channel="chrome"`. No browser is bundled; do not
run `playwright install`.

### C. Check and build — no downloads

```sh
./build/macos/build_macos.command --check
./build/macos/build_macos.command
```

Outputs: `build/macos/dist/AttendanceBook.app`, generated spec/work directories and
`build/macos/build-report.json`. The Mac APP is an onedir bundle, not a Windows EXE
  or a macOS single executable. Keep the complete APP together. It is unsigned;
distribution/Gatekeeper handling needs a deliberate signing/notarization plan,
not blanket disabling of system protections.

For a packaged demo:

```sh
./build/macos/dist/AttendanceBook.app/Contents/MacOS/AttendanceBook --demo --photo-popup
```

## 8. Tests and development checks

Prepared Mac environment:

```sh
./build/macos/.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
./build/macos/.venv/bin/python tests/check_gui.py
./build/macos/.venv/bin/python build/check_environment.py --require-build
```

Prepared Windows environment:

```powershell
.\build\windows\.venv\Scripts\python.exe -m unittest discover -s tests -p 'test_*.py'
.\build\windows\.venv\Scripts\python.exe tests/check_gui.py
.\build\windows\.venv\Scripts\python.exe build/check_environment.py --require-build
```

For this Mac’s existing development environment, without preparing/downloading:

```sh
export PYTHONPATH=/Users/emirydmr/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/lib/python3.12/site-packages
.venv/bin/python -m unittest discover -s tests -p 'test_*.py'
.venv/bin/python tests/check_gui.py
.venv/bin/python build/check_environment.py --system-chrome --report build/macos/development-check.json
```

Sample PDF checks use installed Chrome and fictitious data, not student records:

```sh
.venv/bin/python tests/render_sample.py
.venv/bin/python tests/render_photo_sample.py
.venv/bin/python tests/check_layout.py
```

The automated checks do not prove real OS clipboard interoperability or packaged
resource loading. Build preflight runs from source; test the resulting EXE/APP too.

Regenerate icons locally after editing the SVG (existing Chrome):

```sh
.venv/bin/python build/generate_icons.py --system-chrome
```

Regenerate the portable source ZIP without downloads:

```sh
.venv/bin/python build/export_source.py
```

## 9. PDF blueprint, licences and data handling

One authoritative HTML/CSS template drives automatic PDF and browser printing.
PDFs include cover/photo, Chinese and English instructions, weekly schedules,
a summary table and a leave-slip page. Teachers sign directly in the relevant
class cells; no separate bottom signature area is added. The original Chinese
wording and roles are retained. It is not a pixel-identical DOCX replica:
seven weekdays/twelve periods preserve portal classes. Absence/leave counts and
signatures remain blank, never inferred from a timetable.

LaTeX is archived only under `reference/latex`, not shipped as a second renderer.
Its compilation was not verified; no TeX engine or first-use TeX downloads are
required by this application.

Noto Serif SC Regular is embedded in the document. Its original font bytes and
internal name/copyright are unchanged; only the local file is named
`AttendanceCJK.otf`. Copyright, upstream source/hash and SIL OFL 1.1 are included
under `app/assets/fonts` and viewable via Font licence / 字体许可.
[SIL OFL source](https://github.com/notofonts/noto-cjk/blob/main/Serif/LICENSE).
The user-supplied university SVG remains the source for the application icon;
no university endorsement is implied.

No application credential store, persistent browser profile or cookie export is
implemented. The student logs in through a fresh browser session; HTTP requests
reuse that context. Do not save session cookies, passwords or raw portal pages in
debug logs. Browser/OS temporary files still exist and are not a claim of
forensic zero-retention.

Weekly retrieval uses normal read-only GETs to the observed timetable pages:
`/py/page/student/grkcb.htm?zc=<week>&xj=<term>&xn=<academic-start-year>`.
Profile name is read from `/allogene/page/userinfo.htm`. No public all-week API was
found in the inspected timetable script; selected weeks are requested sequentially
with a modest delay. There is no access-control bypass, endpoint fuzzing, or
another student’s ID supplied to the portal. Site changes can break parsers.

PDF rendering rejects remote resources and page overflow before replacing the
selected destination. Default-browser export saves self-contained HTML with a
print button; its pagination/save dialog depends on that browser. HTML can be
larger because it embeds the full font. Exported PDF/HTML includes personal
information and the photo: protect it and remove it according to school policy.

Browser preview now fits the paper within 80% of viewport width, centered, with
15 mm internal margins. PDF uses the same A4-landscape layout and shared fit
logic, explicitly in print media rather than screen-preview styles. Dense weeks
can use slightly tighter course typography and bounded scaling (minimum 80%);
no course text is truncated. Extremely oversized content identifies the page/
week in the error and does not replace an existing PDF. The preview reports it
and leaves the overflowing content visible rather than hiding it. Desktop/
narrow-window checks cover 360, 800, 1280 and 1920 pixel widths. The screenshot’s
old generic error indicates the guard found overflow, not the specific cause in
that student's data; a dense synthetic timetable reproduced the same old error.

## 10. Release acceptance checklist

On a clean Windows machine with Microsoft Edge, but without Python/Google Chrome:

- Launch EXE and confirm icon, both interface languages and licence dialog.
- Run demo; import a file, drop a path containing spaces, paste a Chrome-copied
  image while the popup is focused, cancel replacement and remove a photo.
  Test Edge’s Copy image workflow too; installed Chrome is not required.
- Produce a PDF without Internet; inspect Chinese text, photograph proportions,
  long course names, merged cells, blank week, weekend/late periods and pagination.
- Log in as a consenting student and retrieve the complete required range.
- Check session expiry/error/retry, year/term/week changes and no stale export.
- End the session, start a second student, and confirm no previous identity/photo.
- Check save cancellation, overwrite confirmation and filenames with Chinese.
- Inspect the build report and ensure no student data is included in distribution.
- Confirm operational permission, teacher approval, signing and deployment policy.

Until those checks pass, binaries are draft builds, not verified releases.

## 11. Troubleshooting

- **Missing Python environment:** run the platform preparation step yourself;
  do not copy the Mac venv to Windows.
- **Browser launch failed:** confirm Microsoft Edge is installed on Windows,
  or Google Chrome on macOS. School/enterprise policies can block automation.
  The application never downloads browsers or silently falls back to another.
  For explicit testing only, `--browser msedge` / `--browser chrome` overrides
  the platform default; the requested browser must already be installed.
- **Tk/tkdnd errors:** use Python 3.12 with Tk; match OS/architecture, then check
  the pinned tkinterdnd2 native library. Do not try `pip install tkinter`.
- **Wrong dependency versions:** rerun preparation; do not bypass preflight.
- **Login expired / student mismatch:** end the session and have the student
  sign in again. Do not paste cookies or credentials into logs.
- **No clipboard image:** use Chrome’s Copy image, not Copy image address, and
  focus the photo popup. Real Windows clipboard/drop tests remain necessary.
- **PDF overflow:** do not silently clip timetable text. Preserve the source data
  and adjust the template after reviewing the offending content.
- **Blank/wrong week:** inspect the selected year/semester; genuinely empty weeks
  are valid. Academic start year is not always the current calendar year.
- **Packaged crash:** use the Windows console build to inspect the error locally;
  redact personal information before sharing diagnostics.
- **Unsigned app/EXE warning:** arrange signing/approval rather than disabling
  antivirus or system security globally.
