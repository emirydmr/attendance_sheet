# Attendance portal retrieval prototype

This is the retrieval diagnostic for the planned Tkinter attendance-book app.
It does not yet generate PDFs. The personal-information name parser has been
tested; the academic forms need additional field mapping.
The finished deliverable is intended to be one Windows executable with its own
Chromium browser, English/Chinese GUI, and a self-contained PDF renderer.

## Run

Use Python 3.12 with Tkinter. Install requirements, then run:

```sh
python -m pip install -r requirements.txt
python -m playwright install chromium --no-shell
python app.py
```

If Chrome is already installed, use `python app.py --system-chrome` to run
the local diagnostic without downloading Chromium. This uses a new temporary
browser context, not the operator's personal Chrome profile. The Windows build
still embeds Chromium and must be checked with that bundled engine.

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
use English. The eventual product should translate the remaining error messages.

`4. Student details (HTTP)` checks the observed portal links for 我的学籍信息,
学籍异动申请 and 个人信息 using the same verified student's session. Requested
name/academic values are displayed to the operator. The saved report retains
only field labels, control identifiers and page readability, not profile values.
专业, 研究方向, and academic 导师 are distinct from the form's fixed 班主任.
`--auto-profile` performs this check after manual login. `--supervised-console`
enables explicit JSON diagnostic commands on stdin for the local supervisor;
this creates no network listener and is unnecessary in the packaged GUI.

The project source now lives in `/Users/emirydmr/attendance_sheet/portal-diagnostic/`.
On this Mac, `run_local.command` opens the GUI with the already installed Chrome
and current development environment, without downloading anything.

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
attendance data; a later export step will deliberately save the selected fields.

## Single Windows executable

Run `build_windows.ps1` on Windows with the standard Python 3.12 installation
(including Tcl/Tk). The script embeds the full Chromium binary and builds:

```text
dist/AttendancePortalDiagnostic.exe
```

The build downloads packages and Chromium. After adjusting the VPN, explicitly
run `./build_windows.ps1 -DownloadsReady`; without that switch it only announces
the required downloads and exits. App startup never installs/downloads browsers.

The target machine should not need Python, Playwright or Chrome installed.
Chromium makes the executable large, and PyInstaller one-file mode extracts
runtime resources into a temporary directory at launch. It does not produce an
installer. The executable needs an actual Windows build and a clean-Windows
launch/retrieval check; this source was prepared on macOS.

For the final app, the PDF engine and Chinese fonts must also be embedded;
assumed external LaTeX or font installations would break the one-file goal.
The reference form has 16 weekly pages, while the portal offers up to 20 weeks
and seven weekdays. Those output choices remain requirements to settle.

## Why Playwright

The browser-associated HTTP client and in-memory storage replay fit the
visible-login/background-retrieval flow directly. Selenium is also possible,
but a separate Python requests client would need session synchronization.
No portal-specific claim of headless or HTTP support is made until the checks
actually pass in an authenticated student session.

## Observed results on this Mac

The visible student login succeeded on September 28, 2026. For academic year
2026–2027, first semester, week 1, all three comparisons passed:

- HTTP retrieval using the visible browser's session matched its rendered page.
- A new headless browser with in-memory session replay matched that page.
- HTTP retrieval using the headless browser's session also matched that page.

This was tested with the Mac's **installed Chrome**, not the intended embedded
Chromium. Week 1 had zero course entries. Week 3 subsequently passed all three
comparisons with five course blocks. The packaged Windows executable still
requires actual checks. Ten offline parser checks
passed, including merged course periods, weekend classes, changed student
identity, malformed grids, wrong selected week, rejected login pages, profile
fields and excluded sensitive values.

Authenticated HTTP GETs returned readable HTTP 200 pages for 我的学籍信息,
学籍异动申请 and 个人信息. The personal-information parser extracted 姓名.
Student number, college and major were extracted from the timetable. A separate
Chinese or passport name has not been verified. Academic-form controls were
inventoried, but their values need additional mapping. See `information_map.md`.

The Chromium download failed with a TLS connection reset and was not retried.
No further downloads were needed for these local checks. `profile_report.json`
contains the latest sanitized profile/week-3 results; `session_report.json`
contains the earlier GUI check result.

The portal's black/orange/conflict course status indicators will also need to
be mapped using a populated timetable before choosing which entries belong
in the final attendance book. This diagnostic compares course text/positions.

Primary references:

- [Playwright Python packaging and threading](https://playwright.dev/python/docs/library)
- [Browser-associated HTTP cookie management](https://playwright.dev/python/docs/api/class-apirequestcontext)
- [PyInstaller one-file behavior](https://pyinstaller.org/en/stable/operating-mode.html)
