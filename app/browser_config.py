"""Installed browser policy shared by login, PDF rendering and build checks."""

import json
import os
import platform
from pathlib import Path

from playwright.sync_api import Error


BROWSER_NAMES = {"msedge": "Microsoft Edge", "chrome": "Google Chrome"}


def default_channel():
    return "msedge" if platform.system() == "Windows" else "chrome"


def settings_path():
    """Keep browser preferences outside the source tree and frozen executable."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA")
        directory = Path(base) if base else Path.home() / "AppData" / "Local"
    elif system == "Darwin":
        directory = Path.home() / "Library" / "Application Support"
    else:
        directory = Path(os.environ.get("XDG_CONFIG_HOME", str(Path.home() / ".config")))
    return directory / "AttendanceBook" / "browser.json"


def load_browser_executable(channel):
    """Read a previously selected executable; malformed settings are ignored."""
    try:
        data = json.loads(settings_path().read_text(encoding="utf-8"))
        paths = data.get("browser_paths", {})
        if not isinstance(paths, dict):
            return None
        value = paths.get(channel)
        return value if isinstance(value, str) and value else None
    except (OSError, ValueError, TypeError, AttributeError):
        return None


def save_browser_executable(channel, executable_path):
    """Persist a browser path only after the caller has successfully launched it."""
    if channel not in BROWSER_NAMES:
        raise ValueError("Unsupported browser.")
    path = Path(executable_path).expanduser()
    if not path.is_file():
        raise ValueError(f"Browser executable not found: {path}")
    if platform.system() == "Windows" and path.suffix.lower() != ".exe":
        raise ValueError("Select a Windows browser executable (.exe).")

    destination = settings_path()
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        data = json.loads(destination.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            data = {}
    except (OSError, ValueError, TypeError):
        data = {}
    paths = data.get("browser_paths", {})
    if not isinstance(paths, dict):
        paths = {}
    paths[channel] = str(path)
    data["browser_paths"] = paths

    temporary = destination.with_name(destination.name + ".tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        os.replace(temporary, destination)
    finally:
        temporary.unlink(missing_ok=True)


def launch_browser(playwright, channel=None, *, headless, executable_path=None):
    """Prefer a user-selected executable; otherwise use Playwright's channel."""
    channel = channel or default_channel()
    if channel not in BROWSER_NAMES:
        raise ValueError("Unsupported installed browser / 不支持的已安装浏览器。")

    def launch_path(value):
        path = Path(value).expanduser()
        if not path.is_file():
            raise ValueError(f"Browser executable not found: {path}")
        if platform.system() == "Windows" and path.suffix.lower() != ".exe":
            raise ValueError("Select a Windows browser executable (.exe).")
        return playwright.chromium.launch(
            executable_path=str(path), headless=headless, timeout=15000
        )

    if executable_path is not None:
        # An explicit selection must never silently fall back to another browser.
        try:
            return launch_path(executable_path)
        except Error as exc:
            raise ValueError(
                f"Could not launch {BROWSER_NAMES[channel]} using the selected executable. "
                "Check the file and automation policies. No browser was downloaded."
            ) from exc

    preferred = load_browser_executable(channel)
    if preferred:
        try:
            return launch_path(preferred)
        except (Error, ValueError):
            # A saved installation can move or be removed.
            pass

    try:
        return playwright.chromium.launch(channel=channel, headless=headless, timeout=15000)
    except Error as exc:
        name = BROWSER_NAMES[channel]
        raise ValueError(
            f"Could not launch {name}. Locate its executable or check installation and "
            "school/browser automation policies. No browser was downloaded. / "
            f"无法启动 {name}。请检查浏览器安装路径及自动化策略。未下载浏览器。"
        ) from exc


def check_browser(playwright, channel=None, *, executable_path=None):
    """Offline launch probe using a separate browser, never the student's session."""
    channel = channel or default_channel()
    options = {"headless": True}
    if executable_path is not None:
        options["executable_path"] = executable_path
    browser = launch_browser(playwright, channel, **options)
    try:
        return {"name": BROWSER_NAMES[channel], "version": browser.version}
    finally:
        browser.close()
