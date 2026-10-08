import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from browser_config import (
    default_channel, launch_browser, check_browser, configured_browser_name,
    load_browser_executable, save_browser_executable, launch_login_context,
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

    def test_saved_browser_failure_never_silently_falls_back_to_edge(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / "msedge.exe"
            executable.write_bytes(b"test")
            chromium = Mock()
            chromium.launch.side_effect = Error("Saved browser failed")
            pw = SimpleNamespace(chromium=chromium)
            with patch('browser_config.load_browser_executable', return_value=str(executable)):
                with self.assertRaisesRegex(ValueError, "Selected browser"):
                    launch_browser(pw, 'msedge', headless=True)
            chromium.launch.assert_called_once_with(
                executable_path=str(executable), headless=True, timeout=15000)

    def test_probe_labels_selected_browser_instead_of_edge(self):
        browser = Mock(version='123')
        with patch('browser_config.launch_browser', return_value=browser), \
             patch('browser_config.load_browser_executable', return_value='C:/Browser/360chrome.exe'):
            self.assertEqual(configured_browser_name('msedge'), '360chrome.exe')
            self.assertEqual(check_browser(Mock(), 'msedge'),
                             {'name': '360chrome.exe', 'version': '123'})

    def test_invalid_manual_selection_does_not_fall_back(self):
        chromium = Mock()
        pw = SimpleNamespace(chromium=chromium)
        with self.assertRaisesRegex(ValueError, "not found"):
            launch_browser(pw, 'msedge', headless=True, executable_path="nonexistent-browser.exe")
        chromium.launch.assert_not_called()

    def test_login_uses_platform_default(self):
        pw = SimpleNamespace(chromium=Mock())
        context = pw.chromium.launch_persistent_context.return_value
        context.pages = []
        with patch('browser_config.platform.system', return_value='Windows'), \
             patch('browser_config.load_browser_executable', return_value=None):
            session = PortalSession(pw)
            session.open()
        args, kwargs = pw.chromium.launch_persistent_context.call_args
        profile_path = Path(args[0])
        self.assertTrue(profile_path.is_dir())
        self.assertEqual(kwargs, {'channel': 'msedge', 'headless': False, 'timeout': 15000})
        pw.chromium.launch.assert_not_called()
        session.page.goto.assert_called_once()
        session.close()
        context.close.assert_called_once()
        self.assertFalse(profile_path.exists())

    def test_login_uses_saved_browser_and_no_edge_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            executable = Path(directory) / '360chrome.exe'
            executable.write_bytes(b'test')
            chromium = Mock()
            pw = SimpleNamespace(chromium=chromium)
            with patch('browser_config.load_browser_executable', return_value=str(executable)):
                launch_login_context(pw, directory, 'msedge')
            chromium.launch_persistent_context.assert_called_once_with(
                directory, executable_path=str(executable), headless=False, timeout=15000)
            chromium.launch.assert_not_called()

    def test_failed_login_launch_removes_temporary_profile(self):
        pw = SimpleNamespace(chromium=Mock())
        pw.chromium.launch_persistent_context.side_effect = Error('private driver details')
        with patch('browser_config.load_browser_executable', return_value=None):
            session = PortalSession(pw, 'chrome')
            with self.assertRaisesRegex(ValueError, 'temporary login profile'):
                session.open()
        profile_path = Path(pw.chromium.launch_persistent_context.call_args.args[0])
        self.assertFalse(profile_path.exists())
        self.assertIsNone(session.context)

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
        with patch('browser_config.launch_browser', return_value=browser) as launch, \
             patch('browser_config.load_browser_executable', return_value=None):
            self.assertEqual(check_browser(Mock(), 'msedge'),
                             {'name': 'Microsoft Edge', 'version': '123'})
        self.assertEqual(launch.call_args.kwargs, {'headless': True})
        browser.close.assert_called_once()
        browser.new_page.assert_not_called()

    def test_login_diagnostic_reports_only_metadata(self):
        session = PortalSession(Mock())
        session.context = Mock()
        session.page = Mock(url='https://login.example.cn/callback?ticket=SECRET')
        session.page.is_closed.return_value = False
        session.request_responses = ['login.example.cn (document): HTTP 200']
        result = session.diagnose_login()
        self.assertEqual(result['page_host'], 'login.example.cn')
        self.assertEqual(result['request_responses'], ['login.example.cn (document): HTTP 200'])
        self.assertNotIn('SECRET', str(result))
        session.context.request.get.assert_not_called()
        session.page.evaluate.assert_not_called()

    def test_login_diagnostic_sanitizes_network_errors(self):
        session = PortalSession(Mock())
        request = Mock(url='https://login.example.cn/callback?ticket=SECRET',
                       failure='net::ERR_CERT_AUTHORITY_INVALID')
        session._request_failed(request)
        response = Mock(status=503, url='https://auth.example.cn/?token=SECRET')
        response.request.resource_type = 'document'
        session._response_received(response)
        self.assertEqual(session.network_issues,
                         ['login.example.cn: net::ERR_CERT_AUTHORITY_INVALID',
                          'auth.example.cn: HTTP 503'])
        self.assertNotIn('SECRET', str(session.network_issues))

    def test_login_diagnostic_reports_pending_without_urls(self):
        session = PortalSession(Mock())
        session.context = Mock()
        session.page = Mock(url='https://login.example.cn/login?token=SECRET')
        session.page.is_closed.return_value = False
        request = Mock(url='https://login.example.cn/api/secret?token=SECRET',
                       resource_type='fetch')
        session._request_started(request)
        result = session.diagnose_login()
        self.assertIn('login.example.cn (fetch)', result['pending_requests'][0])
        self.assertNotIn('SECRET', str(result))
        session._request_finished(request)
        self.assertEqual(session.diagnose_login()['pending_requests'], [])

    def test_login_diagnostic_does_not_claim_authentication(self):
        session = PortalSession(Mock())
        session.context = Mock()
        session.page = Mock(url='https://login.example.cn/login')
        session.page.is_closed.return_value = False
        result = session.diagnose_login()
        self.assertNotIn('authenticated', result)
        session.context.request.get.assert_not_called()


if __name__ == '__main__':
    unittest.main()
