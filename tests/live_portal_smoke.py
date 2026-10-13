"""Developer-only live portal smoke check; not a unittest-discovered test.

Usage: python tests/live_portal_smoke.py --run-live --profile-id ID \
    --year 2026 --term 11 --week 1

The operator must also confirm interactively. This script never writes portal
responses, credentials, screenshots, or student details to a report or log.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from browser_config import load_profiles
from portal import BASE, Selection, profile_fields, read_http


CONFIRMATION = "RUN LIVE PORTAL SMOKE"
PROFILE_PAGE = BASE + "/allogene/page/userinfo.htm"
ISOLATED_DRIVERS = frozenset({"chromedriver", "msedgedriver", "geckodriver"})


def in_ci(environ=None):
    values = os.environ if environ is None else environ
    return any(str(values.get(key, "")).strip().lower() not in ("", "0", "false", "no")
               for key in ("CI", "GITHUB_ACTIONS", "GITLAB_CI", "TF_BUILD", "BUILD_BUILDID"))


def selected_profile(profile_id):
    """Use a saved configuration, never an implicit active or detected browser."""
    profile = next((row for row in load_profiles() if row["id"] == profile_id), None)
    if profile is None:
        raise ValueError("Unknown saved browser profile.")
    if profile.get("driver_kind") not in ISOLATED_DRIVERS:
        raise ValueError("This browser cannot use a fresh temporary profile.")
    return profile


def check_known_pages(session, selection):
    """Read exactly two known GET pages; keep parsed student data in memory only."""
    timetable = read_http(session.client, selection)
    timetable_ok = bool(timetable["identity"].get("学号") and timetable["identity"].get("专业"))
    del timetable
    details, structure = profile_fields(session.client.get(PROFILE_PAGE))
    profile_ok = bool(details.get("recorded_name"))
    del details, structure
    if not timetable_ok or not profile_ok:
        raise ValueError("Known page structure is missing.")


def new_session(profile):
    from service import PortalSession
    return PortalSession(profile)


def run_live(profile, selection):
    session = None
    passed = False
    cleanup_ok = True
    try:
        session = new_session(profile)
        session.open()
        print("Sign in manually in the temporary browser, then return here.")
        input("Press Enter after the browser shows a signed-in portal page: ")
        check_known_pages(session, selection)
        passed = True
    except (KeyboardInterrupt, EOFError):
        print("Live smoke cancelled.")
    except Exception:
        # Selenium and portal exception text may contain URLs, page text, or PII.
        print("Live smoke failed. No portal details were printed.")
    finally:
        if session is not None:
            try:
                session.close()
            except Exception:
                cleanup_ok = False
                print("Browser cleanup could not be confirmed; inspect temporary attendance-login-* folders.")
    if passed and cleanup_ok:
        print("PASS: timetable and profile page checks; browser session closed.")
        return 0
    return 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-live", action="store_true", help="Explicitly allow a live portal run")
    parser.add_argument("--profile-id", required=True, help="ID of a saved browser configuration")
    parser.add_argument("--year", required=True, type=int, help="Academic year")
    parser.add_argument("--term", required=True, type=int, choices=(11, 12, 13), help="Portal semester code")
    parser.add_argument("--week", required=True, type=int, help="Week in the selected semester")
    args = parser.parse_args(argv)
    if not args.run_live:
        print("Live smoke is disabled; add --run-live to opt in.")
        return 2
    if in_ci() or not sys.stdin.isatty():
        print("Live smoke requires an interactive developer terminal outside CI.")
        return 2
    try:
        selection = Selection(args.year, args.term, args.week)
    except Exception:
        print("Invalid academic year, term, or week.")
        return 2
    try:
        answer = input(f"Type {CONFIRMATION} to open a live portal browser: ")
    except (KeyboardInterrupt, EOFError):
        print("Live smoke cancelled.")
        return 2
    if answer != CONFIRMATION:
        print("Live smoke was not confirmed.")
        return 2
    try:
        profile = selected_profile(args.profile_id)
    except Exception:
        print("Saved browser configuration is unavailable or cannot be isolated.")
        return 2
    return run_live(profile, selection)


if __name__ == "__main__":
    raise SystemExit(main())
