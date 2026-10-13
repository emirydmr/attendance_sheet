"""Rasterize our SVG using an explicit installed-browser profile.

No downloads. Not invoked at application startup.
"""
import argparse
from base64 import b64decode
from io import BytesIO
import json
from pathlib import Path
import platform
import sys
import xml.etree.ElementTree as ET

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--browser', type=Path, required=True, help='Explicit browser-profile JSON; never downloads')
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parent / ('windows' if platform.system() == 'Windows' else 'macos') / 'icons')
    args = parser.parse_args()
    assets = Path(__file__).resolve().parents[1] / 'app' / 'assets' / 'icons'
    source = (assets / 'chu_red.svg').read_text(encoding='utf-8')
    svg = ET.fromstring(source)
    # Only static local artwork belongs in the application icon.
    for node in svg.iter():
        tag = node.tag.rsplit('}', 1)[-1].lower()
        if tag in ('script', 'foreignobject', 'image', 'use'):
            raise ValueError('Icon must be static, self-contained SVG')
        if any(k.lower().startswith('on') or k.rsplit('}', 1)[-1] == 'href' for k in node.attrib):
            raise ValueError('External references/events are not allowed in icons')
    from browser_config import launch_browser, resolve_profile
    profile = json.loads(args.browser.read_text(encoding='utf-8'))
    resolve_profile(profile, allow_download=False)
    browser = launch_browser(profile, headless=True)
    try:
        browser.execute_cdp_cmd('Network.enable', {})
        browser.execute_cdp_cmd('Network.setBlockedURLs', {'urls': ['http://*', 'https://*']})
        browser.execute_cdp_cmd('Emulation.setDeviceMetricsOverride',
                                {'width': 512, 'height': 512, 'deviceScaleFactor': 2, 'mobile': False})
        browser.execute_cdp_cmd('Emulation.setDefaultBackgroundColorOverride',
                                {'color': {'r': 0, 'g': 0, 'b': 0, 'a': 0}})
        browser.get('about:blank')
        browser.execute_script('document.write(arguments[0]); document.close();',
                               "<style>html,body{margin:0;background:transparent;width:512px;height:512px;}body{display:flex;align-items:center;justify-content:center;}svg{width:480px;height:480px;}</style>" + source)
        png = b64decode(browser.execute_cdp_cmd('Page.captureScreenshot', {'format': 'png'})['data'])
    finally:
        browser.quit()
    image = Image.open(BytesIO(png)).convert('RGBA')
    args.output.mkdir(parents=True, exist_ok=True)
    image.resize((256, 256), Image.Resampling.LANCZOS).save(args.output / 'chu_red.png')
    image.save(args.output / 'chu_red.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print(f'Created PNG and seven-size ICO in {args.output} without downloads.')


if __name__ == '__main__':
    main()
