import queue
import sys
import tempfile
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
    dialog._generation = 2
    dialog._operation = 0
    dialog._busy = False
    dialog._closed = False
    dialog._suspend_traces = False
    dialog._queue = queue.Queue()
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

    def test_library_download_requires_profile_paired_with_selected_driver(self):
        dialog = make_dialog(str(self.executable))
        dialog.driver_list = Mock()
        dialog.driver_list.selection.return_value = ("row",)
        dialog._driver_rows = {"row": {"kind": "geckodriver"}}
        dialog._download = Mock()
        dialog._download_for_profile()
        dialog._download.assert_not_called()
        dialog._show_error.assert_called_once()
        dialog._driver_rows["row"]["kind"] = "chromedriver"
        dialog._download_for_profile()
        dialog._download.assert_called_once_with()

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


class BrowserSettingsTkTests(unittest.TestCase):
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
                patch.object(bs.BrowserSettingsDialog, "_refresh_drivers"),
            ):
                for chinese in (False, True):
                    dialog = bs.BrowserSettingsDialog(root, Mock(return_value=False), chinese=chinese)
                    try:
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
                                action = dialog._apply_button if tab == 0 else dialog._library_download_button
                                self.assertTrue(action.winfo_viewable())
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
