"""Installed-browser QA helpers; importing this module never starts a browser.

ATTENDANCE_SMOKE_PROFILE selects an absolute profile JSON file. Otherwise,
ATTENDANCE_SMOKE_BROWSER selects a detected browser (test-only default: chrome).
Drivers must already be available: these QA scripts never download anything or
read/write the app's saved active profile. All documents use offline file URLs.
"""
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))

from browser_config import detect_browsers, launch_browser, resolve_profile
from document import browser_html

CHROMIUM_DRIVERS = {"chromedriver", "msedgedriver"}


def smoke_profile(*, require_chromium=False):
    """Resolve one explicit test configuration without downloading or persisting."""
    source = os.environ.get("ATTENDANCE_SMOKE_PROFILE")
    if source is not None:
        path = Path(source).expanduser()
        if not source or not path.is_absolute():
            raise ValueError("ATTENDANCE_SMOKE_PROFILE must be an absolute JSON file path.")
        profile = json.loads(path.read_text(encoding="utf-8"))
    else:
        selected = os.environ.get("ATTENDANCE_SMOKE_BROWSER", "chrome").strip().lower()
        profile = next((item for item in detect_browsers() if item["browser"] == selected), None)
        if profile is None:
            raise ValueError(f"Selected QA browser {selected!r} is not installed; no fallback or download.")
        profile = {**profile, "id": f"qa-{selected}", "name": f"QA {selected}"}
    if not isinstance(profile, dict):
        raise ValueError("QA browser profile must be a JSON object.")
    if profile.get("driver_kind") == "safaridriver" or profile.get("browser") == "safari":
        raise ValueError("Safari cannot run these headless PDF QA scripts.")
    if require_chromium and profile.get("driver_kind") not in CHROMIUM_DRIVERS:
        raise ValueError("Print-media layout QA requires an explicit Chrome/Edge-compatible profile.")
    return resolve_profile(profile, allow_download=False)


@contextmanager
def headless_browser(profile):
    """Keep browser data temporary and clean it up after the browser exits."""
    with tempfile.TemporaryDirectory(prefix="attendance-qa-profile-") as directory:
        browser = launch_browser(profile, headless=True, profile_dir=directory)
        try:
            browser.set_page_load_timeout(30)
            browser.set_script_timeout(30)
            if profile["driver_kind"] in CHROMIUM_DRIVERS:
                browser.execute_cdp_cmd("Network.enable", {})
                browser.execute_cdp_cmd("Network.setBlockedURLs", {"urls": ["http://*", "https://*"]})
            yield browser
        finally:
            browser.quit()


@contextmanager
def preview_document(browser, data):
    """Load browser_html under its offline CSP and await layout/fonts/photos."""
    html = browser_html(data)
    assert "Content-Security-Policy" in html and "default-src 'none'" in html
    # Install error listeners before the layout script without weakening its CSP.
    capture = """<script nonce='attendanceprint'>
      window.attendanceQaErrors = [];
      addEventListener('error', event => window.attendanceQaErrors.push(event.message));
      addEventListener('unhandledrejection', event => window.attendanceQaErrors.push(String(event.reason)));
    </script>"""
    html = html.replace("<body>", "<body>" + capture, 1)
    with tempfile.TemporaryDirectory(prefix="attendance-qa-html-") as directory:
        source = Path(directory) / "attendance.html"
        source.write_text(html, encoding="utf-8")
        browser.get(source.as_uri())
        result = browser.execute_async_script("""
          const done = arguments[arguments.length - 1];
          if (!window.attendanceLayoutReady) {
            done({error: 'Attendance layout readiness promise is missing'});
            return;
          }
          Promise.resolve(window.attendanceLayoutReady).then(async layout => {
            await Promise.all(Array.from(document.images, image => image.decode()));
            done({layout});
          }).catch(error => done({error: String(error)}));
        """)
        assert isinstance(result, dict) and "layout" in result, result
        assert browser.execute_script("return Array.from(document.fonts).every(f => f.status === 'loaded')")
        assert browser.execute_script("return Array.from(document.images).every(i => i.complete && i.naturalWidth > 0)")
        yield result["layout"]
        errors = browser.execute_script("return window.attendanceQaErrors")
        assert not errors, errors
