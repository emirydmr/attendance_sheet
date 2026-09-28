from pathlib import Path
import sys
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from document import print_pdf, browser_html
from test_production import fixture
from test_photo import sample_photo

target = Path(__file__).resolve().parents[1] / "work" / "PHOTO_DEMO001_长安大学国际学生考勤册.pdf"
data = fixture()
data["last_week"] = 3
data["weeks"] = data["weeks"][:3]
data["photo"] = sample_photo()
with sync_playwright() as pw:
    print_pdf(pw, "chrome", data, target)
    browser = pw.chromium.launch(channel="chrome", headless=True)
    try:
        page = browser.new_page()
        page.set_content(browser_html(data), wait_until="load")
        assert page.locator("#print-book").count() == 1
        assert page.evaluate("document.images[0].naturalWidth") == 120
    finally:
        browser.close()
print(target)
