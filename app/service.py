"""Single-thread-owned browser session and read-only student retrieval."""
from __future__ import annotations

from urllib.parse import urlparse
import time

from portal import BASE, Selection, PortalError, read_http, profile_fields
from browser_config import default_channel, launch_browser


class PortalSession:
    def __init__(self, playwright, channel=None):
        self.pw, self.channel = playwright, channel or default_channel()
        self.browser = self.context = self.page = None
        self.student_id = None

    def open(self):
        self.close()
        self.browser = launch_browser(self.pw, self.channel, headless=False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(BASE, wait_until="domcontentloaded", timeout=30000)

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
        if self.browser and self.browser.is_connected():
            self.browser.close()
        self.browser = self.context = self.page = None
        self.student_id = None


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
