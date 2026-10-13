"""Focused profile, strict driver resolution and Selenium launch regression tests."""
import json
import os
import plistlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import ExitStack
from pathlib import Path
from types import ModuleType, SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
import browser_config as bc


def fake_selenium():
    """Only constructor doubles: the suite never executes browsers or drivers."""
    modules = {}
    selenium = ModuleType("selenium")
    webdriver = ModuleType("selenium.webdriver")
    selenium.webdriver = webdriver
    modules.update({"selenium": selenium, "selenium.webdriver": webdriver})

    class Options:
        def __init__(self):
            self.arguments = []
        def add_argument(self, arg):
            self.arguments.append(arg)

    class Service:
        def __init__(self, executable_path=None, **kwargs):
            self.path = os.environ.get("SE_CHROMEDRIVER", executable_path)
            self.DRIVER_PATH_ENV_KEY = "SE_CHROMEDRIVER"

    for name in ("chrome", "edge", "firefox", "safari"):
        for suffix, cls in (("options", Options), ("service", Service)):
            module = ModuleType(f"selenium.webdriver.{name}.{suffix}")
            setattr(module, "Options" if suffix == "options" else "Service", cls)
            modules[module.__name__] = module
        setattr(webdriver, name.capitalize(), Mock())
    manager = ModuleType("selenium.webdriver.common.selenium_manager")
    manager.SeleniumManager = SimpleNamespace(_get_binary=Mock(return_value=Path("/packaged/selenium-manager")))
    modules[manager.__name__] = manager
    return modules, webdriver


class BrowserConfigTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.storage_root_impl = bc.storage_root
        self.stack = ExitStack()
        self.stack.enter_context(patch.object(bc, "storage_root", return_value=self.root / "resources"))
        self.stack.enter_context(patch.object(bc.platform, "system", return_value="Darwin"))
        self.exe = self.file("selected-browser")
        self.driver = self.file("chromedriver")
        self.profile = {"id": "one", "name": "Office Chrome", "browser": "chrome",
                        "executable": str(self.exe), "driver_kind": "chromedriver",
                        "driver_path": "", "driver_mode": "auto"}

    def tearDown(self):
        self.stack.close()
        self.temporary.cleanup()

    def file(self, name):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"fixture")
        path.chmod(0o700)
        return path

    def resolve(self, profile=None, **kwargs):
        with (patch.object(bc, "_browser_version", return_value="150.0.7777.10"),
              patch.object(bc, "_driver_details", return_value="150.0.7777.2")):
            return bc.resolve_profile(profile or self.profile, **kwargs)

    def test_first_run_never_picks_platform_or_legacy_default(self):
        self.assertEqual(bc.load_profiles(), [])
        self.assertIsNone(bc.get_active_profile())
        legacy = bc.storage_root() / "browser.json"
        legacy.parent.mkdir(parents=True)
        legacy.write_text('{"browser_choice":"msedge"}')
        self.assertIsNone(bc.get_active_profile())
        self.assertFalse(bc.settings_path().exists())

    def test_save_inactive_and_explicit_active_selection_round_trip(self):
        self.assertEqual(bc.save_profile(self.profile), self.profile)
        self.assertIsNone(bc.get_active_profile())
        second = {**self.profile, "id": "two", "name": "Another"}
        bc.save_profile(second)
        self.assertEqual(bc.set_active_profile("two"), second)
        self.assertEqual(bc.get_active_profile(), second)
        self.assertEqual(len(bc.load_profiles()), 2)
        bc.save_profile({**self.profile, "name": "Updated inactive"})
        self.assertEqual(bc.get_active_profile()["id"], "two")

    def test_activation_unknown_id_is_rejected_without_change(self):
        bc.save_profile(self.profile, activate=True)
        with self.assertRaises(ValueError):
            bc.set_active_profile("absent")
        self.assertEqual(bc.get_active_profile()["id"], "one")

    def test_delete_active_clears_selection_never_activates_other_profile(self):
        bc.save_profile(self.profile, activate=True)
        bc.save_profile({**self.profile, "id": "two"})
        bc.delete_profile("one")
        self.assertIsNone(bc.get_active_profile())
        self.assertEqual(len(bc.load_profiles()), 1)

    def test_generated_profile_id_and_automatic_kind(self):
        p = {key: val for key, val in self.profile.items() if key not in ("id", "driver_kind")}
        saved = bc.save_profile(p)
        self.assertTrue(saved["id"])
        self.assertEqual(saved["driver_kind"], "chromedriver")
        self.assertNotIn("id", p)

    def test_corrupt_or_malformed_storage_is_not_overwritten(self):
        for text in ("not json", '{"profiles":[null]}', '{"profiles":[],"active_id":"missing"}'):
            path = bc.settings_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
            with self.assertRaises(ValueError):
                bc.save_profile(self.profile)
            self.assertEqual(path.read_text(), text)

    def test_failed_atomic_write_preserves_previous_profile(self):
        bc.save_profile(self.profile)
        old = bc.settings_path().read_bytes()
        with patch.object(bc.os, "replace", side_effect=OSError("sensitive path")):
            with self.assertRaises(ValueError) as error:
                bc.save_profile({**self.profile, "name": "New"})
        self.assertNotIn("sensitive", str(error.exception))
        self.assertEqual(bc.settings_path().read_bytes(), old)

    def test_no_selection_missing_executable_and_invalid_kind_do_not_resolve(self):
        for profile in (None, {}, {**self.profile, "executable": ""}, {**self.profile, "driver_kind": "geckodriver"}):
            with patch.object(bc, "_manager") as manager, patch.object(bc, "detect_browsers") as detect:
                with self.assertRaises(ValueError):
                    bc.resolve_profile(profile, allow_download=True)
                manager.assert_not_called()
                detect.assert_not_called()

    def test_missing_selected_browser_never_tries_another_installation(self):
        with patch.object(bc, "_manager") as manager, patch.object(bc, "detect_browsers") as detect:
            with self.assertRaisesRegex(ValueError, "missing"):
                bc.resolve_profile({**self.profile, "executable": str(self.root / "missing")}, allow_download=True)
            manager.assert_not_called()
            detect.assert_not_called()

    def test_manual_missing_path_does_not_fall_back_even_if_download_allowed(self):
        profile = {**self.profile, "driver_mode": "manual"}
        with patch.object(bc, "_manager") as manager, patch.object(bc, "driver_library") as inventory:
            with self.assertRaisesRegex(ValueError, "manual driver path"):
                self.resolve(profile, allow_download=True)
            manager.assert_not_called()
            inventory.assert_not_called()

    def test_manual_wrong_version_rejected(self):
        with patch.object(bc, "_browser_version", return_value="150.0.7777.10"), patch.object(bc, "_driver_details", return_value="151.0.2.1"):
            with self.assertRaisesRegex(ValueError, "does not match"):
                bc.resolve_profile({**self.profile, "driver_mode": "manual", "driver_path": str(self.driver)})

    def test_cache_selects_matching_driver_instead_of_latest(self):
        newer = self.file("cache/151.0.1.1/chromedriver")
        older = self.file("cache/150.0.7777.2/chromedriver")
        rows = [{"kind": "chromedriver", "path": str(path), "version": version}
                for path, version in ((newer, "151.0.1.1"), (older, "150.0.7777.2"))]
        versions = {str(newer): "151.0.1.1", str(older): "150.0.7777.2"}
        with (patch.object(bc, "_browser_version", return_value="150.0.7777.10"),
              patch.object(bc, "driver_library", return_value=rows),
              patch.object(bc, "_driver_details", side_effect=lambda path, kind: versions[str(path)]),
              patch.object(bc, "_manager") as manager):
            resolved = bc.resolve_profile(self.profile)
        self.assertEqual(resolved["driver_path"], str(older))
        self.assertEqual(resolved["executable"], str(self.exe))
        self.assertNotIn("profile", resolved)
        manager.assert_not_called()

    def test_missing_cache_is_offline_by_default(self):
        with patch.object(bc, "driver_library", return_value=[]), patch.object(bc, "_manager") as manager:
            with self.assertRaisesRegex(ValueError, "Matching driver is missing"):
                self.resolve()
            manager.assert_not_called()

    def test_explicit_download_passes_selected_executable_and_detected_version(self):
        with patch.object(bc, "driver_library", return_value=[]), patch.object(bc, "_manager", return_value=str(self.driver)) as manager:
            result = self.resolve(allow_download=True)
        passed, version, enabled = manager.call_args.args
        self.assertEqual(passed["executable"], str(self.exe))
        self.assertEqual(version, "150.0.7777.10")
        self.assertTrue(enabled)
        self.assertEqual(result["driver_path"], str(self.driver))

    def test_unknown_version_never_downloads_latest(self):
        with patch.object(bc, "_browser_version", return_value=None), patch.object(bc, "_manager") as manager:
            with self.assertRaisesRegex(ValueError, "engine version"):
                bc.resolve_profile(self.profile, allow_download=True)
            manager.assert_not_called()

    def test_experimental_360_requires_manual_when_engine_unknown(self):
        profile = {**self.profile, "browser": "360e"}
        with patch.object(bc, "_manager") as manager:
            with self.assertRaisesRegex(ValueError, "experimental"):
                self.resolve(profile, allow_download=True)
            manager.assert_not_called()
        manual = {**profile, "driver_mode": "manual", "driver_path": str(self.driver)}
        self.assertEqual(self.resolve(manual)["driver_path"], str(self.driver))

    def test_driver_identity_uses_output_not_filename_and_sanitizes_failures(self):
        renamed = self.file("renamed-driver")
        with patch.object(bc, "_run", return_value=SimpleNamespace(returncode=0, stdout="ChromeDriver 150.0.7777.2", stderr="")):
            self.assertEqual(bc._driver_details(renamed, "chromedriver"), "150.0.7777.2")
            with self.assertRaisesRegex(ValueError, "identity"):
                bc._driver_details(renamed, "geckodriver")
        with patch.object(bc, "_run", side_effect=subprocess.TimeoutExpired("private command", 8)):
            with self.assertRaises(ValueError) as error:
                bc._driver_details(renamed, "chromedriver")
            self.assertNotIn("private command", str(error.exception))

    def test_import_is_versioned_and_inventory_lists_all_kinds_without_execution(self):
        with patch.object(bc, "_driver_details", return_value="150.0.7777.2"):
            imported = bc.import_driver(self.driver, "chromedriver")
        self.assertEqual(Path(imported).read_bytes(), b"fixture")
        self.assertIn("/drivers/chromedriver/150.0.7777.2/", imported)
        with patch.object(bc, "_run") as run, patch.object(bc.Path, "home", return_value=self.root):
            rows = bc.driver_library()
        self.assertEqual({row["kind"] for row in rows if not row["installed"]}, set(bc.DRIVER_NAMES))
        self.assertTrue(any(row["path"] == imported and row["version"] == "150.0.7777.2" for row in rows))
        run.assert_not_called()

    def test_macos_bundle_and_detection_are_read_only(self):
        app = self.root / "Chrome.app"
        binary = self.file("Chrome.app/Contents/MacOS/Chrome")
        (app / "Contents/Info.plist").write_bytes(plistlib.dumps({
            "CFBundleExecutable": "Chrome", "CFBundleShortVersionString": "150.0.7777.10",
        }))
        with (patch.object(bc, "_installation_candidates", return_value=iter([("chrome", app), ("chrome", app)])),
              patch.object(bc, "_run") as run):
            rows = bc.detect_browsers()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["executable"], str(binary))
        self.assertEqual(rows[0]["browser_version"], "150.0.7777.10")
        run.assert_not_called()
        self.assertFalse(bc.storage_root().exists())

    def test_bundle_cannot_escape_executable_directory(self):
        app = self.root / "Invalid.app"
        (app / "Contents").mkdir(parents=True)
        (app / "Contents/Info.plist").write_bytes(plistlib.dumps({"CFBundleExecutable": "../../other"}))
        with self.assertRaisesRegex(ValueError, "bundle"):
            bc.browser_executable(app)

    def test_driver_family_and_firefox_support_ranges(self):
        for browser, expected in (("edge", "msedgedriver"), ("firefox", "geckodriver"),
                                  ("safari", "safaridriver"), ("360e", "chromedriver")):
            self.assertEqual(bc.default_driver_kind(browser), expected)
        bc._check_compatibility("geckodriver", "115.0", "0.36.0")
        bc._check_compatibility("geckodriver", "120.0", "0.33.0")
        for kind, browser, driver in (("geckodriver", "121.0", "0.33.0"),
                                      ("geckodriver", "102.0", "0.36.0"),
                                      ("msedgedriver", "150.0.8.1", "150.0.9.1")):
            with self.assertRaises(ValueError):
                bc._check_compatibility(kind, browser, driver)

    def test_safari_rejects_nonmac_and_non_system_executable(self):
        profile = {**self.profile, "browser": "safari", "driver_kind": "safaridriver"}
        with patch.object(bc.platform, "system", return_value="Linux"):
            with self.assertRaisesRegex(ValueError, "macOS"):
                self.resolve(profile)
        with self.assertRaisesRegex(ValueError, "system Safari"):
            self.resolve(profile)

    def test_manager_enforces_browser_path_no_browser_download_and_bounded_wait(self):
        modules, _ = fake_selenium()
        payload = {"result": {"code": 0, "driver_path": str(self.driver), "browser_path": str(self.exe)}}
        with (patch.dict(sys.modules, modules),
              patch.dict(os.environ, {"SE_BROWSER_PATH": "/other", "SE_DRIVER_VERSION": "999"}),
              patch.object(bc, "_run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(payload))) as run):
            path = bc._manager(self.profile, "150.0.7777.10", True)
        args = [str(arg) for arg in run.call_args.args[0]]
        self.assertEqual(path, str(self.driver))
        self.assertEqual(args[args.index("--browser-path") + 1], str(self.exe))
        self.assertEqual(args[args.index("--browser-version") + 1], "150.0.7777.10")
        for flag in ("--avoid-browser-download", "--skip-browser-in-path", "--skip-driver-in-path", "--avoid-stats"):
            self.assertIn(flag, args)
        self.assertLessEqual(run.call_args.kwargs["timeout"], 60)
        self.assertFalse(any(key.startswith("SE_") for key in run.call_args.kwargs["env"]))

    def test_manager_rejects_switched_browser_and_sanitizes_error_output(self):
        modules, _ = fake_selenium()
        data = {"result": {"driver_path": str(self.driver), "browser_path": "/other/browser"}}
        with patch.dict(sys.modules, modules), patch.object(bc, "_run", return_value=SimpleNamespace(returncode=0, stdout=json.dumps(data))):
            with self.assertRaises(ValueError) as error:
                bc._manager(self.profile, "150.0.7777.10", True)
            self.assertNotIn("/other/browser", str(error.exception))

    def test_manager_rejects_config_that_can_force_browser_download_or_clear_cache(self):
        modules, _ = fake_selenium()
        config = bc.storage_root() / "selenium" / "se-config.toml"
        config.parent.mkdir(parents=True)
        for value in ("force-browser-download = true", "clear-cache = true", 'driver-version = "999.0.0.0"'):
            config.write_text(value)
            with patch.dict(sys.modules, modules), patch.object(bc, "_run") as run:
                with self.assertRaises(ValueError):
                    bc._manager(self.profile, "150.0.7777.10", True)
                run.assert_not_called()

    def test_launch_all_families_uses_explicit_service_eager_and_script_timeout(self):
        modules, webdriver = fake_selenium()
        for browser, kind in bc._DEFAULT_DRIVER.items():
            if browser == "custom":
                continue
            p = {**self.profile, "browser": browser, "driver_kind": kind, "driver_path": str(self.driver)}
            name = {"chromedriver": "Chrome", "msedgedriver": "Edge", "geckodriver": "Firefox", "safaridriver": "Safari"}[kind]
            constructor = getattr(webdriver, name)
            constructor.reset_mock()
            with patch.dict(sys.modules, modules), patch.object(bc, "resolve_profile", return_value=p), patch.dict(os.environ, {"SE_CHROMEDRIVER": "/unselected-driver"}):
                result = bc.launch_browser(p, profile_dir=self.root / "student-temp")
            options = constructor.call_args.kwargs["options"]
            service = constructor.call_args.kwargs["service"]
            self.assertEqual(options.page_load_strategy, "eager")
            self.assertEqual(service.path, str(self.driver))
            self.assertIsNone(service.DRIVER_PATH_ENV_KEY)
            result.set_script_timeout.assert_called_with(30)
            if kind != "safaridriver":
                self.assertEqual(options.binary_location, str(self.exe))
            args = options.arguments
            self.assertFalse(any("AutomationControlled" in arg or "enable-automation" in arg for arg in args))
            if kind == "geckodriver":
                self.assertIn("-profile", args)
            elif kind in ("chromedriver", "msedgedriver"):
                self.assertIn("--user-data-dir=" + str(self.root / "student-temp"), args)

    def test_launch_failure_is_sanitized_and_never_tries_alternate_browser(self):
        modules, webdriver = fake_selenium()
        webdriver.Chrome.side_effect = RuntimeError("private command token SECRET")
        p = {**self.profile, "driver_path": str(self.driver)}
        with patch.dict(sys.modules, modules), patch.object(bc, "resolve_profile", return_value=p):
            with self.assertRaises(ValueError) as error:
                bc.launch_browser(p)
        self.assertNotIn("SECRET", str(error.exception))
        webdriver.Edge.assert_not_called()
        webdriver.Firefox.assert_not_called()

    def test_script_timeout_failure_closes_created_driver(self):
        modules, webdriver = fake_selenium()
        webdriver.Chrome.return_value.set_script_timeout.side_effect = RuntimeError("timeout")
        with patch.dict(sys.modules, modules), patch.object(bc, "resolve_profile", return_value={**self.profile, "driver_path": str(self.driver)}):
            with self.assertRaises(ValueError):
                bc.launch_browser(self.profile)
        webdriver.Chrome.return_value.quit.assert_called_once_with()

    def test_safari_headless_is_rejected_before_constructing_driver(self):
        modules, webdriver = fake_selenium()
        p = {**self.profile, "browser": "safari", "driver_kind": "safaridriver"}
        with patch.dict(sys.modules, modules), patch.object(bc, "resolve_profile", return_value=p):
            with self.assertRaisesRegex(ValueError, "headless"):
                bc.launch_browser(p, headless=True)
        webdriver.Safari.assert_not_called()

    def test_per_user_storage_on_windows_and_macos(self):
        with patch.object(bc.platform, "system", return_value="Windows"), patch.dict(os.environ, {"LOCALAPPDATA": str(self.root / "Local")}):
            self.assertEqual(self.storage_root_impl(), self.root / "Local" / "AttendanceBook")
        with patch.object(bc.platform, "system", return_value="Darwin"), patch.object(bc.Path, "home", return_value=self.root):
            self.assertEqual(self.storage_root_impl(), self.root / "Library" / "Application Support" / "AttendanceBook")


if __name__ == "__main__":
    unittest.main()
