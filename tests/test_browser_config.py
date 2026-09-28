import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from browser_config import default_channel, launch_browser, check_browser
from playwright.sync_api import Error
from service import PortalSession


class BrowserTests(unittest.TestCase):
    def test_platform_defaults(self):
        for system, expected in (('Windows', 'msedge'), ('Darwin', 'chrome')):
            with patch('browser_config.platform.system', return_value=system):
                self.assertEqual(default_channel(), expected)

    def test_visible_and_headless_installed_browser(self):
        for channel in ('msedge', 'chrome'):
            for headless in (False, True):
                chromium = Mock()
                pw = SimpleNamespace(chromium=chromium)
                self.assertIs(launch_browser(pw, channel, headless=headless), chromium.launch.return_value)
                chromium.launch.assert_called_once_with(channel=channel, headless=headless, timeout=15000)

    def test_login_uses_platform_default(self):
        pw = SimpleNamespace(chromium=Mock())
        with patch('browser_config.platform.system', return_value='Windows'):
            session = PortalSession(pw)
            session.open()
        pw.chromium.launch.assert_called_once_with(channel='msedge', headless=False, timeout=15000)
        session.page.goto.assert_called_once()

    def test_missing_browser_error_does_not_leak_driver_details(self):
        pw = SimpleNamespace(chromium=Mock())
        pw.chromium.launch.side_effect = Error('private driver details')
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
