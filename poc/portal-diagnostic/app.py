"""Tkinter retrieval diagnostic for the CHD graduate portal.

The student signs in in a visible browser. This app never reads login inputs.
Authenticated HTML retrieval and headless replay are compared to a visible
browser baseline. Storage state is passed directly in memory, never exported.
"""
from __future__ import annotations

import argparse
import json
import os
import queue
import re
import threading
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode, urlparse

# A packaged Windows application uses its embedded browser, not installed Chrome.
import sys
if getattr(sys, "frozen", False):
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = "0"

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

BASE = "https://yjs.chd.edu.cn"
TIMETABLE = BASE + "/py/page/student/grkcb.htm"
ENGINE_CHANNEL = "chromium"
PROFILE_PAGES = (
    ("我的学籍信息", "/gl/page/student/studentBaseOne.htm"),
    ("学籍异动申请", "/gl/page/student/studentException.htm"),
    ("个人信息", "/allogene/page/userinfo.htm"),
)
PROFILE_FIELDS = {
    "student_number": ("学号",),
    "recorded_name": ("姓名", "学生姓名"),
    "chinese_name": ("中文名", "中文姓名"),
    "english_name": ("英文名", "英文姓名", "外文姓名", "外文名"),
    "passport_name": ("护照名", "护照姓名"),
    "major": ("专业", "专业名称", "学科专业", "所学专业"),
    "college": ("学院", "院系", "所属学院", "学院名称"),
    "research_direction": ("研究方向", "方向"),
    "grade": ("年级", "入学年份", "入学年度"),
    "academic_supervisor": ("导师", "导师姓名", "指导教师", "指导老师"),
}


def canonical_label(text):
    text = re.split(r"[（(]", text, maxsplit=1)[0]
    return re.sub(r"[\s*：:]", "", text)


def profile_fields(html):
    """Extract only requested academic/name fields, plus a value-free structure map."""
    soup = BeautifulSoup(html, "html.parser")
    aliases = {label: key for key, labels in PROFILE_FIELDS.items() for label in labels}
    details, sources = {}, {}

    def value_of(element):
        if element is None:
            return "", None
        control = element if element.name in ("input", "select", "textarea") else element.find(
            ["input", "select", "textarea"])
        if control:
            if control.name == "input":
                if control.get("type", "").lower() in ("password", "hidden"):
                    return "", None
                value = control.get("value", "").strip()
            elif control.name == "select":
                option = control.find("option", selected=True)
                value = clean_text(option) if option else ""
            else:
                value = clean_text(control)
            return value, {"tag": control.name, "name": control.get("name", ""),
                           "id": control.get("id", "")}
        return clean_text(element), {"tag": element.name}

    candidates = soup.select("label, .control-label, th, td")
    for label in candidates:
        original = clean_text(label)
        key = aliases.get(canonical_label(original))
        if key is None:
            continue
        target = soup.find(id=label.get("for")) if label.get("for") else None
        if target is None:
            target = label.find_next_sibling()
        if target is None and label.parent:
            target = label.parent.select_one(".controls, input, select, textarea")
        value, locator = value_of(target)
        if locator is not None:
            sources.setdefault(key, []).append({"label": original, **locator,
                                               "value_present": bool(value)})
        if value and key not in details:
            details[key] = value
    # Some read-only pages print label and value together inside one cell.
    for element in soup.select("td, .control-group, .form-group"):
        text = clean_text(element)
        for alias, key in aliases.items():
            match = re.fullmatch(re.escape(alias) + r"\s*[：:]\s*(.+)", text)
            if match and key not in details and len(match.group(1)) <= 100:
                details[key] = match.group(1).strip()
                sources.setdefault(key, []).append({"label": alias, "tag": element.name,
                                                   "value_present": True})
    controls = [{"tag": c.name, "name": c.get("name", ""), "id": c.get("id", ""),
                 "type": c.get("type", "")} for c in soup.select("input, select, textarea")
                if c.get("type", "").lower() not in ("password", "hidden")]
    links = []
    for a in soup.select("a[href]"):
        href = a.get("href", "")
        parsed = urlparse(href)
        if (not parsed.hostname or parsed.hostname == "yjs.chd.edu.cn") and parsed.path.startswith(
                ("/gl/page/student/", "/allogene/page/")):
            links.append({"text": clean_text(a), "path": parsed.path})
    return details, {"fields": sources, "controls": controls, "links": links}


class PortalError(Exception):
    """A public error message containing no session headers or response body."""


@dataclass(frozen=True)
class Selection:
    year: int = 2026
    term: int = 11
    week: int = 1

    def __post_init__(self):
        if not (2003 <= self.year <= 2100 and self.term in (11, 12, 13)
                and 1 <= self.week <= 20):
            raise PortalError("Invalid academic year, semester, or week.")

    @property
    def url(self):
        return TIMETABLE + "?" + urlencode(
            {"zc": self.week, "xj": self.term, "xn": self.year})


def clean_text(element):
    return " ".join(element.get_text(" ", strip=True).split())


def parse_timetable(html, selection):
    """Require a student identity and the exact selected timetable.

    Blank course cells are valid. A login/error page is never an empty schedule.
    Expand row/column spans so a merged class retains its day and periods.
    """
    soup = BeautifulSoup(html, "html.parser")
    table = soup.select_one("table.table-course")
    if table is None:
        raise PortalError("No timetable found; sign in or complete portal authorization.")
    identity = {}
    for label in soup.select(".control-group label"):
        value = label.find_next_sibling("span")
        if value is not None:
            identity[clean_text(label).rstrip("：:")] = clean_text(value)
    if not identity.get("学号") or not identity.get("专业"):
        raise PortalError("Timetable identity is missing; refusing to accept this response.")
    for name, expected in (("xn", selection.year), ("xj", selection.term),
                           ("zc", selection.week)):
        select = soup.select_one(f"select#{name}")
        option = select.select_one("option[selected]") if select else None
        if option is None or option.get("value") != str(expected):
            raise PortalError("Response has different year/semester/week selections.")
    rows = table.find_all("tr")
    if len(rows) != 13:
        raise PortalError("Unexpected timetable row count; parser needs inspection.")
    header = [clean_text(c) for c in rows[0].find_all(["th", "td"], recursive=False)]
    days = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
    if header[-7:] != days:
        raise PortalError("Unexpected weekday headers; parser needs inspection.")
    occupied = set()
    classes = []
    periods = []
    for ri, row in enumerate(rows):
        col = 0
        for cell in row.find_all(["th", "td"], recursive=False):
            while (ri, col) in occupied:
                col += 1
            rs, cs = int(cell.get("rowspan", 1)), int(cell.get("colspan", 1))
            if rs < 1 or cs < 1 or col + cs > 9 or ri + rs > 13:
                raise PortalError("Unexpected timetable cell span.")
            for rr in range(ri, ri + rs):
                for cc in range(col, col + cs):
                    if (rr, cc) in occupied:
                        raise PortalError("Overlapping timetable cell spans.")
                    occupied.add((rr, cc))
            text = clean_text(cell)
            if ri and col == 1:
                periods.append(text)
            if ri and col >= 2 and text:
                classes.append({"day": col - 1, "day_span": cs,
                                "first_period": ri, "period_count": rs,
                                "text": text})
            col += cs
    if len(occupied) != 13 * 9 or len(periods) != 12:
        raise PortalError("Incomplete timetable grid; refusing partial extraction.")
    heading = soup.find("h3")
    return {"identity": identity, "heading": clean_text(heading) if heading else "",
            "selection": {"year": selection.year, "semester": selection.term,
                          "week": selection.week}, "periods": periods, "classes": classes}


def assert_match(actual, baseline):
    if actual != baseline:
        raise PortalError("Response differs from the visible timetable baseline.")


def read_http(context, selection):
    response = context.request.get(selection.url, timeout=25000)
    try:
        if response.status != 200 or urlparse(response.url).hostname != "yjs.chd.edu.cn":
            raise PortalError("HTTP retrieval was redirected or rejected by the portal.")
        return parse_timetable(response.text(), selection)
    finally:
        response.dispose()


def launch(playwright, headless):
    # Use the same full bundled Chromium binary in both modes (new headless).
    return playwright.chromium.launch(channel=ENGINE_CHANNEL, headless=headless)


class Session:
    def __init__(self, playwright):
        self.pw = playwright
        self.browser = None
        self.context = None
        self.page = None
        self.baseline = None
        self.selection = None

    def open(self):
        self.end()
        self.browser = launch(self.pw, False)
        self.context = self.browser.new_context()
        self.page = self.context.new_page()
        self.page.goto(BASE + "/", wait_until="domcontentloaded", timeout=30000)

    def logged_in(self):
        if not self.page or self.page.is_closed():
            return False
        return (urlparse(self.page.url).hostname == "yjs.chd.edu.cn" and
                self.page.locator('a[href="/allogene/page/home.htm"]').count() > 0)

    def baseline_read(self, selection):
        if not self.context:
            raise PortalError("Open the student login browser first.")
        if not self.logged_in():
            raise PortalError("Please complete sign-in in the browser first.")
        self.page.goto(selection.url, wait_until="domcontentloaded", timeout=30000)
        self.baseline = parse_timetable(self.page.content(), selection)
        self.selection = selection
        return self.baseline

    def http_check(self, selection):
        if not self.baseline or self.selection != selection:
            self.baseline_read(selection)
        result = read_http(self.context, selection)
        assert_match(result, self.baseline)
        return {"http_matches_visible": True, "selection": result["selection"],
                "student_suffix": result["identity"]["学号"][-4:],
                "course_blocks": len(result["classes"])}

    def headless_check(self, selection):
        if not self.baseline or self.selection != selection:
            self.baseline_read(selection)
        # Only this app's dedicated student context is used; no personal profile.
        state = self.context.storage_state(indexed_db=True)
        hidden = launch(self.pw, True)
        try:
            context = hidden.new_context(storage_state=state)
            del state
            page = context.new_page()
            page.goto(selection.url, wait_until="domcontentloaded", timeout=30000)
            result = parse_timetable(page.content(), selection)
            assert_match(result, self.baseline)
            http_result = read_http(context, selection)
            assert_match(http_result, self.baseline)
            return {"headless_page_matches_visible": True,
                    "headless_http_matches_visible": True,
                    "native_headless_user_agent": True,
                    "selection": result["selection"],
                    "course_blocks": len(result["classes"])}
        finally:
            hidden.close()

    def profile_check(self, selection):
        self.http_check(selection)  # Verify the active student's session first.
        checked_id = self.baseline["identity"]["学号"]
        pages = []
        for label, path in PROFILE_PAGES:
            response = self.context.request.get(BASE + path, timeout=25000)
            try:
                meta = {"page": label, "path": path, "status": response.status,
                        "final_host": urlparse(response.url).hostname}
                if response.status != 200 or meta["final_host"] != "yjs.chd.edu.cn":
                    meta["readable"] = False
                    meta["reason"] = "Authentication redirect or rejected response"
                    pages.append({"metadata": meta, "details": {}})
                    continue
                details, structure = profile_fields(response.text())
                if details.get("student_number") and details["student_number"] != checked_id:
                    raise PortalError("Profile belongs to a different student; extraction stopped.")
                meta.update({"readable": True,
                             "identity_on_page_verified": details.get("student_number") == checked_id,
                             "structure": structure})
                pages.append({"metadata": meta, "details": details})
            finally:
                response.dispose()
        return {"profile_pages": pages}

    def end(self):
        if self.browser and self.browser.is_connected():
            self.browser.close()
        self.browser = self.context = self.page = self.baseline = self.selection = None


TEXT = {
    "en": {"title": "Attendance Portal Diagnostic", "open": "1. Student login",
           "http": "2. Check HTTP retrieval", "headless": "3. Test headless session",
           "profile": "4. Student details (HTTP)",
           "end": "End student session", "year": "Academic start year",
           "term": "Semester code", "week": "Week", "note":
           "Sign in in the separate browser. Tests compare the same student's selected week.",
           "ready": "Ready. This prototype checks retrieval; it does not generate attendance PDFs."},
    "zh": {"title": "考勤册门户读取诊断", "open": "1. 学生登录",
           "http": "2. 检查 HTTP 读取", "headless": "3. 测试无界面会话",
           "profile": "4. HTTP 读取学籍信息",
           "end": "结束学生会话", "year": "学年起始年份",
           "term": "学期代码", "week": "周次", "note":
           "请在独立浏览器中登录。测试将比较同一学生所选周次的课表。",
           "ready": "就绪。本原型检查信息读取，暂不生成考勤册 PDF。"},
}


class App:
    def __init__(self, args):
        import tkinter as tk
        from tkinter import ttk
        from tkinter.scrolledtext import ScrolledText
        self.tk, self.ttk, self.args = tk, ttk, args
        self.root = tk.Tk()
        self.root.geometry("1050x540")
        self.commands, self.events = queue.Queue(), queue.Queue()
        self.report = {"created": datetime.now().isoformat(timespec="seconds"),
                       "http_matches_visible": None,
                       "headless_page_matches_visible": None}
        self.lang = tk.StringVar(value="en")
        self.year = tk.StringVar(value=str(args.year))
        self.term = tk.StringVar(value=str(args.term))
        self.week = tk.StringVar(value=str(args.week))
        self.busy = self.closing = False
        top = ttk.Frame(self.root, padding=14)
        top.pack(fill="both", expand=True)
        toggle = ttk.Combobox(top, textvariable=self.lang, values=["en", "zh"],
                              state="readonly", width=8)
        toggle.pack(anchor="e")
        toggle.bind("<<ComboboxSelected>>", lambda _: self.relabel())
        self.note = ttk.Label(top, wraplength=800)
        self.note.pack(anchor="w", pady=10)
        fields = ttk.Frame(top)
        fields.pack(fill="x", pady=8)
        self.labels = {}
        for key, variable, values in (("year", self.year, list(range(2025, 2029))),
                                     ("term", self.term, [11, 12, 13]),
                                     ("week", self.week, list(range(1, 21)))):
            self.labels[key] = ttk.Label(fields)
            self.labels[key].pack(side="left", padx=(0, 6))
            ttk.Combobox(fields, textvariable=variable, values=values, width=7).pack(
                side="left", padx=(0, 18))
        buttons = ttk.Frame(top)
        buttons.pack(fill="x", pady=8)
        self.buttons = {}
        for key in ("open", "http", "headless", "profile", "end"):
            b = ttk.Button(buttons, command=lambda k=key: self.submit(k))
            b.pack(side="left", padx=(0, 7))
            self.buttons[key] = b
        self.log = ScrolledText(top, height=15, wrap="word", state="disabled")
        self.log.pack(fill="both", expand=True)
        self.relabel()
        self.write(TEXT[self.lang.get()]["ready"])
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.worker = threading.Thread(target=self.run_worker, daemon=True)
        self.worker.start()
        self.root.after(100, self.poll)
        if args.supervised_console and sys.stdin is not None:
            threading.Thread(target=self.read_console, daemon=True).start()
        if args.auto_check or args.auto_profile:
            self.root.after(200, lambda: self.submit("open"))

    def read_console(self):
        """Optional supervisor commands on stdin; no TCP server or credential input."""
        for line in sys.stdin:
            try:
                data = json.loads(line)
                if data.get("action") not in ("open", "http", "headless", "profile", "end", "quit"):
                    continue
                self.events.put(("command", data))
            except (ValueError, TypeError):
                self.events.put(("log", "Console command must be JSON; do not enter credentials."))

    def relabel(self):
        t = TEXT[self.lang.get()]
        self.root.title(t["title"])
        self.note.configure(text=t["note"])
        for key, label in self.labels.items():
            label.configure(text=t[key])
        for key, button in self.buttons.items():
            button.configure(text=t[key])

    def write(self, message):
        self.log.configure(state="normal")
        self.log.insert("end", message + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        if sys.stdout is not None:
            print(message, flush=True)

    def submit(self, action):
        if self.busy or self.closing:
            return
        try:
            selection = Selection(int(self.year.get()), int(self.term.get()), int(self.week.get()))
        except (ValueError, PortalError) as exc:
            self.write(str(exc))
            return
        self.busy = True
        for button in self.buttons.values():
            button.configure(state="disabled")
        self.commands.put((action, selection))

    def run_worker(self):
        # Playwright is created and used exclusively on this single worker thread.
        with sync_playwright() as playwright:
            session = Session(playwright)
            auto = False
            try:
                while True:
                    try:
                        action, selection = self.commands.get_nowait()
                    except queue.Empty:
                        if session.page and not session.page.is_closed():
                            try:
                                session.page.wait_for_timeout(200)
                            except Exception:
                                auto = False
                                session.end()
                                self.events.put(("reset", "Browser closed. Open student login to continue."))
                                continue
                            if auto and session.logged_in():
                                auto = False
                                self.events.put(("log", "Login detected. Running requested checks."))
                                action = "profile" if self.args.auto_profile else "all"
                                self.commands.put((action, Selection(self.args.year, self.args.term, self.args.week)))
                        else:
                            try:
                                action, selection = self.commands.get(timeout=.2)
                            except queue.Empty:
                                continue
                            self.commands.put((action, selection))
                        continue
                    if action == "quit":
                        break
                    try:
                        if action == "open":
                            session.open()
                            auto = self.args.auto_check or self.args.auto_profile
                            self.events.put(("log", "Student browser open. Complete sign-in there. / 请在浏览器中登录。"))
                        elif action == "end":
                            auto = False
                            session.end()
                            self.events.put(("reset", "Student browser closed; baseline and session references cleared."))
                        else:
                            if action == "profile":
                                self.events.put(("profile", session.profile_check(selection)))
                            if action in ("http", "all"):
                                self.events.put(("result", session.http_check(selection)))
                            if action in ("headless", "all"):
                                self.events.put(("result", session.headless_check(selection)))
                    except Exception as exc:
                        # Playwright exception details can contain request headers.
                        # Only our deliberately safe messages are shown or saved.
                        message = str(exc) if isinstance(exc, PortalError) else type(exc).__name__
                        self.events.put(("failure", {"action": action, "error": message}))
                    finally:
                        self.events.put(("done", None))
            finally:
                session.end()
                self.events.put(("closed", None))

    def poll(self):
        while True:
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind in ("result", "failure"):
                if kind == "result":
                    if self.report.get("selection") != payload.get("selection"):
                        for flag in ("http_matches_visible", "headless_page_matches_visible",
                                     "headless_http_matches_visible"):
                            self.report[flag] = None
                    self.report.update(payload)
                else:
                    self.report.setdefault("failures", []).append(payload)
                self.write(json.dumps(payload, ensure_ascii=False))
                if self.args.report:
                    path = Path(self.args.report)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(self.report, indent=2, ensure_ascii=False), encoding="utf-8")
            elif kind == "profile":
                self.write(json.dumps(payload, ensure_ascii=False))
                # Display requested values to the operator, but save only field structure.
                self.report["profile_pages"] = [p["metadata"] for p in payload["profile_pages"]]
                if self.args.report:
                    path = Path(self.args.report)
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(self.report, indent=2, ensure_ascii=False), encoding="utf-8")
            elif kind == "command":
                if payload["action"] == "quit":
                    self.close()
                else:
                    self.year.set(str(payload.get("year", self.year.get())))
                    self.term.set(str(payload.get("term", self.term.get())))
                    self.week.set(str(payload.get("week", self.week.get())))
                    self.submit(payload["action"])
            elif kind == "closed":
                self.root.destroy()
                return
            elif kind == "done":
                self.busy = False
                if not self.closing:
                    for button in self.buttons.values():
                        button.configure(state="normal")
            elif kind == "reset":
                self.report = {"created": datetime.now().isoformat(timespec="seconds"),
                               "http_matches_visible": None,
                               "headless_page_matches_visible": None}
                self.write(payload)
            else:
                self.write(payload)
        self.root.after(100, self.poll)

    def close(self):
        self.closing = True
        for button in self.buttons.values():
            button.configure(state="disabled")
        self.commands.put(("quit", None))


def anonymous_smoke(selection):
    with sync_playwright() as pw:
        browser = launch(pw, True)
        try:
            context = browser.new_context()
            page = context.new_page()
            response = page.goto(selection.url, wait_until="domcontentloaded", timeout=30000)
            result = {"headless_browser_launched": True,
                      "final_host": urlparse(page.url).hostname,
                      "http_status": response.status if response else None,
                      "login_page_detected": "ids.chd.edu.cn" == urlparse(page.url).hostname,
                      "authenticated_retrieval": "not tested: student login required"}
            return result
        finally:
            browser.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--auto-check", action="store_true")
    parser.add_argument("--auto-profile", action="store_true")
    parser.add_argument("--supervised-console", action="store_true")
    parser.add_argument("--headless-smoke", action="store_true")
    parser.add_argument("--year", type=int, default=2026)
    parser.add_argument("--term", type=int, default=11)
    parser.add_argument("--week", type=int, default=1)
    parser.add_argument("--report", help="Optional sanitized diagnostic JSON; never session state.")
    parser.add_argument("--system-chrome", action="store_true",
                        help="Use installed Chrome for local diagnosis without a browser download.")
    args = parser.parse_args()
    global ENGINE_CHANNEL
    if args.system_chrome:
        ENGINE_CHANNEL = "chrome"
    if args.headless_smoke:
        result = anonymous_smoke(Selection(args.year, args.term, args.week))
        print(json.dumps(result, indent=2), flush=True)
        if args.report:
            Path(args.report).write_text(json.dumps(result, indent=2), encoding="utf-8")
    else:
        App(args).root.mainloop()


if __name__ == "__main__":
    main()
