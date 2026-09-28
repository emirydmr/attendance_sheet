from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from field_help import HELP, TIMETABLE_URL, description


class HelpTests(unittest.TestCase):
    def test_every_input_has_bilingual_help(self):
        for key in ('year', 'term', 'first', 'last', 'chinese_name', 'passport_name',
                    'major', 'teacher', 'phone', 'issue_date', 'language', 'photo'):
            self.assertTrue(description(key))
            self.assertTrue(description(key, True))
            self.assertNotEqual(*HELP[key])

    def test_semester_codes_and_navigation(self):
        text = description('term')
        for value in ('11', '12', '13', 'xj', 'xn=2026', 'AND semester'):
            self.assertIn(value, text)
        self.assertEqual(TIMETABLE_URL, 'https://yjs.chd.edu.cn/py/page/student/grkcb.htm')

    def test_academic_not_calendar_week(self):
        self.assertIn('not calendar', description('first'))
        self.assertIn('2026–2027', description('year'))
