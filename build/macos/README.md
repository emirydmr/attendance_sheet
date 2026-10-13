# macOS development and build

Use macOS 14 or newer and Python 3.12 with Tkinter. From the repository root,
prepare the build environment, then build:

```sh
./build/macos/build_macos.command --prepare --downloads-ready
./build/macos/build_macos.command
```

Preparation creates `build/macos/.venv` and installs the pinned runtime/build
packages. `--downloads-ready` allows those Python dependency downloads; it does
not download a browser. If `python3` is not Python 3.12 with Tkinter, select an
appropriate interpreter explicitly:

```sh
PYTHON_BIN=/path/to/python3.12 ./build/macos/build_macos.command --prepare --downloads-ready
```

To run from the prepared environment:

```sh
./build/macos/.venv/bin/python app/main.py
./build/macos/.venv/bin/python app/main.py --demo
```

Demo mode uses fictitious data without portal retrieval; automatic PDF export
still needs a configured browser. For preflight without packaging:

```sh
./build/macos/build_macos.command --check
```

## Output and distribution

Outputs: `build/macos/dist/AttendanceBook.app` and
`build/macos/dist/AttendanceBook-macos-arm64.zip` on Apple Silicon, or
`AttendanceBook-macos-x86_64.zip` on Intel. The build runs repository checks
and bundles Python/Tkinter, Selenium, templates, icons, the Chinese font and
drag-and-drop support. There is no Playwright/Node.js runtime or bundled browser.
Generated specifications, work files, reports and the environment stay under
`build/macos/`. Packaging does not inspect an installed browser by default.
Distribute the generated ZIP, which preserves macOS application metadata, or
keep the entire `.app` together when copying it.

Build Apple Silicon and Intel versions separately using Python for the matching
architecture. The GitHub workflow targets Apple Silicon. Builds are unsigned and
unnotarized; recipients must approve the app through macOS's normal process for
software they trust. Packaging success does not establish live portal retrieval
or final printed layout on another computer.

## Browser setup

Install the browser yourself. **Browser Settings** opens automatically when no
profile is active. Create a named profile and select the browser; the app detects
its executable and chooses the driver kind. If a matching driver is missing,
click **Download matching driver** first; **Apply** uses only installed drivers
and stays disabled until one matches. Advanced overrides and the driver
library allow manual setup. Configuration and cached drivers live in
`~/Library/Application Support/AttendanceBook`; normal app use needs no
administrator installation. A build does not assign a runtime browser default,
and a failed browser/driver never causes a switch to another browser.

Chrome and Edge support headless PDF export. Firefox uses WebDriver `print_page`
when available. Safari requires **Safari → Settings → Developer → Allow remote automation** first
(one-time system setup may need administrator approval) and supports login with
HTML preview/manual printing, not unattended PDF export. Custom Chromium/360e
builds need compatible drivers and remain experimental. Driver acquisition
downloads drivers only, never a full browser.

See the [repository README](../../README.md) for the student-present workflow,
[GitHub releases](https://github.com/emirydmr/attendance_sheet/releases) and known
limitations.
