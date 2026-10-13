"""Real installed-browser smoke against loopback fixtures only, with offline PDF.

Not discovered by unit tests. Requires an explicit prepared browser profile and
never downloads drivers, opens the school portal, or reads saved user settings.
"""
import argparse
from datetime import date
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading
from urllib.parse import parse_qs, urlparse
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def timetable(year, term, week):
    days = ('星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日')
    header = '<tr><th>时间</th><th>节次</th>' + ''.join('<th>' + day + '</th>' for day in days) + '</tr>'
    rows = []
    for period in range(1, 13):
        cells = ['本地示例课程 / Local fixture' if period == 1 and day == 1 else '' for day in range(1, 8)]
        rows.append(f'<tr><td>上午</td><td>{period}</td>' + ''.join('<td>' + cell + '</td>' for cell in cells) + '</tr>')
    selects = ''.join(f'<select id="{key}"><option selected value="{value}">{value}</option></select>'
                      for key, value in (('xn', year), ('xj', term), ('zc', week)))
    return ('<!doctype html><meta charset="utf-8"><h3>Local smoke timetable</h3>'
            '<div class="control-group"><label>学号：</label><span>DEMO001</span></div>'
            '<div class="control-group"><label>专业：</label><span>计算机科学与技术</span></div>'
            + selects + '<table class="table-course">' + header + ''.join(rows) + '</table>')


class FixtureHandler(BaseHTTPRequestHandler):
    authenticated_requests = 0
    rejected_requests = 0
    page_requests = 0

    def log_message(self, *args):
        pass

    def do_GET(self):
        parsed = urlparse(self.path)
        status, cookie = 200, None
        if parsed.path == '/':
            type(self).page_requests += 1
            cookie = 'attendance_smoke=local_only; HttpOnly; SameSite=Lax; Path=/'
            body = '<!doctype html><meta charset="utf-8"><title>Local cookie fixture</title>'
        elif parsed.path == '/py/page/student/grkcb.htm':
            if 'attendance_smoke=local_only' not in self.headers.get('Cookie', ''):
                type(self).rejected_requests += 1
                status, body = 401, 'Cookie required'
            else:
                type(self).authenticated_requests += 1
                query = parse_qs(parsed.query)
                body = timetable(int(query['xn'][0]), int(query['xj'][0]), int(query['zc'][0]))
        else:
            status, body = 404, 'Local fixture not found'
        payload = body.encode('utf-8')
        self.send_response(status)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.send_header('Content-Length', str(len(payload)))
        if cookie:
            self.send_header('Set-Cookie', cookie)
        self.end_headers()
        self.wfile.write(payload)


def smoke(profile, output):
    from browser_config import launch_browser, resolve_profile
    from document import print_pdf
    import portal
    resolve_profile(profile, allow_download=False)
    output.mkdir(parents=True, exist_ok=True)
    FixtureHandler.authenticated_requests = FixtureHandler.rejected_requests = FixtureHandler.page_requests = 0
    server = ThreadingHTTPServer(('127.0.0.1', 0), FixtureHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    base = f'http://127.0.0.1:{server.server_port}'
    try:
        with tempfile.TemporaryDirectory(prefix='browser-profile-', dir=output) as profile_dir:
            browser = launch_browser(profile, headless=True, profile_dir=profile_dir)
            try:
                browser.execute_cdp_cmd('Network.enable', {})
                browser.execute_cdp_cmd('Network.setBlockedURLs', {'urls': ['https://*', '*://*.chd.edu.cn/*']})
                browser.get(base + '/')
                initial_url = browser.current_url
                if 'attendance_smoke' in browser.execute_script('return document.cookie'):
                    raise AssertionError('Fixture cookie must be HttpOnly.')
                client = portal.BrowserPortalClient(browser, origin=base)
                with patch.object(portal, 'BASE', base), \
                     patch.object(portal, 'TIMETABLE', base + '/py/page/student/grkcb.htm', create=True):
                    if urlparse(portal.Selection(2026, 11, 1).url).netloc != urlparse(base).netloc:
                        raise AssertionError('Fixture URL must remain on the loopback origin.')
                    weeks = [portal.read_http(client, portal.Selection(2026, 11, week)) for week in (1, 2)]
                identity = {'student_id': weeks[0]['identity']['学号'],
                            'major': weeks[0]['identity']['专业']}
                if identity['student_id'] != 'DEMO001' or not all(week['classes'] for week in weeks):
                    raise AssertionError('Browser transport did not parse both local timetables.')
                if FixtureHandler.authenticated_requests != 2 or FixtureHandler.rejected_requests:
                    raise AssertionError('Browser fetch did not preserve the HttpOnly session cookie.')
                if FixtureHandler.page_requests != 1 or browser.current_url != initial_url:
                    raise AssertionError('Background fetch unexpectedly navigated the login page.')
            finally:
                browser.quit()
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    data = {**identity, 'portal_major': identity['major'], 'chinese_name': '示例学生',
            'passport_name': 'SAMPLE STUDENT', 'teacher': '示例老师', 'phone': '00000000000',
            'issue_date': date.today().isoformat(), 'year': 2026, 'term': 11,
            'first_week': 1, 'last_week': 2, 'weeks': weeks, 'demo': True}
    path = output / 'local-smoke.pdf'
    print_pdf(profile, data, path)
    pdf = path.read_bytes()
    if not pdf.startswith(b'%PDF-') or b'%%EOF' not in pdf[-1024:] or len(pdf) < 10000:
        raise AssertionError('Offline PDF export is missing or incomplete.')
    report = {'cookie_and_browser_fetch': 'passed', 'pdf': 'passed',
              'fixture_origin': 'loopback', 'portal_requests': 0,
              'authenticated_requests': FixtureHandler.authenticated_requests,
              'pdf_bytes': len(pdf)}
    (output / 'smoke-report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--browser', type=Path, required=True, help='Prepared explicit browser-profile JSON')
    parser.add_argument('--output', type=Path, required=True, help='Platform build-directory output')
    args = parser.parse_args()
    smoke(json.loads(args.browser.read_text(encoding='utf-8')), args.output)


if __name__ == '__main__':
    main()
