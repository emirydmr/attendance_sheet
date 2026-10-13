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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--require-build', action='store_true')
    parser.add_argument('--browser', type=Path,
                        help='Optional explicit browser-profile JSON for a real headless font check; never downloads')
    parser.add_argument('--report', type=Path)
    parser.add_argument('--artifact', type=Path)
    args = parser.parse_args(argv)
    errors, versions, hashes = audit(args.require_build)
    details = {'python': platform.python_version(), 'platform': platform.system(),
               'architecture': platform.machine(), 'dependencies': versions,
               'assets_sha256': hashes, 'browser_checked': False}
    # Importing Tk is safe without a display or an installed browser.
    try:
        import tkinter
        details['tk'] = tkinter.TkVersion
    except ImportError as exc:
        errors.append(f'Tk is missing: {exc}')
    if args.browser and not errors:
        try:
            from browser_config import launch_browser, resolve_profile
            from document import font_css
            profile = json.loads(args.browser.read_text(encoding='utf-8'))
            resolve_profile(profile, allow_download=False)
            browser = launch_browser(profile, headless=True)
            try:
                browser.execute_cdp_cmd('Network.enable', {})
                browser.execute_cdp_cmd('Network.setBlockedURLs', {'urls': ['http://*', 'https://*']})
                browser.get('about:blank')
                browser.execute_script("document.write(arguments[0]); document.close();",
                                       "<style>" + font_css() + "body{font-family:'Attendance CJK'}</style>长安大学国际学生考勤册")
                font_loaded = browser.execute_async_script(
                    "const done=arguments[arguments.length-1]; document.fonts.ready.then(() => "
                    "done(document.fonts.size > 0 && Array.from(document.fonts).every(f => f.status === 'loaded')));"
                )
                if not font_loaded:
                    errors.append('Bundled font failed to load in the browser.')
                details['browser_version'] = browser.capabilities.get('browserVersion')
                details['browser_checked'] = True
            finally:
                browser.quit()
        except Exception as exc:
            errors.append(f'Headless browser / font check failed: {type(exc).__name__}: {exc}')
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
