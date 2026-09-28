"""Offline browser integration: margins, responsive preview, dense/oversize pages."""
import copy
from pathlib import Path
import sys
import tempfile
import shutil
import subprocess
from PIL import Image

from playwright.sync_api import sync_playwright

sys.path[:0] = [str(Path(__file__).resolve().parents[1] / 'app'), str(Path(__file__).resolve().parent)]
from document import browser_html, print_pdf
from test_production import fixture
from test_photo import sample_photo

data = fixture()
data['last_week'] = 3
data['weeks'] = data['weeks'][:3]
data['photo'] = sample_photo()
data['weeks'][0]['classes'] = [
    {'day': 1, 'day_span': 1, 'first_period': p, 'period_count': 2,
     'text': '\n'.join(['示例课程详情'] * 8)} for p in (1, 3, 5, 7, 9, 11)]

project = Path(__file__).resolve().parents[1]
target = project / 'work' / 'LAYOUT_DEMO_长安大学国际学生考勤册.pdf'
with sync_playwright() as pw:
    browser = pw.chromium.launch(channel='chrome', headless=True)
    try:
        page = browser.new_page()
        page.route('**/*', lambda route: route.abort())
        errors = []
        page.on('pageerror', lambda exc: errors.append(str(exc)))
        page.set_content(browser_html(data), wait_until='load')
        layout = page.evaluate('window.attendanceLayoutReady')
        assert not errors, errors
        assert not any(p['overflow'] for p in layout), layout
        assert 0.8 <= layout[3]['scale'] <= 1, layout[3]
        for width in (1920, 1280, 800, 360):
            page.set_viewport_size({'width': width, 'height': 900})
            page.evaluate("window.dispatchEvent(new Event('resize'))")
            bounds = page.locator('.page').first.bounding_box()
            assert bounds['width'] <= width * 0.8 + 2, (width, bounds)
            assert abs(bounds['x'] - (width-bounds['width'])/2) < 3, (width, bounds)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 2')
            inside = page.evaluate("""() => [...document.querySelectorAll('.schedule')].every(table => {
              const b=table.getBoundingClientRect(), p=table.closest('.page').getBoundingClientRect();
              return b.x>p.x+2 && b.right<p.right-2;
            })""")
            assert inside, width
        page.emulate_media(media='print')
        assert not any(p['overflow'] for p in page.evaluate('window.fitAttendanceBook()'))
        bad = copy.deepcopy(data)
        bad['weeks'][0]['classes'][0]['text'] = '\n'.join(['示例超长内容'] * 100)
        page.emulate_media(media='screen')
        page.set_content(browser_html(bad), wait_until='load')
        bad_layout = page.evaluate('window.attendanceLayoutReady')
        assert bad_layout[3]['overflow']
        assert '4' in page.locator('#layout-warning').inner_text()
    finally:
        browser.close()
    print_pdf(pw, 'chrome', data, target)
    converter = shutil.which('pdftoppm')
    if converter:
        with tempfile.TemporaryDirectory() as directory:
            subprocess.run([converter, '-scale-to', '1100', '-png', str(target), str(Path(directory) / 'page')], check=True)
            images = sorted(Path(directory).glob('page-*.png'))
            assert len(images) == 8, len(images)
            for image_path in images:
                with Image.open(image_path).convert('RGB') as image:
                    # Catch print fragmentation that DOM measurements cannot:
                    # no table border may spill into the top margin.
                    top = int(image.height * 15 / 210) - 3
                    assert min(low for low, high in image.crop((0, 0, image.width, top)).getextrema()) > 240, image_path
    else:
        print('Poppler unavailable: visual PDF margin regression check skipped; inspect PDF manually.')
    with tempfile.TemporaryDirectory() as directory:
        destination = Path(directory) / 'keep.pdf'
        destination.write_bytes(b'previous file')
        try:
            print_pdf(pw, 'chrome', bad, destination)
        except ValueError as exc:
            assert 'Page / 页 4' in str(exc), exc
        else:
            raise AssertionError('Oversized page was not rejected')
        assert destination.read_bytes() == b'previous file'
print('Layout checks passed: 80% preview, margins, dense-page fit, oversized-page detail, safe destination.')
print(target)
