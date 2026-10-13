"""Native ttk editor for explicit browser and WebDriver profiles.

The model owns persistence, discovery, importing, and driver resolution. This
module owns presentation and keeps the threading boundary explicit: Tk values
are copied before a worker starts and workers report through a queue.
"""
from __future__ import annotations

import queue
import threading
import uuid
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from browser_config import (
    BROWSER_NAMES,
    DRIVER_NAMES,
    default_driver_kind,
    storage_root,
    load_profiles,
    get_active_profile,
    save_profile,
    delete_profile,
    detect_browsers,
    resolve_profile,
    driver_library,
    import_driver,
)


_PROFILE_FIELDS = (
    "name", "browser", "executable", "driver_kind", "driver_path", "driver_mode",
)


class BrowserSettingsDialog(tk.Toplevel):
    """Edit named browser profiles without ever launching a browser."""

    POLL_MS = 80

    def __init__(self, parent, on_apply, chinese=False):
        super().__init__(parent)
        self.window = self  # Support the main window's dialog lifecycle API.
        self.on_apply = on_apply
        self.chinese = bool(chinese)
        self._closed = False
        self._busy = False
        self._queue: queue.Queue = queue.Queue()
        self._operation = 0
        self._pending_jobs = []
        self._generation = 0
        self._after_id = None
        self._suspend_traces = True
        self._interactive: list[tuple[tk.Widget, str]] = []
        self._driver_rows: dict[str, dict] = {}
        self._detected: list[dict] = []
        self._working: dict = {}
        self._loaded_id: str | None = None
        self._advanced_visible = False
        self._suggested_name = ""

        initial_error = None
        try:
            self._profiles = list(load_profiles())
            self._active = get_active_profile()
        except ValueError as exc:
            self._profiles, self._active = [], None
            initial_error = exc

        self.title(self._text("Browser settings", "浏览器设置"))
        self.minsize(780, 540)
        self.geometry("860x560")
        self.protocol("WM_DELETE_WINDOW", self.destroy)

        self._vars = {key: tk.StringVar(self, "") for key in _PROFILE_FIELDS}
        self._override_var = tk.BooleanVar(self, False)
        self._browser_label = tk.StringVar(self, "")
        self._driver_label = tk.StringVar(self, "")
        self._detected_label = tk.StringVar(self, "")
        self._status_var = tk.StringVar(
            self,
            self._text(
                "Choose an installed browser. Startup never downloads a driver or browser.",
                "请选择已安装的浏览器。启动应用时不会下载驱动或浏览器。",
            ),
        )
        self._build()
        for variable in self._vars.values():
            variable.trace_add("write", self._editor_changed)
        self._override_var.trace_add("write", self._editor_changed)
        self._suspend_traces = False

        self._refresh_profiles()
        if self._active:
            self._load_profile(self._active)
        else:
            # A blank browser is intentional: first-run setup must be explicit.
            self._new_profile(initial=True)
        self._poll()
        self._detect()
        self._refresh_drivers()
        if initial_error is not None:
            self.after_idle(lambda: self._show_error(initial_error))

    def _text(self, english: str, chinese: str) -> str:
        return chinese if self.chinese else english

    def _track_widget(self, widget, state="normal"):
        self._interactive.append((widget, state))
        return widget

    def _build(self):
        outer = ttk.Frame(self, padding=12)
        outer.pack(fill="both", expand=True)
        notebook = ttk.Notebook(outer)
        notebook.pack(fill="both", expand=True)

        profiles = ttk.Frame(notebook, padding=10)
        drivers = ttk.Frame(notebook, padding=10)
        notebook.add(profiles, text=self._text("Profiles", "配置"))
        notebook.add(drivers, text=self._text("Driver library", "驱动库"))
        self._build_profiles(profiles)
        self._build_drivers(drivers)

        ttk.Label(
            outer, wraplength=780,
            text=self._text(
                "Automatic mode: Apply gets a matching driver if needed. Open browser may get a new driver "
                "after a browser update. Startup never downloads anything; browsers are never downloaded.",
                "自动模式：点击“应用”会按需获取匹配驱动；浏览器更新后，点击“打开浏览器”可能获取新驱动。启动应用时不会下载任何内容，也不会下载浏览器。",
            ),
        ).pack(fill="x", pady=(8, 0))

        ttk.Separator(outer).pack(fill="x", pady=(10, 6))
        footer = ttk.Frame(outer)
        footer.pack(fill="x")
        ttk.Label(footer, textvariable=self._status_var, wraplength=660).pack(
            side="left", fill="x", expand=True
        )
        self._close_button = ttk.Button(
            footer, text=self._text("Close", "关闭"), command=self.destroy
        )
        self._close_button.pack(side="right", padx=(10, 0))

    def _build_profiles(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(3, weight=1)
        ttk.Label(
            parent, text=self._text("Saved profiles", "已保存配置"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 5))
        self.profile_list = ttk.Treeview(
            parent, columns=("browser", "state"), show="tree headings", height=4,
            selectmode="browse",
        )
        self.profile_list.heading("#0", text=self._text("Name", "名称"))
        self.profile_list.heading("browser", text=self._text("Browser", "浏览器"))
        self.profile_list.heading("state", text=self._text("Status", "状态"))
        self.profile_list.column("#0", width=260, stretch=True)
        self.profile_list.column("browser", width=180)
        self.profile_list.column("state", width=100, anchor="center")
        self.profile_list.grid(row=1, column=0, sticky="nsew")
        self.profile_list.bind("<<TreeviewSelect>>", self._select_profile)
        self._track_widget(self.profile_list)

        profile_actions = ttk.Frame(parent)
        profile_actions.grid(row=2, column=0, sticky="ew", pady=(6, 12))
        self._new_button = self._track_widget(
            ttk.Button(profile_actions, text=self._text("New", "新建"), command=self._new_profile)
        )
        self._new_button.pack(side="left")
        self._save_button = self._track_widget(
            ttk.Button(profile_actions, text=self._text("Save inactive", "保存非活动配置"), command=self._save)
        )
        self._save_button.pack(side="left", padx=6)
        self._delete_button = self._track_widget(
            ttk.Button(profile_actions, text=self._text("Delete", "删除"), command=self._delete)
        )
        self._delete_button.pack(side="left")

        form = ttk.LabelFrame(parent, text=self._text("Profile details", "配置详情"), padding=10)
        form.grid(row=3, column=0, sticky="nsew")
        form.columnconfigure(1, weight=1)
        ttk.Label(form, text=self._text("Profile name", "配置名称")).grid(row=0, column=0, sticky="w", pady=4)
        self._name_entry = self._track_widget(ttk.Entry(form, textvariable=self._vars["name"]))
        self._name_entry.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)

        ttk.Label(form, text=self._text("Installed browser", "已安装浏览器")).grid(row=1, column=0, sticky="w", pady=4)
        self._detected_combo = self._track_widget(
            ttk.Combobox(form, textvariable=self._detected_label, state="readonly"), "readonly"
        )
        self._detected_combo.grid(row=1, column=1, sticky="ew", padx=(10, 6), pady=4)
        self._detected_combo.bind("<<ComboboxSelected>>", self._detected_selected)
        self._detect_button = self._track_widget(
            ttk.Button(form, text=self._text("Detect", "检测"), command=self._detect)
        )
        self._detect_button.grid(row=1, column=2, sticky="ew", pady=4)
        self._advanced_button = self._track_widget(
            ttk.Button(form, text=self._text("Advanced settings…", "高级设置…"), command=self._toggle_advanced)
        )
        self._advanced_button.grid(row=2, column=0, columnspan=3, sticky="w", pady=(8, 0))

        advanced = self._advanced_frame = ttk.LabelFrame(
            form, text=self._text("Manual browser and driver setup", "手动浏览器及驱动设置"), padding=8,
        )
        advanced.grid(row=3, column=0, columnspan=3, sticky="ew", pady=(10, 4))
        advanced.columnconfigure(1, weight=1)
        ttk.Label(advanced, text=self._text("Browser family", "浏览器类型")).grid(row=0, column=0, sticky="w", pady=4)
        self._browser_combo = self._track_widget(
            ttk.Combobox(advanced, textvariable=self._browser_label,
                         values=tuple(BROWSER_NAMES.values()), state="readonly"), "readonly",
        )
        self._browser_combo.grid(row=0, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
        self._browser_combo.bind("<<ComboboxSelected>>", self._browser_selected)
        ttk.Label(advanced, text=self._text("Executable", "浏览器程序")).grid(row=1, column=0, sticky="w", pady=4)
        self._executable_entry = self._track_widget(ttk.Entry(advanced, textvariable=self._vars["executable"]))
        self._executable_entry.grid(row=1, column=1, sticky="ew", padx=(10, 6), pady=4)
        self._executable_button = self._track_widget(
            ttk.Button(advanced, text=self._text("Browse…", "浏览…"), command=self._browse_executable)
        )
        self._executable_button.grid(row=1, column=2, sticky="ew", pady=4)
        self._override_check = self._track_widget(
            ttk.Checkbutton(advanced, text=self._text("Override the browser's default driver", "覆盖浏览器默认驱动"),
                            variable=self._override_var, command=self._override_changed)
        )
        self._override_check.grid(row=2, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(advanced, text=self._text("Driver family", "驱动类型")).grid(row=3, column=0, sticky="w", pady=4)
        self._driver_combo = self._track_widget(
            ttk.Combobox(advanced, textvariable=self._driver_label,
                         values=tuple(DRIVER_NAMES.values()), state="readonly"), "readonly",
        )
        self._driver_combo.grid(row=3, column=1, columnspan=2, sticky="ew", padx=(10, 0), pady=4)
        self._driver_combo.bind("<<ComboboxSelected>>", self._driver_selected)
        ttk.Label(advanced, text=self._text("Driver mode", "驱动模式")).grid(row=4, column=0, sticky="w", pady=4)
        mode_box = ttk.Frame(advanced)
        mode_box.grid(row=4, column=1, columnspan=2, sticky="w", padx=(10, 0), pady=4)
        self._auto_radio = self._track_widget(
            ttk.Radiobutton(mode_box, text=self._text("Automatic", "自动"), value="auto",
                            variable=self._vars["driver_mode"], command=self._mode_changed)
        )
        self._auto_radio.pack(side="left")
        self._manual_radio = self._track_widget(
            ttk.Radiobutton(mode_box, text=self._text("Manual", "手动"), value="manual",
                            variable=self._vars["driver_mode"], command=self._mode_changed)
        )
        self._manual_radio.pack(side="left", padx=(12, 0))
        ttk.Label(advanced, text=self._text("Driver path", "驱动路径")).grid(row=5, column=0, sticky="w", pady=4)
        self._driver_path_entry = self._track_widget(ttk.Entry(advanced, textvariable=self._vars["driver_path"]))
        self._driver_path_entry.grid(row=5, column=1, sticky="ew", padx=(10, 6), pady=4)
        self._driver_browse_button = self._track_widget(
            ttk.Button(advanced, text=self._text("Browse…", "浏览…"), command=self._browse_driver)
        )
        self._driver_browse_button.grid(row=5, column=2, sticky="ew", pady=4)
        advanced.grid_remove()

        action_bar = ttk.Frame(form)
        action_bar.grid(row=4, column=0, columnspan=3, sticky="ew", pady=(12, 0))
        self._download_button = self._track_widget(
            ttk.Button(action_bar, text=self._text("Download matching driver", "下载匹配的驱动"), command=self._download)
        )
        self._download_button.pack(side="left")
        self._apply_button = self._track_widget(
            ttk.Button(action_bar, text=self._text("Apply — get matching driver if needed", "应用 — 按需获取匹配驱动"), command=self._apply)
        )
        self._apply_button.pack(side="right")

    def _toggle_advanced(self):
        self._advanced_visible = not self._advanced_visible
        if self._advanced_visible:
            self._advanced_frame.grid()
        else:
            self._advanced_frame.grid_remove()
        self._advanced_button.configure(text=self._text(
            "Hide advanced settings" if self._advanced_visible else "Advanced settings…",
            "收起高级设置" if self._advanced_visible else "高级设置…",
        ))
        self.update_idletasks()
        minimum_height = max(540, self.winfo_reqheight())
        self.minsize(780, minimum_height)
        if self.winfo_height() < minimum_height:
            self.geometry(f"{max(780, self.winfo_width())}x{minimum_height}")

    def _build_drivers(self, parent):
        parent.columnconfigure(0, weight=1)
        parent.rowconfigure(1, weight=1)
        ttk.Label(
            parent,
            text=self._text(
                "Cached and system drivers. Select an installed row to use it. Download for profile "
                "gets the driver matching the browser executable in Profiles.",
                "缓存及系统驱动。选择已安装项即可使用；“为当前配置下载”会获取与“配置”页所选浏览器程序匹配的驱动。",
            ),
            wraplength=700,
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))
        self.driver_list = ttk.Treeview(
            parent, columns=("version", "source", "installed", "path"),
            show="tree headings", selectmode="browse",
        )
        headings = (
            ("#0", self._text("Driver", "驱动"), 170),
            ("version", self._text("Version", "版本"), 110),
            ("source", self._text("Source", "来源"), 120),
            ("installed", self._text("Installed", "已安装"), 90),
            ("path", self._text("Path", "路径"), 310),
        )
        for column, title, width in headings:
            self.driver_list.heading(column, text=title)
            self.driver_list.column(column, width=width, stretch=column in ("#0", "path"))
        self.driver_list.grid(row=1, column=0, sticky="nsew")
        self.driver_list.bind("<Double-1>", lambda _event: self._use_cached_driver())
        self._track_widget(self.driver_list)

        actions = ttk.Frame(parent)
        actions.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._refresh_button = self._track_widget(
            ttk.Button(actions, text=self._text("Refresh", "刷新"), command=self._refresh_drivers)
        )
        self._refresh_button.pack(side="left")
        self._use_button = self._track_widget(
            ttk.Button(actions, text=self._text("Use selected driver", "使用所选驱动"), command=self._use_cached_driver)
        )
        self._use_button.pack(side="left", padx=6)
        self._import_button = self._track_widget(
            ttk.Button(actions, text=self._text("Import driver…", "导入驱动…"), command=self._import)
        )
        self._import_button.pack(side="left")
        self._library_download_button = self._track_widget(
            ttk.Button(actions, text=self._text("Download for profile", "为当前配置下载"),
                       command=self._download_for_profile)
        )
        self._library_download_button.pack(side="left", padx=6)

    # ---- Editor state -------------------------------------------------

    def _editor_changed(self, *_args):
        if not self._suspend_traces:
            self._generation += 1
            self._sync_detected_selection()

    def _set_vars(self, values: dict):
        self._suspend_traces = True
        try:
            for key in _PROFILE_FIELDS:
                self._vars[key].set(str(values.get(key) or ""))
            browser = self._vars["browser"].get()
            kind = self._vars["driver_kind"].get()
            self._browser_label.set(BROWSER_NAMES.get(browser, ""))
            self._driver_label.set(DRIVER_NAMES.get(kind, ""))
            default = default_driver_kind(browser) if browser else ""
            self._override_var.set(bool(kind and kind != default))
        finally:
            self._suspend_traces = False
        self._generation += 1
        self._update_advanced_states()
        self._sync_detected_selection()

    @staticmethod
    def _same_executable(left, right):
        if not left or not right:
            return False
        left, right = Path(left).expanduser().resolve(), Path(right).expanduser().resolve()
        if left == right:
            return True
        # Inactive profiles may retain a .app path while discovery returns its
        # executable. Match the same bundle without running or probing it.
        return (left.suffix.lower() == ".app" and left / "Contents" / "MacOS" in right.parents
                or right.suffix.lower() == ".app" and right / "Contents" / "MacOS" in left.parents)

    def _sync_detected_selection(self):
        browser = self._vars["browser"].get()
        executable = self._vars["executable"].get()
        for index, row in enumerate(self._detected):
            if row.get("browser") == browser and self._same_executable(executable, row.get("executable")):
                self._detected_combo.current(index)
                return
        if executable:
            name = BROWSER_NAMES.get(browser, self._text("Manual setup", "手动设置"))
            self._detected_label.set(self._text(f"{name} — manual / saved selection", f"{name} — 手动或已保存选择"))
        else:
            self._detected_label.set("")

    def _snapshot_profile(self) -> dict:
        """Copy every Tk value; call only on the UI thread."""
        profile = dict(self._working)
        profile.update({key: self._vars[key].get().strip() for key in _PROFILE_FIELDS})
        profile["id"] = str(profile.get("id") or uuid.uuid4())
        return profile

    # Kept as a small controller seam for existing callers and focused tests.
    def _profile(self):
        return self._snapshot_profile()

    def _validate_profile(self, profile: dict) -> dict:
        if not profile.get("name"):
            raise ValueError(self._text("Enter a profile name.", "请输入配置名称。"))
        browser = profile.get("browser")
        if browser not in BROWSER_NAMES:
            raise ValueError(self._text("Choose a browser.", "请选择浏览器。"))
        executable = str(profile.get("executable") or "").strip()
        if not executable:
            raise ValueError(self._text("Choose the browser executable.", "请选择浏览器程序路径。"))
        executable_path = Path(executable).expanduser()
        valid_app = executable_path.suffix.lower() == ".app" and executable_path.is_dir()
        if not (executable_path.is_file() or valid_app):
            raise ValueError(self._text("The browser executable does not exist.", "浏览器程序不存在。"))
        if profile.get("driver_kind") not in DRIVER_NAMES:
            raise ValueError(self._text("Choose a driver family.", "请选择驱动类型。"))
        if profile.get("driver_mode") not in ("auto", "manual"):
            raise ValueError(self._text("Choose a driver mode.", "请选择驱动模式。"))
        if profile["driver_mode"] == "manual":
            driver_path = Path(str(profile.get("driver_path") or "")).expanduser()
            if not driver_path.is_file():
                raise ValueError(self._text("Choose an existing driver file.", "请选择存在的驱动文件。"))
        return profile

    def _load_profile(self, profile: dict):
        self._working = dict(profile)
        self._suggested_name = ""
        self._loaded_id = str(profile.get("id") or "") or None
        self._set_vars(profile)
        self._select_profile_row(self._loaded_id)

    def _new_profile(self, _event=None, initial=False):
        self._working = {"id": str(uuid.uuid4())}
        self._suggested_name = ""
        self._loaded_id = None
        self._set_vars({
            "name": "", "browser": "", "executable": "", "driver_kind": "",
            "driver_path": "", "driver_mode": "auto",
        })
        if hasattr(self, "profile_list"):
            self.profile_list.selection_remove(self.profile_list.selection())
        if not initial:
            self._name_entry.focus_set()

    def _browser_selected(self, _event=None):
        browser = next((key for key, label in BROWSER_NAMES.items()
                        if label == self._browser_label.get()), "")
        if not browser:
            return
        previous = self._vars["browser"].get()
        self._suspend_traces = True
        try:
            self._vars["browser"].set(browser)
            if previous != browser:
                self._vars["executable"].set("")
                kind = default_driver_kind(browser)
                self._vars["driver_kind"].set(kind)
                self._driver_label.set(DRIVER_NAMES[kind])
                self._vars["driver_mode"].set("auto")
                self._vars["driver_path"].set("")
                self._override_var.set(False)
                name = self._vars["name"].get().strip()
                if not name or (not self._loaded_id and name == self._suggested_name):
                    self._vars["name"].set(BROWSER_NAMES[browser])
                    self._suggested_name = BROWSER_NAMES[browser]
        finally:
            self._suspend_traces = False
        self._generation += 1
        self._update_advanced_states()
        self._sync_detected_selection()

    def _driver_selected(self, _event=None):
        kind = next((key for key, label in DRIVER_NAMES.items()
                     if label == self._driver_label.get()), "")
        self._vars["driver_kind"].set(kind)

    def _override_changed(self):
        browser = self._vars["browser"].get()
        if browser and (not self._override_var.get() or not self._vars["driver_kind"].get()):
            kind = default_driver_kind(browser)
            self._vars["driver_kind"].set(kind)
            self._driver_label.set(DRIVER_NAMES.get(kind, ""))
        self._update_advanced_states()

    def _mode_changed(self):
        self._update_advanced_states()

    def _update_advanced_states(self):
        if self._busy:
            return
        self._driver_combo.configure(state="readonly" if self._override_var.get() else "disabled")
        # Browsing remains available in automatic mode and makes it manual.
        self._driver_path_entry.configure(
            state="normal" if self._vars["driver_mode"].get() == "manual" else "disabled"
        )

    # ---- Profile actions ---------------------------------------------

    def _refresh_profiles(self):
        self.profile_list.delete(*self.profile_list.get_children())
        active_id = str((self._active or {}).get("id") or "")
        for profile in self._profiles:
            profile_id = str(profile.get("id") or "")
            marker = self._text("Active", "活动") if profile_id == active_id else ""
            browser = BROWSER_NAMES.get(profile.get("browser"), profile.get("browser", ""))
            self.profile_list.insert(
                "", "end", iid=profile_id, text=profile.get("name") or profile_id,
                values=(browser, marker),
            )

    def _select_profile_row(self, profile_id):
        if profile_id and self.profile_list.exists(profile_id):
            self.profile_list.selection_set(profile_id)
            self.profile_list.see(profile_id)

    def _select_profile(self, _event=None):
        selection = self.profile_list.selection()
        if not selection:
            return
        profile_id = selection[0]
        if profile_id == self._loaded_id:
            return
        profile = next((item for item in self._profiles
                        if str(item.get("id")) == profile_id), None)
        if profile is not None:
            self._load_profile(profile)

    def _save(self):
        try:
            profile = self._validate_profile(self._snapshot_profile())
            active_id = str((self._active or {}).get("id") or "")
            if active_id and profile["id"] == active_id:
                raise ValueError(self._text(
                    "The active profile can only be changed through Apply.",
                    "活动配置只能通过“应用”更改。",
                ))
            saved = save_profile(profile, activate=False)
            self._profiles = list(load_profiles())
            self._refresh_profiles()
            self._load_profile(saved)
            self._status_var.set(self._text("Inactive profile saved.", "非活动配置已保存。"))
        except ValueError as exc:
            self._show_error(exc)

    def _delete(self):
        if not self._loaded_id:
            self._show_error(ValueError(self._text("Select a saved profile first.", "请先选择已保存的配置。")))
            return
        active_id = str((self._active or {}).get("id") or "")
        if self._loaded_id == active_id:
            self._show_error(ValueError(
                self._text("The active profile cannot be deleted here.", "不能在此删除活动配置。")
            ))
            return
        if not messagebox.askyesno(
            self._text("Delete profile", "删除配置"),
            self._text("Delete the selected profile?", "确定删除所选配置吗？"), parent=self,
        ):
            return
        try:
            delete_profile(self._loaded_id)
            self._profiles = list(load_profiles())
            self._refresh_profiles()
            self._new_profile(initial=True)
            self._status_var.set(self._text("Profile deleted.", "配置已删除。"))
        except ValueError as exc:
            self._show_error(exc)

    def _apply(self):
        try:
            profile = self._validate_profile(self._snapshot_profile())
            accepted = bool(self.on_apply(profile))
        except ValueError as exc:
            self._show_error(exc)
            return
        if accepted:
            self.destroy()

    # ---- Pickers and library -----------------------------------------

    def _browse_executable(self):
        path = filedialog.askopenfilename(
            parent=self, title=self._text("Choose browser executable", "选择浏览器程序"),
            filetypes=[
                (self._text("Browser applications", "浏览器程序"), "*.app *.exe"),
                (self._text("All files", "所有文件"), "*"),
            ],
        )
        if path:
            self._vars["executable"].set(path)

    def _browse_driver(self):
        path = filedialog.askopenfilename(
            parent=self, title=self._text("Choose driver executable", "选择驱动程序"),
            filetypes=[(self._text("Executable files", "可执行文件"), "*.exe *")],
        )
        if path:
            self._vars["driver_path"].set(path)
            self._vars["driver_mode"].set("manual")
            self._update_advanced_states()

    def _detected_selected(self, _event=None):
        index = self._detected_combo.current()
        if index < 0 or index >= len(self._detected):
            return
        detected = self._detected[index]
        browser = str(detected.get("browser") or "")
        if browser not in BROWSER_NAMES:
            return
        self._suspend_traces = True
        try:
            self._vars["browser"].set(browser)
            self._browser_label.set(BROWSER_NAMES[browser])
            self._vars["executable"].set(str(detected.get("executable") or ""))
            kind = default_driver_kind(browser)
            self._vars["driver_kind"].set(kind)
            self._driver_label.set(DRIVER_NAMES[kind])
            self._vars["driver_mode"].set("auto")
            self._vars["driver_path"].set("")
            self._override_var.set(False)
            name = self._vars["name"].get().strip()
            if not name or (not self._loaded_id and name == self._suggested_name):
                self._vars["name"].set(BROWSER_NAMES[browser])
                self._suggested_name = BROWSER_NAMES[browser]
        finally:
            self._suspend_traces = False
        self._generation += 1
        self._update_advanced_states()
        self._sync_detected_selection()

    def _use_cached_driver(self):
        selection = self.driver_list.selection()
        if not selection:
            self._show_error(ValueError(self._text("Select a driver row first.", "请先选择驱动项。")))
            return
        row = self._driver_rows.get(selection[0], {})
        path = str(row.get("path") or "")
        if not path:
            self._show_error(ValueError(self._text("That driver is not installed.", "该驱动尚未安装。")))
            return
        kind = str(row.get("kind") or "")
        self._vars["driver_kind"].set(kind)
        self._driver_label.set(DRIVER_NAMES.get(kind, kind))
        browser = self._vars["browser"].get()
        self._override_var.set(bool(browser and kind != default_driver_kind(browser)))
        self._vars["driver_path"].set(path)
        self._vars["driver_mode"].set("manual")
        self._update_advanced_states()
        self._status_var.set(self._text("Selected driver added to the editor.", "所选驱动已填入编辑器。"))

    # ---- Background operations --------------------------------------

    def _set_busy(self, busy: bool, label: str = ""):
        self._busy = busy
        for widget, normal_state in self._interactive:
            try:
                widget.configure(state="disabled" if busy else normal_state)
            except tk.TclError:
                pass
        if not busy:
            self._update_advanced_states()
        if label:
            self._status_var.set(label)

    def _start_worker(self, kind, work, *, stale_sensitive=False, status=""):
        if self._closed:
            return False
        # Discovery and inventory share one worker slot. Queue both initial
        # jobs, and coalesce refreshes instead of dropping whichever starts last.
        if kind in ("detect", "library"):
            self._pending_jobs = [job for job in self._pending_jobs if job[0] != kind]
            if self._busy:
                self._pending_jobs.append((kind, work, {"stale_sensitive": stale_sensitive, "status": status}))
                return True
        elif self._busy:
            return False
        self._operation += 1
        operation = self._operation
        generation = self._generation if stale_sensitive else None
        self._set_busy(True, status)
        threading.Thread(
            target=self._worker_entry, args=(operation, generation, kind, work),
            name=f"browser-settings-{kind}", daemon=True,
        ).start()
        return True

    def _run_next_worker(self):
        if not self._closed and not self._busy and self._pending_jobs:
            kind, work, options = self._pending_jobs.pop(0)
            self._start_worker(kind, work, **options)

    def _worker_entry(self, operation, generation, kind, work):
        try:
            result = work()
        except Exception as exc:  # transported to and rendered on the UI thread
            self._queue.put((operation, generation, kind, False, exc))
        else:
            self._queue.put((operation, generation, kind, True, result))

    def _detect(self):
        self._start_worker(
            "detect", detect_browsers,
            status=self._text("Detecting installed browsers…", "正在检测已安装的浏览器…"),
        )

    def _refresh_drivers(self):
        self._start_worker(
            "library", driver_library,
            status=self._text("Refreshing driver library…", "正在刷新驱动库…"),
        )

    def _download(self):
        try:
            # Snapshot every Tk value now, before the worker exists.
            snapshot = self._snapshot_profile()
            # This explicit action requests automatic resolution even if the
            # editor was previously using a manually imported driver.
            snapshot.update(driver_mode="auto", driver_path="")
            snapshot = dict(self._validate_profile(snapshot))
        except ValueError as exc:
            self._show_error(exc)
            return
        self._start_worker(
            "download", lambda profile=snapshot: resolve_profile(profile, allow_download=True),
            stale_sensitive=True,
            status=self._text("Downloading the matching driver…", "正在下载匹配的驱动…"),
        )

    def _download_for_profile(self):
        selected = self.driver_list.selection()
        if selected:
            row = self._driver_rows.get(selected[0], {})
            if row.get("kind") != self._vars["driver_kind"].get():
                self._show_error(ValueError(self._text(
                    "Choose a profile whose browser uses the selected driver first.",
                    "请先选择使用此驱动的浏览器配置。",
                )))
                return
        self._download()

    def _import(self):
        kind = self._vars["driver_kind"].get().strip()
        if kind not in DRIVER_NAMES:
            self._show_error(ValueError(self._text("Choose a driver family first.", "请先选择驱动类型。")))
            return
        path = filedialog.askopenfilename(
            parent=self, title=self._text("Import driver", "导入驱动"),
            filetypes=[(self._text("Executable files", "可执行文件"), "*.exe *")],
        )
        if not path:
            return
        # Plain strings are captured on the UI thread; the helper does all I/O.
        snapshot_kind, snapshot_path = str(kind), str(path)
        self._start_worker(
            "import", lambda: (snapshot_kind, import_driver(snapshot_path, snapshot_kind)),
            stale_sensitive=True,
            status=self._text("Importing driver…", "正在导入驱动…"),
        )

    def _poll(self):
        if self._closed:
            return
        while True:
            try:
                item = self._queue.get_nowait()
            except queue.Empty:
                break
            self._handle_worker_result(item)
        if not self._closed:
            self._after_id = self.after(self.POLL_MS, self._poll)

    def _handle_worker_result(self, item):
        try:
            self._accept_worker_result(item)
        finally:
            self._run_next_worker()

    def _accept_worker_result(self, item):
        operation, generation, kind, ok, payload = item
        if self._closed or operation != self._operation:
            return
        self._set_busy(False)
        if generation is not None and generation != self._generation:
            self._status_var.set(self._text("Ignored an outdated result.", "已忽略过期结果。"))
            return
        if not ok:
            self._show_error(payload)
            return
        if kind == "detect":
            self._detected = list(payload or [])
            labels = []
            for row in self._detected:
                name = row.get("name") or BROWSER_NAMES.get(row.get("browser"), row.get("browser", ""))
                version = str(row.get("browser_version") or row.get("version") or "").strip()
                labels.append(f"{name} — {version}" if version else str(name))
            labels = [f"{label} — {row.get('executable', '')}" if labels.count(label) > 1 else label
                      for label, row in zip(labels, self._detected)]
            self._detected_combo.configure(values=tuple(labels))
            self._sync_detected_selection()
            self._status_var.set(self._text(
                f"Found {len(labels)} browser(s). Choose one, or use Advanced settings for manual setup.",
                f"检测到 {len(labels)} 个浏览器。请选择一个，或通过高级设置手动配置。",
            ))
        elif kind == "library":
            self._render_driver_library(list(payload or []))
            self._status_var.set(self._text("Driver library refreshed.", "驱动库已刷新。"))
        elif kind == "download":
            self._update_from_resolved(payload)
            self._status_var.set(self._text(
                "Driver downloaded; review and Apply to save.",
                "驱动已下载；请检查后点击“应用”保存。",
            ))
            self._refresh_drivers()
        elif kind == "import":
            driver_kind, driver_path = payload
            self._vars["driver_kind"].set(str(driver_kind))
            self._driver_label.set(DRIVER_NAMES.get(driver_kind, driver_kind))
            browser = self._vars["browser"].get()
            self._override_var.set(bool(browser and driver_kind != default_driver_kind(browser)))
            self._vars["driver_path"].set(str(driver_path))
            self._vars["driver_mode"].set("manual")
            self._update_advanced_states()
            self._status_var.set(self._text(
                "Driver imported; review and Apply to save.",
                "驱动已导入；请检查后点击“应用”保存。",
            ))
            self._refresh_drivers()

    def _update_from_resolved(self, resolved):
        if not isinstance(resolved, dict):
            self._show_error(ValueError(self._text(
                "Driver resolution returned invalid data.", "驱动解析结果无效。"
            )))
            return
        self._suspend_traces = True
        try:
            for key in ("executable", "driver_path", "driver_kind", "driver_mode"):
                if key in resolved and resolved[key] is not None:
                    self._vars[key].set(str(resolved[key]))
            kind = self._vars["driver_kind"].get()
            self._driver_label.set(DRIVER_NAMES.get(kind, kind))
        finally:
            self._suspend_traces = False
        self._generation += 1
        self._update_advanced_states()
        self._sync_detected_selection()

    def _render_driver_library(self, rows):
        self.driver_list.delete(*self.driver_list.get_children())
        self._driver_rows = {}
        for index, source_row in enumerate(rows):
            row = dict(source_row)
            item_id = f"driver-{index}"
            self._driver_rows[item_id] = row
            kind = str(row.get("kind") or "")
            path = str(row.get("path") or "")
            installed = bool(row.get("installed", bool(path)))
            self.driver_list.insert(
                "", "end", iid=item_id,
                text=DRIVER_NAMES.get(kind, row.get("name") or kind),
                values=(
                    row.get("version") or "—", row.get("source") or "—",
                    self._text("Yes", "是") if installed else self._text("No", "否"),
                    path or "—",
                ),
            )

    def _show_error(self, exc):
        if isinstance(exc, ValueError) and str(exc).strip():
            message = str(exc).strip()
        else:
            message = self._text("The operation could not be completed.", "操作未能完成。")
        messagebox.showerror(self._text("Browser settings", "浏览器设置"), message, parent=self)

    def destroy(self):
        if self._closed:
            return
        self._closed = True
        self._operation += 1
        self._pending_jobs.clear()
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None
        super().destroy()


__all__ = ["BrowserSettingsDialog"]
