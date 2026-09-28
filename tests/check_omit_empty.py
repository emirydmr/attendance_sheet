"""Offline output integration for omitting scanned weeks with no classes."""
import copy
from pathlib import Path
import sys

from playwright.sync_api import sync_playwright
from pypdf import PdfReader

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'app'), str(Path(__file__).resolve().parent)]
from browser_config import default_channel, launch_browser
from document import browser_html, print_pdf
from test_production import fixture
from test_photo import sample_photo

project = Path(__file__).resolve().parents[1]
data = fixture()
data['last_week'] = 3
data['weeks'] = data['weeks'][:3]
data['photo'] = sample_photo()
data['omit_empty_weeks'] = True
original = copy.deepcopy(data)
target = project / 'work/OMIT_EMPTY_DEMO_长安大学国际学生考勤册.pdf'
all_empty_target = project / 'work/ALL_EMPTY_DEMO_长安大学国际学生考勤册.pdf'

with sync_playwright() as pw:
    browser = launch_browser(pw, headless=True)
    try:
        page = browser.new_page()
        page.route('**/*', lambda route: route.abort())
        page.set_content(browser_html(data), wait_until='load')
        layout = page.evaluate('window.attendanceLayoutReady')
        assert len(layout) == 7 and not any(item['overflow'] for item in layout), layout
        assert page.locator('.weekly').count() == 2
        assert '第2周' in page.locator('.weekly h2').nth(0).inner_text()
        assert '第3周' in page.locator('.weekly h2').nth(1).inner_text()
        rows = page.locator('.summary tr td:first-child').all_inner_texts()
        assert rows == ['2', '3', '总计'], rows
    finally:
        browser.close()
    print_pdf(pw, default_channel(), data, target)
    assert len(PdfReader(target).pages) == 7
    assert data == original
    empty = copy.deepcopy(data)
    for week in empty['weeks']:
        week['classes'] = []
    print_pdf(pw, default_channel(), empty, all_empty_target)
    assert len(PdfReader(all_empty_target).pages) == 5
print('Omission checks passed: complete source retained, original week numbers, matching summary, 7/5-page PDFs.')
