"""Offline release preflight and optional build report. Never installs anything."""
import argparse
import hashlib
import importlib.metadata as metadata
import json
from pathlib import Path
import platform
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))


def pinned_requirements(path):
    return dict(line.strip().split('==', 1) for line in path.read_text().splitlines()
                if line.strip() and not line.lstrip().startswith(('#', '-r')))


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            value.update(chunk)
    return value.hexdigest()


def audit(require_build=False):
    errors, versions = [], {}
    if sys.version_info[:2] != (3, 12):
        errors.append('Build baseline is Python 3.12; use an environment with Tk included.')
    if require_build and platform.system() == 'Windows' and platform.machine().lower() not in ('amd64', 'x86_64'):
        errors.append('Windows release baseline is x64; use x64 Python on Windows 11.')
    pins = pinned_requirements(ROOT / 'requirements.txt')
    if require_build:
        pins.update(pinned_requirements(ROOT / 'build' / 'requirements-build.txt'))
    for name, expected in pins.items():
        try:
            versions[name] = metadata.version(name)
            if versions[name] != expected:
                errors.append(f'{name}: expected {expected}, found {versions[name]}')
        except metadata.PackageNotFoundError:
            errors.append(f'{name}: missing; prepare dependencies explicitly.')
    assets = ('templates/attendance_blueprint.html', 'templates/layout.js', 'assets/icons/chu_red.svg',
              'assets/icons/chu_red.png', 'assets/icons/chu_red.ico',
              'assets/fonts/AttendanceCJK.otf', 'assets/fonts/LICENSE.txt',
              'assets/fonts/FONT_INFO.txt')
    hashes = {}
    for relative in assets:
        path = ROOT / 'app' / relative
        if not path.is_file():
            errors.append(f'Missing asset: {relative}')
        else:
            hashes['app/' + relative] = digest(path)
    font = ROOT / 'app/assets/fonts/AttendanceCJK.otf'
    if font.is_file():
        raw = font.read_bytes()
        blob = hashlib.sha1(b'blob ' + str(len(raw)).encode() + b'\0' + raw).hexdigest()
        if blob != 'be55fbdf3fe53bfc99779389f3f0b875707bf496':
            errors.append('Font differs from the verified upstream file; review provenance.')
    return errors, versions, hashes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-build', action='store_true')
    browsers = parser.add_mutually_exclusive_group()
    browsers.add_argument('--system-chrome', action='store_true', help='Use installed Chrome (legacy alias)')
    browsers.add_argument('--browser', choices=('msedge', 'chrome'), help='Default: installed Edge on Windows, Chrome on macOS')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--artifact', type=Path)
    args = parser.parse_args()
    from browser_config import default_channel, BROWSER_NAMES, launch_browser
    channel = 'chrome' if args.system_chrome else args.browser or default_channel()
    errors, versions, hashes = audit(args.require_build)
    details = {'python': platform.python_version(), 'platform': platform.system(),
               'architecture': platform.machine(), 'dependencies': versions,
               'assets_sha256': hashes, 'browser': 'installed ' + BROWSER_NAMES[channel],
               'browser_channel': channel}
    if not errors:
        try:
            from photo import create_root
            from branding import apply_icon
            root = create_root()
            try:
                root.withdraw()
                apply_icon(root)
                details['tk'] = root.tk.call('info', 'patchlevel')
                details['tkdnd'] = root.tk.call('package', 'present', 'tkdnd')
            finally:
                root.destroy()
        except Exception as exc:
            errors.append(f'Tk / icon / native drag-and-drop check failed: {type(exc).__name__}: {exc}')
        try:
            from playwright.sync_api import sync_playwright
            from document import font_css
            with sync_playwright() as pw:
                browser = launch_browser(pw, channel, headless=True)
                try:
                    details['browser_version'] = browser.version
                    page = browser.new_page()
                    page.route('**/*', lambda route: route.abort())
                    page.set_content("<style>" + font_css() + "body{font-family:'Attendance CJK'}</style>长安大学国际学生考勤册")
                    page.evaluate('document.fonts.ready')
                    if not page.evaluate("Array.from(document.fonts).length > 0 && Array.from(document.fonts).every(f => f.status === 'loaded')"):
                        errors.append('Bundled font failed to load in the browser.')
                finally:
                    browser.close()
        except Exception as exc:
            errors.append(f'Headless browser / font check failed: {type(exc).__name__}. '
                          f'Check installed {BROWSER_NAMES[channel]} and automation policies; no download started.')
    if args.artifact:
        if not args.artifact.is_file():
            errors.append('Build artifact file is missing.')
        else:
            details['artifact'] = {'name': args.artifact.name, 'bytes': args.artifact.stat().st_size,
                                   'sha256': digest(args.artifact)}
    details['errors'] = errors
    details['all_installed_packages'] = {d.metadata['Name']: d.version for d in metadata.distributions()}
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(details, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k: v for k, v in details.items() if k != 'all_installed_packages'}, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
