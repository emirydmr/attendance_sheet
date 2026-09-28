"""Production Tkinter draft. No dependency or browser downloads at startup."""
from __future__ import annotations

import argparse
from datetime import date
import queue
import threading
import webbrowser
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from portal import PortalError, Selection
from service import PortalSession, demo_identity, demo_weeks
from document import pdf_filename, print_pdf, validate_book, save_browser_document, resource_root
from photo import PhotoDialog, create_root
from branding import apply_icon
from field_help import HELP, TIMETABLE_URL, description
from browser_config import default_channel, BROWSER_NAMES, check_browser

SEMESTERS = (
    ("11", "First semester", "第一学期"),
    ("12", "Second semester", "第二学期"),
    ("13", "Short semester", "短学期"),
)

TEXT = {
    "check_browser": ("Check browser / retry", "检查浏览器 / 重试"),
    "browser_checking": ("Checking {name}…", "正在检查 {name}…"),
    "browser_available": ("✓ {name} check passed (version {version}).", "✓ {name} 检查成功（版本 {version}）。"),
    "browser_check_passed": ("Browser check passed. You can open the login browser.", "浏览器检查成功，可以打开登录页面。"),
    "browser_unavailable": ("{name} is missing or cannot launch. Install/repair it or ask IT about automation restrictions, then click Check browser / retry. No automatic downloads.", "{name} 未安装或无法启动。请安装/修复浏览器，或向 IT 咨询自动化限制，然后点击“检查浏览器 / 重试”。不会自动下载。"),
    "field_info": ("Field information", "字段说明"),
    "portal_timetable": ("Open portal timetable", "打开门户课表"),
    "font_license": ("Font licence", "字体许可"),
    "title": ("Attendance book", "国际学生考勤册"),
    "open": ("Open browser / log in", "打开浏览器 / 登录"),
    "end": ("End student session", "结束学生会话"),
    "year": ("Academic start year", "学年起始年"),
    "term": ("Semester", "学期"),
    "first": ("First week", "起始周"), "last": ("Last week", "结束周"),
    "omit_empty_weeks": ("Omit empty weeks", "省略无课周"),
    "identity": ("Student number & major", "学号与专业"),
    "names": ("Student name", "学生姓名"),
    "weeks": ("Weekly timetables", "每周课表"),
    "retrieve": ("Retrieve", "获取"), "missing": ("Missing", "未获取"),
    "success": ("Success · click to view", "成功 · 点击查看"),
    "partial": ("Review names · click", "请确认姓名 · 点击"),
    "working": ("Retrieving…", "正在获取…"), "failed": ("Failed · click for details", "失败 · 点击详情"),
    "settings": ("Cover details", "封面信息"),
    "chinese_name": ("Chinese name / 中文名", "中文名"),
    "passport_name": ("Passport name / 护照名", "护照名"),
    "major": ("Cover major / 专业", "封面专业"),
    "teacher": ("Head teacher / 班主任", "班主任"),
    "phone": ("Teacher phone / 联系电话", "联系电话"),
    "issue_date": ("Issue date (YYYY-MM-DD)", "制表日期（YYYY-MM-DD）"),
    "pdf": ("Create PDF…", "生成 PDF…"),
    "ready": ("Open the browser and let the student log in. No passwords are stored.", "打开浏览器，由学生自行登录。不保存密码。"),
    "signed": ("Browser opened. Finish login, then retrieve information.", "浏览器已打开。完成登录后获取信息。"),
    "note": ("Click a status to inspect results; ⓘ explains each field. Confirm 中文名 and 护照名 before exporting.", "点击状态查看信息，ⓘ 可查看字段说明。导出前确认中文名、护照名。"),
    "demo": ("DEMO — fictitious student data; no portal requests", "示例模式 — 虚构学生数据，不访问教务系统"),
    "busy": ("Please wait for the current operation.", "请等待当前操作完成。"),
    "closing": ("Closing the student session…", "正在关闭学生会话…"),
    "confirm": ("Confirm names", "确认姓名"),
    "name_note": ("Portal 姓名 is shown below. Confirm the actual Chinese and passport names; they are not inferred.", "下方显示门户姓名。请确认中文名和护照名，不进行自动推断。"),
    "saved": ("PDF saved", "PDF 已保存"),
    "student_id": ("Student number", "学号"), "college": ("College", "学院"),
    "recorded_name": ("Portal name (姓名)", "门户姓名（姓名）"),
    "week": ("Week", "周次"), "blocks": ("course blocks", "课程块"),
    "empty": ("No courses", "无课程"), "completed": ("Retrieved. Click the status to review.", "获取完成。点击状态查看信息。"),
    "photo": ("Add / change photo…", "添加 / 更换照片…"),
    "no_photo": ("No photo added", "尚未添加照片"),
    "photo_ready": ("Photo added", "已添加照片"),
    "browser_print": ("Open in default browser / print…", "在默认浏览器打开 / 打印…"),
    "photo_missing": ("No photo is attached. Export with an empty photo box?", "尚未添加照片。是否保留空白照片框并导出？"),
    "browser_saved": ("HTML saved. Print / Save as PDF in your default browser.", "HTML已保存。请在默认浏览器中打印或另存为PDF。"),
}


def worker(commands, events, channel, demo):
    # Every Playwright object belongs to this thread. Tk owns only messages/data.
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        session = PortalSession(pw, channel)
        try:
            while True:
                try:
                    task, args = commands.get(timeout=.1)
                except queue.Empty:
                    if session.page and not session.page.is_closed():
                        try:
                            session.page.wait_for_timeout(100)
                        except Exception:
                            pass
                    continue
                if task == "quit":
                    break
                try:
                    if task == "check_browser":
                        result = check_browser(pw, channel)
                    elif task == "open":
                        if not demo:
                            session.open()
                        result = None
                    elif task == "end":
                        session.close()
                        result = None
                    elif task == "identity":
                        result = demo_identity() if demo else session.identity(*args)
                    elif task == "names":
                        result = {"recorded_name": "SAMPLE STUDENT"} if demo else session.names(*args)
                    elif task == "weeks":
                        result = demo_weeks(*args) if demo else session.timetables(
                            *args, lambda n, last: events.put(("progress", "weeks", (n, last))))
                    elif task == "pdf":
                        data, destination = args
                        print_pdf(pw, channel, data, destination)
                        result = destination
                    elif task == "browser_print":
                        data, destination = args
                        result = (destination, save_browser_document(data, destination))
                    else:
                        raise ValueError("Unknown operation")
                    events.put(("done", task, result))
                except Exception as exc:
                    # Never display a raw Playwright exception with headers/cookies.
                    error = str(exc) if isinstance(exc, (PortalError, ValueError)) else type(exc).__name__
                    events.put(("error", task, error))
        finally:
            session.close()
    events.put(("stopped", "quit", None))


class AttendanceApp:
    def __init__(self, root, channel=None, demo=False):
        self.root, self.demo = root, demo
        self.channel = channel or default_channel()
        self.browser_state = "checking"
        self.browser_version = ""
        apply_icon(root)
        self.language = tk.StringVar(value="English")
        self.omit_empty_weeks = tk.BooleanVar(value=True)
        self.commands, self.events = queue.Queue(), queue.Queue()
        self.busy = self.closing = False
        self.data, self.results, self.errors = {}, {}, {}
        self.photo = None
        self.photo_dialog = None
        self.states = {key: "missing" for key in ("identity", "names", "weeks")}
        self.translated, self.inputs, self.actions = [], [], []
        self.help_controls, self.field_entries = {}, {}
        self.vars = {key: tk.StringVar(value=value) for key, value in {
            "year": str(date.today().year), "term": "11", "first": "1", "last": "18",
            "chinese_name": "示例学生" if demo else "",
            "passport_name": "SAMPLE STUDENT" if demo else "",
            "major": "", "teacher": "李冠楠", "phone": "02968578129",
            "issue_date": date.today().isoformat(),
        }.items()}
        self.names_confirmed = demo
        self.build()
        for key in ("year", "term", "first", "last"):
            self.vars[key].trace_add("write", lambda *_args, k=key: self.invalidate(k))
        for key in ("chinese_name", "passport_name"):
            self.vars[key].trace_add("write", lambda *_: self.set_names_state())
        self.thread = threading.Thread(target=worker, args=(self.commands, self.events, self.channel, demo), daemon=True)
        self.thread.start()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(100, self.poll)
        self.submit("check_browser")

    def tr(self, key):
        return TEXT[key][int(self.language.get() == "中文")]

    def widget(self, parent, cls, key, **kwargs):
        widget = cls(parent, text=self.tr(key), **kwargs)
        self.translated.append((widget, key))
        return widget

    def build(self):
        self.root.title(self.tr("title"))
        self.root.geometry("890x810")
        self.root.minsize(820, 790)
        style = ttk.Style(self.root)
        style.configure("Title.TLabel", font=("TkDefaultFont", 21, "bold"))
        style.configure("Success.TButton", foreground="#167342")
        style.configure("Partial.TButton", foreground="#926200")
        style.configure("Failed.TButton", foreground="#a52b28")
        panel = ttk.Frame(self.root, padding=24)
        panel.pack(fill="both", expand=True)
        top = ttk.Frame(panel)
        top.pack(fill="x")
        self.widget(top, ttk.Label, "title", style="Title.TLabel").pack(side="left")
        languages = ttk.Combobox(top, textvariable=self.language, values=("English", "中文"), state="readonly", width=12)
        languages.pack(side="right")
        languages.bind("<<ComboboxSelected>>", lambda _: self.translate())
        self.widget(top, ttk.Button, "font_license", command=self.show_font_license).pack(side="right", padx=10)
        if self.demo:
            self.widget(panel, ttk.Label, "demo", foreground="#926200").pack(anchor="w", pady=(8, 0))
        session = ttk.Frame(panel)
        session.pack(fill="x", pady=(18, 16))
        for key in ("open", "end", "check_browser"):
            button = self.widget(session, ttk.Button, key, command=lambda k=key: self.submit(k))
            button.pack(side="left", padx=(0, 10))
            self.actions.append(button)
        self.browser_status = ttk.Label(panel, wraplength=770)
        self.browser_status.pack(anchor="w", pady=(0, 10))
        selections = ttk.Frame(panel)
        selections.pack(fill="x", pady=(0, 14))
        for col, key in enumerate(("year", "term", "first", "last")):
            heading = ttk.Frame(selections)
            heading.grid(row=0, column=col, sticky="w", padx=(0, 14))
            label = self.widget(heading, ttk.Label, key)
            label.pack(side="left")
            self.bind_help(label, key)
            self.info_button(heading, key).pack(side="left", padx=4)
            if key == "term":
                self.semester_label = tk.StringVar()
                entry = self.semester_dropdown = ttk.Combobox(
                    selections, textvariable=self.semester_label, state="readonly", width=16)
                entry.bind("<<ComboboxSelected>>", self.choose_semester)
                self.refresh_semester()
            else:
                entry = ttk.Entry(selections, textvariable=self.vars[key], width=14)
            entry.grid(row=1, column=col, sticky="w", padx=(0, 20), pady=(4, 0))
            self.inputs.append(entry)
            self.field_entries[key] = entry
            self.bind_help(entry, key)
        options = ttk.Frame(selections)
        options.grid(row=2, column=0, columnspan=4, sticky="w", pady=(8, 0))
        self.omit_empty_checkbox = self.widget(
            options, ttk.Checkbutton, "omit_empty_weeks", variable=self.omit_empty_weeks)
        self.omit_empty_checkbox.pack(side="left")
        self.inputs.append(self.omit_empty_checkbox)
        self.bind_help(self.omit_empty_checkbox, "omit_empty_weeks")
        self.info_button(options, "omit_empty_weeks").pack(side="left", padx=4)
        self.badges = {}
        for key in ("identity", "names", "weeks"):
            row = ttk.Frame(panel)
            row.pack(fill="x", pady=5)
            self.widget(row, ttk.Label, key, width=27).pack(side="left")
            action = self.widget(row, ttk.Button, "retrieve", command=lambda k=key: self.retrieve(k), width=13)
            action.pack(side="left", padx=(0, 12))
            self.actions.append(action)
            badge = ttk.Button(row, command=lambda k=key: self.inspect(k), width=30)
            badge.pack(side="left")
            badge.bind("<Enter>", lambda event, k=key: self.tooltip(event, k))
            badge.bind("<Leave>", lambda _: self.hide_tooltip())
            badge.bind("<ButtonPress>", lambda _: self.hide_tooltip())
            self.badges[key] = badge
        self.widget(panel, ttk.Label, "note", wraplength=770, foreground="#666").pack(anchor="w", pady=(8, 14))
        form = self.widget(panel, ttk.LabelFrame, "settings", padding=12)
        form.pack(fill="x")
        for n, key in enumerate(("chinese_name", "passport_name", "major", "teacher", "phone", "issue_date")):
            row, col = divmod(n, 2)
            heading = ttk.Frame(form)
            heading.grid(row=row * 2, column=col, sticky="w", pady=(3, 2))
            label = self.widget(heading, ttk.Label, key)
            label.pack(side="left")
            self.bind_help(label, key)
            self.info_button(heading, key).pack(side="left", padx=4)
            entry = ttk.Entry(form, textvariable=self.vars[key], width=39)
            entry.grid(row=row * 2 + 1, column=col, sticky="ew", padx=(0, 16) if col == 0 else (0, 0), pady=(0, 6))
            self.inputs.append(entry)
            self.field_entries[key] = entry
            self.bind_help(entry, key)
            form.columnconfigure(col, weight=1)
        photo_row = ttk.Frame(panel)
        photo_row.pack(fill="x", pady=(12, 2))
        photo_button = self.widget(photo_row, ttk.Button, "photo", command=self.add_photo)
        photo_button.pack(side="left")
        self.bind_help(photo_button, "photo")
        self.info_button(photo_row, "photo").pack(side="left", padx=4)
        self.actions.append(photo_button)
        self.photo_status = ttk.Label(photo_row)
        self.photo_status.pack(side="left", padx=12)
        export_row = ttk.Frame(panel)
        export_row.pack(fill="x", pady=(12, 8))
        for key in ("browser_print", "pdf"):
            export = self.widget(export_row, ttk.Button, key, command=lambda k=key: self.export(k))
            export.pack(side="right", padx=(8, 0))
            self.actions.append(export)
        self.status = ttk.Label(panel, text=self.tr("ready"), wraplength=770, foreground="#555")
        self.status.pack(anchor="w")
        self.refresh()

    def translate(self):
        self.hide_tooltip()
        self.root.title(self.tr("title"))
        for widget, key in self.translated:
            if widget.winfo_exists():
                widget.configure(text=self.tr(key))
        self.refresh_semester()
        self.refresh()
        if not self.busy:
            self.status.configure(text=self.tr("ready"))

    def refresh(self):
        self.browser_status.configure(
            text=self.tr("browser_" + self.browser_state).format(
                name=BROWSER_NAMES[self.channel], version=self.browser_version),
            foreground={"available": "#167342", "unavailable": "#a52b28"}.get(self.browser_state, "#555"))
        self.photo_status.configure(text=self.tr("photo_ready" if self.photo else "no_photo"))
        for key, state in self.states.items():
            style = {"success": "Success.TButton", "partial": "Partial.TButton", "failed": "Failed.TButton"}.get(state, "TButton")
            self.badges[key].configure(text=self.tr(state), style=style)

    def set_busy(self, value):
        self.busy = value
        for widget in self.inputs + self.actions:
            widget.configure(state="disabled" if value or self.closing else
                             "readonly" if widget is self.semester_dropdown else "normal")

    def refresh_semester(self):
        language_index = 2 if self.language.get() == "中文" else 1
        self.semester_dropdown.configure(values=[item[language_index] for item in SEMESTERS])
        self.semester_label.set(next((item[language_index] for item in SEMESTERS
                                     if item[0] == self.vars["term"].get()), ""))

    def choose_semester(self, _event=None):
        index = self.semester_dropdown.current()
        if index >= 0 and not self.busy and not self.closing:
            code = SEMESTERS[index][0]
            if code != self.vars["term"].get():
                self.vars["term"].set(code)

    def selection(self):
        year, term, first, last = (int(self.vars[k].get()) for k in ("year", "term", "first", "last"))
        Selection(year, term, first)
        Selection(year, term, last)
        if first > last:
            raise ValueError("First week must not exceed last week / 起始周不能晚于结束周。")
        return year, term, first, last

    def invalidate(self, key):
        if key == "term":
            self.refresh_semester()
        affected = ("identity", "names", "weeks") if key in ("year", "term") else ("weeks",)
        for item in affected:
            self.states[item] = "missing"
            self.results.pop(item, None)
        self.refresh()

    def clear_student(self):
        if self.photo_dialog and self.photo_dialog.window.winfo_exists():
            self.photo_dialog.cancel()
        self.photo_dialog = None
        self.photo = None
        self.data.clear()
        self.results.clear()
        self.errors.clear()
        self.names_confirmed = self.demo
        for k in ("chinese_name", "passport_name", "major"):
            self.vars[k].set({"chinese_name": "示例学生", "passport_name": "SAMPLE STUDENT"}.get(k, "") if self.demo else "")
        self.states = dict.fromkeys(self.states, "missing")
        self.refresh()

    def submit(self, task, args=()):
        if self.busy:
            return
        if task in ("open", "end"):
            self.clear_student()
        if task == "check_browser":
            self.browser_state = "checking"
            self.refresh()
        self.set_busy(True)
        if task in self.states:
            self.states[task] = "working"
            self.results.pop(task, None)
            self.refresh()
        self.status.configure(text=self.tr("browser_checking").format(name=BROWSER_NAMES[self.channel])
                              if task == "check_browser" else self.tr("working"))
        self.commands.put((task, args))

    def retrieve(self, task):
        try:
            values = self.selection()
            self.submit(task, values if task == "weeks" else values[:2])
        except (ValueError, PortalError) as exc:
            messagebox.showerror(self.tr("title"), str(exc), parent=self.root)

    def set_names_state(self):
        self.names_confirmed = bool(self.vars["chinese_name"].get().strip() and self.vars["passport_name"].get().strip())
        if "names" in self.results:
            self.states["names"] = "success" if self.names_confirmed else "partial"
            self.refresh()

    def display_result(self, key):
        if key in self.errors and self.states[key] == "failed":
            return self.errors[key]
        result = self.results.get(key)
        if result is None:
            return self.tr("missing")
        if key == "weeks":
            days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"] if self.language.get() == "English" else ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            return "\n\n".join(f"{self.tr('week')} {w['selection']['week']} · {len(w['classes'])} {self.tr('blocks')}\n" +
                ("\n".join(f"{days[c['day']-1]} / {c['first_period']}–{c['first_period']+c['period_count']-1}: {c['text']}" for c in w["classes"]) or self.tr("empty")) for w in result)
        values = result.copy()
        if key == "names":
            values.update({k: self.vars[k].get() or self.tr("missing") for k in ("chinese_name", "passport_name")})
        return "\n".join(f"{self.tr(k) if k in TEXT else k}: {v}" for k, v in values.items())

    def inspect(self, key):
        if self.busy:
            return
        window = tk.Toplevel(self.root)
        window.title(self.tr(key))
        window.geometry("680x470")
        window.transient(self.root)
        container = ttk.Frame(window, padding=16)
        container.pack(fill="both", expand=True)
        if key == "names":
            ttk.Label(container, text=self.tr("name_note"), wraplength=620).pack(anchor="w", pady=(0, 8))
        text = tk.Text(container, wrap="word", height=12)
        text.insert("1.0", self.display_result(key))
        text.configure(state="disabled")
        text.pack(fill="both", expand=True)
        if key == "names" and key in self.results:
            for k in ("chinese_name", "passport_name"):
                heading = ttk.Frame(container)
                heading.pack(anchor="w", pady=(8, 2))
                label = ttk.Label(heading, text=self.tr(k))
                label.pack(side="left")
                self.bind_help(label, k)
                button = ttk.Button(heading, text="ⓘ", width=2, command=lambda key=k: self.show_field_help(key))
                button.pack(side="left", padx=4)
                self.bind_help(button, k)
                entry = ttk.Entry(container, textvariable=self.vars[k])
                entry.pack(fill="x")
                self.bind_help(entry, k)
            ttk.Button(container, text=self.tr("confirm"), command=lambda: (self.set_names_state(), window.destroy())).pack(anchor="e", pady=(8, 0))

    def tooltip(self, event, key):
        self.hide_tooltip()
        self.tip = tk.Toplevel(self.root)
        self.tip.overrideredirect(True)
        self.tip.geometry(f"+{event.x_root + 10}+{event.y_root + 14}")
        content = self.display_result(key)
        if len(content) > 700:
            content = content[:700] + "\n… click to view / 点击查看全部"
        ttk.Label(self.tip, text=content, wraplength=480, padding=10, relief="solid").pack()

    def info_button(self, parent, key):
        button = ttk.Button(parent, text="ⓘ", width=2, command=lambda: self.show_field_help(key))
        self.help_controls[key] = button
        self.bind_help(button, key)
        return button

    def bind_help(self, widget, key):
        widget.bind("<Enter>", lambda event: self.schedule_help(event, key), add="+")
        widget.bind("<Leave>", lambda _: self.hide_tooltip(), add="+")
        widget.bind("<ButtonPress>", lambda _: self.hide_tooltip(), add="+")

    def schedule_help(self, event, key):
        self.hide_tooltip()
        x, y = event.x_root, event.y_root
        self.help_timer = self.root.after(400, lambda: self.show_help_tip(key, x, y))

    def show_help_tip(self, key, x, y):
        self.help_timer = None
        self.tip = tk.Toplevel(self.root)
        self.tip.overrideredirect(True)
        ttk.Label(self.tip, text=description(key, self.language.get() == "中文"), wraplength=430, padding=12, relief="solid").pack()
        self.tip.update_idletasks()
        x = max(0, min(x + 12, self.root.winfo_screenwidth() - self.tip.winfo_reqwidth() - 12))
        y = max(0, min(y + 18, self.root.winfo_screenheight() - self.tip.winfo_reqheight() - 12))
        self.tip.geometry(f"+{x}+{y}")

    def show_field_help(self, key):
        self.hide_tooltip()
        window = tk.Toplevel(self.root)
        window.title(self.tr("field_info"))
        window.transient(self.root)
        frame = ttk.Frame(window, padding=20)
        frame.pack(fill="both", expand=True)
        ttk.Label(frame, text=self.tr(key) if key in TEXT else self.language.get(), font=("TkDefaultFont", 14, "bold")).pack(anchor="w", pady=(0, 10))
        ttk.Label(frame, text=description(key, self.language.get() == "中文"), wraplength=540, justify="left").pack(anchor="w")
        if key in ("year", "term", "first", "last"):
            ttk.Label(frame, text=TIMETABLE_URL, wraplength=540).pack(anchor="w", pady=(12, 6))
            ttk.Button(frame, text=self.tr("portal_timetable"), command=lambda: webbrowser.open(TIMETABLE_URL)).pack(anchor="w")
        return window

    def hide_tooltip(self):
        if getattr(self, "help_timer", None):
            self.root.after_cancel(self.help_timer)
            self.help_timer = None
        if getattr(self, "tip", None):
            self.tip.destroy()
            self.tip = None

    def payload(self):
        year, term, first, last = self.selection()
        if any(self.states[k] not in ("success", "partial") for k in self.states):
            raise ValueError("Retrieve all three information groups first / 请先获取三项信息。")
        return {**self.data, **{k: self.vars[k].get().strip() for k in
                ("chinese_name", "passport_name", "major", "teacher", "phone", "issue_date")},
                "year": year, "term": term, "first_week": first, "last_week": last,
                "portal_major": self.data["major"], "weeks": self.results["weeks"], "demo": self.demo, "photo": self.photo,
                "omit_empty_weeks": self.omit_empty_weeks.get()}

    def add_photo(self):
        if self.busy:
            return
        if self.photo_dialog and self.photo_dialog.window.winfo_exists():
            self.photo_dialog.window.lift()
            return
        self.photo_dialog = PhotoDialog(self.root, self.photo, self.commit_photo, self.language.get() == "中文")

    def commit_photo(self, photo):
        self.photo = photo
        self.refresh()

    def export(self, mode="pdf"):
        try:
            data = self.payload()
            validate_book(data)
        except (ValueError, KeyError, PortalError) as exc:
            messagebox.showerror(self.tr("title"), str(exc), parent=self.root)
            return
        if self.photo is None and not messagebox.askyesno(self.tr("title"), self.tr("photo_missing"), parent=self.root):
            return
        browser_mode = mode == "browser_print"
        extension = ".html" if browser_mode else ".pdf"
        initial = pdf_filename(data["student_id"])[:-4] + extension
        destination = filedialog.asksaveasfilename(parent=self.root, title=self.tr(mode),
            initialfile=initial, defaultextension=extension, filetypes=[("HTML" if browser_mode else "PDF", "*" + extension)])
        if destination:
            self.submit(mode, (data, destination))

    def poll(self):
        while True:
            try:
                kind, task, result = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "stopped":
                self.root.destroy()
                return
            if kind == "progress":
                self.status.configure(text=f"{self.tr('working')} {result[0]} / {result[1]}")
                continue
            self.set_busy(False)
            if kind == "error":
                self.errors[task] = result
                if task in self.states:
                    self.states[task] = "failed"
                self.status.configure(text=result)
                if task == "check_browser":
                    self.browser_state = "unavailable"
                    self.browser_version = ""
                    self.status.configure(text=self.tr("browser_unavailable").format(name=BROWSER_NAMES[self.channel]))
            else:
                if task == "check_browser":
                    self.browser_state = "available"
                    self.browser_version = result["version"]
                    self.errors.pop(task, None)
                if task in self.states:
                    self.results[task] = result
                    self.states[task] = "success"
                if task == "identity":
                    self.data.update(result)
                    self.vars["major"].set(result["major"])
                elif task == "names":
                    for key in ("chinese_name", "passport_name"):
                        if result.get(key):
                            self.vars[key].set(result[key])
                    self.set_names_state()
                elif task == "pdf":
                    self.status.configure(text=f"{self.tr('saved')}: {result}")
                elif task == "browser_print":
                    self.status.configure(text=f"{self.tr('browser_saved')} {result[0]}" + (" (Browser did not open automatically / 浏览器未自动打开)" if not result[1] else ""))
                if task not in ("pdf", "browser_print"):
                    self.status.configure(text=self.tr("browser_check_passed" if task == "check_browser" else
                                                       "signed" if task == "open" else "ready" if task == "end" else "completed"))
            self.refresh()
        self.root.after(100, self.poll)

    def show_font_license(self):
        fonts = resource_root() / "assets" / "fonts"
        window = tk.Toplevel(self.root)
        window.title(self.tr("font_license"))
        window.geometry("700x520")
        window.transient(self.root)
        text = tk.Text(window, wrap="word", padx=14, pady=14)
        text.pack(fill="both", expand=True)
        content = "\n\n".join((fonts / name).read_text(encoding="utf-8") for name in ("FONT_INFO.txt", "LICENSE.txt"))
        text.insert("1.0", content)
        text.configure(state="disabled")

    def close(self):
        if self.closing:
            return
        self.closing = True
        if self.photo_dialog and self.photo_dialog.window.winfo_exists():
            self.photo_dialog.cancel()
        self.hide_tooltip()
        self.set_busy(True)
        self.status.configure(text=self.tr("closing"))
        self.commands.put(("quit", ()))


def main():
    parser = argparse.ArgumentParser()
    browsers = parser.add_mutually_exclusive_group()
    browsers.add_argument("--system-chrome", action="store_true", help="Use installed Chrome (legacy alias)")
    browsers.add_argument("--browser", choices=("msedge", "chrome"), help="Installed browser; default Edge on Windows, Chrome on macOS")
    parser.add_argument("--demo", action="store_true", help="Fictitious offline UI test data")
    parser.add_argument("--photo-popup", action="store_true", help="Show photo popup immediately for manual testing")
    args = parser.parse_args()
    root = create_root()
    app = AttendanceApp(root, "chrome" if args.system_chrome else args.browser or default_channel(), args.demo)
    if args.photo_popup:
        root.after(250, app.add_photo)
    root.mainloop()


if __name__ == "__main__":
    main()
