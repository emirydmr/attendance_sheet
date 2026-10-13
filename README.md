# AttendanceBook / 国际学生考勤册

AttendanceBook prepares international student attendance books for a specific
administrative workflow at Chang'an University: a member of staff runs the app
with the student present, and the student signs in manually to the
[graduate portal](https://yjs.chd.edu.cn). It relies on that portal's student
information and weekly timetable format; it is not a general attendance system.

The app retrieves the student's details and selected teaching weeks, then combines
them with confirmed cover information and a photograph. The resulting book
contains the cover, attendance instructions, weekly schedules, summary table and
leave-slip page. Teachers record attendance by signing the printed class cells.

## Install and run

Download a Windows executable or macOS application ZIP from
[GitHub Releases](https://github.com/emirydmr/attendance_sheet/releases), when a
release is available. On Windows, run `AttendanceBook.exe`; on macOS, extract the
ZIP and keep the complete `AttendanceBook.app` bundle together. Packaged apps
include Python, Tkinter, Selenium, templates, icons and the Chinese font. They
need no separate Python, Node.js or LaTeX installation.

Target platforms are Windows 11 x64 and macOS 14 or newer. Install a supported
browser yourself before use; neither the app nor its driver setup downloads a
full browser. Normal use needs no administrator installation. The macOS build
is unsigned and unnotarized; use your system's approval process for apps from a
trusted source.

### Run from source

Use Python 3.12 with Tkinter. From the repository root, create an environment and
install the pinned dependencies in [requirements.txt](requirements.txt), including
Selenium 4.51.0.

Windows (PowerShell):

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe app/main.py
```

macOS:

```sh
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements.txt
./.venv/bin/python app/main.py
```

Tkinter must come with your Python installation; pip does not install it. Append
`--demo` for fictitious data without portal retrieval. Automated PDF export still needs a configured
browser in demo mode.

## Browser profiles

On first launch, **Browser Settings** opens automatically when no profile is
active. Create a named profile and select an installed browser; the app detects
its executable and chooses the corresponding Selenium driver kind. Click
**Download matching driver** if no compatible driver is installed, then click
**Apply** to use the profile. Apply stays disabled until the browser and driver
match; it never downloads anything. There is no operating-system default browser
choice or browser launch check at startup.

A saved profile is a browser/driver configuration, not a student's saved login.
Keep multiple named configurations and explicitly choose the active one in
Browser Settings. Advanced settings allow executable, driver-kind and manual
driver-path overrides. The dialog's driver library lists installed driver
versions. Different versions can coexist after browser updates. **App cache**
is downloaded by AttendanceBook, **App import** was copied into its storage by
the user, **Shared Selenium** is a cache outside AttendanceBook that other
applications may use, and **System** includes macOS's built-in SafariDriver.
Only app-owned driver versions can be deleted in the dialog; a driver referenced
by a saved profile must be unassigned first. Deleting one version does not
remove other versions or the browser itself.

| Installed browser | Driver | Attendance-book export |
| --- | --- | --- |
| Google Chrome | ChromeDriver | Headless PDF through CDP |
| Microsoft Edge | EdgeDriver | Headless PDF through CDP |
| Mozilla Firefox | GeckoDriver | PDF through WebDriver `print_page`, when available |
| Safari (macOS) | Built-in SafariDriver | HTML preview and manual printing; no unattended PDF export |
| Chromium, 360e or another custom build | Compatible driver required | Experimental; login and PDF compatibility are not guaranteed |

For Safari, enable **Safari → Settings → Developer → Allow remote automation**
before use; the Developer menu may first need enabling in Safari settings.
Its one-time system setup may require administrator approval. Driver downloads
require network access. For offline or restricted machines, import a compatible
driver manually. A browser update may require a new matching driver. The explicit
Download action shows an activity window and elapsed time; Selenium Manager does
not provide reliable byte-by-byte progress to this interface. Opening a browser
does not download a driver.

Configuration and cached drivers are stored outside the app and repository:

- Windows: `%LOCALAPPDATA%\AttendanceBook`
- macOS: `~/Library/Application Support/AttendanceBook`

Chrome, Edge and Firefox login sessions use temporary browser state separately
from those saved configurations. Safari manages its own automation session.
A failed browser or driver never triggers an automatic switch to another browser.
Switching profiles ends the current student session and clears retrieved results.
PDF export uses the selected profile as well.

## Create an attendance book

1. Configure and select a profile in **Browser Settings**.
2. Click **Open browser / log in**. Have the student complete the university
   sign-in and enter the graduate portal. Keep that browser window open during
   retrieval.
3. Select the academic start year, semester and inclusive teaching-week range.
   For 2026–2027, enter **2026**. Weeks run from 1 to 20; the default is 1–18.
   Semester choices map to the portal automatically.
4. Retrieve student number/major, student name and weekly timetables using their
   separate controls. Inspect the result statuses before continuing.
5. Confirm the Chinese name, passport name, cover major, 班主任, contact number and
   issue date. The portal's generic 姓名 field does not determine whether a name
   is Chinese or a passport name.
6. Add a photograph from a file, by dragging a local image into the photo popup,
   or by using **Copy image** in the browser and pasting into the active popup
   with Ctrl+V / Command+V. Copying an image address is not supported.
7. Click **Create PDF** and choose a destination. The suggested filename is
   `<student_id>_长安大学国际学生考勤册.pdf`. Alternatively, choose
   **Open in default browser / print…** to save an HTML preview and print it
   yourself. This explicit preview action uses the system's default browser.
8. Click **End student session** before working with another student.

Empty weeks are valid. **Omit empty weeks / 省略无课周** is on by default and
affects the document and summary only: every selected week is still retrieved
and validated, and retained weeks keep their original numbers. Changing the
academic year or semester clears retrieved results; changing the range clears
timetables. The issue date defaults to today and prints as year/month on the cover.

## How it works

Selenium controls the chosen installed browser while the student signs in
manually. Retrieval runs same-origin `fetch()` calls inside the logged-in portal
tab, so requests use the browser's authenticated session. The browser stays open;
selected weeks are requested sequentially. Existing HTML parsers verify the
student identity and returned academic year, semester and week. A login page,
unexpected response or incomplete scan is not accepted as an empty timetable.

The sole maintained document layout is
[HTML/CSS](app/templates/attendance_blueprint.html), with shared
[layout logic](app/templates/layout.js) and the bundled Chinese font. Selenium
prints the same layout using the selected browser's supported PDF mechanism.
Output is A4 landscape, with oversized content reported rather than silently
clipped. There is no LaTeX rendering step or Playwright/Node.js runtime.

Core code: [interface](app/main.py), [browser profiles](app/browser_config.py),
[portal session](app/service.py), [HTML parsers](app/portal.py) and
[document generation](app/document.py). Build resources live under [build](build);
the older LaTeX draft has been retired.

## Build and GitHub releases

Build on the target operating system with Python 3.12 and Tkinter. On Windows,
prepare the dependencies once, then package the executable:

```powershell
.\build\windows\build_windows.ps1 -Prepare -DownloadsReady
.\build\windows\build_windows.ps1
```

Output: `build/windows/dist/AttendanceBook.exe`. See the
[Windows build guide](build/windows/README.md) for diagnostic options.

macOS has a separate dependency preparation step:

```sh
./build/macos/build_macos.command --prepare --downloads-ready
./build/macos/build_macos.command
```

Output: `build/macos/dist/AttendanceBook.app` and an architecture-specific ZIP
alongside it. See the
[macOS build guide](build/macos/README.md) for Python selection and distribution.
Build environments, reports and generated files remain in their platform build
directories. Packaging does not select the user's runtime browser or bundle one.

The [GitHub workflow](.github/workflows/build-release.yml) produces Windows x64
and macOS Apple Silicon packages. Pushes to `main`, pull requests and manual runs
produce downloadable [Actions artifacts](https://github.com/emirydmr/attendance_sheet/actions).
Pushing a version tag matching `v*` automatically publishes a GitHub Release
after both builds pass, attaching the packages, SHA-256 checksums and build
reports. Test the target machines before pushing a version tag. Intel Macs
require a separate local build
with an Intel Python installation. No repository secrets are needed; the
workflow uses GitHub's built-in token.

Each push to `main` starts an Actions build; completed runs provide artifacts
retained for 14 days, but not a permanent Release. A newer push may cancel an
unfinished run. To publish a chosen, tested commit as a
Release, tag it and push the tag; for example:

```sh
git tag v0.1.0
git push origin v0.1.0
```

Use the next unused version number and check the Actions run before sharing the
Release link. Tags point to a specific commit, so a Release does not silently
change when later commits are pushed.

CI runs a local browser, cookie and PDF smoke check against loopback fixtures;
it does not sign in to the university portal. For an opt-in, student-present
check on a target machine, use a saved browser profile ID from the app's
`browser_profiles.json` (Safari is excluded because it cannot use the isolated
temporary profile required by this check) and run:

```sh
python tests/manual/live_portal_smoke.py --run-live --profile-id PROFILE_ID --year 2026 --term 11 --week 1
```

The script requires an interactive confirmation, opens a fresh temporary
browser, waits for manual sign-in, checks one timetable and the known profile
page, then closes the session. It prints only pass/fail status, not student
details. It never runs as part of CI or the default unit tests.

### Optional developer helpers

An optional portable source archive can be generated with
`python build/export_source.py` using a prepared environment. Its output is
`build/source/AttendanceBook-source.zip`.
The icon generator (`build/generate_icons.py`) and layout/omission QA scripts
([tests/manual/check_layout.py](tests/manual/check_layout.py),
[tests/manual/check_omit_empty.py](tests/manual/check_omit_empty.py)) are development tools,
not alternative release builders. They use an explicitly configured local
browser and do not download one. The [test map](tests/README.md) separates
routine checks from opt-in browser and live-portal checks.

## Limitations and troubleshooting

- This app depends on Chang'an University's graduate portal HTML and login
  behavior. A portal change or expired session can require signing in again or
  updating the parsers. Check the academic selection before retrieving again.
- If a browser fails, check its executable, driver compatibility and automation
  policies in Browser Settings. Choose another installed profile explicitly if
  needed. Custom Chromium/360e builds remain experimental.
- Firefox PDF support depends on the installed browser/driver. Safari requires
  HTML/manual printing. The app never silently chooses another browser for PDF.
- Hosted build checks do not establish successful student login, complete live
  retrieval or operation on the teacher's Windows computer. Clean-machine
  validation, native clipboard/drop behavior and final printed layout still need
  checking before distribution; signing and notarization are not configured.
- For PDF overflow, inspect the reported page/week and its course content. For
  packaging errors, inspect the platform build report or use the Windows console
  build described in its guide.

## Licensing

The application does not yet declare a source-code licence. The bundled Noto
Serif SC font uses SIL Open Font License 1.1; its licence and provenance are in
[app/assets/fonts](app/assets/fonts) and available through **Font licence / 字体许可**
in the app.

## Author

Emir Aydemir · Chang'an University

[aydemir.emir@icloud.com](mailto:aydemir.emir@icloud.com)
