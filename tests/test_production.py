import copy
from datetime import date
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app"))
from document import book_html, browser_html, font_css, pdf_filename, resource_root, validate_book, weekly_grid
from service import demo_identity, demo_weeks
from portal import profile_fields


def fixture():
    return {**demo_identity(), "chinese_name": "示例学生", "passport_name": "SAMPLE STUDENT",
            "teacher": "李冠楠", "phone": "02968578129", "issue_date": date.today().isoformat(),
            "year": 2026, "term": 11, "first_week": 1, "last_week": 16,
            "portal_major": "计算机科学与技术", "weeks": demo_weeks(2026, 11, 1, 16), "demo": True}


class ProductionTests(unittest.TestCase):
    def test_template_is_authoritative(self):
        self.assertTrue((resource_root() / 'templates' / 'attendance_blueprint.html').is_file())
        self.assertNotIn('${pages}', book_html(fixture()))

    def test_frozen_resource_location(self):
        with patch.object(sys, 'frozen', True, create=True), patch.object(sys, '_MEIPASS', '/test/extracted', create=True):
            self.assertEqual(resource_root(), Path('/test/extracted'))

    def test_development_font_fallback(self):
        with tempfile.TemporaryDirectory() as directory, patch('document.resource_root', return_value=Path(directory)):
            self.assertEqual(font_css(), '')

    def test_frozen_missing_font_rejected(self):
        with tempfile.TemporaryDirectory() as directory, patch('document.resource_root', return_value=Path(directory)), patch.object(sys, 'frozen', True, create=True):
            with self.assertRaisesRegex(ValueError, 'Chinese font is missing'):
                font_css()

    def test_font_embedding_and_browser_policy(self):
        # Synthetic bytes exercise serialization only, not actual font rendering.
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'assets' / 'fonts').mkdir(parents=True)
            (root / 'assets' / 'fonts' / 'AttendanceCJK.otf').write_bytes(b'font-test')
            with patch('document.resource_root', return_value=root):
                self.assertIn('data:font/otf;base64,Zm9udC10ZXN0', font_css())
        self.assertIn('font-src data:', browser_html(fixture()))

    def test_filename_windows_safe(self):
        self.assertEqual(pdf_filename("2026124901"), "2026124901_长安大学国际学生考勤册.pdf")
        self.assertNotIn("*", pdf_filename("bad*id"))

    def test_full_book_and_original_roles(self):
        html = book_html(fixture())
        self.assertEqual(html.count("<section "), 21)
        for text in ("班主任签字", "代课老师", "请假条粘贴处", "星期日", "第16周"):
            self.assertIn(text, html)

    def test_no_separate_weekly_signature_area(self):
        for html in (book_html(fixture()), browser_html(fixture())):
            self.assertNotIn("signature-caption", html)
            self.assertNotIn("class='signatures'", html)
            self.assertIn("考勤签字栏由代课老师亲自如实填写", html)
            self.assertIn("班主任签字", html)

    def test_never_infer_name(self):
        data = fixture()
        data["chinese_name"] = ""
        with self.assertRaises(ValueError):
            validate_book(data)

    def test_incomplete_weeks_rejected(self):
        data = fixture()
        data["weeks"].pop()
        with self.assertRaises(ValueError):
            validate_book(data)

    def test_wrong_student_rejected(self):
        data = fixture()
        data["weeks"][2]["identity"]["学号"] = "another"
        with self.assertRaises(ValueError):
            validate_book(data)

    def test_wrong_term_rejected(self):
        data = fixture()
        data["weeks"][2]["selection"]["semester"] = 12
        with self.assertRaises(ValueError):
            validate_book(data)

    def test_escaped_values(self):
        data = fixture()
        data["passport_name"] = "<script>alert(1)</script>"
        self.assertNotIn("<script>", book_html(data))

    def test_merged_grid_and_weekend(self):
        html = weekly_grid(demo_weeks(2026, 11, 3, 3)[0])
        self.assertIn("rowspan='4'", html)
        self.assertIn("示例周末课程", html)
        self.assertIn(">12</th>", html)

    def test_empty_week_valid(self):
        self.assertIn("节次", weekly_grid(demo_weeks(2026, 11, 1, 1)[0]))

    def test_overlaps_rejected(self):
        week = demo_weeks(2026, 11, 3, 3)[0]
        week["classes"].append(copy.deepcopy(week["classes"][0]))
        with self.assertRaises(ValueError):
            weekly_grid(week)

    def test_profile_name(self):
        fields, _ = profile_fields('<label for="n">姓名：</label><input id="n" value="SAMPLE">')
        self.assertEqual(fields["recorded_name"], "SAMPLE")
        self.assertNotIn("passport_name", fields)


if __name__ == "__main__":
    unittest.main()
