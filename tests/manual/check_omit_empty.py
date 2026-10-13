"""Offline Selenium QA for omitting scanned weeks with no classes."""
import copy
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser_fixture import headless_browser, preview_document, smoke_profile
from document import print_pdf
from test_production import fixture
from test_photo import sample_photo


def main():
    from pypdf import PdfReader

    project = Path(__file__).resolve().parents[2]
    data = fixture()
    data['last_week'] = 3
    data['weeks'] = data['weeks'][:3]
    data['photo'] = sample_photo()
    data['omit_empty_weeks'] = True
    original = copy.deepcopy(data)
    target = project / 'work/OMIT_EMPTY_DEMO_长安大学国际学生考勤册.pdf'
    all_empty_target = project / 'work/ALL_EMPTY_DEMO_长安大学国际学生考勤册.pdf'
    profile = smoke_profile()
    target.parent.mkdir(parents=True, exist_ok=True)

    with headless_browser(profile) as browser:
        with preview_document(browser, data) as layout:
            assert len(layout) == 7 and not any(item['overflow'] for item in layout), layout
            assert len(browser.find_elements('css selector', '.weekly')) == 2
            headings = browser.find_elements('css selector', '.weekly h2')
            assert '第2周' in headings[0].text
            assert '第3周' in headings[1].text
            rows = [element.text for element in browser.find_elements('css selector', '.summary tr td:first-child')]
            assert rows == ['2', '3', '总计'], rows
    print_pdf(profile, data, target)
    assert len(PdfReader(target).pages) == 7
    assert data == original
    empty = copy.deepcopy(data)
    for week in empty['weeks']:
        week['classes'] = []
    print_pdf(profile, empty, all_empty_target)
    assert len(PdfReader(all_empty_target).pages) == 5
    print('Omission checks passed: complete source retained, original week numbers, matching summary, 7/5-page PDFs.')


if __name__ == '__main__':
    main()
