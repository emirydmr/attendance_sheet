"""Offline Selenium QA: margins, responsive preview, dense/oversize pages."""
import copy
from pathlib import Path
import sys
import tempfile
import shutil
import subprocess
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from browser_fixture import headless_browser, preview_document, smoke_profile
from document import print_pdf
from test_production import fixture
from test_photo import sample_photo


def main():
    data = fixture()
    data['last_week'] = 3
    data['weeks'] = data['weeks'][:3]
    data['photo'] = sample_photo()
    data['weeks'][0]['classes'] = [
        {'day': 1, 'day_span': 1, 'first_period': p, 'period_count': 2,
         'text': '\n'.join(['示例课程详情'] * 8)} for p in (1, 3, 5, 7, 9, 11)]

    project = Path(__file__).resolve().parents[2]
    target = project / 'work' / 'LAYOUT_DEMO_长安大学国际学生考勤册.pdf'
    profile = smoke_profile(require_chromium=True)
    target.parent.mkdir(parents=True, exist_ok=True)
    with headless_browser(profile) as browser:
        with preview_document(browser, data) as layout:
            errors = browser.execute_script('return window.attendanceQaErrors')
            assert not errors, errors
            assert not any(p['overflow'] for p in layout), layout
            assert 0.8 <= layout[3]['scale'] <= 1, layout[3]
            for width in (1920, 1280, 800, 360):
                browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride', {
                    'width': width, 'height': 900, 'deviceScaleFactor': 1, 'mobile': False})
                browser.execute_script("window.dispatchEvent(new Event('resize'))")
                assert browser.execute_script('return innerWidth') == width
                # Auto margins center in the layout viewport, excluding the
                # vertical scrollbar; preview scaling intentionally uses innerWidth.
                content_width = browser.execute_script('return document.documentElement.clientWidth')
                bounds = browser.execute_script("return document.querySelector('.page').getBoundingClientRect().toJSON()")
                assert bounds['width'] <= width * 0.8 + 2, (width, bounds)
                assert abs(bounds['x'] - (content_width-bounds['width'])/2) < 3, (width, content_width, bounds)
                assert browser.execute_script('return document.documentElement.scrollWidth <= innerWidth + 2')
                inside = browser.execute_script("""return [...document.querySelectorAll('.schedule')].every(table => {
                  const b=table.getBoundingClientRect(), p=table.closest('.page').getBoundingClientRect();
                  return b.x>p.x+2 && b.right<p.right-2;
                });""")
                assert inside, width
            browser.execute_cdp_cmd('Emulation.setEmulatedMedia', {'media': 'print'})
            assert not any(p['overflow'] for p in browser.execute_script('return window.fitAttendanceBook()'))
        bad = copy.deepcopy(data)
        bad['weeks'][0]['classes'][0]['text'] = '\n'.join(['示例超长内容'] * 100)
        browser.execute_cdp_cmd('Emulation.setEmulatedMedia', {'media': 'screen'})
        with preview_document(browser, bad) as bad_layout:
            assert bad_layout[3]['overflow']
            assert '4' in browser.find_element('css selector', '#layout-warning').text
    print_pdf(profile, data, target)
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
            print_pdf(profile, bad, destination)
        except ValueError as exc:
            assert 'Page / 页 4' in str(exc), exc
        else:
            raise AssertionError('Oversized page was not rejected')
        assert destination.read_bytes() == b'previous file'
    print('Layout checks passed: 80% preview, margins, dense-page fit, oversized-page detail, safe destination.')
    print(target)


if __name__ == '__main__':
    main()
