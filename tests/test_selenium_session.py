"""Transport and session regressions without external networking or browsers."""
import sys
import queue
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from portal import BASE, BrowserPortalClient, PortalError
from service import PortalSession
from selenium.common.exceptions import TimeoutException, WebDriverException


class TransportTests(unittest.TestCase):
    def setUp(self):
        self.driver = Mock(current_url=BASE + "/allogene/page/home.htm")
        self.client = BrowserPortalClient(self.driver)

    def test_same_origin_fetch_stays_in_browser_and_returns_text(self):
        self.driver.execute_async_script.return_value = {"status": 200, "url": BASE + "/page", "text": "fixture"}
        self.assertEqual(self.client.get(BASE + "/page"), "fixture")
        script, url, timeout = self.driver.execute_async_script.call_args.args
        self.assertIn("credentials: 'same-origin'", script)
        self.assertIn("AbortController", script)
        self.assertIn("cache: 'no-store'", script)
        self.driver.get_cookies.assert_not_called()
        self.assertEqual(self.client.observations, ["yjs.chd.edu.cn: HTTP 200"])

    def test_rejects_external_request_before_browser_call(self):
        with self.assertRaises(PortalError):
            self.client.get("https://example.com/")
        self.driver.execute_async_script.assert_not_called()

    def test_requires_login_to_return_to_portal_origin(self):
        self.driver.current_url = "https://ids.chd.edu.cn/login"
        with self.assertRaisesRegex(PortalError, "Finish signing in"):
            self.client.get(BASE)
        self.driver.execute_async_script.assert_not_called()

    def test_redirect_status_and_abort_rejected_without_exposing_content(self):
        for result in ({"error": "request_failed"}, {"status": 401, "url": BASE, "text": "secret"},
                       {"status": 200, "url": "https://ids.chd.edu.cn/login?secret", "text": "secret"}):
            self.driver.execute_async_script.return_value = result
            with self.assertRaises(PortalError) as caught:
                self.client.get(BASE)
            self.assertNotIn("secret", str(caught.exception))
        self.assertTrue(all("secret" not in row for row in self.client.observations))


class SessionTests(unittest.TestCase):
    def test_no_default_browser_or_launch_at_initialization(self):
        with patch("service.launch_browser") as launch:
            session = PortalSession()
            self.assertIsNone(session.driver)
            with self.assertRaises(PortalError):
                session.open()
            launch.assert_not_called()

    def test_navigation_timeout_keeps_window_for_manual_refresh(self):
        driver = Mock()
        driver.get.side_effect = TimeoutException()
        with patch("service.launch_browser", return_value=driver) as launch:
            session = PortalSession({"id": "selected"})
            self.assertTrue(session.open()["navigation_timeout"])
            folder = Path(session._profile.name)
            self.assertTrue(folder.is_dir())
            self.assertIs(session.driver, driver)
            driver.quit.assert_not_called()
            launch.assert_called_once_with({"id": "selected"}, headless=False, profile_dir=str(folder))
            session.close()
            driver.quit.assert_called_once()
            self.assertFalse(folder.exists())

    def test_failed_launch_cleans_temporary_session(self):
        with patch("service.launch_browser", side_effect=ValueError("launch failed")):
            session = PortalSession({"id": "selected"})
            with self.assertRaises(ValueError):
                session.open()
            self.assertIsNone(session._profile)
            self.assertIsNone(session.driver)

    def test_closed_browser_still_cleans_folder(self):
        with patch("service.launch_browser", return_value=Mock()) as launch:
            session = PortalSession({"id": "selected"})
            session.open()
            folder = Path(session._profile.name)
            launch.return_value.quit.side_effect = WebDriverException()
            session.close()
            self.assertFalse(folder.exists())
            self.assertIsNone(session.student_id)

    def test_diagnostic_is_passive_and_does_not_claim_pending_requests(self):
        session = PortalSession()
        session.driver = Mock(current_url=BASE)
        session.driver.execute_script.return_value = {"readyState": "interactive", "resources": []}
        session.client = Mock(observations=[])
        result = session.diagnose_login()
        self.assertEqual(result["page_state"], "interactive")
        self.assertNotIn("pending_requests", result)
        session.client.get.assert_not_called()


class WorkerTests(unittest.TestCase):
    def run_commands(self, commands):
        from main import worker
        tasks, events = queue.Queue(), queue.Queue()
        for command in commands:
            tasks.put(command)
        tasks.put(("quit", ()))
        worker(tasks, events, {"id": "old"}, False)
        return list(events.queue)

    def test_reopen_retires_old_login_before_failed_driver_resolution(self):
        order = []
        session = Mock()
        session.close.side_effect = lambda: order.append("close")
        def failed_resolution(*args, **kwargs):
            order.append("resolve")
            raise ValueError("driver missing")
        with patch("main.PortalSession", return_value=session), \
                patch("main.resolve_profile", side_effect=failed_resolution):
            events = self.run_commands([("open", ())])
        self.assertEqual(order[:2], ["close", "resolve"])
        session.open.assert_not_called()
        self.assertIn(("error", "open", "driver missing"), events)

    def test_activation_cleanup_failure_does_not_persist_new_active_profile(self):
        session = Mock()
        session.close.side_effect = [PermissionError(), None]
        with patch("main.PortalSession", return_value=session), \
                patch("main.resolve_profile", return_value={"id": "new"}), \
                patch("main.save_profile") as save:
            events = self.run_commands([("activate_profile", ({"id": "new"},))])
        save.assert_not_called()
        self.assertIn(("session_closed", "activate_profile", None), events)
        self.assertIn(("error", "activate_profile", "PermissionError"), events)


if __name__ == "__main__":
    unittest.main()
