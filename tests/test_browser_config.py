import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from browser_config import (
    default_channel, launch_browser, check_browser,
    load_browser_executable, save_browser_executable,
)
from playwright.sync_api import Error
from service import PortalSession


class BrowserTests(unittest.TestCase):
    def test_platform_defaults(self):
        for system, expected in (('Windows', 'msedge'), ('Darwin', 'chrome')):
            with patch('browser_config.platform.system', return_value=system):
                self.assertEqual(default_channel(), expected)

    def test_visible_and_headless_installed_browser(self):
        with patch('browser_config.load_browser_executable', return_value=None):
            for channel in ('msedge', 'chrome'):
                for headless in (False, True):
                    chromium = Mock()
                    pw = SimpleNamespace(chromium=chromium)
                    self.assertIs(launch_browser(pw, channel, headless=headless), chromium.launch.return_value)
                    chromium.launch.assert_called_once_with(channel=channel, headless=headless, timeout=15000)

    def test_manual_executable_selection(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "Microsoft Edge.exe"
            executable.write_bytes(b"test")
            chromium = Mock()
            pw = SimpleNamespace(chromium=chromium)
            result = launch_browser(pw, 'msedge', headless=True, executable_path=str(executable))
            self.assertIs(result, chromium.launch.return_value)
            chromium.launch.assert_called_once_with(
                executable_path=str(executable), headless=True, timeout=15000
            )

    def test_settings_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Path(directory) / "browser.json"
            executable = Path(directory) / "Microsoft Edge.exe"
            executable.write_bytes(b"test")
            with patch('browser_config.settings_path', return_value=settings):
                self.assertIsNone(load_browser_executable('msedge'))
                save_browser_executable('msedge', str(executable))
                self.assertEqual(load_browser_executable('msedge'), str(executable))

    def test_saved_browser_is_preferred(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "msedge.exe"
            executable.write_bytes(b"test")
            chromium = Mock()
            pw = SimpleNamespace(chromium=chromium)
            with patch('browser_config.load_browser_executable', return_value=str(executable)):
                launch_browser(pw, 'msedge', headless=True)
            chromium.launch.assert_called_once_with(
                executable_path=str(executable), headless=True, timeout=15000
            )

    def test_saved_browser_failure_falls_back_to_channel(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "msedge.exe"
            executable.write_bytes(b"test")
            chromium = Mock()
            chromium.launch.side_effect = [Error("Saved browser failed"), Mock(version="123")]
            pw = SimpleNamespace(chromium=chromium)
            with patch('browser_config.load_browser_executable', return_value=str(executable)):
                launch_browser(pw, 'msedge', headless=True)
            self.assertEqual(chromium.launch.call_count, 2)
            chromium.launch.assert_any_call(channel='msedge', headless=True, timeout=15000)

    def test_invalid_manual_selection_does_not_fall_back(self):
        chromium = Mock()
        pw = SimpleNamespace(chromium=chromium)
        with self.assertRaisesRegex(ValueError, "not found"):
            launch_browser(pw, 'msedge', headless=True, executable_path="nonexistent-browser.exe")
        chromium.launch.assert_not_called()

    def test_login_uses_platform_default(self):
        pw = SimpleNamespace(chromium=Mock())
        with patch('browser_config.platform.system', return_value='Windows'), \
             patch('browser_config.load_browser_executable', return_value=None):
            session = PortalSession(pw)
            session.open()
        pw.chromium.launch.assert_called_once_with(channel='msedge', headless=False, timeout=15000)
        session.page.goto.assert_called_once()

    def test_missing_browser_error_does_not_leak_driver_details(self):
        pw = SimpleNamespace(chromium=Mock())
        pw.chromium.launch.side_effect = Error('private driver details')
        with patch('browser_config.load_browser_executable', return_value=None):
            with self.assertRaises(ValueError) as raised:
                launch_browser(pw, 'msedge', headless=False)
        self.assertIn('Microsoft Edge', str(raised.exception))
        self.assertIn('No browser was downloaded', str(raised.exception))
        self.assertNotIn('private driver details', str(raised.exception))

    def test_probe_closes_browser_without_portal_request(self):
        browser = Mock(version='123')
        with patch('browser_config.launch_browser', return_value=browser) as launch:
            self.assertEqual(check_browser(Mock(), 'msedge'),
                             {'name': 'Microsoft Edge', 'version': '123'})
        self.assertEqual(launch.call_args.kwargs, {'headless': True})
        browser.close.assert_called_once()
        browser.new_page.assert_not_called()


if __name__ == '__main__':
    unittest.main()
