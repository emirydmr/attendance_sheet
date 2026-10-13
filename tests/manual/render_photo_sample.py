"""Render a fictitious photo book and check the offline browser preview."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser_fixture import headless_browser, preview_document, smoke_profile
from document import print_pdf
from test_production import fixture
from test_photo import sample_photo


def main():
    target = Path(__file__).resolve().parents[2] / "work" / "PHOTO_DEMO001_长安大学国际学生考勤册.pdf"
    data = fixture()
    data["last_week"] = 3
    data["weeks"] = data["weeks"][:3]
    data["photo"] = sample_photo()
    profile = smoke_profile()
    target.parent.mkdir(parents=True, exist_ok=True)
    print_pdf(profile, data, target)
    with headless_browser(profile) as browser:
        with preview_document(browser, data):
            assert len(browser.find_elements("css selector", "#print-book")) == 1
            assert browser.execute_script("return document.images[0].naturalWidth") == 120
    print(target)


if __name__ == "__main__":
    main()
