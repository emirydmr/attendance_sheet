# Historical attendance portal retrieval prototype

This is the September 2026 Playwright proof of concept, retained for its portal
investigation and parser history. It is not the current AttendanceBook app or a
supported release build. For the current Selenium application, use the
[repository README](../../README.md). The commands and results below describe
this historical prototype only.

At the time, this diagnostic explored retrieval for a planned Tkinter app. It
did not generate PDFs, and its academic forms still needed field mapping. Its
proposed Windows deliverable would have embedded Chromium. The current app uses
Selenium with an installed browser and the maintained HTML/PDF layout.

## Historical run instructions

From `poc/portal-diagnostic/`, use Python 3.12 with Tkinter. Install the
prototype requirements, then run:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium --no-shell
python app.py
```

If Chrome is already installed, use `python app.py --system-chrome` to run
the local diagnostic without downloading Chromium. This uses a new temporary
browser context, not the operator's personal Chrome profile. The prototype's
Windows diagnostic build embedded Chromium and required testing with that engine.

The numbered controls perform visible login, HTTP retrieval comparison,
headless comparison, and student-details retrieval. Academic year is the
**start** year (2026 means 2026–2027).
Semester codes are 11 for first semester, 12 for second, 13 for short term.
Week 1 can legitimately contain no courses; blank schedules are distinguished
from login redirects using the student identity, selected controls and table.

For supervised diagnosis, `--auto-check` opens the student browser and runs
both checks after the student finishes manual sign-in. `--report path.json`
writes only a sanitized result (selected term/week, course count, student number
suffix, pass/failure flags); it does not save HTML, passwords or session state.
English/Chinese applies to GUI controls; developer diagnostic messages currently
use English. The planned product was expected to translate the remaining errors.

`4. Student details (HTTP)` checks the observed portal links for 我的学籍信息,
学籍异动申请 and 个人信息 using the same verified student's session. Requested
name/academic values are displayed to the operator. The saved report retains
only field labels, control identifiers and page readability, not profile values.
专业, 研究方向, and academic 导师 are distinct from the form's fixed 班主任.
`--auto-profile` performs this check after manual login. `--supervised-console`
enables explicit JSON diagnostic commands on stdin for the local supervisor;
this creates no network listener and is unnecessary in the packaged GUI.

The prototype source lives in `poc/portal-diagnostic/` within this repository.
At the time, `run_local.command` opened its GUI on the development Mac with the
installed Chrome and existing environment, without downloading anything.

## What the checks prove

1. The visible browser loads the selected timetable as a baseline.
2. `context.request.get()` retrieves that exact page using the same cookie jar;
   normalized identity, selected year/semester/week, periods and course blocks
   must match the baseline.
3. A separate Chromium process runs with native headless settings and session
   state passed directly in memory. Its rendered page and HTTP request must
   independently match the baseline. The visible session remains available.

The storage replay includes cookies, local storage and IndexedDB. Session
storage or unusual single-use SSO state may need a browser fallback; success on
one page does not establish compatibility of every portal module. The prototype
reads only the selected student's one timetable week, not other students' data.

Each student gets a fresh temporary browser context. End student session closes
the browser and clears the captured baseline. Browser-managed temporary files
are cleaned up by normal closure. No persistent browser profile or explicit
storage-state export is created. After a browser failure the operator can end
the session and open a fresh login window. The diagnostic report is not student
attendance data; export of selected fields was planned for a later app.

## Historical Windows diagnostic build

From `poc/portal-diagnostic/`, run its `build_windows.ps1` on Windows with the
standard Python 3.12 installation (including Tcl/Tk). That prototype script
embedded the full Chromium binary and built:

```text
dist/AttendancePortalDiagnostic.exe
```

That prototype build downloaded packages and Chromium. After adjusting the VPN,
the historical build instructions called for explicitly running
`./build_windows.ps1 -DownloadsReady`; without that switch it only announces
the required downloads and exits. App startup never installs/downloads browsers.

The prototype diagnostic's target machine was not expected to need Python,
Playwright or Chrome installed. Chromium makes the executable large, and
PyInstaller one-file mode extracts runtime resources into a temporary directory
at launch. It does not produce an
installer. The prototype executable needed an actual Windows build and a clean
Windows launch/retrieval check; this source was prepared on macOS.

At the time, the PDF engine and Chinese fonts were still planned for a future
app, and the reference form's 16 weekly pages had not yet been reconciled with
the portal's 20 weeks and seven weekdays. These are historical design notes;
the current document layout is maintained in HTML/CSS.

## Why Playwright

The browser-associated HTTP client and in-memory storage replay fit the
prototype's visible-login/background-retrieval flow directly. The current
application uses Selenium and same-origin requests in the signed-in browser.
The prototype required an authenticated student session before claiming portal
support for headless or HTTP retrieval.

## Observed results on this Mac

The visible student login succeeded on September 28, 2026. For academic year
2026–2027, first semester, week 1, all three comparisons passed:

- HTTP retrieval using the visible browser's session matched its rendered page.
- A new headless browser with in-memory session replay matched that page.
- HTTP retrieval using the headless browser's session also matched that page.

This was tested with the Mac's **installed Chrome**, not the intended embedded
Chromium. Week 1 had zero course entries. Week 3 subsequently passed all three
comparisons with five course blocks. The prototype Windows executable had not
undergone those checks. Ten offline parser checks passed, including merged
course periods, weekend classes, changed student identity, malformed grids,
wrong selected week, rejected login pages, profile
fields and excluded sensitive values.

Authenticated HTTP GETs returned readable HTTP 200 pages for 我的学籍信息,
学籍异动申请 and 个人信息. The personal-information parser extracted 姓名.
Student number, college and major were extracted from the timetable. A separate
Chinese or passport name has not been verified. Academic-form controls were
inventoried, but their values need additional mapping. See `information_map.md`.

The Chromium download failed with a TLS connection reset and was not retried.
No further downloads were needed for these local checks. The private reports were
moved to the repository's ignored `.archive/portal-diagnostic/` directory:
`profile_report.json` contains the sanitized profile/week-3 results and
`session_report.json` contains the earlier GUI check result. They are not
included in Git or release builds.

The prototype left the portal's black/orange/conflict course status indicators
unmapped; it compared course text and positions.

Primary references:

- [Playwright Python packaging and threading](https://playwright.dev/python/docs/library)
- [Browser-associated HTTP cookie management](https://playwright.dev/python/docs/api/class-apirequestcontext)
- [PyInstaller one-file behavior](https://pyinstaller.org/en/stable/operating-mode.html)
