"""Offline guards for the developer-only live smoke script."""
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import live_portal_smoke as smoke


ARGS = ["--profile-id", "saved", "--year", "2026", "--term", "11", "--week", "1"]


class GuardTests(unittest.TestCase):
    def invoke(self, args, *, tty=True, ci=False, answers=()):
        stdin = Mock()
        stdin.isatty.return_value = tty
        output = StringIO()
        with patch.object(smoke.sys, "stdin", stdin), \
             patch.object(smoke, "in_ci", return_value=ci), \
             patch("builtins.input", side_effect=answers), \
             patch.object(smoke, "selected_profile", return_value={"id": "saved"}) as select, \
             patch.object(smoke, "run_live", return_value=0) as live, \
             redirect_stdout(output):
            result = smoke.main(args)
        return result, select, live, output.getvalue()

    def test_missing_flag_never_selects_profile_or_launches(self):
        result, select, live, _ = self.invoke(ARGS)
        self.assertEqual(result, 2)
        select.assert_not_called()
        live.assert_not_called()

    def test_ci_and_noninteractive_terminal_refuse_before_confirmation(self):
        for tty, ci in ((True, True), (False, False)):
            with self.subTest(tty=tty, ci=ci):
                result, select, live, _ = self.invoke(["--run-live", *ARGS], tty=tty, ci=ci)
                self.assertEqual(result, 2)
                select.assert_not_called()
                live.assert_not_called()

    def test_confirmation_must_match_exact_phrase(self):
        for answer in ("", "yes", "run live portal smoke"):
            with self.subTest(answer=answer):
                result, select, live, _ = self.invoke(["--run-live", *ARGS], answers=(answer,))
                self.assertEqual(result, 2)
                select.assert_not_called()
                live.assert_not_called()

    def test_explicit_confirmation_reaches_only_selected_saved_profile(self):
        result, select, live, _ = self.invoke(["--run-live", *ARGS], answers=(smoke.CONFIRMATION,))
        self.assertEqual(result, 0)
        select.assert_called_once_with("saved")
        self.assertEqual(live.call_args.args[0], {"id": "saved"})
        self.assertEqual(live.call_args.args[1].week, 1)

    def test_ci_environment_detection(self):
        self.assertTrue(smoke.in_ci({"GITHUB_ACTIONS": "true"}))
        self.assertTrue(smoke.in_ci({"CI": "1"}))
        self.assertFalse(smoke.in_ci({"CI": "false"}))

    def test_unknown_or_nonisolated_saved_profile_refused(self):
        profiles = [{"id": "safari", "driver_kind": "safaridriver"},
                    {"id": "chrome", "driver_kind": "chromedriver"}]
        with patch.object(smoke, "load_profiles", return_value=profiles):
            with self.assertRaises(ValueError):
                smoke.selected_profile("missing")
            with self.assertRaises(ValueError):
                smoke.selected_profile("safari")
            self.assertEqual(smoke.selected_profile("chrome"), profiles[1])

    def test_live_failure_redacts_exception_and_closes_session(self):
        session = Mock()
        session.open.side_effect = RuntimeError("SECRET student name and token")
        output = StringIO()
        with patch.object(smoke, "new_session", return_value=session), redirect_stdout(output):
            result = smoke.run_live({"id": "saved"}, smoke.Selection(2026, 11, 1))
        self.assertEqual(result, 1)
        self.assertNotIn("SECRET", output.getvalue())
        session.close.assert_called_once()

    def test_success_requires_cleanup_and_cancel_also_closes(self):
        session = Mock()
        output = StringIO()
        with patch.object(smoke, "new_session", return_value=session), \
             patch.object(smoke, "check_known_pages") as check, \
             patch("builtins.input", return_value=""), redirect_stdout(output):
            self.assertEqual(smoke.run_live({"id": "saved"}, smoke.Selection(2026, 11, 1)), 0)
        check.assert_called_once()
        session.close.assert_called_once()
        self.assertIn("PASS:", output.getvalue())

        session.close.side_effect = OSError("SECRET cleanup path")
        output = StringIO()
        with patch.object(smoke, "new_session", return_value=session), \
             patch.object(smoke, "check_known_pages"), \
             patch("builtins.input", return_value=""), redirect_stdout(output):
            self.assertEqual(smoke.run_live({"id": "saved"}, smoke.Selection(2026, 11, 1)), 1)
        self.assertNotIn("PASS:", output.getvalue())
        self.assertNotIn("SECRET", output.getvalue())

        session.close.side_effect = None
        output = StringIO()
        with patch.object(smoke, "new_session", return_value=session), \
             patch.object(smoke, "check_known_pages") as check, \
             patch("builtins.input", side_effect=KeyboardInterrupt), redirect_stdout(output):
            self.assertEqual(smoke.run_live({"id": "saved"}, smoke.Selection(2026, 11, 1)), 1)
        check.assert_not_called()
        self.assertEqual(session.close.call_count, 3)

    def test_known_checks_are_limited_to_timetable_and_profile_page(self):
        session = Mock()
        selection = smoke.Selection(2026, 11, 1)
        with patch.object(smoke, "read_http", return_value={"identity": {"学号": "PRIVATE", "专业": "PRIVATE"}}) as timetable, \
             patch.object(smoke, "profile_fields", return_value=({"recorded_name": "PRIVATE"}, {})) as profile:
            smoke.check_known_pages(session, selection)
        timetable.assert_called_once_with(session.client, selection)
        session.client.get.assert_called_once_with(smoke.PROFILE_PAGE)
        profile.assert_called_once()


if __name__ == "__main__":
    unittest.main()
