import queue
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import browser_settings as bs


class FakeVar:
    def __init__(self, value=""):
        self.value = value

    def get(self):
        return self.value

    def set(self, value):
        self.value = value


def make_dialog(executable, *, profile_id="profile-1", active=None):
    dialog = object.__new__(bs.BrowserSettingsDialog)
    profile = {
        "id": profile_id,
        "name": "Work",
        "browser": "chrome",
        "executable": executable,
        "driver_kind": "chromedriver",
        "driver_path": "",
        "driver_mode": "auto",
    }
    dialog.chinese = False
    dialog._working = {"id": profile_id}
    dialog._vars = {key: FakeVar(profile[key]) for key in bs._PROFILE_FIELDS}
    dialog._active = active
    dialog._profiles = []
    dialog._loaded_id = profile_id
    dialog._suggested_name = ""
    dialog._generation = 2
    dialog._operation = 0
    dialog._busy = False
    dialog._closed = False
    dialog._suspend_traces = False
    dialog._queue = queue.Queue()
    dialog._pending_jobs = []
    dialog._ready_after_id = None
    dialog._ready_generation = None
    dialog._download_progress = None
    dialog._detected = []
    dialog._detected_combo = Mock()
    dialog._detected_label = FakeVar()
    dialog._browser_label = FakeVar()
    dialog._driver_label = FakeVar()
    dialog._status_var = FakeVar()
    dialog._override_var = FakeVar(False)
    dialog._show_error = Mock()
    return dialog


class BrowserSettingsControllerTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.executable = Path(self.tempdir.name, "browser.exe")
        self.executable.touch()

    def tearDown(self):
        self.tempdir.cleanup()

    def test_360_browser_uses_chromedriver(self):
        self.assertEqual(bs.default_driver_kind("360e"), "chromedriver")
        self.assertIn("360e", bs.BROWSER_NAMES)

    def test_apply_passes_flat_snapshot_and_false_keeps_dialog_open(self):
        dialog = make_dialog(str(self.executable))
        dialog.on_apply = Mock(return_value=False)
        dialog.destroy = Mock()

        with patch.object(bs, "save_profile") as persist:
            dialog._apply()

        passed = dialog.on_apply.call_args.args[0]
        self.assertEqual(set(passed).intersection(bs._PROFILE_FIELDS), set(bs._PROFILE_FIELDS))
        self.assertEqual(passed["browser"], "chrome")
        persist.assert_not_called()
        dialog.destroy.assert_not_called()
        dialog._show_error.assert_not_called()

    def test_apply_true_closes_and_value_error_is_presented(self):
        dialog = make_dialog(str(self.executable))
        dialog.on_apply = Mock(return_value=True)
        dialog.destroy = Mock()
        dialog._apply()
        dialog.destroy.assert_called_once_with()

        rejected = make_dialog(str(self.executable))
        rejected.on_apply = Mock(side_effect=ValueError("safe model message"))
        rejected.destroy = Mock()
        rejected._apply()
        rejected._show_error.assert_called_once()
        self.assertEqual(str(rejected._show_error.call_args.args[0]), "safe model message")
        rejected.destroy.assert_not_called()

    def test_save_inactive_uses_nonactivating_model_call(self):
        dialog = make_dialog(str(self.executable), active={"id": "active"})
        dialog._refresh_profiles = Mock()
        dialog._load_profile = Mock()
        saved = dialog._snapshot_profile()

        with (
            patch.object(bs, "save_profile", return_value=saved) as save,
            patch.object(bs, "load_profiles", return_value=[saved]) as load,
        ):
            dialog._save()

        save.assert_called_once_with(saved, activate=False)
        load.assert_called_once_with()
        dialog._refresh_profiles.assert_called_once_with()
        dialog._load_profile.assert_called_once_with(saved)

    def test_save_and_delete_refuse_active_profile(self):
        active = {"id": "profile-1"}
        dialog = make_dialog(str(self.executable), active=active)

        with patch.object(bs, "save_profile") as save:
            dialog._save()
        save.assert_not_called()
        self.assertIn("active profile", str(dialog._show_error.call_args.args[0]).lower())

        dialog._show_error.reset_mock()
        with patch.object(bs, "delete_profile") as delete:
            dialog._delete()
        delete.assert_not_called()
        self.assertIn("active profile", str(dialog._show_error.call_args.args[0]).lower())

    def test_download_captures_tk_values_before_worker_starts(self):
        dialog = make_dialog(str(self.executable))
        captured = {}

        def capture(kind, work, **options):
            captured.update(kind=kind, work=work, options=options)
            return True

        dialog._start_worker = capture
        with patch.object(bs, "resolve_profile", return_value={}) as resolve:
            dialog._download()
            dialog._vars["name"].set("Changed after start")
            captured["work"]()

        self.assertEqual(captured["kind"], "download")
        self.assertTrue(captured["options"]["stale_sensitive"])
        snapshot = resolve.call_args.args[0]
        self.assertEqual(snapshot["name"], "Work")
        self.assertEqual(snapshot["executable"], str(self.executable))
        self.assertTrue(resolve.call_args.kwargs["allow_download"])

    def test_explicit_download_replaces_manual_mode_only_in_worker_snapshot(self):
        dialog = make_dialog(str(self.executable))
        dialog._vars["driver_mode"].set("manual")
        dialog._vars["driver_path"].set("/missing/manual/driver")
        captured = {}
        dialog._start_worker = lambda kind, work, **options: captured.update(work=work)
        with patch.object(bs, "resolve_profile", return_value={}) as resolve:
            dialog._download()
            captured["work"]()
        self.assertEqual(resolve.call_args.args[0]["driver_mode"], "auto")
        self.assertEqual(resolve.call_args.args[0]["driver_path"], "")
        self.assertEqual(dialog._vars["driver_mode"].get(), "manual")

    def test_apply_stays_disabled_until_offline_resolution_succeeds(self):
        dialog = make_dialog(str(self.executable))
        dialog._apply_button = Mock()
        callbacks = []
        dialog.after = lambda delay, callback: callbacks.append(callback) or "timer"
        dialog.after_cancel = Mock()
        with patch.object(bs, "resolve_profile", return_value={"driver_path": "/ready"}) as resolve:
            dialog._schedule_readiness()
            dialog._apply_button.configure.assert_called_with(state="disabled")
            with patch.object(bs.threading, "Thread") as thread:
                callbacks.pop()()
                thread.call_args.kwargs["target"]()
            dialog._accept_readiness(*dialog._queue.get_nowait()[1:])
        resolve.assert_called_once()
        self.assertFalse(resolve.call_args.kwargs["allow_download"])
        dialog._apply_button.configure.assert_called_with(state="normal")
        dialog._generation += 1
        dialog._accept_readiness(dialog._generation, False)
        dialog._apply_button.configure.assert_called_with(state="disabled")

    def test_driver_delete_action_rejects_shared_cache(self):
        dialog = make_dialog(str(self.executable))
        dialog._driver_rows = {"one": {"path": "/shared/driver", "source": "selenium-cache"}}
        dialog.driver_list = Mock()
        dialog.driver_list.selection.return_value = ("one",)
        dialog._delete_driver_button = Mock()
        dialog._driver_library_selected()
        dialog._delete_driver_button.configure.assert_called_with(state="disabled")
        with patch.object(bs, "delete_managed_driver") as remove:
            dialog._delete_driver()
        remove.assert_not_called()
        dialog._show_error.assert_called_once()

    def test_driver_delete_action_uses_exact_managed_path(self):
        dialog = make_dialog(str(self.executable))
        dialog._driver_rows = {"one": {"path": "/app/driver/one", "source": "cache"}}
        dialog.driver_list = Mock()
        dialog.driver_list.selection.return_value = ("one",)
        captured = {}
        dialog._start_worker = lambda kind, work, **options: captured.update(kind=kind, work=work)
        with patch.object(bs.messagebox, "askyesno", return_value=True), \
                patch.object(bs, "delete_managed_driver") as remove:
            dialog._delete_driver()
            captured["work"]()
        self.assertEqual(captured["kind"], "delete_driver")
        remove.assert_called_once_with("/app/driver/one")

    def test_stale_download_result_cannot_replace_editor(self):
        dialog = make_dialog(str(self.executable))
        dialog._operation = 9
        dialog._generation = 5
        dialog._set_busy = Mock()
        dialog._update_from_resolved = Mock()
        dialog._refresh_drivers = Mock()

        dialog._handle_worker_result((9, 4, "download", True, {"driver_path": "/old"}))

        dialog._set_busy.assert_called_once_with(False)
        dialog._update_from_resolved.assert_not_called()
        dialog._refresh_drivers.assert_not_called()
        self.assertIn("outdated", dialog._status_var.get())

    def test_worker_queues_value_error_without_touching_tk(self):
        dialog = make_dialog(str(self.executable))

        def fail():
            raise ValueError("sanitized failure")

        dialog._worker_entry(3, 2, "detect", fail)
        operation, generation, kind, ok, error = dialog._queue.get_nowait()
        self.assertEqual((operation, generation, kind, ok), (3, 2, "detect", False))
        self.assertIsInstance(error, ValueError)
        self.assertEqual(str(error), "sanitized failure")

    def test_same_profile_selection_does_not_reload_or_reset_edits(self):
        dialog = make_dialog(str(self.executable))
        dialog.profile_list = Mock()
        dialog.profile_list.selection.return_value = ("profile-1",)
        dialog._load_profile = Mock()
        dialog._select_profile()
        dialog._load_profile.assert_not_called()

    def test_closed_dialog_ignores_late_worker_result(self):
        dialog = make_dialog(str(self.executable))
        dialog._closed = True
        dialog._set_busy = Mock()
        dialog._update_from_resolved = Mock()
        dialog._handle_worker_result((0, 2, "download", True, {}))
        dialog._set_busy.assert_not_called()
        dialog._update_from_resolved.assert_not_called()

    def test_unexpected_worker_error_is_not_leaked_to_message_box(self):
        dialog = make_dialog(str(self.executable))
        # Exercise the real renderer rather than the per-test recording mock.
        del dialog._show_error
        with patch.object(bs.messagebox, "showerror") as show:
            bs.BrowserSettingsDialog._show_error(dialog, RuntimeError("private filesystem detail"))
        shown_message = show.call_args.args[1]
        self.assertNotIn("private filesystem detail", shown_message)
        self.assertIn("could not be completed", shown_message)

    def test_initial_detection_and_library_jobs_are_serialized_and_not_dropped(self):
        dialog = make_dialog(str(self.executable))
        dialog._set_busy = lambda busy, label="": setattr(dialog, "_busy", busy)
        dialog._sync_detected_selection = Mock()
        dialog._render_driver_library = Mock()
        with patch.object(bs.threading, "Thread") as thread:
            dialog._detect()
            dialog._refresh_drivers()
            dialog._refresh_drivers()
            self.assertEqual(thread.call_count, 1)
            self.assertEqual([job[0] for job in dialog._pending_jobs], ["library"])
            dialog._handle_worker_result((1, None, "detect", True, []))
            self.assertEqual(thread.call_count, 2)
            self.assertEqual(thread.call_args.kwargs["args"][2], "library")
            dialog._handle_worker_result((2, None, "library", True, []))
        self.assertFalse(dialog._busy)
        self.assertEqual(dialog._pending_jobs, [])
        dialog._render_driver_library.assert_called_once_with([])

    def test_detection_completion_matches_current_editor_without_restoring_old_profile(self):
        dialog = make_dialog(str(self.executable))
        dialog._vars["name"].set("Current edited name")
        dialog._set_busy = Mock()
        profile_before = dialog._snapshot_profile()
        dialog._handle_worker_result((0, None, "detect", True, [
            {"browser": "chrome", "name": "Google Chrome", "executable": str(self.executable)},
        ]))
        self.assertEqual(dialog._snapshot_profile(), profile_before)
        dialog._detected_combo.current.assert_called_with(0)

    def test_same_app_bundle_matches_discovered_executable(self):
        bundle = self.executable.parent / "Browser.app"
        binary = bundle / "Contents" / "MacOS" / "Browser"
        self.assertTrue(bs.BrowserSettingsDialog._same_executable(str(bundle), str(binary)))
        self.assertFalse(bs.BrowserSettingsDialog._same_executable(str(bundle), str(self.executable)))


class BrowserSettingsTkTests(unittest.TestCase):
    def test_auto_detection_selection_saved_profiles_and_advanced_toggle(self):
        try:
            root = bs.tk.Tk()
        except bs.tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        try:
            with tempfile.TemporaryDirectory() as directory:
                rows = [
                    {"browser": browser, "name": name, "executable": str(Path(directory, browser)),
                     "browser_version": version}
                    for browser, name, version in (("chrome", "Google Chrome", "150.0"),
                                                   ("firefox", "Mozilla Firefox", "145.0"),
                                                   ("safari", "Safari", "26.0"))
                ]
                for row in rows:
                    Path(row["executable"]).touch()
                active = {"id": "safari", "name": "My Safari", "browser": "safari",
                          "executable": rows[2]["executable"], "driver_kind": "safaridriver",
                          "driver_mode": "auto", "driver_path": ""}
                other = {**active, "id": "firefox", "name": "My Firefox", "browser": "firefox",
                         "executable": rows[1]["executable"], "driver_kind": "geckodriver",
                         "driver_mode": "manual", "driver_path": str(Path(directory, "manual-driver"))}
                ui_thread = threading.get_ident()

                def detect():
                    self.assertNotEqual(threading.get_ident(), ui_thread)
                    return rows

                def library():
                    self.assertNotEqual(threading.get_ident(), ui_thread)
                    return [{"kind": "chromedriver", "installed": False}]

                with (
                    patch.object(bs, "load_profiles", return_value=[active, other]),
                    patch.object(bs, "get_active_profile", return_value=active),
                    patch.object(bs, "detect_browsers", side_effect=detect) as detector,
                    patch.object(bs, "driver_library", side_effect=library) as inventory,
                    patch.object(bs, "resolve_profile") as resolver,
                ):
                    for chinese in (False, True):
                        dialog = bs.BrowserSettingsDialog(root, Mock(return_value=False), chinese=chinese)
                        try:
                            root.update()
                            self._assert_children_fit(dialog)
                            deadline = time.monotonic() + 3
                            while (dialog._busy or dialog._pending_jobs) and time.monotonic() < deadline:
                                root.update()
                                time.sleep(.005)
                            root.update()
                            self.assertFalse(dialog._busy)
                            self.assertFalse(dialog._pending_jobs)
                            self.assertEqual(dialog._detected_combo.current(), 2)
                            self.assertEqual(dialog._vars["name"].get(), "My Safari")
                            self.assertFalse(dialog._browser_combo.winfo_viewable())
                            self.assertFalse(dialog._executable_entry.winfo_viewable())
                            self.assertTrue(dialog._detected_combo.winfo_viewable())
                            self.assertTrue(dialog._driver_rows)

                            dialog.profile_list.selection_set("firefox")
                            dialog.profile_list.event_generate("<<TreeviewSelect>>")
                            root.update()
                            self.assertEqual(dialog._detected_combo.current(), 1)
                            self.assertEqual(dialog._vars["name"].get(), "My Firefox")
                            self.assertEqual(dialog._vars["driver_mode"].get(), "manual")
                            self.assertEqual(dialog._vars["driver_path"].get(), other["driver_path"])

                            dialog._new_button.invoke()
                            root.update()
                            self.assertEqual(dialog._vars["browser"].get(), "")
                            self.assertEqual(dialog._detected_label.get(), "")
                            dialog._detected_combo.current(0)
                            dialog._detected_combo.event_generate("<<ComboboxSelected>>")
                            root.update()
                            self.assertEqual(dialog._vars["name"].get(), "Google Chrome")
                            self.assertEqual(dialog._vars["browser"].get(), "chrome")
                            self.assertEqual(dialog._vars["executable"].get(), rows[0]["executable"])
                            self.assertEqual(dialog._vars["driver_kind"].get(), "chromedriver")
                            self.assertEqual(dialog._vars["driver_mode"].get(), "auto")
                            dialog._detected_combo.current(1)
                            dialog._detected_combo.event_generate("<<ComboboxSelected>>")
                            root.update()
                            self.assertEqual(dialog._vars["name"].get(), "Mozilla Firefox")
                            dialog._vars["name"].set("My new profile")
                            dialog._detected_combo.current(0)
                            dialog._detected_combo.event_generate("<<ComboboxSelected>>")
                            root.update()
                            self.assertEqual(dialog._vars["name"].get(), "My new profile")

                            dialog._advanced_button.invoke()
                            root.update()
                            self.assertTrue(dialog._browser_combo.winfo_viewable())
                            self.assertTrue(dialog._executable_entry.winfo_viewable())
                            self.assertTrue(dialog._apply_button.winfo_viewable())
                            self._assert_children_fit(dialog)
                            dialog._browser_combo.set(bs.BROWSER_NAMES["custom"])
                            dialog._browser_combo.event_generate("<<ComboboxSelected>>")
                            root.update()
                            self.assertEqual(dialog._vars["executable"].get(), "")
                            dialog._vars["executable"].set(str(Path(directory, "custom-browser")))
                            root.update()
                            self.assertEqual(dialog._vars["browser"].get(), "custom")
                            self.assertEqual(dialog._detected_combo.current(), -1)
                            dialog._advanced_button.invoke()
                            root.update()
                            self.assertFalse(dialog._browser_combo.winfo_viewable())
                            self.assertTrue(dialog._apply_button.winfo_viewable())
                        finally:
                            dialog.destroy()
                    self.assertEqual(detector.call_count, 2)
                    self.assertEqual(inventory.call_count, 2)
                    # Readiness checks may run asynchronously while the
                    # dialog is open. They must never trigger downloads.
                    for call in resolver.call_args_list:
                        self.assertEqual(len(call.args), 1)
                        self.assertIs(
                            call.kwargs.get("allow_download"), False
                        )
        finally:
            root.destroy()

    def test_real_dialog_constructs_with_visible_actions_in_both_languages(self):
        try:
            root = bs.tk.Tk()
        except bs.tk.TclError as exc:
            self.skipTest(f"Tk display unavailable: {exc}")
        root.withdraw()
        try:
            with (
                patch.object(bs, "load_profiles", return_value=[]),
                patch.object(bs, "get_active_profile", return_value=None),
                patch.object(bs.BrowserSettingsDialog, "_detect"),
                patch.object(bs.BrowserSettingsDialog, "_refresh_drivers"),
            ):
                for chinese in (False, True):
                    dialog = bs.BrowserSettingsDialog(root, Mock(return_value=False), chinese=chinese)
                    try:
                        root.update()
                        self._assert_children_fit(dialog)
                        self.assertIs(dialog.window, dialog)
                        self.assertEqual(dialog._vars["browser"].get(), "")
                        notebook = next(widget for widget in dialog.winfo_children()[0].winfo_children()
                                        if isinstance(widget, bs.ttk.Notebook))
                        for geometry in ("860x680", "780x680"):
                            dialog.geometry(geometry)
                            for tab in (0, 1):
                                notebook.select(tab)
                                root.update()
                                self._assert_children_fit(dialog)
                                action = dialog._download_button if tab == 0 else dialog._import_button
                                self.assertTrue(action.winfo_viewable())
                            self.assertFalse(hasattr(dialog, "_library_download_button"))
                        dialog._show_download_progress()
                        root.update()
                        popup = dialog._download_progress[0]
                        progress_status = dialog._download_progress[2]
                        self.assertTrue(popup.winfo_exists())
                        dialog._finish_download_progress(True)
                        self.assertIn("Apply" if not chinese else "应用", progress_status.get())
                        popup.destroy()
                        dialog.window.lift()
                    finally:
                        dialog.window.destroy()
        finally:
            root.destroy()

    def _assert_children_fit(self, parent):
        for child in parent.winfo_children():
            if not child.winfo_ismapped():
                continue
            self.assertLessEqual(child.winfo_x() + child.winfo_width(), parent.winfo_width() + 2,
                                 f"{child.winfo_class()} clipped horizontally")
            self.assertLessEqual(child.winfo_y() + child.winfo_height(), parent.winfo_height() + 2,
                                 f"{child.winfo_class()} clipped vertically")
            self._assert_children_fit(child)


if __name__ == "__main__":
    unittest.main()
