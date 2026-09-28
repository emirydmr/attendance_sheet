"""Rasterize our SVG with installed Edge (Windows) or Chrome (macOS).

No downloads. Not invoked at application startup.
"""
import argparse
from io import BytesIO
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

from PIL import Image
from playwright.sync_api import sync_playwright

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from browser_config import launch_browser


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--system-chrome', action='store_true')
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
    with sync_playwright() as pw:
        browser = launch_browser(pw, 'chrome' if args.system_chrome else None, headless=True)
        try:
            page = browser.new_page(viewport={'width': 512, 'height': 512}, device_scale_factor=2)
            page.route('**/*', lambda route: route.abort())
            page.set_content("<style>html,body{margin:0;background:transparent;width:512px;height:512px;}body{display:flex;align-items:center;justify-content:center;}svg{width:480px;height:480px;}</style>" + source)
            png = page.screenshot(omit_background=True)
        finally:
            browser.close()
    image = Image.open(BytesIO(png)).convert('RGBA')
    image.resize((256, 256), Image.Resampling.LANCZOS).save(assets / 'chu_red.png')
    image.save(assets / 'chu_red.ico', sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    print('Created PNG and seven-size ICO from chu_red.svg without downloads.')


if __name__ == '__main__':
    main()
