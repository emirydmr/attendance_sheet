"""Single-thread-owned browser session and read-only student retrieval."""
from __future__ import annotations

from urllib.parse import urlparse
import re
import tempfile
import time

from playwright.sync_api import Error as PlaywrightError

from portal import BASE, Selection, PortalError, read_http, profile_fields
from browser_config import default_channel, launch_login_context


class PortalSession:
    def __init__(self, playwright, channel=None):
        self.pw, self.channel = playwright, channel or default_channel()
        self.browser = self.context = self.page = None
        self._profile = None
        self.student_id = None
        self.network_issues = []
        self.request_responses = []
        self.pending_requests = {}

    def _request_started(self, request):
        if request.resource_type in ("document", "xhr", "fetch"):
            host = urlparse(request.url).hostname or "unknown"
            self.pending_requests[id(request)] = (host, request.resource_type, time.monotonic())

    def _request_finished(self, request):
        self.pending_requests.pop(id(request), None)

    def _request_failed(self, request):
        self.pending_requests.pop(id(request), None)
        # Record only host and Chromium error code, never URL, headers or body.
        failure = request.failure or ""
        match = re.search(r"net::ERR_[A-Z0-9_]+", failure)
        if match:
            host = urlparse(request.url).hostname or "unknown"
            self.network_issues.append(f"{host}: {match.group()}")
            self.network_issues = self.network_issues[-8:]

    def _response_received(self, response):
        if response.request.resource_type in ("document", "xhr", "fetch"):
            host = urlparse(response.url).hostname or "unknown"
            self.request_responses.append(
                f"{host} ({response.request.resource_type}): HTTP {response.status}")
            self.request_responses = self.request_responses[-12:]
        if response.status >= 400 and response.request.resource_type in ("document", "xhr", "fetch"):
            host = urlparse(response.url).hostname or "unknown"
            self.network_issues.append(f"{host}: HTTP {response.status}")
            self.network_issues = self.network_issues[-8:]

    def open(self):
        self.close()
        self._profile = tempfile.TemporaryDirectory(prefix="attendance-login-")
        try:
            self.context = launch_login_context(self.pw, self._profile.name, self.channel)
        except Exception:
            self.close()
            raise
        self.context.on("request", self._request_started)
        self.context.on("requestfinished", self._request_finished)
        self.context.on("requestfailed", self._request_failed)
        self.context.on("response", self._response_received)
        self.page = self.context.pages[0] if self.context.pages else self.context.new_page()
        self.page.goto(BASE, wait_until="domcontentloaded", timeout=30000)

    def diagnose_login(self):
        """Report browser events without starting another network request."""
        if not self.context or not self.page or self.page.is_closed():
            raise PortalError("Open the login browser first / 请先打开登录页面。")
        now = time.monotonic()
        pending = [f"{host} ({kind}): {int(now - started)}s"
                   for host, kind, started in self.pending_requests.values()]
        return {"page_host": urlparse(self.page.url).hostname or "unknown",
                "request_responses": list(self.request_responses),
                "pending_requests": pending[-8:],
                "network_issues": list(self.network_issues)}

    def identity(self, year, term):
        if not self.context:
            raise PortalError("Open the login browser first / 请先打开登录页面。")
        result = read_http(self.context, Selection(year, term, 1))
        sid = result["identity"]["学号"]
        if self.student_id is not None and self.student_id != sid:
            raise PortalError("Student changed. Start a new session / 学生已更换，请重新开始。")
        self.student_id = sid
        return {"student_id": sid, "major": result["identity"]["专业"],
                "college": result["identity"].get("学院", "")}

    def names(self, year, term):
        self.identity(year, term)
        response = self.context.request.get(BASE + "/allogene/page/userinfo.htm", timeout=25000)
        try:
            if response.status != 200 or urlparse(response.url).hostname != "yjs.chd.edu.cn":
                raise PortalError("Sign-in expired / 登录已失效。")
            details, _ = profile_fields(response.text())
            if not details.get("recorded_name"):
                raise PortalError("Name field missing / 未找到姓名字段。")
            return {k: v for k, v in details.items() if k in ("recorded_name", "chinese_name", "passport_name")}
        finally:
            response.dispose()

    def timetables(self, year, term, first, last, progress):
        self.identity(year, term)
        weeks = []
        for number in range(first, last + 1):
            result = read_http(self.context, Selection(year, term, number))
            if result["identity"]["学号"] != self.student_id:
                raise PortalError("Student identity mismatch / 学号不一致。")
            weeks.append(result)
            progress(number, last)
            if number != last:
                time.sleep(.35)  # Sequential, modest-rate requests; no probing.
        return weeks  # Partial retrieval never becomes a successful result.

    def close(self):
        try:
            if self.context:
                try:
                    self.context.close()
                except PlaywrightError:
                    # The student may already have closed the browser window.
                    pass
            if self.browser and self.browser.is_connected():
                self.browser.close()
        finally:
            if self._profile:
                self._profile.cleanup()
            self._profile = None
            self.browser = self.context = self.page = None
            self.student_id = None
            self.network_issues = []
            self.request_responses = []
            self.pending_requests = {}


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
