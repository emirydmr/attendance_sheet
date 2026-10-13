"""Inspect frozen package contents without launching a browser or application."""
import argparse
from pathlib import Path
import plistlib

ASSETS = ('templates/attendance_blueprint.html', 'templates/layout.js',
          'assets/fonts/AttendanceCJK.otf', 'assets/fonts/LICENSE.txt',
          'assets/fonts/FONT_INFO.txt', 'assets/icons/chu_red.png', 'assets/icons/chu_red.ico')
MODULES = ('selenium.webdriver.common.selenium_manager', 'browser_config',
           'browser_settings', 'document', 'portal', 'service', 'self_test')


def verify_names(names):
    names = {name.replace('\\', '/') for name in names}
    errors = []
    for asset in ASSETS:
        if not any(name == asset or name.endswith('/' + asset) for name in names):
            errors.append('Missing bundled asset: ' + asset)
    for module in MODULES:
        if module not in names:
            errors.append('Missing frozen module: ' + module)
    if not any(Path(name).name in ('selenium-manager', 'selenium-manager.exe') for name in names):
        errors.append('Selenium Manager is missing from the frozen package.')
    for name in sorted(names):
        parts = name.lower().split('/')
        if (any(part.startswith('playwright') or part in ('.local-browsers', '.cache') for part in parts)
                or parts[-1] in ('node', 'node.exe', 'chrome', 'chrome.exe', 'chromium',
                                 'chromium.exe', 'msedge', 'msedge.exe', 'chromedriver',
                                 'chromedriver.exe', 'msedgedriver', 'msedgedriver.exe')):
            errors.append('Unexpected bundled runtime/browser/cache: ' + name)
    return errors


def package_names(path):
    from PyInstaller.archive.readers import CArchiveReader, ZlibArchiveReader
    def embedded_names(executable):
        archive = CArchiveReader(str(executable))
        names = set(archive.toc)
        for name in archive.toc:
            if name.endswith('.pyz'):
                names.update(archive.open_embedded_archive(name).toc)
        return names
    if path.is_dir():
        names = set()
        for file in path.rglob('*'):
            if file.is_file():
                names.add(file.relative_to(path).as_posix())
                if file.name == 'PYZ.pyz':
                    names.update(ZlibArchiveReader(str(file)).toc)
        info = path / 'Contents/Info.plist'
        if info.is_file():
            with info.open('rb') as stream:
                executable = plistlib.load(stream)['CFBundleExecutable']
            if not isinstance(executable, str) or Path(executable).name != executable:
                raise ValueError('Invalid application executable name.')
            names.update(embedded_names(path / 'Contents/MacOS' / executable))
        return names
    return embedded_names(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('artifact', type=Path)
    args = parser.parse_args()
    if not args.artifact.exists():
        parser.error('Package does not exist: ' + str(args.artifact))
    errors = verify_names(package_names(args.artifact))
    for error in errors:
        print(error)
    if not errors:
        print('Frozen package contains Selenium Manager, app modules, font and icons; no browser or Node.')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
