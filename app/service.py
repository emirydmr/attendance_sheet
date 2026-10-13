"""Single-thread-owned Selenium session and read-only student retrieval."""
from __future__ import annotations
from urllib.parse import urlparse
import tempfile
import time
from selenium.common.exceptions import TimeoutException, WebDriverException
from portal import BASE, Selection, PortalError, read_http, profile_fields, BrowserPortalClient
from browser_config import launch_browser


class PortalSession:
    def __init__(self, profile=None):
        self.profile = profile
        self.driver = self.client = self._profile = None
        self.student_id = None

    def open(self):
        self.close()
        if not self.profile:
            raise PortalError("Select a browser profile first / 请先选择浏览器配置。")
        self._profile = tempfile.TemporaryDirectory(prefix="attendance-login-")
        try:
            self.driver = launch_browser(self.profile, headless=False, profile_dir=self._profile.name)
            self.driver.set_page_load_timeout(30)
            self.driver.set_script_timeout(30)
            self.client = BrowserPortalClient(self.driver)
            try:
                self.driver.get(BASE)
            except TimeoutException:
                return {"navigation_timeout": True}  # Keep visible window for manual login/refresh.
            return {"navigation_timeout": False}
        except Exception:
            self.close()
            raise

    def diagnose_login(self):
        """Passive state only: never send a probe or claim authentication."""
        if not self.driver:
            raise PortalError("Open the login browser first / 请先打开登录页面。")
        state = self.driver.execute_script("""
            return {readyState: document.readyState,
                    resources: performance.getEntriesByType('resource').slice(-12).map(r => {
                        let host; try {host = new URL(r.name).hostname} catch (_) {host = 'unknown'}
                        return {host, kind: r.initiatorType, duration: Math.round(r.duration)};
                    })};
        """)
        return {"page_host": urlparse(self.driver.current_url).hostname or "unknown",
                "page_state": state["readyState"],
                "request_responses": list(self.client.observations), "resources": state["resources"]}

    def identity(self, year, term):
        if not self.client:
            raise PortalError("Open the login browser first / 请先打开登录页面。")
        result = read_http(self.client, Selection(year, term, 1))
        sid = result["identity"]["学号"]
        if self.student_id is not None and self.student_id != sid:
            raise PortalError("Student changed. Start a new session / 学生已更换，请重新开始。")
        self.student_id = sid
        return {"student_id": sid, "major": result["identity"]["专业"],
                "college": result["identity"].get("学院", "")}

    def names(self, year, term):
        self.identity(year, term)
        details, _ = profile_fields(self.client.get(BASE + "/allogene/page/userinfo.htm"))
        if not details.get("recorded_name"):
            raise PortalError("Name field missing / 未找到姓名字段。")
        return {k: v for k, v in details.items() if k in ("recorded_name", "chinese_name", "passport_name")}

    def timetables(self, year, term, first, last, progress):
        self.identity(year, term)
        weeks = []
        for number in range(first, last + 1):
            result = read_http(self.client, Selection(year, term, number))
            if result["identity"]["学号"] != self.student_id:
                raise PortalError("Student identity mismatch / 学号不一致。")
            weeks.append(result)
            progress(number, last)
            if number != last:
                time.sleep(.35)
        return weeks  # Partial retrieval never becomes a successful result.

    def close(self):
        driver, folder = self.driver, self._profile
        self.driver = self.client = self._profile = None
        self.student_id = None
        try:
            if driver:
                try:
                    driver.quit()
                except WebDriverException:
                    pass
        finally:
            if folder:
                folder.cleanup()


def demo_identity():
    return {"student_id": "DEMO001", "major": "计算机科学与技术", "college": "示例学院"}


def demo_weeks(year, term, first, last):
    identity = {"学号": "DEMO001", "专业": "计算机科学与技术", "学院": "示例学院"}
    return [{"identity": identity.copy(), "selection": {"year": year, "semester": term, "week": n},
             "classes": [] if n == 1 else [
                 {"day": 3, "day_span": 1, "first_period": 1, "period_count": 4,
                  "text": "示例课程：汉语语言（一）\n第1节—第4节\n示例教师 / 示例教室"},
                 {"day": 2, "day_span": 1, "first_period": 9, "period_count": 2,
                  "text": "示例课程：高级算法设计与分析\n第9节—第10节"},
                 {"day": 6, "day_span": 1, "first_period": 11, "period_count": 2,
                  "text": "示例周末课程\n第11节—第12节"}],
             "periods": [str(p) for p in range(1, 13)], "heading": "示例课表"}
            for n in range(first, last + 1)]
