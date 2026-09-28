from io import BytesIO
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from PIL import Image
from photo import normalize_photo, photo_from_file, photo_from_clipboard
from document import book_html, browser_html
from test_production import fixture


def sample_photo():
    # Fictitious QA pattern, not a portrait of a student.
    image = Image.new("RGB", (120, 160), "#87a9bd")
    for x in range(120):
        for y in range(160):
            if x < 12 or y < 12 or x > 107 or y > 147:
                image.putpixel((x, y), (25, 60, 90))
    return normalize_photo(image)


class PhotoTests(unittest.TestCase):
    def test_image_normalized(self):
        photo = sample_photo()
        self.assertEqual((photo.width, photo.height), (120, 160))
        self.assertTrue(photo.png.startswith(b"\x89PNG"))
        self.assertTrue(photo.data_url.startswith("data:image/png;base64,"))

    def test_file(self):
        with tempfile.TemporaryDirectory() as directory:
            file = Path(directory) / "photo with spaces.png"
            file.write_bytes(sample_photo().png)
            self.assertEqual(photo_from_file(file).width, 120)

    def test_transparency_flattened(self):
        photo = normalize_photo(Image.new("RGBA", (5, 8), (0, 0, 0, 0)))
        with Image.open(BytesIO(photo.png)) as image:
            self.assertEqual(image.getpixel((0, 0)), (255, 255, 255))

    def test_metadata_removed(self):
        raw = BytesIO()
        exif = Image.Exif()
        exif[270] = "Private metadata"
        Image.new("RGB", (20, 30)).save(raw, "JPEG", exif=exif)
        with Image.open(BytesIO(normalize_photo(raw.getvalue()).png)) as output:
            self.assertFalse(output.getexif())

    def test_limits(self):
        with patch("photo.MAX_PIXELS", 10):
            with self.assertRaises(ValueError):
                normalize_photo(Image.new("RGB", (4, 4)))
        with patch("photo.MAX_FILE_BYTES", 3):
            with self.assertRaises(ValueError):
                normalize_photo(b"1234")

    def test_reject_text_and_svg(self):
        for raw in (b"https://school/photo.jpg", b"<svg><script/></svg>"):
            with self.assertRaises(ValueError):
                normalize_photo(raw)

    def test_clipboard_image(self):
        with patch("PIL.ImageGrab.grabclipboard", return_value=Image.new("RGB", (10, 15))):
            self.assertEqual(photo_from_clipboard().height, 15)

    def test_clipboard_empty_does_not_fetch_url(self):
        with patch("PIL.ImageGrab.grabclipboard", return_value=None):
            with self.assertRaisesRegex(ValueError, "Copy image"):
                photo_from_clipboard()

    def test_photo_in_html_and_browser_print(self):
        data = fixture()
        data["photo"] = sample_photo()
        html = browser_html(data)
        self.assertIn(data["photo"].data_url, html)
        self.assertIn("window.print()", html)
        self.assertIn("Content-Security-Policy", html)
        self.assertNotIn("https://", html)
        self.assertIn("object-fit:contain", html)

    def test_blank_photo_box(self):
        self.assertIn("照片 / Photo", book_html(fixture()))


if __name__ == "__main__":
    unittest.main()
