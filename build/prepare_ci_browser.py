"""Select the runner's installed Chrome and acquire only its small driver download.

CI-only and explicitly opted in. Never writes application browser settings.
"""
import argparse
import json
import os
from pathlib import Path
import platform


def installed_chrome():
    if platform.system() == 'Darwin':
        candidates = [Path('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome')]
    elif platform.system() == 'Windows':
        candidates = [Path(os.environ.get(key, default)) / 'Google/Chrome/Application/chrome.exe'
                      for key, default in (('PROGRAMFILES', 'C:/Program Files'),
                                           ('PROGRAMFILES(X86)', 'C:/Program Files (x86)'))]
    else:
        raise ValueError('This helper supports Windows and macOS runners only.')
    for candidate in candidates:
        if candidate.is_file():
            return candidate.resolve()
    raise ValueError('Runner-installed Google Chrome is missing; no browser will be downloaded.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--allow-driver-download', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if os.environ.get('GITHUB_ACTIONS') != 'true' or not args.allow_driver_download:
        parser.error('Requires a GitHub Actions runner and explicit --allow-driver-download.')
    chrome = installed_chrome()
    from selenium.webdriver.common.selenium_manager import SeleniumManager
    args.output.parent.mkdir(parents=True, exist_ok=True)
    cache = args.output.parent / 'selenium-cache'
    print('Acquiring ChromeDriver only for the runner-installed Chrome; no browser download.', flush=True)
    result = SeleniumManager().binary_paths([
        '--browser', 'chrome', '--browser-path', str(chrome), '--avoid-browser-download',
        '--avoid-stats', '--skip-browser-in-path', '--skip-driver-in-path', '--cache-path', str(cache.resolve()),
        '--timeout', '120',
    ])
    if result.get('browser_path') and Path(result['browser_path']).resolve() != chrome:
        raise ValueError('Selenium Manager selected a different browser executable.')
    driver = Path(result['driver_path'])
    if not driver.is_file() or driver.name.lower() not in ('chromedriver', 'chromedriver.exe'):
        raise ValueError('Selenium Manager did not return a ChromeDriver executable.')
    profile = {'id': 'ci-installed-chrome', 'name': 'CI installed Chrome', 'browser': 'chrome',
               'executable': str(chrome), 'driver_kind': 'chromedriver',
               'driver_mode': 'manual', 'driver_path': str(driver.resolve())}
    args.output.write_text(json.dumps(profile, indent=2), encoding='utf-8')
    print('Generated explicit profile: ' + str(args.output))


if __name__ == '__main__':
    main()
