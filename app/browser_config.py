"""Installed browser policy shared by login, PDF rendering and build checks."""
import platform

from playwright.sync_api import Error

BROWSER_NAMES = {"msedge": "Microsoft Edge", "chrome": "Google Chrome"}


def default_channel():
    return "msedge" if platform.system() == "Windows" else "chrome"


def launch_browser(playwright, channel=None, *, headless):
    channel = channel or default_channel()
    if channel not in BROWSER_NAMES:
        raise ValueError("Unsupported installed browser / 不支持的已安装浏览器。")
    try:
        return playwright.chromium.launch(channel=channel, headless=headless, timeout=15000)
    except Error as exc:
        name = BROWSER_NAMES[channel]
        raise ValueError(
            f"Could not launch {name}. Install it on this computer and check whether "
            "school/browser policies permit automation. No browser was downloaded. / "
            f"无法启动 {name}。请确认此电脑已安装该浏览器，并检查学校或浏览器策略是否允许自动化。未下载浏览器。"
        ) from exc


def check_browser(playwright, channel=None):
    """Offline launch probe, using a separate browser, never the student's session."""
    channel = channel or default_channel()
    browser = launch_browser(playwright, channel, headless=True)
    try:
        return {"name": BROWSER_NAMES[channel], "version": browser.version}
    finally:
        browser.close()
