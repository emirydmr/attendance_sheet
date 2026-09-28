from pathlib import Path
import sys
import unittest

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from document import resource_root


class BrandingTests(unittest.TestCase):
    def test_svg_and_png_assets(self):
        assets = resource_root() / 'assets' / 'icons'
        self.assertTrue((assets / 'chu_red.svg').is_file())
        with Image.open(assets / 'chu_red.png') as image:
            self.assertEqual(image.size, (256, 256))
            self.assertEqual(image.mode, 'RGBA')
            self.assertEqual(image.getpixel((0, 0))[3], 0)

    def test_windows_icon_sizes(self):
        with Image.open(resource_root() / 'assets' / 'icons' / 'chu_red.ico') as image:
            self.assertEqual(image.format, 'ICO')
            self.assertEqual(image.ico.sizes(), {(s, s) for s in (16, 24, 32, 48, 64, 128, 256)})


if __name__ == '__main__':
    unittest.main()
